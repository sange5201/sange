"""test_theme.py — theme.THEMES / get_theme（S-THM 验收）。

仅数据令牌，不做绘制（system-design C2）；UI 直接读 dict。
"""
import pytest

from core.theme import THEMES, get_theme, available_themes, DEFAULT_THEME


def test_themes_have_light_and_dark():
    assert "light" in THEMES and "dark" in THEMES


def test_theme_values_aligned():
    for name in ("light", "dark"):
        t = THEMES[name]
        for key in ("BG", "LIGHT", "DARK", "BLACK", "RED", "NUM",
                    "lcd_bg", "lcd_fg"):
            assert key in t
        # 数字令牌 1-8 齐全
        assert set(t["NUM"].keys()) == set(range(1, 9))


def test_get_theme_unknown_falls_back_to_default():
    assert get_theme("nope") is THEMES[DEFAULT_THEME]
    assert get_theme("light") is THEMES["light"]


def test_available_themes():
    assert available_themes() == list(THEMES.keys())
