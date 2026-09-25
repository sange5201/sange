"""presentation/ui/icons.py — 程序化像素图标（零位图资产 · 美术圣经 §3）。

分两半：
1) **纯几何区（零 Kivy 依赖，可本机单测）**：图标在 16×16 虚拟像素网格上定义，
   坐标归一化到 0..16，等比缩放保证任意 DPI 下像素比例一致（美术圣经 §4.1）。
   几何直接移植自 `minesweeper.py` 的 draw_flag / draw_mine / draw_face。
2) **绘制区（Kivy）**：把图元映射为 Canvas 指令。kivy 未安装时仍可 import
   本模块（几何部分可用），绘制函数会自然失败但不会被收集期触发。

图元类型（归一化网格坐标，左上原点）：
- ("rect", x, y, w, h)
- ("tri", [(x1,y1), (x2,y2), (x3,y3)])
- ("ellipse", x, y, w, h)
- ("line", [(x1,y1), (x2,y2)], width_grid)   width_grid 为网格单位线宽
- ("dots", [(x,y,w,h), ...])                 点阵（3×5 数字字体）

依赖：core.theme（令牌，仅数据）。不反向修改 core。
"""
from core.theme import get_theme

try:                                    # Kivy 可选：几何部分在无 Kivy 时仍可测
    from kivy.graphics import Color, Rectangle, Triangle, Ellipse, Line
    HAS_KIVY = True
except Exception:                       # pragma: no cover - 本机/CI 无 kivy 分支
    HAS_KIVY = False

GRID = 16  # 虚拟像素网格边长（美术圣经 §4.1）

# ---- 3×5 点阵数字字体（棋盘数字 / LCD 备用）----
DIGIT_3X5 = {
    0: ("111", "101", "101", "101", "111"),
    1: ("010", "110", "010", "010", "111"),
    2: ("111", "001", "111", "100", "111"),
    3: ("111", "001", "111", "001", "111"),
    4: ("101", "101", "111", "001", "001"),
    5: ("111", "100", "111", "001", "111"),
    6: ("111", "100", "111", "101", "111"),
    7: ("111", "001", "001", "001", "001"),
    8: ("111", "101", "111", "101", "111"),
    9: ("111", "101", "111", "001", "111"),
}
QUESTION_3X5 = ("111", "001", "011", "000", "010")   # 「?」标记

# ---- 七段数码管（经典 LCD 计数器）----
# 段位：0上 1右上 2右下 3下 4左下 5左上 6中
SEVEN_SEG = {
    "0": {0, 1, 2, 3, 4, 5}, "1": {1, 2}, "2": {0, 1, 6, 4, 3},
    "3": {0, 1, 6, 2, 3}, "4": {5, 6, 1, 2}, "5": {0, 5, 6, 2, 3},
    "6": {0, 5, 6, 4, 3, 2}, "7": {0, 1, 2}, "8": {0, 1, 2, 3, 4, 5, 6},
    "9": {0, 1, 2, 3, 5, 6}, "-": {6}, " ": set(),
}


# ======================================================================
# 一、纯几何区（零 Kivy 依赖）
# ======================================================================
def digit_bitmap(n):
    """棋盘数字 → 3×5 点阵亮格坐标列表 [(px, py), ...]（0..2 × 0..4）。

    n 为 1..8（棋盘有效数字）；其他值返回空表。
    """
    rows = DIGIT_3X5.get(n)
    if rows is None:
        return []
    return [(x, y) for y, row in enumerate(rows) for x, ch in enumerate(row)
            if ch == "1"]


def question_bitmap():
    """「?」标记 → 3×5 点阵亮格坐标列表。"""
    return [(x, y) for y, row in enumerate(QUESTION_3X5)
            for x, ch in enumerate(row) if ch == "1"]


def seven_seg(ch):
    """字符 → 点亮段位集合；未知字符返回空集（熄灭）。"""
    return set(SEVEN_SEG.get(str(ch), set()))


def _seg_rect(seg, w=8.0, h=14.0, t=2.0):
    """段位 → (x, y, w, h) 归一化矩形（左上原点，w/h 为 LCD 单字符尺寸）。"""
    if seg == 0:
        return (t, 0.0, w - 2 * t, t)
    if seg == 3:
        return (t, h - t, w - 2 * t, t)
    if seg == 6:
        return (t, (h - t) / 2.0, w - 2 * t, t)
    if seg == 5:
        return (0.0, t, t, (h - 3 * t) / 2.0)
    if seg == 4:
        return (0.0, (h + t) / 2.0, t, (h - 3 * t) / 2.0)
    if seg == 1:
        return (w - t, t, t, (h - 3 * t) / 2.0)
    if seg == 2:
        return (w - t, (h + t) / 2.0, t, (h - 3 * t) / 2.0)
    return (0.0, 0.0, 0.0, 0.0)


