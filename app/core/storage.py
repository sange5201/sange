"""core/storage.py — Storage / JsonStorage / StorageBackend（本地 JSON 持久化 · 零 UI 依赖）。

S-STOR 验收（架构 §2.2 / ADR-04；system-design §2.5 schema）。

设计要点：
- 4 类 JSON 各自原子写（`.tmp` + `os.replace`），防中断损坏。
- 文件缺失 / 损坏 → 回退默认结构（不崩）；读时按默认补缺失字段（向前兼容迁移）。
- `StorageBackend.base_dir()`：桌面映射 `~/MineSweeper`（便于调试）；Android 由
  platform 层经 `set_base_dir(app.user_data_dir)` 注入，core 永不 import kivy（ADR-03/04）。
- 每次变更访问器即原子落盘；`save()` 为生命周期（on_pause）幂等 durability flush。

依赖：标准库 os/json/copy/datetime/abc；config（TIMER_CAP）。不依赖 UI / kivy。
"""
import abc
import copy
import datetime
import json
import os

from .config import TIMER_CAP


def _now_iso() -> str:
    """当前 ISO8601 时间戳（成就解锁时间）。"""
    return datetime.datetime.now().isoformat(timespec="seconds")


class Storage(abc.ABC):
    """持久化抽象接口（system-design §2.5）。

    子类实现 best/achievements/daily/settings 四类访问器 + 原子读写。
    """

    base_dir: str

    @abc.abstractmethod
    def load(self) -> None:
        """启动预热：读全部命名空间，触发容错/迁移。"""

    @abc.abstractmethod
    def save(self) -> None:
        """生命周期 flush（如 App.on_pause）。"""

    @abc.abstractmethod
    def get_best(self, level: str):
        """返回该难度最佳用时（秒，int）；未记录为 None。"""

    @abc.abstractmethod
    def set_best(self, level: str, t: int) -> None:
        """记录最佳用时（取最小值，封顶 TIMER_CAP）。"""

    @abc.abstractmethod
    def get_achievements(self) -> dict:
        """返回 {ach_id: {unlocked, unlocked_at, progress}}。"""

    @abc.abstractmethod
    def unlock(self, ach_id: str, progress: int = 0) -> None:
        """解锁成就（幂等：已解锁不重复写时间）。"""

    @abc.abstractmethod
    def get_daily_best(self, date_str: str):
        """返回该日期每日最佳用时；未记录为 None。"""

    @abc.abstractmethod
    def set_daily_best(self, date_str: str, t: int) -> None:
        """记录每日最佳（取最小值，封顶 TIMER_CAP）。"""

    @abc.abstractmethod
    def get_daily_completed(self, date_str: str) -> bool:
        """该日期每日挑战是否已完成。"""

    @abc.abstractmethod
    def set_daily_completed(self, date_str: str, completed: bool) -> None:
        """标记每日挑战完成态。"""

    @abc.abstractmethod
    def get_settings(self) -> dict:
        """返回全部设置字典。"""

    @abc.abstractmethod
    def set_setting(self, key: str, value) -> None:
        """写入单条设置。"""


