"""core/game.py — GameSession（对局编排 · 零 UI 依赖）。

S-GAME 验收（架构 §2.2 / §6.2 骨架）。

职责：编排 board + timer + daily + storage + achievements，驱动 core 状态与事件。
表现层（Kivy UI）只依赖本类，**绝不反向**依赖。

关键决策（与已拍板项对齐）：
- B-1 bus 注入：Board(bus=None) 兜底内部总线；GameSession 传**共享总线**给 board/定时器/成就。
- B-3 undo：一步撤销（UNDO_DEPTH=1），快照棋盘状态，**不回退计时**；game_over 后禁用。
- 胜负结算：board 内部 emit 空 WIN/LOSE（无 level/time）；GameSession 在每次动作后
  检查 board 状态，发出**富 WIN/LOSE**（带 level/time/flags_wrong，供成就评估），
  并写 best/daily 到 storage。成就引擎忽略空 WIN（无 level）。无事件递归风险。

依赖：board / timer / daily / storage / achievements / events / config。不依赖 UI / kivy。
"""
import datetime

from .board import Board
from .timer import GameTimer
from .daily import DailyProvider
from .storage import JsonStorage, StorageBackend
from .achievements import AchievementEngine
from .events import EventBus, GameEvent
from .config import LEVELS, TIMER_CAP, UNDO_DEPTH