def seven_seg_rects(ch, w=8.0, h=14.0, t=2.0):
    """字符 → 段位矩形列表 [(x, y, w, h), ...]。"""
    return [_seg_rect(s, w, h, t) for s in sorted(seven_seg(ch))]


def flag_primitives():
    """像素红旗（移植 minesweeper.py::draw_flag 几何）。"""
    return [
        ("line", [(8, 2), (8, 14)], 1.0),        # 旗杆
        ("tri", [(7.5, 3), (2, 6), (7.5, 9)]),   # 旗面（朝左）
        ("rect", 5, 13, 6, 1.5),                 # 底座横杆
        ("rect", 6.5, 13.5, 3, 1.5),             # 底座
    ]


def mine_primitives():
    """像素地雷（移植 minesweeper.py::draw_mine 几何）。"""
    return [
        ("ellipse", 3, 3, 10, 10),               # 雷体
        ("rect", 7, 1.5, 2, 3),                  # 引信（上）
        ("rect", 1.5, 7, 3, 2),                  # 刺（左）
        ("rect", 11.5, 7, 3, 2),                 # 刺（右）
        ("rect", 7, 11.5, 2, 3),                 # 刺（下）
        ("rect", 5.5, 5.5, 2, 2),                # 高光
    ]


def cross_primitives():
    """误旗红叉（失败时标出插错的旗）。"""
    return [("line", [(3, 3), (13, 13)], 1.5), ("line", [(13, 3), (3, 13)], 1.5)]


def face_primitives(state="smile"):
    """笑脸四态几何：smile / wow / cool / dead（移植 draw_face）。"""
    prims = [("ellipse", 1.5, 1.5, 13, 13)]      # 脸盘（黄底由调用方上色）
    if state == "dead":                          # 失败：X 眼 + 平嘴
        prims += [("line", [(4.5, 5), (7.5, 8)], 1.0),
                  ("line", [(7.5, 5), (4.5, 8)], 1.0),
                  ("line", [(8.5, 5), (11.5, 8)], 1.0),
                  ("line", [(11.5, 5), (8.5, 8)], 1.0),
                  ("rect", 5, 10.5, 6, 1.2)]
    elif state == "cool":                        # 胜利：墨镜
        prims += [("rect", 3, 5.5, 4, 2.5), ("rect", 9, 5.5, 4, 2.5),
                  ("line", [(7, 6.5), (9, 6.5)], 1.0),
                  ("line", [(3, 7.5), (1.5, 8.5)], 1.0),
                  ("line", [(13, 7.5), (14.5, 8.5)], 1.0),
                  ("line", [(5.5, 10.5), (10.5, 10.5)], 1.2)]
    elif state == "wow":                         # 按下/紧张：o 嘴
        prims += [("rect", 4.5, 5, 2, 2), ("rect", 9.5, 5, 2, 2),
                  ("ellipse", 6.5, 9.5, 3, 3)]
    else:                                        # smile：微笑弧（折线近似）
        prims += [("rect", 4.5, 5, 2, 2), ("rect", 9.5, 5, 2, 2),
                  ("line", [(5, 10), (7, 12), (11, 10)], 1.2)]
    return prims


def hex_to_rgba(h, alpha=1.0):
    """'#rrggbb' → (r, g, b, a) 浮点元组（Kivy Color 需要 0..1）。"""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
    except (ValueError, IndexError):
        r = g = b = 0.5
    return (r, g, b, alpha)


# ======================================================================
# 二、绘制区（Kivy）
# ======================================================================
def _map_point(x, y, x0, y0, u, size):
    """网格坐标（左上原点，y 向下）→ Kivy 坐标（左下原点，y 向上）。"""
    return (x0 + x * u, y0 + size - (y + 0.0) * u)


def draw_primitives(group, prims, x, y, size, color):
    """把图元列表画进 InstructionGroup。

    :param group: Kivy InstructionGroup（已创建，未加入 canvas）
    :param prims: 图元列表（见模块头）
    :param x, y:  该图标所在区域的**左下角** Kivy 坐标
    :param size:  区域边长（px）
    :param color: (r,g,b,a) 浮点元组
    """
    u = size / float(GRID)
    group.add(Color(*color))
    for prim in prims:
        kind = prim[0]
        if kind == "rect":
            _, px, py, pw, ph = prim
            gx = x + px * u
            gy = y + size - (py + ph) * u
            group.add(Rectangle(pos=(gx, gy), size=(pw * u, ph * u)))
        elif kind == "tri":
            pts = []
            for (px, py) in prim[1]:
                pts.extend(_map_point(px, py, x, y, u, size))
            group.add(Triangle(points=pts))
        elif kind == "ellipse":
            _, px, py, pw, ph = prim
            gx = x + px * u
            gy = y + size - (py + ph) * u
            group.add(Ellipse(pos=(gx, gy), size=(pw * u, ph * u)))
        elif kind == "line":
            pts = []
            for (px, py) in prim[1]:
                pts.extend(_map_point(px, py, x, y, u, size))
            width = prim[2] * u if len(prim) > 2 else u
            group.add(Line(points=pts, width=max(width, 1.0)))
        elif kind == "dots":
            for (px, py, pw, ph) in prim[1]:
                gx = x + px * u
                gy = y + size - (py + ph) * u
                group.add(Rectangle(pos=(gx, gy), size=(pw * u, ph * u)))
    return group


