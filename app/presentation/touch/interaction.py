"""presentation/touch/interaction.py — TouchDispatcher（Kivy 事件 → 对局动作）。

S-TOUCH 验收（UX §3 / GDD §2.2）：
- 点按 tap → reveal；长按 ≥350ms → cycle_mark；双击已翻开数字格 ≤300ms → chord。
- 长按与模式切换按钮**并存不互斥**（用户拍板「两者都提供」）：
  `tool_mode` 仅改变 tap 的默认语义，长按永远可用。
- 长按一旦触发即消费该次 down，不补发 tap（杜绝「想翻开却插旗」）。
- 单步撤销（UNDO_DEPTH=1），game_over 后禁用。

时序判定委托 `gesture.GestureRecognizer`（纯逻辑，零 Kivy）；
本类只做：坐标换算 → 喂时间戳 → 取决策 → 调 session。
"""
import time

from core.config import LONG_PRESS_MS, UNDO_DEPTH
from presentation.touch.gesture import GestureRecognizer, is_chordable_cell, TAP_SLOP_DP

try:                                    # Kivy 可选：无 kivy 时仍可 import（动作方法可测）
    from kivy.clock import Clock
    from kivy.metrics import dp
    HAS_KIVY = True
except Exception:                       # pragma: no cover
    Clock = None
    HAS_KIVY = False

    def dp(v):
        return float(v)


def _now_ms() -> float:
    return time.time() * 1000.0


