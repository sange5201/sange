"""presentation/ui/board_widget.py — 单 Canvas / 单 Widget 棋盘（ADR-02）。

S-UI-BOARD 验收要点：
- **单 Widget + 单 Canvas**：大棋盘（30×30=900 格）不建 900 个独立 Widget，
  全部格用 Canvas 指令绘制，规避 Kivy 子控件树卡顿（架构 R3 / ADR-02）。
- **增量重绘**：每格一个 InstructionGroup，缓存于 `self._groups`；
  `repaint(cells)` 仅替换 changed 格（board.reveal 返回 changed 列表）。
- **零位图**：旗/雷/数字/问号全部由 icons.py 程序化绘制。
- 坐标换算走 `layout.cell_at`（纯函数），row 0 在顶部。

依赖：core（session/board 只读 + 主题令牌）、icons、layout。
对局动作**不**由此控件执行，统一交给 TouchDispatcher（presentation/touch）。
"""
from kivy.graphics import InstructionGroup, Rectangle, Color
from kivy.uix.widget import Widget

from presentation.ui import icons
from presentation.ui.layout import compute_cell_dp, board_size, cell_at, cell_rect


class BoardWidget(Widget):
    """棋盘绘制控件（单 Canvas）。

    用法：
        w = BoardWidget(session=session, bus=bus)
        w.fit(avail_w, avail_h)     # 计算 cell 尺寸（旋转/首次布局）
        w.build_canvas()            # 全量重绘
        w.repaint(changed_cells)    # 增量重绘
    """

    def __init__(self, session=None, bus=None, theme: str = "light",
                 cell: float = 48.0, colorblind: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.bus = bus
        self.theme_name = theme
        self.colorblind = colorblind
        self.cell = float(cell)
        self._groups = {}                 # (r,c) -> InstructionGroup
        self.size_hint = (None, None)
        self._sync_size()

    # ------------------------------------------------------------------
    # 尺寸 / 布局
    # ------------------------------------------------------------------
    def _board(self):
        return getattr(self.session, "board", None)

    def _sync_size(self) -> None:
        b = self._board()
        if b is None:
            self.size = (0, 0)
            return
        w, h = board_size(b.rows, b.cols, self.cell)
        self.size = (w, h)

    def fit(self, avail_w: float, avail_h: float) -> float:
        """按可用空间重算 cell（旋转/首次布局）。返回新的 cell 边长。"""
        b = self._board()
        if b is None:
            return self.cell
        self.cell = float(compute_cell_dp(avail_w, avail_h, b.rows, b.cols))
        self._sync_size()
        return self.cell

    def cell_count(self) -> int:
        """棋盘格数（烟雾测试断言用：rows*cols）。"""
        b = self._board()
        return 0 if b is None else b.rows * b.cols

    def cell_at_pos(self, x: float, y: float):
        """Kivy 坐标 → (r, c)；越界 None。"""
        b = self._board()
        if b is None:
            return None
        return cell_at(x, y, b.rows, b.cols, self.cell)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.build_canvas()

    def set_colorblind(self, enabled: bool) -> None:
        """色盲辅助开关（美术圣经 §8.2）：数字换 Okabe-Ito 安全色板。"""
        self.colorblind = enabled
        self.build_canvas()

    def build_canvas(self) -> None:
        """全量重绘（新局 / 主题切换 / 首次）。"""
        self.canvas.clear()
        self._groups.clear()
        b = self._board()
        if b is None:
            return
        for r in range(b.rows):
            for c in range(b.cols):
                self._draw_cell(r, c)

    def repaint(self, cells=None) -> None:
        """增量重绘；cells 为 None 时全量。"""
        if cells is None:
            self.build_canvas()
            return
        for (r, c) in cells:
            self._draw_cell(r, c)

    def _draw_cell(self, r: int, c: int) -> None:
        """（重）画一格：先移除该格旧指令组，再新建。"""
        b = self._board()
        if b is None:
            return
        key = (r, c)
        old = self._groups.pop(key, None)
        if old is not None:
            self.canvas.remove(old)

        grp = InstructionGroup()
        self._paint_cell(grp, b, r, c)
        self._groups[key] = grp
        self.canvas.add(grp)

    # ------------------------------------------------------------------
    # 单格绘制细节
    # ------------------------------------------------------------------
    def _paint_cell(self, grp, b, r: int, c: int) -> None:
        col = icons.theme_colors(self.theme_name, colorblind=self.colorblind)
        x, y = cell_rect(r, c, b.rows, self.cell)
        s = self.cell
        bevel = max(1.5, s * 0.08)

        revealed = b.is_revealed(r, c)
        flagged = b.is_flagged(r, c)
        marked = b.is_marked(r, c)
        mine = b.is_mine(r, c)
        trig = b.is_triggered

        # 1) 底 + 斜面（未翻开=凸起；已翻开=凹陷）
        grp.add(Color(*col["bg"]))
        grp.add(Rectangle(pos=(x, y), size=(s, s)))
        if revealed:
            grp.add(Color(*col["dark"]))
            grp.add(Rectangle(pos=(x, y + s - bevel), size=(s, bevel)))     # 上
            grp.add(Rectangle(pos=(x, y), size=(bevel, s)))                 # 左
            grp.add(Color(*col["light"]))
            grp.add(Rectangle(pos=(x, y), size=(s, bevel)))                 # 下
            grp.add(Rectangle(pos=(x + s - bevel, y), size=(bevel, s)))     # 右
        else:
            grp.add(Color(*col["light"]))
            grp.add(Rectangle(pos=(x, y + s - bevel), size=(s, bevel)))
            grp.add(Rectangle(pos=(x, y), size=(bevel, s)))
            grp.add(Color(*col["dark"]))
            grp.add(Rectangle(pos=(x, y), size=(s, bevel)))
            grp.add(Rectangle(pos=(x + s - bevel, y), size=(bevel, s)))

        # 2) 触发雷格：红底（边界 8）
        if trig is not None and trig == (r, c):
            grp.add(Color(*col["red"]))
            grp.add(Rectangle(pos=(x, y), size=(s, s)))

        # 3) 内容
        pad = s * 0.18
        ix, iy, isz = x + pad, y + pad, s - 2 * pad
        if flagged:
            icons.draw_flag(grp, ix, iy, isz, col["red"], col["black"])
            if b.game_over and not mine:
                icons.draw_primitives(grp, icons.cross_primitives(),
                                      ix, iy, isz, col["red"])
        elif revealed and mine:
            icons.draw_mine(grp, ix, iy, isz, col["black"], col["light"])
        elif marked:
            icons.draw_question(grp, ix, iy, isz, col["black"])
        elif revealed:
            n = b.number_at(r, c)
            if n > 0:
                icons.draw_number(grp, n, ix, iy, isz, col["num"].get(n, col["black"]))
