"""core/board.py — 棋盘内核（纯逻辑 · 零 UI 依赖）。

三大结构性改造落点（architecture §3.2）：
  ① 洪水 reveal：递归 → 显式栈（ADR-05），语义等价，零递归风险。
  ② place_mines：RNG 可注入（默认模块 random；每日注入 random.Random(seed)）。
  ③ 胜负 / chord / 计时：emit 事件（ADR-03），核心不 import 成就。

依赖：config（维度校验由调用方负责，本模块假定入参合法）、events（抛事件）。
P1 红线：首击安全、洪水、chord、胜负、邻接计数 与桌面版逐字节一致。

接口就绪度：§2.2 签名已定。唯一微调——构造函数增加可选 `bus` 参数
（§2.2 原签名未含 bus，但 board 需 emit；本实现以 `bus=None` 兜底内部总线，
GameSession 传入共享总线，见 control-checklist 待定项 B-1）。
"""
import random
from typing import Optional, Dict, List, Tuple

from .events import EventBus, GameEvent


class Board:
    def __init__(self, rows: int, cols: int, mines: int,
                 rng=random, question_enabled: bool = True,
                 bus: Optional[EventBus] = None):
        self.rows, self.cols, self.mines = rows, cols, mines
        self.rng = rng                      # 可注入；每日挑战传 random.Random(seed)
        self.question_enabled = question_enabled
        self.bus = bus or EventBus()        # 见文件头 B-1 说明

        self.board = [[0] * cols for _ in range(rows)]     # -1 雷 / 0-8 邻雷数
        self.revealed = [[False] * cols for _ in range(rows)]
        self.flagged = [[False] * cols for _ in range(rows)]
        self.marked = [[False] * cols for _ in range(rows)]

        self.mines_placed = False
        self.game_over = False
        self.win = False
        self.is_triggered = None            # 触发失败的雷格坐标
        self.chord_count = 0                # 本局成功 chord 累计（成就/UI 用）
        self.wrong_flag_events = 0          # 全程误旗操作次数（插旗到非雷格），供「零误旗」成就评估

    # ---------------- 布雷（首击安全 + rng 注入）----------------
    def place_mines(self, safe_r: int, safe_c: int, rng=None) -> None:
        """在 safe 格 3×3 禁区外随机布雷，随后 8 邻域计数。

        越界禁区格被 clamp（边界 2）；rng 默认用 self.rng（每日局注入 seed rng）。
        """
        rng = rng or self.rng
        forbidden = {
            (safe_r + dr, safe_c + dc)
            for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            if 0 <= safe_r + dr < self.rows and 0 <= safe_c + dc < self.cols
        }
        candidates = [
            (r, c) for r in range(self.rows) for c in range(self.cols)
            if (r, c) not in forbidden
        ]
        assert self.mines <= len(candidates), "mines exceed safe candidates"
        for (r, c) in rng.sample(candidates, self.mines):
            self.board[r][c] = -1
        self._count_adjacent()
        self.mines_placed = True

    def _count_adjacent(self) -> None:
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    continue
                cnt = 0
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        rr, cc = r + dr, c + dc
                        if (0 <= rr < self.rows and 0 <= cc < self.cols
                                and self.board[rr][cc] == -1):
                            cnt += 1
                self.board[r][c] = cnt

    # ---------------- 首击 ----------------
    def first_click(self, r: int, c: int) -> Dict:
        """首击：布雷（注入 self.rng）+ 揭示；返回 reveal 结果字典。"""
        if not self.mines_placed:
            self.place_mines(r, c)
        return self.reveal(r, c)

    # ---------------- 揭示（显式栈洪水，ADR-05）----------------
    def reveal(self, r: int, c: int) -> Dict:
        """翻开 (r,c)。返回 {result, changed, triggered}。

        - result: 'reveal' | 'lose' | 'noop'
        - changed: 本次新翻开坐标列表（供表现层增量重绘）
        - triggered: 触雷坐标（lose 时），否则 None

        显式栈语义（§3.2①）：0 值格入栈继续展开；数字格不入栈；
        flagged 优先跳过；遇雷 → lose_game + emit LOSE。
        """
        if self.game_over:
            return {"result": "noop", "changed": [], "triggered": None}
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return {"result": "noop", "changed": [], "triggered": None}
        if self.revealed[r][c] or self.flagged[r][c]:
            return {"result": "noop", "changed": [], "triggered": None}

        changed: List[Tuple[int, int]] = []
        stack = [(r, c)]
        while stack:
            cr, cc = stack.pop()
            if not (0 <= cr < self.rows and 0 <= cc < self.cols):
                continue
            if self.revealed[cr][cc] or self.flagged[cr][cc]:
                continue
            self.revealed[cr][cc] = True
            changed.append((cr, cc))
            if self.board[cr][cc] == -1:
                self.lose_game(cr, cc)
                self.bus.emit(GameEvent.LOSE, {"triggered": (cr, cc)})
                return {"result": "lose", "changed": changed, "triggered": (cr, cc)}
            if self.board[cr][cc] == 0:           # 仅 0 值格展开邻域
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        stack.append((cr + dr, cc + dc))

        if changed:
            self.bus.emit(GameEvent.REVEAL, {"changed": list(changed)})
        self.check_win()
        return {"result": "reveal", "changed": changed, "triggered": None}

    # ---------------- chord（数字格连开）----------------
    def chord(self, r: int, c: int) -> Dict:
        """对已翻开数字格执行连开：邻旗数 == 数字 → 翻开全部未插旗邻格。

        返回 {result, changed, triggered}；result: 'chord' | 'noop' | 'lose'。
        条件不足（旗数≠数字 / 非数字 / 未翻开）→ noop（边界 4）。
        """
        if self.game_over:
            return {"result": "noop", "changed": [], "triggered": None}
        if self.board[r][c] <= 0 or not self.revealed[r][c]:
            return {"result": "noop", "changed": [], "triggered": None}

        neighbors = []
        flags = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < self.rows and 0 <= cc < self.cols:
                    neighbors.append((rr, cc))
                    if self.flagged[rr][cc]:
                        flags += 1

        if flags != self.board[r][c]:
            return {"result": "noop", "changed": [], "triggered": None}

        changed: List[Tuple[int, int]] = []
        for (rr, cc) in neighbors:
            if not self.flagged[rr][cc]:
                res = self.reveal(rr, cc)
                changed.extend(res["changed"])
                if res["result"] == "lose":
                    return {"result": "lose", "changed": changed,
                            "triggered": res["triggered"]}
        self.chord_count += 1
        self.bus.emit(GameEvent.CHORD, {"count": self.chord_count})
        return {"result": "chord", "changed": changed}

    # ---------------- 标记循环（无→旗→?→无）----------------
    def cycle_mark(self, r: int, c: int) -> None:
        """长按/模式按钮共用的纯逻辑标记循环。

        question_enabled 关 → 退化为 无→旗→无（边界：系统-design §2.2 数值）。
        胜利/已翻开格忽略（边界 5/6 由调用方保证 game_over 时不调用）。
        """
        if self.game_over or self.revealed[r][c]:
            return
        if self.flagged[r][c]:
            self.flagged[r][c] = False
            if self.question_enabled:
                self.marked[r][c] = True
        elif self.marked[r][c]:
            self.marked[r][c] = False
        else:
            self.flagged[r][c] = True
            # 误旗：插旗到非雷格（仅布雷后可判定；未布雷时 board 全 0 不计数）
            if self.mines_placed and self.board[r][c] != -1:
                self.wrong_flag_events += 1
        self.bus.emit(GameEvent.FLAG,
                      {"r": r, "c": c, "flagged": self.flagged[r][c]})

    # ---------------- 胜负 ----------------
    def check_win(self) -> bool:
        """全部非雷格已翻开 → 胜；胜利后自动给剩余雷插旗 + emit WIN。"""
        if self.game_over:
            return False
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] != -1 and not self.revealed[r][c]:
                    return False
        self.win = True
        self.game_over = True
        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    self.flagged[r][c] = True   # 边界 7：胜利自动插旗
        self.bus.emit(GameEvent.WIN, {})
        return True

    def lose_game(self, r: int, c: int) -> None:
        """踩雷：标记 game_over、揭示全部雷、记录触发格（边界 8 由 UI 标红叉）。"""
        self.game_over = True
        self.win = False
        self.is_triggered = (r, c)
        for rr in range(self.rows):
            for cc in range(self.cols):
                if self.board[rr][cc] == -1:
                    self.revealed[rr][cc] = True

    # ---------------- 查询 ----------------
    def number_at(self, r: int, c: int) -> int:
        return self.board[r][c]

    def is_mine(self, r: int, c: int) -> bool:
        return self.board[r][c] == -1

    def is_flagged(self, r: int, c: int) -> bool:
        return self.flagged[r][c]

    def is_revealed(self, r: int, c: int) -> bool:
        return self.revealed[r][c]

    def is_marked(self, r: int, c: int) -> bool:
        return self.marked[r][c]

    def remaining_mines(self) -> int:
        """剩余未插旗雷数（HUD 雷数计数器）。"""
        flagged = sum(sum(row) for row in self.flagged)
        return self.mines - flagged
