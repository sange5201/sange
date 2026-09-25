"""test_board.py — Board 内核验收 + P1 数值等价性（S-BRD 验收核心）。

最关键用例：test_flood_explicit_stack_equals_recursive
  - 用一份**自包含的递归参考实现**对照显式栈 reveal 的翻开结果；
  - 覆盖 200+ 随机盘（含 30×30/250 大棋盘），验证 ADR-05「语义逐格等价」
    不破坏 P1 红线（洪水展开行为一致）。

就绪度：接口已定（§2.2 board / §3.2① 显式栈）。本文件 Sprint 1 全绿运行。
"""
import random

import pytest

from core.board import Board
from core.config import LEVELS
from core.events import EventBus, GameEvent


# ----------------------------------------------------------------------
# 递归参考实现（仅用于等价性验证，绝不进入生产代码）
# 语义与架构 §3.2① 显式栈完全一致：0 值格展开邻域，数字格不入栈。
# ----------------------------------------------------------------------
def _recursive_flood(board_arr, rows, cols, r, c, revealed):
    if not (0 <= r < rows and 0 <= c < cols):
        return
    if revealed[r][c]:
        return
    revealed[r][c] = True
    if board_arr[r][c] == 0:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                _recursive_flood(board_arr, rows, cols, r + dr, c + dc, revealed)


# ----------------------------------------------------------------------
# P1 红线 #1：洪水显式栈 ≡ 递归（等价性）
# ----------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(200))
def test_flood_explicit_stack_equals_recursive(seed):
    # 覆盖全部档位 + 重点压力大棋盘
    level_names = list(LEVELS.keys())
    level_names.remove("自定义")
    rng_pick = random.Random(seed * 7 + 13)
    name = rng_pick.choice(level_names)
    cfg = LEVELS[name]
    rng = random.Random(seed)

    b = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng)
    r, c = cfg["rows"] // 2, cfg["cols"] // 2
    b.first_click(r, c)

    # 显式栈结果
    exp = {(rr, cc) for rr in range(b.rows) for cc in range(b.cols)
           if b.revealed[rr][cc]}
    # 递归参考结果（同布局、同首击）
    ref = [[False] * b.cols for _ in range(b.rows)]
    _recursive_flood(b.board, b.rows, b.cols, r, c, ref)
    ref_set = {(rr, cc) for rr in range(b.rows) for cc in range(b.cols)
               if ref[rr][cc]}

    assert exp == ref_set, (
        f"seed={seed} level={name}: 显式栈与递归翻开集合不一致\n"
        f"仅在显式栈: {exp - ref_set}\n仅在递归: {ref_set - exp}"
    )
    # 所有翻开的格都不是雷（首击安全 + 安全洪水）
    assert all(not b.is_mine(rr, cc) for (rr, cc) in exp)
    # 首击必然展开至少 1 格（3×3 禁区保证首击为 0 值）
    assert len(exp) >= 1


# ----------------------------------------------------------------------
# P1 红线 #2：首击安全（3×3 禁区无雷）
# ----------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(50))
def test_first_click_safe_3x3(seed):
    cfg = LEVELS["中级"]
    rng = random.Random(seed)
    b = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng)
    r, c = 4, 7
    b.first_click(r, c)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            rr, cc = r + dr, c + dc
            if 0 <= rr < b.rows and 0 <= cc < b.cols:
                assert not b.is_mine(rr, cc), "首击 3×3 禁区内出现雷"


# ----------------------------------------------------------------------
# 布雷正确性：邻接计数独立重算一致 + 雷数正确
# ----------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(50))
def test_place_mines_counts_and_total(seed):
    cfg = LEVELS["高级"]
    rng = random.Random(seed)
    b = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng)
    b.first_click(0, 0)

    total = sum(1 for r in range(b.rows) for c in range(b.cols) if b.is_mine(r, c))
    assert total == b.mines

    for r in range(b.rows):
        for c in range(b.cols):
            if b.is_mine(r, c):
                continue
            expected = 0
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < b.rows and 0 <= cc < b.cols and b.is_mine(rr, cc):
                        expected += 1
            assert b.number_at(r, c) == expected


# ----------------------------------------------------------------------
# 确定性：同 seed + 同首击 → 同盘（每日挑战基础）
# ----------------------------------------------------------------------
def test_deterministic_same_seed_same_first_click():
    cfg = LEVELS["初级"]
    b1 = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=random.Random(12345))
    b2 = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=random.Random(12345))
    b1.first_click(5, 5)
    b2.first_click(5, 5)
    assert b1.board == b2.board


