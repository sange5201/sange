"""test_timer.py — GameTimer 验收（S-TMR）。

就绪度：接口已定（§2.2 timer / §6.2 骨架），但「秒级调度归属」待定
（core 内线程 vs 表现层 Clock 驱动 _tick）——见 control-checklist B-2。

本文件为就绪骨架：core.timer 实现前由 importorskip 跳过，不阻断 Sprint 1 绿灯。
"""
import pytest

pytest.importorskip("core.timer")  # 未实现时整模块跳过
from core.timer import GameTimer
from core.events import EventBus, GameEvent
from core.config import TIMER_CAP


def test_start_sets_running_and_zero():
    bus = EventBus()
    t = GameTimer(bus)
    t.start()
    assert t._running is True
    assert t.elapsed == 0


def test_pause_freezes_elapsed():
    bus = EventBus()
    t = GameTimer(bus)
    t.start()
    t._tick()            # +1
    t.pause()
    assert t._running is False
    t._tick()            # pause 后不应累加
    assert t.elapsed == 1


def test_resume_restores_running():
    bus = EventBus()
    t = GameTimer(bus)
    t.start(); t._tick(); t.pause()
    t.resume()
    assert t._running is True
    t._tick()
    assert t.elapsed == 2


def test_elapsed_caps_at_999():
    bus = EventBus()
    t = GameTimer(bus)
    t.start()
    for _ in range(TIMER_CAP + 50):
        t._tick()
    assert t.elapsed == TIMER_CAP


def test_tick_emits_tick_event():
    bus = EventBus()
    ticks = []
    bus.subscribe(GameEvent.TICK, lambda p: ticks.append(p))
    t = GameTimer(bus)
    t.start()
    t._tick()
    assert len(ticks) == 1
    assert ticks[0]["elapsed"] == 1


def test_resume_after_game_over_noop():
    bus = EventBus()
    t = GameTimer(bus)
    t.start()
    t.game_over = True
    t.resume()
    assert t._running is False
