"""core/timer.py — GameTimer（纯逻辑 · 零 UI 依赖）。

S-TMR 验收（架构 §2.2 / §6.2 骨架）。

设计要点（B-2 已拍板：核内不依赖 Kivy）：
- core 内**不** `import kivy`；「每秒」调度由表现层（Kivy `Clock`）驱动
  `GameTimer._tick()`，或测试中直接调用 `_tick()` 作为「fake clock 注入」。
- 计时封顶 `TIMER_CAP=999`（秒，int）；`pause()` 冻结 `elapsed` 与 tick，
  `resume()` 在 `game_over` 之前恢复运行；`game_over` 后 `resume()` 无效
  （R6 / system-design §2.2 边界 5）。
- 每秒 `_tick()` 经事件总线 `emit(TICK, {elapsed})`，供 HUD 刷新与成就计时。

依赖：events（emit TICK）。不依赖任何 UI / 文件系统。
"""
from .events import EventBus, GameEvent
from .config import TIMER_CAP


class GameTimer:
    """游戏计时器。

    调度模型：表现层每秒调用一次 `_tick()`（Kivy `Clock.schedule_interval`）。
    测试可直接调用 `_tick()` 模拟秒针推进（可注入的 fake clock）。
    """

    def __init__(self, bus: EventBus):
        self.bus = bus
        self._elapsed = 0          # 已流逝秒数（内部，封顶前）
        self._running = False      # 是否计 running（pause/resume 切换）
        self.game_over = False     # 对局结束标志（resume 失效）

    # ---------------- 生命周期 ----------------
    def start(self) -> None:
        """开始/重开计时：清零并进入 running。new_game 时调用。"""
        self._running = True
        self._elapsed = 0
        self.game_over = False

    def pause(self) -> None:
        """冻结计时（如 App.on_pause）。不丢失已计秒数。"""
        self._running = False

    def resume(self) -> None:
        """恢复计时（如 App.on_resume）。game_over 后无效（防篡改纪录）。"""
        self._running = not self.game_over

    def stop(self) -> None:
        """停止计时（对局结束）。"""
        self._running = False

    # ---------------- 秒针（由表现层驱动）----------------
    def _tick(self) -> None:
        """推进一秒。由表现层 Kivy Clock 或测试 fake clock 调用。

        仅在 running 时累加；累加后 emit TICK；封顶 TIMER_CAP。
        """
        if not self._running:
            return
        self._elapsed = min(self._elapsed + 1, TIMER_CAP)
        self.bus.emit(GameEvent.TICK, {"elapsed": self._elapsed})

    # ---------------- 查询 ----------------
    @property
    def elapsed(self) -> int:
        """已流逝秒数（封顶 TIMER_CAP）。"""
        return min(self._elapsed, TIMER_CAP)
