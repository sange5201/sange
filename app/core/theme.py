"""core/theme.py — 双主题令牌表（仅数据，不做绘制）。Leaf，无内部依赖。

迁移自 `minesweeper.py::THEMES`（逐项对齐美术圣经 §2.2 / system-design C2）。
UI 层直接读取 dict 令牌，不在此处执行任何绘制逻辑。
"""
from typing import Dict, Any

THEMES: Dict[str, Dict[str, Any]] = {
    "light": {
        "BG": "#c0c0c0", "LIGHT": "#ffffff", "DARK": "#808080",
        "BLACK": "#000000", "RED": "#ff0000", "YELLOW": "#ffff00",
        "BLUE": "#0000ff",
        "NUM": {1: "#0000FF", 2: "#008000", 3: "#FF0000", 4: "#000080",
                5: "#800000", 6: "#008080", 7: "#000000", 8: "#808080"},
        "lcd_bg": "#000000", "lcd_fg": "#ff0000",
        "win_bg": "#c0c0c0", "panel_bg": "#c0c0c0",
    },
    "dark": {
        "BG": "#2d2d3a", "LIGHT": "#3c3c4d", "DARK": "#14141c",
        "BLACK": "#0b0b12", "RED": "#ff6b6b", "YELLOW": "#ffe066",
        "BLUE": "#74c0fc",
        "NUM": {1: "#5b9eff", 2: "#69db7c", 3: "#ff8787", 4: "#b197fc",
                5: "#ffa94d", 6: "#3bc9db", 7: "#ced4da", 8: "#adb5bd"},
        "lcd_bg": "#0b0b12", "lcd_fg": "#ff6b6b",
        "win_bg": "#1c1c26", "panel_bg": "#2d2d3a",
    },
}

DEFAULT_THEME = "light"


def get_theme(name: str) -> Dict[str, Any]:
    """返回指定主题令牌表；未知名称回退默认主题。"""
    if name not in THEMES:
        name = DEFAULT_THEME
    return THEMES[name]


def available_themes() -> list:
    return list(THEMES.keys())
