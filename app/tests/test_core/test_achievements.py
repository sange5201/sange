"""test_achievements.py — AchievementEngine 验收（S-ACH）。

就绪度：ACHIEVEMENTS 初值表已定（system-design §2.4）；阈值 60s/20chord/50flag 初版。
事件 payload 契约待定（WIN 带 level/time/flags_wrong 等——control-checklist C-1）⚠。

本文件为就绪骨架：core.achievements 实现前由 importorskip 跳过。
"""
import pytest

pytest.importorskip("core.achievements")
from core.achievements import AchievementEngine, ACHIEVEMENTS
from core.events import EventBus, GameEvent
from core.config import TIMER_CAP


@pytest.fixture
def engine():
    bus = EventBus()
    # storage 用内存/临时桩；此处仅验证订阅与解锁逻辑
    eng = AchievementEngine(bus, storage=None)
    return bus, eng


def test_first_win_unlock(engine):
    bus, eng = engine
    bus.emit(GameEvent.WIN, {"level": "初级", "time": 30, "flags_wrong": 0})
    assert eng.is_unlocked("ach_first_win")


def test_win_unlock_idempotent(engine):
    bus, eng = engine
    for _ in range(3):
        bus.emit(GameEvent.WIN, {"level": "初级", "time": 30, "flags_wrong": 0})
    # 重复解锁不重复记录（幂等）；计数/进度稳定
    assert eng.is_unlocked("ach_first_win")
    assert eng.unlock_count("ach_first_win") == 1


def test_lightning_threshold_60s(engine):
    bus, eng = engine
    bus.emit(GameEvent.WIN, {"level": "初级", "time": 60, "flags_wrong": 0})
    assert eng.is_unlocked("ach_lightning")
    # 独立引擎验证 61s 不解锁（避免复用同一引擎触发幂等误导）
    bus2 = EventBus()
    eng2 = AchievementEngine(bus2, storage=None)
    bus2.emit(GameEvent.WIN, {"level": "初级", "time": 61, "flags_wrong": 0})
    assert not eng2.is_unlocked("ach_lightning")


def test_chord_master_threshold(engine):
    bus, eng = engine
    for _ in range(20):
        bus.emit(GameEvent.CHORD, {"count": _ + 1})
    assert eng.is_unlocked("ach_chord_master")


def test_achievement_table_has_required_ids():
    ids = {a["id"] for a in ACHIEVEMENTS}
    for rid in ("ach_first_win", "ach_rookie", "ach_expert", "ach_hell",
                "ach_lightning", "ach_chord_master", "ach_flawless",
                "ach_daily_first", "ach_flag_forest"):
        assert rid in ids


def test_level_specific_wins():
    # 入门 → rookie；专家 → expert；地狱 → hell
    for lvl, aid in (("入门", "ach_rookie"),
                     ("专家", "ach_expert"),
                     ("地狱", "ach_hell")):
        bus = EventBus()
        eng = AchievementEngine(bus, storage=None)
        bus.emit(GameEvent.WIN, {"level": lvl, "time": 30, "flags_wrong": 0})
        assert eng.is_unlocked(aid)


def test_flag_forest_threshold(engine):
    bus, eng = engine
    for _ in range(50):
        bus.emit(GameEvent.FLAG, {"r": 0, "c": 0, "flagged": True})
    assert eng.is_unlocked("ach_flag_forest")


def test_chord_without_count_field():
    bus = EventBus()
    eng = AchievementEngine(bus, storage=None)
    for _ in range(20):
        bus.emit(GameEvent.CHORD, {})          # 无 count 字段
    assert eng.is_unlocked("ach_chord_master")


def test_win_after_chords_unlocks_via_recheck(engine):
    bus, eng = engine
    for _ in range(20):
        bus.emit(GameEvent.CHORD, {"count": _ + 1})
    bus.emit(GameEvent.WIN, {"level": "初级", "time": 30, "flags_wrong": 0})
    assert eng.is_unlocked("ach_chord_master")


def test_engine_with_storage_persists(tmp_path):
    from core.storage import JsonStorage
    storage = JsonStorage(str(tmp_path))
    bus = EventBus()
    eng = AchievementEngine(bus, storage=storage)
    bus.emit(GameEvent.WIN, {"level": "初级", "time": 30, "flags_wrong": 0})
    assert eng.is_unlocked("ach_first_win")
    assert storage.is_unlocked("ach_first_win")      # 持久化
    eng2 = AchievementEngine(EventBus(), storage=storage)
    assert eng2.is_unlocked("ach_first_win")          # 重载保留
    assert eng2.unlock_count("ach_first_win") == 1


def test_lose_event_no_crash(engine):
    bus, eng = engine
    bus.emit(GameEvent.LOSE, {"level": "初级", "triggered": (0, 0)})
    assert not eng.is_unlocked("ach_first_win")
