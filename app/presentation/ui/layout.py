"""presentation/ui/layout.py — 布局与尺寸计算（零 Kivy 依赖，可本机单测）。

把 UX 规格 §2 的 dp 骨架与 cell_dp 算法抽成纯函数，便于：
- 无 Kivy 环境验证数值（本机 Win10 未装 kivy）；
- 横屏/旋转重算（UX §2.5：仅重算 cell_dp 重建布局，不重置对局状态）。

数值来源（跨文档一致）：
- TopNav 48dp / HUD Row1 56dp / Row2 48dp（UX §2.1–2.4）
- MIN_TAP_DP 44（美术圣经 §5 / UX §6 热区恒 ≥44dp）
- cell_dp = clamp(round(avail / max(rows, cols)), CELL_MIN=30, CELL_MAX=56)（UX §2.3）
"""
MIN_TAP_DP = 44
CELL_MIN_DP = 30
CELL_MAX_DP = 56
TOPNAV_DP = 48
HUD_ROW1_DP = 56
HUD_ROW2_DP = 48
HUD_TOTAL_DP = HUD_ROW1_DP + HUD_ROW2_DP     # 104dp（UX §2.4）


def compute_cell_dp(avail_w: float, avail_h: float, rows: int, cols: int,
                    cell_min: int = CELL_MIN_DP, cell_max: int = CELL_MAX_DP):
    """按可用空间计算单格边长（dp）。

    UX §2.3：以较长边为准，保证整盘可见；结果 clamp 到 [30, 56]。
    返回值 < MIN_TAP_DP(44) 时，调用方应启用 ScrollView + pinch-zoom
    （UX §2.3：不压缩热区）。
    """
    if rows <= 0 or cols <= 0:
        return cell_min
    longest = max(rows, cols)
    avail = min(avail_w, avail_h) if min(avail_w, avail_h) > 0 else avail_w
    if avail <= 0:
        return cell_min
    raw = round(avail / float(longest))
    return max(cell_min, min(cell_max, raw))


def board_size(rows: int, cols: int, cell: float):
    """棋盘像素尺寸（宽 × 高）。"""
    return (cols * cell, rows * cell)


def needs_scroll(cell_dp: float) -> bool:
    """单格 <44dp → 需滚动/缩放辅助（UX §2.3 R2）。"""
    return cell_dp < MIN_TAP_DP


def cell_at(x: float, y: float, rows: int, cols: int, cell: float):
    """Kivy 坐标（widget 左下原点）→ (r, c)；越界返回 None。

    row 0 在**顶部**，故 r = rows-1-floor(y/cell)。
    """
    if cell <= 0:
        return None
    c = int(x // cell)
    r_from_bottom = int(y // cell)
    r = rows - 1 - r_from_bottom
    if 0 <= r < rows and 0 <= c < cols:
        return (r, c)
    return None


def cell_rect(r: int, c: int, rows: int, cell: float):
    """格 (r,c) → Kivy 左下角坐标 (x, y)。"""
    return (c * cell, (rows - 1 - r) * cell)
