"""test_game.py — GameSession 编排验收（S-GAME）。

覆盖 new_game / start_daily / reveal / chord / cycle_mark / undo 闭环，
以及胜负结算（富 WIN/LOSE、best/daily 写入、成就解锁）、计时停表、确定性。
无 UI 命令行可玩的核心证明（deliverable #7）。
"""
import datetime

import pytest

from core.game import GameSession
from core.events import EventBus, GameEvent
from core.storage import JsonStorage


@pytest.fixture
def session(tmp_path):
    bus = EventBus()
    storage = JsonStorage(str(tmp_path))
    return GameSession(bus=bus, storage=storage), bus, storage


def _force_layout(board, layout):
    """测试辅助：手工铺盘（绕过随机布雷），mines_placed=True。"""
    board.board = [row[:] for row in layout]
    board.mines_placed = True
    board.mines = sum(1 for row in layout for v in row if v == -1)
    board.revealed = [[False] * board.cols for _ in range(board.rows)]
    board.flagged = [[False] * board.cols for _ in range(board.rows)]
    board.marked = [[False] * board.cols for _ in range(board.rows)]


def test_new_game_creates_board(session):
    s, bus, _ = session
    s.new_game("初级")
    assert s.board is not None
    assert s.board.rows == 12 and s.board.cols == 12 and s.board.mines == 20
    assert s._level == "初级"
    assert not s.board.game_over


def test_reveal_before_new_game_is_noop(session):
    s, _, _ = session
    assert s.board is None
    assert s.reveal(0, 0)["result"] == "noop"


def test_reveal_first_click_floods(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 5, "cols": 5, "mines": 3})
    res = s.reveal(0, 0)
    assert res["result"] in ("reveal", "lose")
    if res["result"] == "reveal":
        assert len(res["changed"]) >= 1


def test_cycle_mark_via_game(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 4, "cols": 4, "mines": 1})
    s.cycle_mark(3, 3)
    assert s.board.is_flagged(3, 3)


def test_undo_restores_board_and_not_timer(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 4, "cols": 4, "mines": 1})
    s.cycle_mark(3, 3)
    assert s.board.is_flagged(3, 3)
    assert s.undo() is True
    assert not s.board.is_flagged(3, 3)
    # 计时不随撤销回退（边界 7）
    s.timer._tick()
    e1 = s.timer.elapsed
    s.cycle_mark(2, 2)
    assert s.undo() is True
    assert s.timer.elapsed == e1


def test_undo_disabled_after_game_over(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 4, "cols": 4, "mines": 1})
    _force_layout(s.board, [[1, -1, 0, 0],
                            [0, 0, 0, 0],
                            [0, 0, 0, 0],
                            [0, 0, 0, 0]])
    s.cycle_mark(3, 3)                   # 某动作（压入快照）
    s.reveal(0, 1)                       # 触雷 → 结束
    assert s.board.game_over
    assert s.undo() is False             # 结束后禁用


def test_win_writes_best_and_unlocks_achievement(session):
    s, bus, storage = session
    s.new_game(custom={"rows": 4, "cols": 4, "mines": 1})
    s.reveal(0, 0)
    for r in range(s.board.rows):
        for c in range(s.board.cols):
            if not s.board.is_mine(r, c):
                s.reveal(r, c)
    assert s.board.win
    assert storage.get_best("自定义 4x4") is not None
    assert s.achievements.is_unlocked("ach_first_win")


def test_lose_does_not_unlock_win_achievement(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 4, "cols": 4, "mines": 1})
    _force_layout(s.board, [[1, -1, 0, 0],
                            [0, 0, 0, 0],
                            [0, 0, 0, 0],
                            [0, 0, 0, 0]])
    res = s.reveal(0, 0)                 # 数字格，仅翻开自身（不洪水/不胜利）
    assert res["result"] == "reveal"
    assert not s.board.game_over and not s.board.win
    res = s.reveal(0, 1)                 # 触雷 → 失败
    assert res["result"] == "lose"
    assert s.board.game_over and not s.board.win
    assert not s.achievements.is_unlocked("ach_first_win")


def test_timer_stops_on_game_over(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 4, "cols": 4, "mines": 1})
    _force_layout(s.board, [[1, -1, 0, 0],
                            [0, 0, 0, 0],
                            [0, 0, 0, 0],
                            [0, 0, 0, 0]])
    s.timer._tick(); s.timer._tick()
    assert s.timer.elapsed == 2
    s.reveal(0, 1)                       # 触雷 → 停表
    assert s.board.game_over
    e = s.timer.elapsed
    s.timer._tick()                      # game_over 后 noop
    assert s.timer.elapsed == e


def test_start_daily_is_deterministic(session):
    d = datetime.date(2025, 9, 25)
    s1, _, _ = session
    s1.start_daily(d); s1.reveal(8, 8)
    s2, _, _ = session
    s2.start_daily(d); s2.reveal(8, 8)
    assert s1.board.board == s2.board.board
    assert s1._is_daily and s1._daily_date == d


def test_daily_win_writes_daily_best_and_achievement(session):
    d = datetime.date(2025, 9, 25)
    s, bus, storage = session
    s.start_daily(d)
    s.reveal(0, 0)
    for r in range(s.board.rows):
        for c in range(s.board.cols):
            if not s.board.is_mine(r, c):
                s.reveal(r, c)
    assert s.board.win
    assert storage.get_daily_best(d.isoformat()) is not None
    assert s.achievements.is_unlocked("ach_daily_first")


def test_default_constructor_runs():
    # 默认 storage 映射到 ~/MineSweeper，构造不应崩溃或建文件
    s = GameSession()
    s.new_game("中级")
    assert s.board.mines == 40


def test_chord_via_game(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 3, "cols": 3, "mines": 1})
    _force_layout(s.board, [[0, 1, -1],
                            [0, 1, 1],
                            [0, 0, 0]])
    res = s.reveal(1, 1)                  # 翻开数字格
    assert res["result"] == "reveal"
    s.cycle_mark(0, 2)                    # 给雷插旗
    cres = s.chord(1, 1)                  # chord 成功
    assert cres["result"] == "chord"


def test_win_with_wrong_flag_not_flawless(session):
    """全程误旗（插错旗后取消再通关）→ 不解锁「零误旗」。

    注意：胜利与「残留误旗」互斥（误旗格插旗即不会翻开 → 判不胜），
    故用「插错旗 → 取消 → 再翻开通关」构造全程误旗=1 的场景。
    """
    s, bus, storage = session
    s.new_game(custom={"rows": 3, "cols": 3, "mines": 1})
    _force_layout(s.board, [[0, 1, -1],
                            [0, 1, 1],
                            [0, 0, 0]])
    s.cycle_mark(0, 0)                    # 误旗：(0,0) 非雷 → 全程误旗 +1
    assert s.board.is_flagged(0, 0)
    s.cycle_mark(0, 0)                    # 旗 → ?
    s.cycle_mark(0, 0)                    # ? → 无（取消误旗，使该格可翻开）
    assert not s.board.is_flagged(0, 0)
    assert s.board.wrong_flag_events == 1
    for r in range(s.board.rows):
        for c in range(s.board.cols):
            if not s.board.is_mine(r, c):
                s.reveal(r, c)
    assert s.board.win
    assert s.achievements.is_unlocked("ach_first_win")
    assert not s.achievements.is_unlocked("ach_flawless")   # 全程误旗 → 不解锁


def test_undo_empty_stack_returns_false(session):
    s, bus, _ = session
    s.new_game(custom={"rows": 4, "cols": 4, "mines": 1})
    assert s.undo() is False              # 尚无快照
