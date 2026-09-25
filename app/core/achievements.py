"""core/achievements.py — AchievementEngine（成就引擎 · 零 UI 依赖）。

S-ACH 验收（架构 §2.2 / system-design §2.4）。

设计要点（ADR-03：核心不 import 成就，成就纯订阅）：
- 仅经事件总线订阅 WIN/LOSE/CHORD/TICK/DAILY_COMPLETE/FLAG/NEW_GAME。
- 9 条成就（初值表），阈值沿用初值：闪电 ≤60s / 连开大师 chord≥20 / 旗帜如林 插旗≥50。
- 解锁**幂等**：已解锁不重复写（unlock_count 仅在首次转变时 +1）。
- game_over 后撤销禁用（由 board/game 保证不调用），成就基于结算事件，无冲突。
- 成就持久化走 storage（可为 None → 仅内存，便于测试）。
- schema 带 version（见 storage）；新增成就只追加 id，旧状态保留。

依赖：events（订阅）、config（阈值初值由本文件定义）、storage（可选持久化）。不依赖 UI。
"""
import datetime

from .events import EventBus, GameEvent

# 阈值初值（system-design §2.4；Phase 3 平衡微调点为 C-1，本期沿用）
LIGHTNING_SECONDS = 60
CHORD_MASTER_COUNT = 20
FLAG_FOREST_COUNT = 50

# 9 条成就（id/name/condition/category/threshold）
ACHIEVEMENTS = [
    {"id": "ach_first_win",   "name": "初次通关", "condition": "任意难度胜利 1 次",        "category": "累计", "threshold": None},
    {"id": "ach_rookie",      "name": "入门通关", "condition": "胜利「入门」",            "category": "单局", "threshold": None},
    {"id": "ach_expert",      "name": "专家征服", "condition": "胜利「专家」",            "category": "单局", "threshold": None},
    {"id": "ach_hell",        "name": "地狱征服", "condition": "胜利「地狱」",            "category": "单局", "threshold": None},
    {"id": "ach_lightning",   "name": "闪电思维", "condition": f"任意胜利 ≤ {LIGHTNING_SECONDS}s", "category": "单局", "threshold": LIGHTNING_SECONDS},
    {"id": "ach_chord_master","name": "连开大师", "condition": f"单局 chord ≥ {CHORD_MASTER_COUNT} 次", "category": "单局", "threshold": CHORD_MASTER_COUNT},
    {"id": "ach_flawless",    "name": "零误旗",   "condition": "胜利且全程误旗==0（从未插错旗）", "category": "单局", "threshold": 0},
    {"id": "ach_daily_first", "name": "每日首胜", "condition": "完成当日每日挑战",         "category": "单局", "threshold": None},
    {"id": "ach_flag_forest", "name": "旗帜如林", "condition": f"单局插旗 ≥ {FLAG_FOREST_COUNT}", "category": "单局", "threshold": FLAG_FOREST_COUNT},
]


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


