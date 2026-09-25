"""core/events.py — 轻量事件总线 + 事件类型（Leaf，无内部依赖）。

ADR-03：单向解耦。core 逻辑层（board/timer）emit，成就纯 subscribe；
核心层永不 import achievements / presentation。
依赖方向：presentation → core → events（events 为 core 内部 leaf）。
"""


class GameEvent:
    """事件类型常量（字符串，便于 JSON / 调试可读）。"""
    WIN = "win"
    LOSE = "lose"
    CHORD = "chord"
    REVEAL = "reveal"
    FLAG = "flag"
    TICK = "tick"
    NEW_GAME = "new_game"
    DAILY_COMPLETE = "daily_complete"


class EventBus:
    """极简发布/订阅总线。handler 签名为 callable(payload)。

    设计要点（ADR-03）：
    - subscribe 返回 handler id（int），用于未来 unsubscribe；
    - emit 对订阅者异常做隔离，单点失败不阻断整条事件流；
    - clear 用于测试隔离 / 会话重置。
    """

    def __init__(self):
        self._handlers = {}      # etype -> {id: handler}
        self._next_id = 1

    def subscribe(self, etype: str, handler) -> int:
        hid = self._next_id
        self._next_id += 1
        self._handlers.setdefault(etype, {})[hid] = handler
        return hid

    def unsubscribe(self, etype: str, hid: int) -> None:
        self._handlers.get(etype, {}).pop(hid, None)

    def emit(self, etype: str, payload=None) -> None:
        for hid, handler in list(self._handlers.get(etype, {}).items()):
            try:
                handler(payload)
            except Exception:
                # 事件流隔离：单个订阅者异常不影响其他订阅者（含成就结算）
                # 生产环境建议在此处上报日志；脚手架阶段静默以保测试稳定。
                pass

    def clear(self) -> None:
        self._handlers.clear()

    # 便捷查询（测试/调试用）
    def handler_count(self, etype: str) -> int:
        return len(self._handlers.get(etype, {}))