class TouchDispatcher:
    """把触摸事件翻译为对局动作。

    :param widget: BoardWidget（可选；为 None 时仅可用 on_tap/on_long_press
                   /on_double_tap 直接驱动，供测试与程序化调用）
    :param session: GameSession
    :param bus: EventBus（可选，用于 UI 反馈广播）
    :param get_setting: 读取设置的回调（默认走 session.storage）
    :param on_change: 棋盘变更回调（供 UI 增量重绘，签名 f(cells, action)）
    """

    def __init__(self, widget=None, session=None, bus=None,
                 get_setting=None, on_change=None):
        self.widget = widget
        self.session = session
        self.bus = bus
        self.on_change = on_change
        self._get_setting = get_setting
        self.tool_mode = "dig"           # "dig" | "mark"（模式切换按钮）
        self.gesture = GestureRecognizer(
            long_press_ms=LONG_PRESS_MS,
            tap_slop_px=dp(TAP_SLOP_DP) if HAS_KIVY else TAP_SLOP_DP)
        self._touch = None               # 当前追踪的 touch 对象
        self._long_ev = None             # Clock 长按定时
        self._undo_stack = []
        if widget is not None:
            self.attach(widget)

    # ------------------------------------------------------------------
    # 绑定 / 解绑
    # ------------------------------------------------------------------
    def attach(self, widget) -> None:
        self.widget = widget
        widget.bind(on_touch_down=self.on_touch_down,
                    on_touch_move=self.on_touch_move,
                    on_touch_up=self.on_touch_up)

    def detach(self) -> None:
        if self.widget is not None:
            self.widget.unbind(on_touch_down=self.on_touch_down,
                               on_touch_move=self.on_touch_move,
                               on_touch_up=self.on_touch_up)

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------
    def _setting(self, key, default=None):
        if self._get_setting is not None:
            try:
                return self._get_setting(key, default)
            except Exception:
                return default
        try:
            return self.session.storage.get_setting(key, default)
        except Exception:
            return default

    def apply_settings(self) -> None:
        """从设置初始化 tool_mode（UX §3.5）。

        default_mark_mode == "button" → 初始为标记模式；否则为挖掘模式。
        """
        mode = self._setting("default_mark_mode", "longpress")
        self.tool_mode = "mark" if mode == "button" else "dig"

    def toggle_mode(self) -> str:
        """模式切换按钮：dig ⇄ mark。返回新模式。"""
        self.tool_mode = "mark" if self.tool_mode == "dig" else "dig"
        return self.tool_mode

    # ------------------------------------------------------------------
    # Kivy 触摸事件
    # ------------------------------------------------------------------
    def _local(self, touch):
        w = self.widget
        if w is None:
            return touch.x, touch.y
        try:
            return w.to_widget(touch.x, touch.y, relative=False)
        except TypeError:                # 旧版 Kivy 签名
            return w.to_widget(touch.x, touch.y)

    def on_touch_down(self, widget, touch) -> bool:
        if self._touch is not None:
            return False                 # 第二指 → 交给缩放（UX §3.4）
        lx, ly = self._local(touch)
        if not (0 <= lx <= widget.width and 0 <= ly <= widget.height):
            return False
        if self.widget is not None and not widget.collide_point(*touch.pos):
            return False
        cell = self.widget.cell_at_pos(lx, ly)
        if cell is None:
            return False
        if not self.gesture.on_down(cell, _now_ms(), lx, ly):
            return False
        self._touch = touch
        if Clock is not None:
            self._long_ev = Clock.schedule_once(
                self._fire_long_press, LONG_PRESS_MS / 1000.0)
        return True

    def on_touch_move(self, widget, touch) -> bool:
        if self._touch is not touch:
            return False
        lx, ly = self._local(touch)
        self.gesture.on_move(lx, ly)
        if self.gesture.has_down() and self._down_moved():
            self._cancel_long()          # 拖动 → 取消长按候选
        return True

    def on_touch_up(self, widget, touch) -> bool:
        if self._touch is not touch:
            return False
        self._touch = None
        self._cancel_long()
        cell = self._cell_of_gesture()
        decision = self.gesture.on_up(
            _now_ms(), is_chordable=is_chordable_cell(self._board(), cell))
        if cell is None:
            return True
        if decision == "tap":
            self.on_tap(*cell)
        elif decision == "chord":
            self.on_double_tap(*cell)
        elif decision == "long":
            self.on_long_press(*cell)
        # "drag" / "consumed" / "none" → 不产生格子动作
        return True

    def _down_moved(self) -> bool:
        d = getattr(self.gesture, "_down", None)
        return bool(d and d.get("moved"))

    def _cell_of_gesture(self):
        d = getattr(self.gesture, "_down", None)
        return d["cell"] if d else None

    def _fire_long_press(self, dt) -> None:
        cell = self._cell_of_gesture()
        self._long_ev = None
        if cell is None:
            return
        if self.gesture.poll_long_press(_now_ms()):
            self.on_long_press(*cell)

    def _cancel_long(self) -> None:
        if self._long_ev is not None and Clock is not None:
            self._long_ev.cancel()
        self._long_ev = None

    def _board(self):
        return getattr(self.session, "board", None)

    # ------------------------------------------------------------------
    # 动作（供事件分发与测试共用）
    # ------------------------------------------------------------------
    def on_tap(self, r: int, c: int):
        """点按：标记模式下插旗，否则翻开（UX §3.2）。"""
        b = self._board()
        if b is None:
            return None
        if b.is_flagged(r, c):
            return {"result": "noop", "changed": [], "triggered": None}
        if b.is_marked(r, c):            # 先清 ? 再翻开
            b.marked[r][c] = False
            self._emit_change([(r, c)], "unmark")
        if self.tool_mode == "mark":
            return self.on_long_press(r, c)
        res = self.session.reveal(r, c)
        self._emit_change(res.get("changed", []), "reveal")
        return res

    def on_long_press(self, r: int, c: int):
        """长按 / 模式按钮：循环标记 无→旗→?→无。"""
        if self._board() is None:
            return None
        self.session.cycle_mark(r, c)
        self._emit_change([(r, c)], "mark")
        return {"result": "mark", "changed": [(r, c)], "triggered": None}

    def on_double_tap(self, r: int, c: int):
        """双击已翻开数字格 → 连开 chord。"""
        if self._board() is None:
            return None
        res = self.session.chord(r, c)
        self._emit_change(res.get("changed", []), "chord")
        return res

    def undo(self) -> bool:
        """撤销一步（不回退计时；game_over 禁用）。"""
        ok = bool(self.session.undo()) if self.session else False
        if ok:
            self._emit_change(None, "undo")
        return ok

    def _emit_change(self, cells, action: str) -> None:
        if self.on_change is not None:
            self.on_change(cells, action)
