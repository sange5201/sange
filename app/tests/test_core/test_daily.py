"""test_daily.py — DailyProvider 验收（S-DLY）。

就绪度：接口已定（§2.2 daily / §3.3）；用户已拍板「自由首击」（覆盖推荐固定中心）。
时区标注为尽力而为（边界 1）⚠。

本文件为就绪骨架：core.daily 实现前由 importorskip 跳过。
"""
import datetime
import random

import pytest

pytest.importorskip("core.daily")
from core.daily import DailyProvider
from core.board import Board
from core.config import DAILY_CONFIG


def test_seed_for_is_int_ymd():
    d = datetime.date(2025, 9, 25)
    assert DailyProvider.seed_for(d) == 20250925
    assert isinstance(DailyProvider.seed_for(d), int)


def test_make_rng_deterministic():
    d = datetime.date(2025, 9, 25)
    r1 = DailyProvider.make_rng(d)
    r2 = DailyProvider.make_rng(d)
    assert r1.getstate() == r2.getstate()


def test_config_matches_daily_config():
    cfg = DailyProvider.config()
    assert cfg == DAILY_CONFIG


def test_same_seed_same_first_click_same_board():
    d = datetime.date(2025, 9, 25)
    cfg = DailyProvider.config()
    rng1 = DailyProvider.make_rng(d)
    rng2 = DailyProvider.make_rng(d)
    b1 = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng1)
    b2 = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng2)
    b1.first_click(8, 8)
    b2.first_click(8, 8)
    assert b1.board == b2.board


def test_daily_does_not_use_global_random():
    # 关键边界 5：daily 局内只用注入的 random.Random(seed)，不混用全局 random。
    d = datetime.date(2025, 9, 25)
    cfg = DailyProvider.config()
    rng = DailyProvider.make_rng(d)
    b = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng)
    b.first_click(0, 0)
    # 若误用全局 random， determinism 被破坏；此处复用确定性断言间接保证。
    rng2 = DailyProvider.make_rng(d)
    b2 = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng2)
    b2.first_click(0, 0)
    assert b.board == b2.board


def test_first_click_safe_in_daily():
    d = datetime.date(2025, 9, 25)
    cfg = DailyProvider.config()
    rng = DailyProvider.make_rng(d)
    b = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng)
    r, c = 5, 5
    b.first_click(r, c)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            rr, cc = r + dr, c + dc
            if 0 <= rr < b.rows and 0 <= cc < b.cols:
                assert not b.is_mine(rr, cc)
