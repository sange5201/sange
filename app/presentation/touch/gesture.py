"""presentation/touch/gesture.py — 手势判定纯逻辑状态机（零 Kivy 依赖）。

S-TOUCH 核心。抽离纯逻辑的目的：
1) 时序判定（350ms 长按 / 300ms 双击 / 12dp 位移）可在**无 Kivy 环境**单测
   （本机 Win10 未装 kivy，CI 才装）；
2) interaction.py 只负责「Kivy 事件 → 喂时间戳/坐标 → 取决策」，不含判定逻辑。

阈值跨文档一致（UX §3.1 / 美术圣经附录 A / GDD §2.2 / 架构 §2.2）：
- LONG_PRESS_MS = 350
- DOUBLE_TAP_MS = 300
- TAP_SLOP_DP  = 12（位移容忍；本层收 px，由调用方 dp→px 换算）

决策返回值（供 TouchDispatcher 分发）：
- "tap"      点按 → reveal
- "chord"    双击已翻开数字格 → chord
- "long"     长按 → cycle_mark
- "drag"     位移超阈值（滚动/pan），不做格子动作
- "consumed" 长按已触发，本次 down 被消费，不补发 tap（GDD §2.2 边界 1）
- "none"     无有效 down（如第二指按下 → 双指缩放）
"""
from core.config import LONG_PRESS_MS, DOUBLE_TAP_MS

TAP_SLOP_DP = 12.0          # UX §3.1 新增常量（本层收 px）


class GestureRecognizer:
    """单指手势判定状态机。

    用法（由 TouchDispatcher 驱动）：
        g.on_down(cell, t_ms, x, y)        # 第一指按下
        g.on_move(x, y)                    # 移动（判位移）
        g.poll_long_press(now_ms) -> bool  # Clock 每帧/定时轮询
        g.on_up(t_ms, is_chordable) -> str # 抬起，取决策
    """

    def __init__(self, long_press_ms: int = LONG_PRESS_MS,
                 double_tap_ms: int = DOUBLE_TAP_MS,
                 tap_slop_px: float = TAP_SLOP_DP):
        self.long_press_ms = long_press_ms
        self.double_tap_ms = double_tap_ms
        self.tap_slop_px = tap_slop_px
        self._down = None          # {cell, t, x, y, moved, long_fired}
        self._last_tap = None      # (cell, t_ms)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """重置全部瞬时状态（新局 / 失焦 / 手势中断）。"""
        self._down = None
        self._last_tap = None

    def has_down(self) -> bool:
        return self._down is not None

    # ------------------------------------------------------------------
    # 输入
    # ------------------------------------------------------------------
    def on_down(self, cell, t_ms: float, x: float, y: float) -> bool:
        """第一指按下。返回是否接受（已有 down → 判为双指缩放，拒绝）。"""
        if self._down is not None:
            return False
        self._down = {"cell": cell, "t": t_ms, "x": x, "y": y,
                      "moved": False, "long_fired": False}
        return True

    def on_move(self, x: float, y: float) -> None:
        """移动。位移 > tap_slop_px 判为拖动（pan/滚动），取消长按候选。"""
        d = self._down
        if d is None:
            return
        if abs(x - d["x"]) > self.tap_slop_px or abs(y - d["y"]) > self.tap_slop_px:
            d["moved"] = True

    # ------------------------------------------------------------------
    # 长按判定
    # ------------------------------------------------------------------
    def poll_long_press(self, now_ms: float) -> bool:
        """Clock 轮询：是否已达到长按阈值。

        条件：有 down + 未移动 + 未触发过 + 时长 ≥ long_press_ms。
        命中则标记 long_fired（保证仅触发一次），返回 True。
        """
        d = self._down
        if d is None or d["moved"] or d["long_fired"]:
            return False
        if now_ms - d["t"] >= self.long_press_ms:
            d["long_fired"] = True
            return True
        return False

    # ------------------------------------------------------------------
    # 抬起 → 决策
    # ------------------------------------------------------------------
    def on_up(self, t_ms: float, is_chordable: bool = False) -> str:
        """抬起取决策。is_chordable 由调用方判定（该格已翻开且数字>0）。"""
        d = self._down
        if d is None:
            return "none"
        self._down = None

        if d["moved"]:
            return "drag"
        if d["long_fired"]:
            # 长按已执行并消费该次 down，不补发 tap（杜绝「想翻开却插旗」）
            self._last_tap = None
            return "consumed"

        elapsed = t_ms - d["t"]
        if elapsed >= self.long_press_ms:
            # Clock 未轮询到（时序抖动）但时长已够 → 兜底按长按语义（不误翻开）
            return "long"

        cell = d["cell"]
        prev = self._last_tap
        if (prev is not None and is_chordable
                and prev[0] == cell and (t_ms - prev[1]) <= self.double_tap_ms):
            self._last_tap = None
            return "chord"

        self._last_tap = (cell, t_ms)
        return "tap"


def is_chordable_cell(board, cell) -> bool:
    """该格是否可 chord（已翻开且数字 > 0）——GDD §2.2 边界 4。"""
    if board is None or cell is None:
        return False
    r, c = cell
    if not (0 <= r < board.rows and 0 <= c < board.cols):
        return False
    return board.is_revealed(r, c) and board.number_at(r, c) > 0