# ----------------------------------------------------------------------
# 踩雷：reveal 命中雷 → lose，全盘雷揭示，game_over
# ----------------------------------------------------------------------
def test_reveal_mine_triggers_loss():
    b = Board(5, 5, 3, rng=random.Random(1))
    b.first_click(0, 0)
    # 找一个雷格
    mine = next(( (r, c) for r in range(b.rows) for c in range(b.cols)
                 if b.is_mine(r, c) and not b.is_revealed(r, c) ), None)
    res = b.reveal(*mine)
    assert res["result"] == "lose"
    assert b.game_over and not b.win
    assert b.is_triggered == mine
    # 全盘雷已揭示
    assert all(b.is_revealed(r, c) for r in range(b.rows) for c in range(b.cols)
               if b.is_mine(r, c))


# ----------------------------------------------------------------------
# 标记循环：三态（question_enabled=True）与退化（=False）
# ----------------------------------------------------------------------
@pytest.mark.parametrize("qe,expected_cycle", [
    (True,  ["none", "flag", "mark", "none"]),   # 无→旗→?→无
    (False, ["none", "flag", "none"]),           # 退化 无→旗→无
])
def test_cycle_mark_states(qe, expected_cycle):
    # 用 _set_layout 避免首击洪水干扰（聚焦标记循环纯逻辑）
    b = Board(3, 3, 0, question_enabled=qe)
    _set_layout(b, [[0, 0, 0], [0, 0, 0], [0, 0, 0]])
    seq = []
    for _ in range(len(expected_cycle)):
        seq.append(
            "flag" if b.is_flagged(2, 2)
            else "mark" if b.is_marked(2, 2)
            else "none"
        )
        b.cycle_mark(2, 2)
    assert seq == expected_cycle


def test_cycle_mark_ignored_on_revealed():
    b = Board(3, 3, 0)
    _set_layout(b, [[0, 0, 0], [0, 0, 0], [0, 0, 0]])
    b.revealed[2][2] = True          # 已翻开格
    before = b.is_flagged(2, 2)
    b.cycle_mark(2, 2)               # 已翻开格忽略标记
    assert b.is_flagged(2, 2) == before


# ----------------------------------------------------------------------
# flagged 优先 / 已翻开 noop（边界 5/6）
# ----------------------------------------------------------------------
def test_reveal_ignores_flagged():
    b = Board(4, 4, 0)
    _set_layout(b, [[0] * 4 for _ in range(4)])
    b.cycle_mark(3, 3)            # 插旗
    res = b.reveal(3, 3)
    assert res["result"] == "noop"
    assert not b.is_revealed(3, 3)


# ----------------------------------------------------------------------
# chord：成功 / 条件不足 noop
# ----------------------------------------------------------------------
def _set_layout(b, layout):
    """测试辅助：手工铺盘（layout 为 -1/0-8 二维列表），跳过随机布雷。"""
    b.board = [row[:] for row in layout]
    b.mines_placed = True
    b.mines = sum(1 for row in layout for v in row if v == -1)
    b.revealed = [[False] * b.cols for _ in range(b.rows)]
    b.flagged = [[False] * b.cols for _ in range(b.rows)]
    b.marked = [[False] * b.cols for _ in range(b.rows)]


def test_chord_success():
    b = Board(3, 3, 0)
    # layout: 中心(1,1)=1 邻 1 雷(0,2)；其余 0
    _set_layout(b, [
        [0, 1, -1],
        [0, 1, 1],
        [0, 0, 0],
    ])
    b.revealed[1][1] = True          # 已翻开数字格
    b.flagged[0][2] = True           # 邻雷已插旗（旗数==1==数字）
    res = b.chord(1, 1)
    assert res["result"] == "chord"
    # 非雷邻格被翻开，被插旗的雷格保持 flagged 且不被动
    assert b.is_revealed(0, 0) and b.is_revealed(2, 0)
    assert b.is_flagged(0, 2)


def test_chord_noop_when_flags_insufficient():
    b = Board(3, 3, 0)
    _set_layout(b, [
        [0, 1, -1],
        [0, 1, 1],
        [0, 0, 0],
    ])
    b.revealed[1][1] = True          # 未插旗 → 旗数 0 ≠ 1
    res = b.chord(1, 1)
    assert res["result"] == "noop"


def test_chord_noop_on_zero_cell():
    b = Board(3, 3, 0)
    _set_layout(b, [[0, 0, 0], [0, 0, 0], [0, 0, 0]])
    res = b.chord(1, 1)              # board<=0 → noop
    assert res["result"] == "noop"


