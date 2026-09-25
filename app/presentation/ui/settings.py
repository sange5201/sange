"""presentation/ui/settings.py — 设置页 + 成就墙 + 每日榜（S5/S6/S7）。

UX §6 无障碍：色盲辅助 / 减少动态 / 大字体（显示缩放）三个开关**一级入口**。
UX §3.5：默认标记方式（longpress / button）与模式按钮显隐（toolbar_mode）。
所有开关经 `on_change(key, value)` 回传，由 main.py 落 storage（唯一真源）。
"""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton

from core.achievements import ACHIEVEMENTS


class _ToggleRow(BoxLayout):
    """一行开关：[说明文字] [开关按钮]。"""

    def __init__(self, title, options, current, group_prefix, on_pick, **kwargs):
        super().__init__(orientation="horizontal", size_hint=(1, None),
                         height=dp(48), spacing=dp(8), **kwargs)
        self.add_widget(Label(text=title, size_hint=(0.5, 1), halign="left"))
        btns = BoxLayout(orientation="horizontal", size_hint=(0.5, 1), spacing=dp(4))
        self.buttons = {}
        for opt, label in options:
            tb = ToggleButton(text=label, group=f"{group_prefix}",
                              state="down" if opt == current else "normal")
            tb.bind(on_release=lambda b, o=opt: on_pick(o))
            self.buttons[opt] = tb
            btns.add_widget(tb)
        self.add_widget(btns)


class SettingsPanel(ModalView):
    """设置 / 成就墙 / 每日榜 面板。"""

    def __init__(self, session=None, storage=None, settings=None,
                 on_change=None, **kwargs):
        kwargs.setdefault("size_hint", (0.95, 0.9))
        kwargs.setdefault("pos_hint", {"center_x": 0.5, "center_y": 0.5})
        kwargs.setdefault("auto_dismiss", True)
        super().__init__(**kwargs)
        self.on_change = on_change
        self.settings = dict(settings or {})

        scroll = ScrollView()
        root = BoxLayout(orientation="vertical", spacing=dp(10),
                         size_hint_y=None, padding=dp(12))
        root.bind(minimum_height=root.setter("height"))

        def changed(key, value):
            self.settings[key] = value
            if self.on_change is not None:
                self.on_change(key, value)

        # ---------------- 外观 ----------------
        root.add_widget(self._title("外观"))
        root.add_widget(_ToggleRow(
            "主题", [("light", "经典灰"), ("dark", "护眼深")],
            self.settings.get("theme", "light"), "theme",
            lambda v: changed("theme", v)))

        # ---------------- 操作 ----------------
        root.add_widget(self._title("操作"))
        root.add_widget(_ToggleRow(
            "默认标记方式",
            [("longpress", "长按为主"), ("button", "模式按钮")],
            self.settings.get("default_mark_mode", "longpress"), "markmode",
            lambda v: changed("default_mark_mode", v)))
        root.add_widget(_ToggleRow(
            "显示模式按钮", [("on", "显示"), ("off", "隐藏")],
            "on" if self.settings.get("toolbar_mode", True) else "off", "toolbar",
            lambda v: changed("toolbar_mode", v == "on")))
        root.add_widget(_ToggleRow(
            "问号标记", [("on", "开"), ("off", "关")],
            "on" if self.settings.get("question_enabled", True) else "off", "question",
            lambda v: changed("question_enabled", v == "on")))

        # ---------------- 无障碍 ----------------
        root.add_widget(self._title("无障碍"))
        root.add_widget(_ToggleRow(
            "色盲辅助", [("on", "开"), ("off", "关")],
            "on" if self.settings.get("colorblind", False) else "off", "cb",
            lambda v: changed("colorblind", v == "on")))
        root.add_widget(_ToggleRow(
            "减少动态效果", [("on", "开"), ("off", "关")],
            "on" if self.settings.get("reduce_motion", False) else "off", "rm",
            lambda v: changed("reduce_motion", v == "on")))
        root.add_widget(_ToggleRow(
            "显示缩放",
            [("standard", "标准"), ("large", "大"), ("xlarge", "特大")],
            self.settings.get("display_scale", "standard"), "scale",
            lambda v: changed("display_scale", v)))

        # ---------------- 成就墙 ----------------
        root.add_widget(self._title("成就墙"))
        unlocked = self._unlocked_map(session, storage)
        for ach in ACHIEVEMENTS:
            got = unlocked.get(ach["id"], False)
            mark = "★" if got else "☆"
            root.add_widget(Label(
                text=f"{mark} {ach['name']} — {ach['condition']}",
                size_hint=(1, None), height=dp(28), halign="left",
                shorten=False))

        # ---------------- 每日榜 ----------------
        root.add_widget(self._title("每日挑战"))
        root.add_widget(Label(text=self._daily_text(storage),
                              size_hint=(1, None), height=dp(56), halign="left"))

        close = Button(text="关闭", size_hint=(1, None), height=dp(48))
        close.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(close)

        scroll.add_widget(root)
        self.add_widget(scroll)

    # ------------------------------------------------------------------
    @staticmethod
    def _title(text):
        return Label(text=text, size_hint=(1, None), height=dp(34),
                     bold=True, halign="left")

    @staticmethod
    def _unlocked_map(session, storage) -> dict:
        if session is not None and getattr(session, "achievements", None):
            return {a["id"]: session.achievements.is_unlocked(a["id"])
                    for a in ACHIEVEMENTS}
        if storage is not None:
            data = storage.get_achievements()
            return {a["id"]: bool(data.get(a["id"], {}).get("unlocked"))
                    for a in ACHIEVEMENTS}
        return {}

    @staticmethod
    def _daily_text(storage) -> str:
        if storage is None:
            return "今日：—"
        import datetime
        today = datetime.date.today().isoformat()
        best = storage.get_daily_best(today)
        done = storage.get_daily_completed(today)
        return (f"今日 {today}：{'已完成' if done else '未完成'}"
                f"　最佳 {best if best is not None else '—'} 秒")
