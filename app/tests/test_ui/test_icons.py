"""test_icons.py — 像素图标几何单测（零 Kivy 依赖，本机可直接跑）。

守护美术圣经 §3/§4：图标在 16×16 虚拟网格内定义、几何与桌面版一致、
色盲色板可切换、七段数码管段位正确。
"""
import pytest

from presentation.ui import icons
from presentation.ui.layout import (compute_cell_dp, board_size, cell_at,
                                    cell_rect, needs_scroll, MIN_TAP_DP,
                                    CELL_MIN_DP, CELL_MAX_DP)


# ----------------------------------------------------------------------
# 点阵数字 / 问号
# ----------------------------------------------------------------------
@pytest.mark.parametrize("n", range(1, 9))
def test_digit_bitmap_size_and_range(n):
    bm = icons.digit_bitmap(n)
    assert bm, f"数字 {n} 点阵为空"
    for (x, y) in bm:
        assert 0 <= x <= 2 and 0 <= y <= 4


def test_digit_bitmap_invalid():
    # 点阵表含 0 与 9（LCD/备用），棋盘实际只用 1..8
    assert icons.digit_bitmap(0) != []
    assert icons.digit_bitmap(9) != []
    assert icons.digit_bitmap(-1) == []
    assert icons.digit_bitmap(99) == []


def test_question_bitmap_nonempty():
    bm = icons.question_bitmap()
    assert bm and all(0 <= x <= 2 and 0 <= y <= 4 for (x, y) in bm)


# ----------------------------------------------------------------------
# 七段数码管
# ----------------------------------------------------------------------
def test_seven_seg_known_digits():
    assert icons.seven_seg("0") == {0, 1, 2, 3, 4, 5}
    assert icons.seven_seg("1") == {1, 2}
    assert icons.seven_seg("8") == set(range(7))
    assert icons.seven_seg("-") == {6}
    assert icons.seven_seg("?") == set()          # 未知 → 熄灭


def test_seven_seg_rects_in_bounds():
    for ch in "0123456789-":
        rects = icons.seven_seg_rects(ch)
        assert len(rects) == len(icons.seven_seg(ch))
        for (x, y, w, h) in rects:
            assert 0 <= x <= 10 and 0 <= y <= 18
            assert w >= 0 and h >= 0


# ----------------------------------------------------------------------
# 图标图元
# ----------------------------------------------------------------------
def _all_points(prims):
    pts = []
    for p in prims:
        if p[0] == "rect":
            pts += [(p[1], p[2]), (p[1] + p[3], p[2] + p[4])]
        elif p[0] == "tri":
            pts += list(p[1])
        elif p[0] == "ellipse":
            pts += [(p[1], p[2]), (p[1] + p[3], p[2] + p[4])]
        elif p[0] == "line":
            pts += list(p[1])
    return pts


@pytest.mark.parametrize("getter", [icons.flag_primitives, icons.mine_primitives,
                                    icons.cross_primitives])
def test_primitives_within_grid(getter):
    for (x, y) in _all_points(getter()):
        assert 0 <= x <= icons.GRID and 0 <= y <= icons.GRID


@pytest.mark.parametrize("state", ["smile", "wow", "cool", "dead"])
def test_face_primitives_states(state):
    prims = icons.face_primitives(state)
    assert prims[0][0] == "ellipse"                # 首图元恒为脸盘
    assert len(prims) >= 4
    for (x, y) in _all_points(prims):
        assert 0 <= x <= icons.GRID and 0 <= y <= icons.GRID


# ----------------------------------------------------------------------
# 主题与色盲
# ----------------------------------------------------------------------
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_colors(theme):
    c = icons.theme_colors(theme)
    for key in ("bg", "light", "dark", "black", "red", "yellow",
                "lcd_bg", "lcd_fg"):
        rgba = c[key]
        assert len(rgba) == 4
        assert all(0.0 <= v <= 1.0 for v in rgba)
    assert set(c["num"].keys()) == set(range(1, 9))


def test_colorblind_swaps_number_palette():
    normal = icons.theme_colors("light", colorblind=False)["num"]
    cb = icons.theme_colors("light", colorblind=True)["num"]
    assert normal != cb
    assert set(cb.keys()) == set(range(1, 9))
    assert all(v in icons.OKABE_ITO_NUM.values() for v in
               [icons.OKABE_ITO_NUM[k] for k in range(1, 9)])


def test_hex_to_rgba():
    assert icons.hex_to_rgba("#000000")[:3] == (0.0, 0.0, 0.0)
    assert icons.hex_to_rgba("#ffffff")[:3] == (1.0, 1.0, 1.0)
    assert len(icons.hex_to_rgba("#f00")) == 4          # 简写可解析


# ----------------------------------------------------------------------
# 布局计算（layout.py）
# ----------------------------------------------------------------------
def test_compute_cell_dp_clamped():
    assert compute_cell_dp(10000, 10000, 9, 9) == CELL_MAX_DP     # 上限
    assert compute_cell_dp(10, 10, 30, 30) == CELL_MIN_DP         # 下限
    mid = compute_cell_dp(600, 800, 16, 16)
    assert CELL_MIN_DP <= mid <= CELL_MAX_DP


def test_needs_scroll_for_big_board():
    cell = compute_cell_dp(360, 500, 30, 30)      # 30 列 → 360/30 = 12 → clamp 30
    assert needs_scroll(cell) is True
    assert compute_cell_dp(900, 900, 9, 9) >= MIN_TAP_DP


def test_board_size_and_cell_mapping():
    w, h = board_size(rows=10, cols=12, cell=40.0)
    assert (w, h) == (480.0, 400.0)
    # row 0 在顶部：y 接近 h
    assert cell_at(0, h - 1, 10, 12, 40.0) == (0, 0)
    assert cell_at(w - 1, 0, 10, 12, 40.0) == (9, 11)
    assert cell_at(-5, 10, 10, 12, 40.0) is None       # 越界
    assert cell_rect(0, 0, 10, 40.0) == (0.0, 360.0)