# ----------------------------------------------------------------------
# 胜利：全非雷翻开 → WIN，剩余雷自动插旗
# ----------------------------------------------------------------------
def test_check_win_flags_remaining_mines():
    b = Board(2, 2, 1)
    _set_layout(b, [
        [-1, 1],
        [1, 1],
    ])
    for (r, c) in [(0, 1), (1, 0), (1, 1)]:
        b.reveal(r, c)
    assert b.win and b.game_over
    assert b.is_flagged(0, 0)        # 胜利自动给雷插旗


# ----------------------------------------------------------------------
# 事件：WIN / LOSE / CHORD / REVEAL / FLAG 抛出（ADR-03）
# ----------------------------------------------------------------------
def _subscribe_all(bus):
    log = []
    for et in (GameEvent.WIN, GameEvent.LOSE, GameEvent.CHORD,
               GameEvent.REVEAL, GameEvent.FLAG):
        bus.subscribe(et, lambda p, et=et: log.append(et))
    return log


def test_event_flag_emitted():
    bus = EventBus()
    log = _subscribe_all(bus)
    b = Board(3, 3, 0, bus=bus)
    _set_layout(b, [[0, 0, 0], [0, 0, 0], [0, 0, 0]])
    b.cycle_mark(0, 0)
    assert GameEvent.FLAG in log


def test_events_chord_reveal_win_emitted():
    bus = EventBus()
    log = _subscribe_all(bus)
    b = Board(3, 3, 0, bus=bus)
    _set_layout(b, [
        [0, 1, -1],
        [0, 1, 1],
        [0, 0, 0],
    ])
    b.revealed[1][1] = True
    b.flagged[0][2] = True          # 仅雷格插旗：旗数 1 == 数字 1
    res = b.chord(1, 1)             # CHORD + 连锁 REVEAL + 收尾胜利 WIN
    assert res["result"] == "chord"
    assert GameEvent.CHORD in log
    assert GameEvent.REVEAL in log
    assert GameEvent.WIN in log
    assert GameEvent.LOSE not in log


# ----------------------------------------------------------------------
# P1 红线 #2：chord 连锁 / 已翻开格再 reveal 的显式栈 ≡ 递归（R-EQ-02）
# 关闭 QA CONCERNS 3：首击洪水之外的 P1 等价性守护盲区
# ----------------------------------------------------------------------
def test_chord_chain_explicit_stack_equals_recursive():
    """chord 连锁（批量 reveal + 洪水）与递归参考实现逐格等价。"""
    b = Board(3, 3, 0)
    _set_layout(b, [
        [-1, 1, 0],
        [1, 1, 0],
        [0, 0, 0],
    ])
    b.revealed[0][1] = True      # chord 目标：已翻开数字格（值 1）
    b.flagged[0][0] = True       # 邻雷插旗 → 旗数 1 == 数字 1
    res = b.chord(0, 1)
    assert res["result"] == "chord"

    # 显式栈结果（chord 触发的批量 reveal + 洪水连锁）
    exp = {(r, c) for r in range(3) for c in range(3) if b.revealed[r][c]}

    # 递归参考：初始仅 (0,1) 翻开，对 chord 的每个非旗邻格重放递归洪水
    ref = [[False] * 3 for _ in range(3)]
    ref[0][1] = True
    for (rr, cc) in [(0, 2), (1, 0), (1, 1), (1, 2)]:
        _recursive_flood(b.board, 3, 3, rr, cc, ref)
    ref_set = {(r, c) for r in range(3) for c in range(3) if ref[r][c]}

    assert exp == ref_set, (
        f"chord 连锁：显式栈与递归不一致\n"
        f"仅在显式栈: {exp - ref_set}\n仅在递归: {ref_set - exp}"
    )
    # P1：所有翻开格都不是雷；被插旗的雷格保持未翻开
    assert all(not b.is_mine(r, c) for (r, c) in exp)
    assert not b.is_revealed(0, 0)


def test_reveal_already_revealed_is_noop_equivalent():
    """已翻开格再 reveal：显式栈与递归均为 noop，翻开集合不变。"""
    b = Board(3, 3, 0)
    _set_layout(b, [
        [0, 1, -1],
        [0, 1, 1],
        [0, 0, 0],
    ])
    b.revealed[1][1] = True
    before = {(r, c) for r in range(3) for c in range(3) if b.revealed[r][c]}
    res = b.reveal(1, 1)          # 已翻开 → noop
    assert res["result"] == "noop"
    after = {(r, c) for r in range(3) for c in range(3) if b.revealed[r][c]}
    assert after == before        # 显式栈：集合不变
    # 递归参考：已翻开格直接 return，语义一致
    ref = [[False] * 3 for _ in range(3)]
    ref[1][1] = True
    _recursive_flood(b.board, 3, 3, 1, 1, ref)
    ref_set = {(r, c) for r in range(3) for c in range(3) if ref[r][c]}
    assert ref_set == before