def draw_bitmap(group, bitmap, x, y, size, cell_px, color):
    """3×5 点阵 → 方块序列。cell_px 为单个点阵像素边长。"""
    group.add(Color(*color))
    for (px, py) in bitmap:
        gx = x + px * cell_px
        gy = y + size - (py + 1) * cell_px
        group.add(Rectangle(pos=(gx, gy), size=(cell_px, cell_px)))
    return group


def draw_number(group, n, x, y, size, color):
    """棋盘数字（1..8）居中绘制（3×5 点阵，点边长 = size/5）。"""
    bitmap = digit_bitmap(n)
    if not bitmap:
        return group
    u = size / 5.0
    ox = x + (size - 3 * u) / 2.0
    oy = y + (size - 5 * u) / 2.0
    return draw_bitmap(group, bitmap, ox, oy, size, u, color)


def draw_question(group, x, y, size, color):
    """「?」标记（3×5 点阵）。"""
    u = size / 5.0
    ox = x + (size - 3 * u) / 2.0
    oy = y + (size - 5 * u) / 2.0
    return draw_bitmap(group, question_bitmap(), ox, oy, size, u, color)


def draw_flag(group, x, y, size, flag_color, pole_color):
    """红旗：旗杆黑、旗面红。"""
    prims = flag_primitives()
    draw_primitives(group, [prims[0], prims[2], prims[3]], x, y, size, pole_color)
    draw_primitives(group, [prims[1]], x, y, size, flag_color)
    return group


def draw_mine(group, x, y, size, mine_color, highlight=None):
    """地雷：雷体黑 + 白色高光。"""
    prims = mine_primitives()
    draw_primitives(group, prims[:5], x, y, size, mine_color)
    if highlight is not None:
        draw_primitives(group, [prims[5]], x, y, size, highlight)
    return group


def draw_face(group, x, y, size, face_color, ink_color, state="smile"):
    """笑脸按钮四态。"""
    draw_primitives(group, [("ellipse", 1.5, 1.5, 13, 13)],
                    x, y, size, face_color)
    draw_primitives(group, face_primitives(state)[1:], x, y, size, ink_color)
    return group


def draw_lcd(group, text, x, y, w, h, fg, bg, digits=3):
    """经典 LCD 计数器（七段数码管，黑底红字）。

    :param text: 整数或字符串；负数显示 '-' 前缀
    :param digits: 位数（不足补空格）
    """
    group.add(Color(*bg))
    group.add(Rectangle(pos=(x, y), size=(w, h)))
    s = str(text)
    if len(s) > digits:
        s = s[-digits:]
    s = s.rjust(digits)
    cw = w / float(digits)
    th = max(1.0, min(cw, h) * 0.14)          # 段厚
    for i, ch in enumerate(s):
        cx = x + i * cw
        rects = seven_seg_rects(ch, w=10.0, h=18.0, t=2.0)
        group.add(Color(*fg))
        for (rx, ry, rw, rh) in rects:
            group.add(Rectangle(
                pos=(cx + rx / 10.0 * cw, y + h - (ry + rh) / 18.0 * h),
                size=(rw / 10.0 * cw, rh / 18.0 * h)))
    return group


# Okabe-Ito 色盲安全色板（美术圣经 §8.2：默认保留经典配色，开关后启用）
OKABE_ITO_NUM = {
    1: "#0072B2", 2: "#009E73", 3: "#D55E00", 4: "#CC79A7",
    5: "#E69F00", 6: "#56B4E9", 7: "#000000", 8: "#666666",
}


def theme_colors(name="light", colorblind: bool = False):
    """主题令牌 → 常用绘制色（浮点 rgba）。

    colorblind=True 时数字 1–8 换用 Okabe-Ito 安全色板（美术圣经 §8.2），
    其余令牌不变（形状编码本身已安全：旗为旗形、雷为圆形）。
    """
    t = get_theme(name)
    num_hex = OKABE_ITO_NUM if colorblind else t["NUM"]
    return {
        "bg": hex_to_rgba(t["BG"]),
        "light": hex_to_rgba(t["LIGHT"]),
        "dark": hex_to_rgba(t["DARK"]),
        "black": hex_to_rgba(t["BLACK"]),
        "red": hex_to_rgba(t["RED"]),
        "yellow": hex_to_rgba(t["YELLOW"]),
        "num": {k: hex_to_rgba(v) for k, v in num_hex.items()},
        "lcd_bg": hex_to_rgba(t["lcd_bg"]),
        "lcd_fg": hex_to_rgba(t["lcd_fg"]),
    }