class JsonStorage(Storage):
    """基于 JSON 文件的 Storage 实现（原子写 + 容错 + 迁移）。"""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    # ------------------------------------------------------------------
    # 原子读写原语（测试直接调用）
    # ------------------------------------------------------------------
    def _write_json(self, name: str, data: dict) -> None:
        """原子写：先写 .tmp，再 os.replace 到目标（无残留 .tmp）。"""
        os.makedirs(self.base_dir, exist_ok=True)
        target = os.path.join(self.base_dir, name + ".json")
        tmp = os.path.join(self.base_dir, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, target)   # 跨平台原子替换

    def _read_json(self, name: str, default: dict) -> dict:
        """读 JSON；缺失/损坏 → 回退默认；读后按默认补缺失字段（迁移）。"""
        target = os.path.join(self.base_dir, name + ".json")
        if not os.path.exists(target):
            return copy.deepcopy(default)
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError):
            return copy.deepcopy(default)
        if not isinstance(data, dict):
            return copy.deepcopy(default)
        return self._migrate(data, default)

    @staticmethod
    def _migrate(loaded: dict, default: dict) -> dict:
        """向前兼容迁移：以 default 为权威结构，叠加 loaded 的已知键；
        缺失键由 default 补齐（含嵌套 dict 递归）。"""
        if not isinstance(loaded, dict) or not isinstance(default, dict):
            return loaded if isinstance(loaded, dict) else copy.deepcopy(default)
        merged = copy.deepcopy(default)
        for k, v in loaded.items():
            if (k in merged and isinstance(merged[k], dict)
                    and isinstance(v, dict)):
                merged[k] = JsonStorage._migrate(v, merged[k])
            else:
                merged[k] = copy.deepcopy(v)
        return merged

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def _namespaces(self):
        """(命名空间名, 默认 schema 工厂) 列表。"""
        return (
            ("best", self._default_best),
            ("achievements", self._default_achievements),
            ("daily", self._default_daily),
            ("settings", self._default_settings),
        )

    def load(self) -> None:
        for name, factory in self._namespaces():
            self._read_json(name, factory())   # 触发容错 + 迁移

    def save(self) -> None:
        # 幂等 durability flush：重新当前磁盘态再原子写一次
        for name, factory in self._namespaces():
            self._write_json(name, self._read_json(name, factory()))

    # ------------------------------------------------------------------
    # 默认 schema（version=1，system-design §2.5）
    # ------------------------------------------------------------------
    @staticmethod
    def _default_best():
        return {"version": 1, "best": {}}

    @staticmethod
    def _default_achievements():
        return {"version": 1, "achievements": {}}

    @staticmethod
    def _default_daily():
        return {"version": 1, "daily": {}}

    @staticmethod
    def _default_settings():
        # toolbar_mode 默认 True（UX 规格 T1 建议，落实「两者都提供」）
        # display_scale 为新增待定字段，预留默认 "standard"
        return {
            "version": 1,
            "theme": "light",
            "default_mark_mode": "longpress",
            "toolbar_mode": True,
            "question_enabled": True,
            "reduce_motion": False,
            "colorblind": False,
            "display_scale": "standard",
        }

    # ------------------------------------------------------------------
    # best 访问器
    # ------------------------------------------------------------------
    def get_best(self, level: str):
        data = self._read_json("best", self._default_best())
        return data["best"].get(level)

    def set_best(self, level: str, t: int) -> None:
        data = self._read_json("best", self._default_best())
        cur = data["best"].get(level)
        if cur is None or t < cur:
            data["best"][level] = min(int(t), TIMER_CAP)
            self._write_json("best", data)

    # ------------------------------------------------------------------
    # achievements 访问器
    # ------------------------------------------------------------------
    def get_achievements(self) -> dict:
        data = self._read_json("achievements", self._default_achievements())
        return data.get("achievements", {})

    def unlock(self, ach_id: str, progress: int = 0) -> None:
        data = self._read_json("achievements", self._default_achievements())
        rec = data["achievements"].get(
            ach_id, {"unlocked": False, "unlocked_at": None, "progress": 0})
        rec["unlocked"] = True
        if rec.get("unlocked_at") is None:
            rec["unlocked_at"] = _now_iso()
        rec["progress"] = progress
        data["achievements"][ach_id] = rec
        self._write_json("achievements", data)

    def is_unlocked(self, ach_id: str) -> bool:
        return self.get_achievements().get(ach_id, {}).get("unlocked", False)

    # ------------------------------------------------------------------
    # daily 访问器
    # ------------------------------------------------------------------
    def get_daily_best(self, date_str: str):
        data = self._read_json("daily", self._default_daily())
        return data.get("daily", {}).get(date_str, {}).get("best")

    def set_daily_best(self, date_str: str, t: int) -> None:
        data = self._read_json("daily", self._default_daily())
        rec = data.setdefault("daily", {}).setdefault(
            date_str, {"best": None, "completed": False})
        cur = rec.get("best")
        if cur is None or t < cur:
            rec["best"] = min(int(t), TIMER_CAP)
        self._write_json("daily", data)

    def get_daily_completed(self, date_str: str) -> bool:
        data = self._read_json("daily", self._default_daily())
        return bool(data.get("daily", {}).get(date_str, {}).get("completed", False))

    def set_daily_completed(self, date_str: str, completed: bool) -> None:
        data = self._read_json("daily", self._default_daily())
        rec = data.setdefault("daily", {}).setdefault(
            date_str, {"best": None, "completed": False})
        rec["completed"] = bool(completed)
        self._write_json("daily", data)

    # ------------------------------------------------------------------
    # settings 访问器
    # ------------------------------------------------------------------
    def get_settings(self) -> dict:
        return self._read_json("settings", self._default_settings())

    def get_setting(self, key: str, default=None):
        return self.get_settings().get(key, default)

    def set_setting(self, key: str, value) -> None:
        data = self._read_json("settings", self._default_settings())
        data[key] = value
        self._write_json("settings", data)


class StorageBackend:
    """解析平台存储根目录（ADR-04）。core 零 Kivy 依赖。

    - 桌面：返回 `~/MineSweeper`（便于调试）。
    - Android：由 platform 层调用 `set_base_dir(app.user_data_dir)` 注入，
      本类不 import kivy，保持 core 纯逻辑（ADR-03）。
    """

    _override = None

    @staticmethod
    def base_dir() -> str:
        if StorageBackend._override:
            return StorageBackend._override
        return os.path.join(os.path.expanduser("~"), "MineSweeper")

    @staticmethod
    def set_base_dir(path: str) -> None:
        """注入平台特定根目录（如 Android app.user_data_dir）。"""
        StorageBackend._override = path