class GameSession:
    """一局扫雷的编排者。"""

    def __init__(self, bus=None, storage=None, timer=None, daily=None):
        self.bus = bus or EventBus()
        self.storage = storage or JsonStorage(StorageBackend.base_dir())
        self.daily = daily or DailyProvider
        self.timer = timer or GameTimer(self.bus)
        # 成就引擎订阅共享总线（仅创建一次，避免重复订阅）
        self.achievements = AchievementEngine(self.bus, self.storage)

        self.board = None
        self._level = None
        self._is_daily = False
        self._daily_date = None
        self._resolved = False          # 胜负是否已结算（防重复）
        self._undo_stack = []           # B-3：撤销快照（深度 UNDO_DEPTH）

    # ------------------------------------------------------------------
    # 开局
    # ------------------------------------------------------------------
    def new_game(self, level: str = "初级", custom: dict = None) -> dict:
        """开常局。custom={rows,cols,mines} 时按自定义；否则用 LEVELS[level]。"""
        self._resolved = False
        self._undo_stack.clear()
        self._is_daily = False
        self._daily_date = None

        if custom is not None:
            rows, cols, mines = custom["rows"], custom["cols"], custom["mines"]
            self._level = f"自定义 {rows}x{cols}"
        else:
            cfg = LEVELS[level]
            rows, cols, mines = cfg["rows"], cfg["cols"], cfg["mines"]
            self._level = level

        self.board = Board(rows, cols, mines,
                           question_enabled=self._question_enabled(), bus=self.bus)
        self.timer = GameTimer(self.bus)
        self.timer.start()
        self.bus.emit(GameEvent.NEW_GAME,
                      {"level": self._level, "daily": False})
        return {"level": self._level, "rows": rows, "cols": cols, "mines": mines}

    def start_daily(self, date: datetime.date = None) -> dict:
        """开每日挑战局（自由首击 + DAILY_CONFIG + 种子 RNG）。"""
        self._resolved = False
        self._undo_stack.clear()
        date = date or datetime.date.today()
        cfg = self.daily.config()
        rng = self.daily.make_rng(date)
        self._level = f"每日 {date.isoformat()}"
        self._is_daily = True
        self._daily_date = date

        self.board = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng,
                           question_enabled=self._question_enabled(), bus=self.bus)
        self.timer = GameTimer(self.bus)
        self.timer.start()
        self.bus.emit(GameEvent.NEW_GAME,
                      {"level": self._level, "daily": True,
                       "date": date.isoformat()})
        return {"date": date.isoformat(), "config": cfg}

    # ------------------------------------------------------------------
    # 动作（转发到 board，驱动 timer/结算）
    # ------------------------------------------------------------------
    def reveal(self, r: int, c: int) -> dict:
        if self.board is None or self.board.game_over:
            return {"result": "noop", "changed": [], "triggered": None}
        self._push_undo()
        if not self.board.mines_placed:
            res = self.board.first_click(r, c)
        else:
            res = self.board.reveal(r, c)
        self._after_action(res)
        return res

    def chord(self, r: int, c: int) -> dict:
        if self.board is None or self.board.game_over:
            return {"result": "noop", "changed": [], "triggered": None}
        self._push_undo()
        res = self.board.chord(r, c)
        self._after_action(res)
        return res

    def cycle_mark(self, r: int, c: int) -> None:
        if self.board is None or self.board.game_over:
            return
        self._push_undo()
        self.board.cycle_mark(r, c)   # board 自行 emit FLAG

    # ------------------------------------------------------------------
    # 撤销（B-3：一步、不回退计时、game_over 禁用）
    # ------------------------------------------------------------------
    def undo(self) -> bool:
        if self.board is None or self.board.game_over:
            return False               # 禁用
        if not self._undo_stack:
            return False
        snap = self._undo_stack.pop()
        self.board.board = [row[:] for row in snap["board"]]
        self.board.revealed = [row[:] for row in snap["revealed"]]
        self.board.flagged = [row[:] for row in snap["flagged"]]
        self.board.marked = [row[:] for row in snap["marked"]]
        self.board.mines_placed = snap["mines_placed"]
        self.board.game_over = snap["game_over"]
        self.board.win = snap["win"]
        self.board.is_triggered = snap["is_triggered"]
        self.board.chord_count = snap["chord_count"]
        self.board.wrong_flag_events = snap["wrong_flag_events"]
        return True                    # 计时（elapsed）不受影响

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _question_enabled(self) -> bool:
        try:
            return bool(self.storage.get_setting("question_enabled", True))
        except Exception:
            return True

    def _push_undo(self) -> None:
        if self.board is None or self.board.game_over:
            return
        self._undo_stack.append(self._snapshot())
        while len(self._undo_stack) > UNDO_DEPTH:
            self._undo_stack.pop(0)

    def _snapshot(self) -> dict:
        return {
            "board": [row[:] for row in self.board.board],
            "revealed": [row[:] for row in self.board.revealed],
            "flagged": [row[:] for row in self.board.flagged],
            "marked": [row[:] for row in self.board.marked],
            "mines_placed": self.board.mines_placed,
            "game_over": self.board.game_over,
            "win": self.board.win,
            "is_triggered": self.board.is_triggered,
            "chord_count": self.board.chord_count,
            "wrong_flag_events": self.board.wrong_flag_events,
        }

    def _after_action(self, res: dict) -> None:
        if self.board.game_over and not self._resolved:
            self._resolved = True
            self.timer.stop()
            if self.board.win:
                self._handle_win()
            else:
                self._handle_lose(res)

    def _count_wrong_flags(self) -> int:
        """全程误旗次数（插旗到非雷格的操作累计）。

        语义修正：胜利与「残留误旗」互斥（误旗格插旗即不会翻开 → 不胜），
        故结算时统计残留误旗恒为 0、「零误旗」成就无区分度。改为统计**全程
        误旗操作次数**（board.wrong_flag_events）：玩家插错旗后取消再通关仍计 1 次，
        成就方有实际意义。
        """
        return self.board.wrong_flag_events

    def _handle_win(self) -> None:
        t = self.timer.elapsed
        level = self._level
        flags_wrong = self._count_wrong_flags()
        # 富 WIN（带 level/time/flags_wrong，供成就评估；board 空 WIN 已被忽略）
        self.bus.emit(GameEvent.WIN,
                      {"level": level, "time": t,
                       "flags_wrong": flags_wrong, "daily": self._is_daily})
        if self._is_daily and self._daily_date is not None:
            self.storage.set_daily_best(self._daily_date.isoformat(),
                                        min(t, TIMER_CAP))
            self.bus.emit(GameEvent.DAILY_COMPLETE,
                          {"date": self._daily_date.isoformat(), "time": t})
        else:
            self.storage.set_best(level, min(t, TIMER_CAP))

    def _handle_lose(self, res: dict) -> None:
        self.bus.emit(GameEvent.LOSE, {"level": self._level,
                                       "triggered": res.get("triggered")})
