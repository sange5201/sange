"""test_gesture.py — 手势判定纯逻辑单测（零 Kivy 依赖，本机可直接跑）。

覆盖 UX §3 全部时序规则：
- 点按（<350ms、位移<12dp）→ tap
- 长按（≥350ms 静止）→ long，且触发后 up 返回 consumed（不补发 tap）
- 双击同格（≤300ms，且已翻开数字格）→ chord；否则 tap
- 位移 >12dp → drag（滚动/缩放，不产生格子动作）
- 第二指按下 → 拒绝（判为 pinch-zoom）
"""
from presentation.touch.gesture import (GestureRecognizer, is_chordable_cell,
                                        TAP_SLOP_DP)
from core.config import LONG_PRESS_MS, DOUBLE_TAP_MS

SLOP = 12.0


class _FakeBoard:
    """最小替身：只提供 is_revealed / number_at / rows / cols。"""

    def __init__(self, rows=9, cols=9, layout=None):
        self.rows, self.cols = rows, cols
        self._revealed = set()
        self._layout = layout or {}

    def reveal(self, r, c):
        self._revealed.add((r, c))

    def is_revealed(self, r, c):
        return (r, c) in self._revealed

    def number_at(self, r, c):
        return self._layout.get((r, c), 0)


def _g(**kw):
    return GestureRecognizer(tap_slop_px=SLOP, **kw)


# ----------------------------------------------------------------------
# 点按 / 长按
# ----------------------------------------------------------------------
def test_short_press_is_tap():
    g = _g()
    g.on_down((0, 0), 0, 10, 10)
    assert g.on_up(100, False) == "tap"


def test_long_press_fired_and_consumes_up():
    g = _g()
    g.on_down((1, 1), 0, 10, 10)
    assert g.poll_long_press(LONG_PRESS_MS - 1) is False
    assert g.poll_long_press(LONG_PRESS_MS) is True
    assert g.poll_long_press(LONG_PRESS_MS + 10) is False   # 仅触发一次
    assert g.on_up(LONG_PRESS_MS + 20, False) == "consumed"  # 不补发 tap


def test_up_after_threshold_without_clock_poll_is_long():
    """Clock 未轮询到但时长已够 → 兜底按长按语义（不误翻开）。"""
    g = _g()
    g.on_down((2, 2), 0, 0, 0)
    assert g.on_up(400, False) == "long"


def test_move_beyond_slop_is_drag():
    g = _g()
    g.on_down((0, 0), 0, 0, 0)
    g.on_move(SLOP + 1, 0)
    assert g.poll_long_press(1000) is False      # 拖动取消长按候选
    assert g.on_up(120, False) == "drag"


def test_move_within_slop_still_tap():
    g = _g()
    g.on_down((0, 0), 0, 0, 0)
    g.on_move(SLOP - 1, 0)
    assert g.on_up(100, False) == "tap"


# ----------------------------------------------------------------------
# 双击 chord
# ----------------------------------------------------------------------
def test_double_tap_on_number_chords():
    g = _g()
    g.on_down((3, 3), 1000, 0, 0)
    assert g.on_up(1100, True) == "tap"                  # 首击记录
    g.on_down((3, 3), 1100 + DOUBLE_TAP_MS - 10, 0, 0)   # ≤300ms 同格
    assert g.on_up(1100 + DOUBLE_TAP_MS, True) == "chord"


def test_double_tap_beyond_window_is_tap():
    g = _g()
    g.on_down((3, 3), 0, 0, 0)
    assert g.on_up(50, True) == "tap"
    g.on_down((3, 3), 50 + DOUBLE_TAP_MS + 1, 0, 0)
    assert g.on_up(50 + DOUBLE_TAP_MS + 80, True) == "tap"


def test_double_tap_different_cell_is_tap():
    g = _g()
    g.on_down((3, 3), 0, 0, 0)
    assert g.on_up(50, True) == "tap"
    g.on_down((4, 4), 100, 0, 0)
    assert g.on_up(150, True) == "tap"


def test_double_tap_on_non_chordable_is_tap():
    """未翻开格不可 chord（GDD §2.2 边界 4）。"""
    g = _g()
    g.on_down((0, 0), 0, 0, 0)
    assert g.on_up(50, False) == "tap"
    g.on_down((0, 0), 100, 0, 0)
    assert g.on_up(150, False) == "tap"


# ----------------------------------------------------------------------
# 多指 / 重置
# ----------------------------------------------------------------------
def test_second_finger_rejected():
    g = _g()
    assert g.on_down((0, 0), 0, 0, 0) is True
    assert g.on_down((1, 1), 10, 20, 20) is False        # 第二指 → 缩放
    assert g.on_up(50, False) == "tap"                   # 首指仍有效


def test_reset_clears_state():
    g = _g()
    g.on_down((0, 0), 0, 0, 0)
    assert g.on_up(50, True) == "tap"
    g.reset()
    assert g.on_up(100, True) == "none"
    assert g.has_down() is False


# ----------------------------------------------------------------------
# chordable 判定
# ----------------------------------------------------------------------
def test_is_chordable_cell():
    b = _FakeBoard(layout={(1, 1): 3})
    b.reveal(1, 1)
    assert is_chordable_cell(b, (1, 1)) is True
    assert is_chordable_cell(b, (0, 0)) is False        # 未翻开
    b.reveal(0, 0)
    assert is_chordable_cell(b, (0, 0)) is False        # 数字 0 不可 chord
    assert is_chordable_cell(b, (99, 99)) is False      # 越界
    assert is_chordable_cell(None, (0, 0)) is False
