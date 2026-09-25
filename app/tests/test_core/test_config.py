"""test_config.py — config.LEVELS / DAILY_CONFIG / 常量 / validate_level（S-CFG 验收）。

数值唯一真源对齐 minesweeper.py（system-design C1）；README 旧表作废。
"""
import pytest

from core.config import (
    LEVELS, DAILY_CONFIG, LONG_PRESS_MS, DOUBLE_TAP_MS, UNDO_DEPTH, TIMER_CAP,
    MAX_CUSTOM, MIN_CUSTOM, max_mines, validate_level,
)


# minesweeper.py 真值表（与代码逐项一致，P1 数值红线）
EXPECTED = {
    "入门": (9, 9, 8), "简单": (9, 9, 12), "初级": (12, 12, 20),
    "中级": (16, 16, 40), "进阶": (16, 16, 56), "高级": (16, 30, 99),
    "专家": (20, 30, 140), "大师": (24, 30, 190), "地狱": (30, 30, 250),
}


@pytest.mark.parametrize("name,expected", list(EXPECTED.items()))
def test_levels_values_match_reference(name, expected):
    cfg = LEVELS[name]
    assert (cfg["rows"], cfg["cols"], cfg["mines"]) == expected


def test_custom_level_is_marker():
    assert LEVELS["自定义"]["custom"] is True
    assert LEVELS["自定义"]["rows"] == 0


def test_daily_config_is_mid():
    assert DAILY_CONFIG == {"rows": 16, "cols": 16, "mines": 40}


def test_constants():
    assert LONG_PRESS_MS == 350
    assert DOUBLE_TAP_MS == 300
    assert UNDO_DEPTH == 1
    assert TIMER_CAP == 999
    assert MIN_CUSTOM == 5 and MAX_CUSTOM == 40


def test_max_mines_formula():
    assert max_mines(9, 9) == 81 - 9 == 72
    assert max_mines(16, 16) == 256 - 9 == 247


@pytest.mark.parametrize("rows,cols,mines,ok", [
    (9, 9, 8, True),          # 合法
    (1, 1, 1, False),         # 棋盘太小（<10 格）
    (9, 9, 0, False),         # 雷数 < 1
    (9, 9, 100, False),       # 雷数超上限
    (0, 9, 5, False),         # 行 < 1
])
def test_validate_level(rows, cols, mines, ok):
    good, _ = validate_level(rows, cols, mines)
    assert good is ok


def test_validate_level_returns_chinese_error():
    good, msg = validate_level(1, 1, 1)
    assert good is False
    assert isinstance(msg, str) and msg
