"""test_events.py — EventBus 单向契约（S-EVT 验收 + ADR-03 断言）。

就绪度：接口已定（§2.2 events）。本文件 Sprint 1 即可全绿运行。
"""
import pytest
from core.events import EventBus, GameEvent


def test_subscribe_returns_unique_ids():
    bus = EventBus()
    a = bus.subscribe(GameEvent.WIN, lambda p: None)
    b = bus.subscribe(GameEvent.WIN, lambda p: None)
    assert a != b
    assert bus.handler_count(GameEvent.WIN) == 2


def test_emit_delivers_payload_to_all_subscribers():
    bus = EventBus()
    received = []
    bus.subscribe(GameEvent.WIN, lambda p: received.append(("x", p)))
    bus.subscribe(GameEvent.WIN, lambda p: received.append(("y", p)))
    bus.emit(GameEvent.WIN, {"level": "初级", "time": 12})
    assert len(received) == 2
    assert all(r[1]["level"] == "初级" for r in received)


def test_clear_removes_handlers():
    bus = EventBus()
    bus.subscribe(GameEvent.LOSE, lambda p: None)
    bus.clear()
    assert bus.handler_count(GameEvent.LOSE) == 0


def test_handler_exception_is_isolated():
    bus = EventBus()
    good = []
    bus.subscribe(GameEvent.TICK, lambda p: good.append(p))
    bus.subscribe(GameEvent.TICK, lambda p: 1 / 0)  # 故意抛异常
    bus.emit(GameEvent.TICK, {"elapsed": 5})
    assert good == [{"elapsed": 5}]   # 异常订阅者不阻断其他订阅者


def test_game_event_constants_present():
    for name in ("WIN", "LOSE", "CHORD", "REVEAL", "FLAG",
                 "TICK", "NEW_GAME", "DAILY_COMPLETE"):
        assert hasattr(GameEvent, name)


# ADR-03 静态契约：事件类型均为字符串（可读 / 可序列化）
@pytest.mark.parametrize("val", [
    GameEvent.WIN, GameEvent.LOSE, GameEvent.CHORD, GameEvent.REVEAL,
    GameEvent.FLAG, GameEvent.TICK, GameEvent.NEW_GAME, GameEvent.DAILY_COMPLETE,
])
def test_event_values_are_strings(val):
    assert isinstance(val, str)
