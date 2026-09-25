"""core/config.py — 难度/每日/交互常量唯一真源（Leaf，无内部依赖）。

迁移自 `minesweeper.py::LEVELS` / `THEMES` 关联常量。
数值以本文件为准；README 旧难度表已作废（system-design C1）。
"""
from typing import Tuple, Optional

# ---- 10 档难度（唯一真源，逐项对齐 minesweeper.py）----
LEVELS = {
    "入门":   {"rows": 9,  "cols": 9,  "mines": 8},
    "简单":   {"rows": 9,  "cols": 9,  "mines": 12},
    "初级":   {"rows": 12, "cols": 12, "mines": 20},
    "中级":   {"rows": 16, "cols": 16, "mines": 40},
    "进阶":   {"rows": 16, "cols": 16, "mines": 56},
    "高级":   {"rows": 16, "cols": 30, "mines": 99},
    "专家":   {"rows": 20, "cols": 30, "mines": 140},
    "大师":   {"rows": 24, "cols": 30, "mines": 190},
    "地狱":   {"rows": 30, "cols": 30, "mines": 250},
    "自定义": {"rows": 0,  "cols": 0,  "mines": 0, "custom": True},
}

# ---- 每日挑战默认配置（用户拍板：自由首击 + 默认中级）----
DAILY_CONFIG = {"rows": 16, "cols": 16, "mines": 40}

# ---- 交互 / 动画常量（system-design §2.2 / §2.6）----
LONG_PRESS_MS = 350      # 长按插旗阈值
DOUBLE_TAP_MS = 300      # 双击 chord 窗口
UNDO_DEPTH = 1           # 撤销深度默认 1（≤5 可配）
TIMER_CAP = 999          # 计时封顶（秒，int）

# ---- 自定义难度相关 ----
MIN_CUSTOM = 5           # 自定义维度下限（沿用 ask_custom）
MAX_CUSTOM = 40          # 自定义维度上限


def max_mines(rows: int, cols: int) -> int:
    """首击安全（3×3 禁区）下可布雷上限。"""
    return rows * cols - 9


def validate_level(rows: int, cols: int, mines: int) -> Tuple[bool, Optional[str]]:
    """校验自定义/外部传入的难度维度与雷数（system-design §2.1 边界 1/3）。

    返回 (ok, error_msg)。ok=False 时 error_msg 为非 None 的中文提示。
    """
    if rows < 1 or cols < 1:
        return False, "行/列必须 ≥ 1"
    if max_mines(rows, cols) < 1:
        return False, "棋盘太小，无法保证首击安全（需 ≥10 格）"
    if mines < 1:
        return False, "雷数必须 ≥ 1"
    if mines > max_mines(rows, cols):
        return False, f"雷数超过首击安全上限（≤ {max_mines(rows, cols)}）"
    return True, None