class AchievementEngine:
    """成就引擎：订阅核心事件，评估并持久化解锁。"""

    def __init__(self, bus: EventBus, storage=None):
        self.bus = bus
        self.storage = storage
        self._state = self._default_state()
        if storage is not None:
            self._load_state(storage)
        # 单局累计计数器（NEW_GAME 时清零）
        self._session_flags = 0
        self._session_chords = 0
        self._subscribe()

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    @staticmethod
    def _default_state():
        return {a["id"]: {"unlocked": False, "unlocked_at": None,
                          "progress": 0, "_unlock_count": 0}
                for a in ACHIEVEMENTS}

    def _load_state(self, storage) -> None:
        """从持久化载入已解锁状态（向前兼容；已解锁记为 1 次基准）。"""
        data = storage.get_achievements()
        for aid, rec in data.items():
            if aid in self._state:
                st = self._state[aid]
                st["unlocked"] = bool(rec.get("unlocked", False))
                st["unlocked_at"] = rec.get("unlocked_at")
                st["progress"] = rec.get("progress", 0)
                if st["unlocked"]:
                    st["_unlock_count"] = 1

    def is_unlocked(self, aid: str) -> bool:
        return self._state.get(aid, {}).get("unlocked", False)

    def unlock_count(self, aid: str) -> int:
        """该成就实际「新解锁」次数（幂等基准，重复解锁不累计）。"""
        return self._state.get(aid, {}).get("_unlock_count", 0)

    def _unlock(self, aid: str, progress: int = 0) -> None:
        st = self._state.get(aid)
        if st is None:
            return
        if not st["unlocked"]:
            st["unlocked"] = True
            st["unlocked_at"] = _now_iso()
            st["_unlock_count"] += 1          # 仅首次转变计数（幂等）
        if progress:
            st["progress"] = max(st["progress"], progress)
        if self.storage is not None:
            self.storage.unlock(aid, st["progress"])

    # ------------------------------------------------------------------
    # 事件订阅
    # ------------------------------------------------------------------
    def _subscribe(self) -> None:
        self.bus.subscribe(GameEvent.WIN, self._on_win)
        self.bus.subscribe(GameEvent.LOSE, self._on_lose)
        self.bus.subscribe(GameEvent.CHORD, self._on_chord)
        self.bus.subscribe(GameEvent.FLAG, self._on_flag)
        self.bus.subscribe(GameEvent.NEW_GAME, self._on_new_game)
        self.bus.subscribe(GameEvent.DAILY_COMPLETE, self._on_daily_complete)
        self.bus.subscribe(GameEvent.TICK, self._on_tick)

    def _on_win(self, payload) -> None:
        # 仅处理「真实胜利」：带 level 的富 WIN（由 GameSession 发出）。
        # board 内部发出的空 WIN {} 不含 level，忽略，避免误解锁。
        if not isinstance(payload, dict) or "level" not in payload:
            return
        self._unlock("ach_first_win")
        level = payload.get("level")
        if level == "入门":
            self._unlock("ach_rookie")
        elif level == "专家":
            self._unlock("ach_expert")
        elif level == "地狱":
            self._unlock("ach_hell")
        if payload.get("time", 9999) <= LIGHTNING_SECONDS:
            self._unlock("ach_lightning")
        if payload.get("flags_wrong", 0) == 0:
            self._unlock("ach_flawless")
        # 单局累计型：收尾再校验一次（含本局 chord/flag 累计）
        if self._session_chords >= CHORD_MASTER_COUNT:
            self._unlock("ach_chord_master", self._session_chords)
        if self._session_flags >= FLAG_FOREST_COUNT:
            self._unlock("ach_flag_forest", self._session_flags)

    def _on_chord(self, payload) -> None:
        cnt = payload.get("count") if isinstance(payload, dict) else None
        if cnt is None:
            self._session_chords += 1
        else:
            self._session_chords = max(self._session_chords, cnt)
        if self._session_chords >= CHORD_MASTER_COUNT:
            self._unlock("ach_chord_master", self._session_chords)

    def _on_flag(self, payload) -> None:
        flagged = payload.get("flagged") if isinstance(payload, dict) else False
        if flagged:
            self._session_flags += 1
        if self._session_flags >= FLAG_FOREST_COUNT:
            self._unlock("ach_flag_forest", self._session_flags)

    def _on_new_game(self, payload) -> None:
        # 新局清零单局累计计数器（边界 5/7）
        self._session_flags = 0
        self._session_chords = 0

    def _on_daily_complete(self, payload) -> None:
        self._unlock("ach_daily_first")

    def _on_lose(self, payload) -> None:
        # 无负向成就；保留订阅以兑现 AC（订阅即契约）。
        pass

    def _on_tick(self, payload) -> None:
        # 订阅以兑现 AC；计时类成就已由 WIN.time 评估。
        pass
