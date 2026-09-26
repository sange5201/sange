"""app/main.py — Kivy App 入口（架构 §6.3 线框落地）。

职责：
- 组装 TopNav(48dp) + 棋盘 ScrollView + 底部 HUD(104dp)（UX §2 竖屏骨架）
- 平台适配注入：Android 内部存储（ADR-04）、生命周期 on_pause/on_resume（R6）
- 每秒驱动 `GameTimer._tick()`（core 零 Kivy 依赖，调度在表现层）
- 结算 / 难度抽屉 / 设置 / 成就墙 / 每日榜 / 首玩引导 的装配与回调

桌面调试：`python main.py`（需 pip install kivy）
安卓打包：`buildozer android debug`（见 buildozer.spec；本机 4GB 建议云 CI）
"""
import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView

from core.config import LEVELS
from core.events import EventBus, GameEvent
from core.game import GameSession
from core.storage import JsonStorage, StorageBackend
from osenv import android_bridge
from presentation.touch.interaction import TouchDispatcher
from presentation.ui.board_widget import BoardWidget
from presentation.ui.drawer import LevelDrawer
from presentation.ui.hud import HudBar
from presentation.ui.layout import HUD_TOTAL_DP, TOPNAV_DP, MIN_TAP_DP
from presentation.ui.onboarding import OnboardingOverlay
from presentation.ui.settings import SettingsPanel

FONT_SCALE = {"standard": 1.0, "large": 1.15, "xlarge": 1.3}


class MineSweeperApp(App):
    """扫雷 · 安卓版（Kivy）。"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bus = EventBus()
        self.storage = None
        self.session = None
        self.settings = {}
        self.level = "初级"
        self.is_daily = False
        self.board_widget = None
        self.hud = None
        self.dispatcher = None
        self.scroll = None

    # ==================================================================
    # 构建
    # ==================================================================
    def build(self):
        # 1) 存储路径（Android 内部存储优先，ADR-04）
        android_bridge.bind_storage()
        self.storage = JsonStorage(StorageBackend.base_dir())
        self.storage.load()

        # 2) 会话（共享总线：board / timer / achievements 全部挂在同一个 bus）
        self.session = GameSession(bus=self.bus, storage=self.storage)
        self.settings = self.storage.get_settings()
        self.session.new_game(self.level)

        # 3) 根布局
        root = BoxLayout(orientation="vertical")
        self._paint_bg(root)

        # 3.1 顶部导航（低频）
        nav = BoxLayout(orientation="horizontal", size_hint=(1, None),
                        height=dp(TOPNAV_DP), spacing=dp(6), padding=dp(6))
        for text, cb in (("难度", self.open_drawer),
                         ("每日", self.start_daily),
                         ("成就", self.open_settings),
                         ("设置", self.open_settings)):
            btn = Button(text=text, size_hint=(1, 1))
            btn.bind(on_release=lambda b, f=cb: f())
            btn.font_size = dp(15) * FONT_SCALE.get(
                self.settings.get("display_scale", "standard"), 1.0)
            nav.add_widget(btn)
        root.add_widget(nav)

        # 3.2 棋盘（ScrollView：大棋盘滚动 + pinch-zoom 接入点，UX §2.3）
        self.board_widget = BoardWidget(
            session=self.session, bus=self.bus,
            theme=self.settings.get("theme", "light"),
            colorblind=bool(self.settings.get("colorblind", False)))
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=True,
                                 do_scroll_y=True, scroll_type=["content"])
        self.scroll.add_widget(self.board_widget)
        self.scroll.bind(size=self._on_scroll_size)
        root.add_widget(self.scroll)

        # 3.3 底部 HUD（高频操作，UX §2.4）
        self.hud = HudBar(
            session=self.session, bus=self.bus,
            theme=self.settings.get("theme", "light"),
            on_face=self.restart, on_undo=self.do_undo,
            on_toggle_mode=self.toggle_mode,
            show_toolbar=bool(self.settings.get("toolbar_mode", True)))
        root.add_widget(self.hud)

        # 4) 手势分发
        self.dispatcher = TouchDispatcher(
            widget=self.board_widget, session=self.session, bus=self.bus,
            get_setting=self._get_setting, on_change=self._on_board_change)
        self.dispatcher.apply_settings()
        self.hud.set_mode_text(self.dispatcher.tool_mode)

        # 5) 事件订阅（结算 / 计时刷新）
        self.bus.subscribe(GameEvent.WIN, self._on_win)
        self.bus.subscribe(GameEvent.LOSE, self._on_lose)

        # 6) 秒针（core 不 import kivy，调度在表现层）
        Clock.schedule_interval(self._on_tick, 1.0)

        self.hud.refresh()
        self._refresh_best()
        return root

    def on_start(self):
        """首启：布局尺寸确定后 fit 棋盘；未引导则弹三步引导（UX §4）。"""
        self._fit_board()
        if not self.settings.get("onboarded", False):
            OnboardingOverlay(on_finish=self._on_onboarded).open()

    # ==================================================================
    # 布局 / 绘制
    # ==================================================================
    def _paint_bg(self, root) -> None:
        from presentation.ui import icons
        c = icons.theme_colors(self.settings.get("theme", "light") if self.settings
                               else "light")
        with root.canvas.before:
            self._bg_color = Color(*c["bg"])
            self._bg_rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._update_bg, pos=self._update_bg)

    def _update_bg(self, root, *args) -> None:
        self._bg_rect.size = root.size
        self._bg_rect.pos = root.pos

    def _on_scroll_size(self, scroll, size) -> None:
        self._fit_board()

    def _fit_board(self) -> None:
        """按可用空间重算 cell 并重绘（旋转/首次布局，不重置对局，UX §2.5）。"""
        if self.board_widget is None or self.session.board is None:
            return
        self.board_widget.fit(self.scroll.width, self.scroll.height)
        self.board_widget.build_canvas()

    def _on_board_change(self, cells, action) -> None:
        """棋盘变更 → 增量重绘 + HUD 同步（ADR-02）。"""
        if self.board_widget is not None:
            self.board_widget.repaint(cells)
        if self.hud is not None:
            self.hud.refresh()

    # ==================================================================
    # 秒针 / 生命周期
    # ==================================================================
    def _on_tick(self, dt) -> None:
        if self.session is None or self.session.timer is None:
            return
        self.session.timer._tick()          # core 内部判 running + emit TICK
        if self.hud is not None:
            self.hud.time_lcd.value = self.session.timer.elapsed

    def on_pause(self):
        """Android 挂起：冻结计时 + flush 存储（R6）。"""
        if self.session is not None and self.session.timer is not None:
            self.session.timer.pause()
        if self.storage is not None:
            self.storage.save()
        return True

    def on_resume(self):
        """Android 恢复：game_over 后 resume 无效（防篡改纪录）。"""
        if self.session is not None and self.session.timer is not None:
            self.session.timer.resume()

    def on_stop(self):
        if self.storage is not None:
            self.storage.save()

    # ==================================================================
    # 对局控制
    # ==================================================================
    def _get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def restart(self) -> None:
        """笑脸重开：保持当前难度（每日局则重开当日挑战）。"""
        self.new_game(self.level)

    def new_game(self, level: str, custom=None) -> None:
        self.level = level
        self.is_daily = False
        self.session.new_game(level, custom=custom)
        self._after_new_game()

    def start_daily(self) -> None:
        """每日挑战（自由首击 + 16×16/40，用户拍板）。"""
        self.is_daily = True
        self.session.start_daily(datetime.date.today())
        self._after_new_game()

    def _after_new_game(self) -> None:
        self.hud.set_face("smile")
        self._fit_board()
        self.hud.refresh()
        self._refresh_best()

    def do_undo(self) -> None:
        """撤销一步（不回退计时；game_over 禁用）。"""
        if self.dispatcher.undo():
            if self.board_widget is not None:
                self.board_widget.build_canvas()
            if self.hud is not None:
                self.hud.refresh()

    def toggle_mode(self) -> None:
        mode = self.dispatcher.toggle_mode()
        self.hud.set_mode_text(mode)

    def _refresh_best(self) -> None:
        if self.hud is None:
            return
        if self.is_daily:
            today = datetime.date.today().isoformat()
            best = self.storage.get_daily_best(today)
            self.hud.set_best_text(f"今日最佳 {best if best is not None else '—'}s")
        else:
            best = self.storage.get_best(self.level)
            self.hud.set_best_text(f"最佳 {best if best is not None else '—'}s")

    # ==================================================================
    # 结算
    # ==================================================================
    def _on_win(self, payload) -> None:
        # board 内部空 WIN {} 先到；只处理 GameSession 的富 WIN（含 level）
        if not isinstance(payload, dict) or "level" not in payload:
            return
        self.hud.set_face("cool")
        self._refresh_best()
        self._show_result(True, payload)

    def _on_lose(self, payload) -> None:
        self.hud.set_face("dead")
        android_bridge.vibrate(30)
        self._show_result(False, payload or {})

    def _show_result(self, win: bool, payload: dict) -> None:
        if self.board_widget is not None:
            self.board_widget.build_canvas()      # 揭示全部雷 / 标红叉
        t = payload.get("time", self.session.timer.elapsed)
        best = (self.storage.get_daily_best(datetime.date.today().isoformat())
                if self.is_daily else self.storage.get_best(self.level))
        text = (f"{'胜利！' if win else '踩雷了'}　用时 {t}s\n"
                f"最佳 {best if best is not None else '—'}s")

        sheet = ModalView(size_hint=(0.85, None), height=dp(200),
                          pos_hint={"center_x": 0.5, "y": 0.06})
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        box.add_widget(Label(text=text, halign="center"))
        bar = BoxLayout(orientation="horizontal", spacing=dp(10),
                        size_hint=(1, None), height=dp(MIN_TAP_DP))
        again = Button(text="再来一局")
        again.bind(on_release=lambda *_: (sheet.dismiss(), self.restart()))
        close = Button(text="看看棋盘")
        close.bind(on_release=lambda *_: sheet.dismiss())
        bar.add_widget(close)
        bar.add_widget(again)
        box.add_widget(bar)
        sheet.add_widget(box)
        sheet.open()

    # ==================================================================
    # 面板
    # ==================================================================
    def open_drawer(self) -> None:
        LevelDrawer(on_pick=self._on_pick_level).open()

    def _on_pick_level(self, name, custom) -> None:
        self.new_game(name, custom=custom)

    def open_settings(self) -> None:
        SettingsPanel(session=self.session, storage=self.storage,
                      settings=self.settings,
                      on_change=self._on_setting_change).open()

    def _on_setting_change(self, key, value) -> None:
        """设置变更：落盘 + 立即生效（唯一真源 = storage）。"""
        self.settings[key] = value
        self.storage.set_setting(key, value)
        if key == "theme":
            self.board_widget.set_theme(value)
            self.hud.set_theme(value)
        elif key == "toolbar_mode":
            self.hud.set_toolbar_visible(bool(value))
        elif key == "default_mark_mode":
            self.dispatcher.apply_settings()
            self.hud.set_mode_text(self.dispatcher.tool_mode)
        elif key == "colorblind":
            self.board_widget.set_colorblind(bool(value))
        elif key == "question_enabled":
            pass                      # 下一局生效（Board 构造时读取）

    def _on_onboarded(self, completed: bool) -> None:
        """引导完成/跳过均写 onboarded=true（UX §4.3 闭环）。"""
        self.settings["onboarded"] = True
        self.storage.set_setting("onboarded", True)


if __name__ == "__main__":
    MineSweeperApp().run()
