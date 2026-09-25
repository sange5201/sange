"""test_storage.py — Storage / JsonStorage / StorageBackend 验收（S-STOR）。

就绪度：4 类 JSON schema 已定（version=1，system-design §2.5）；原子写/容错/迁移已定。
具体「迁移补字段逻辑」待实现落地（control-checklist D-1）⚠。

本文件为就绪骨架：core.storage 实现前由 importorskip 跳过。
"""
import json
import os

import pytest

pytest.importorskip("core.storage")
from core.storage import JsonStorage, StorageBackend


@pytest.fixture
def tmp_storage(tmp_path):
    return JsonStorage(str(tmp_path))


def test_atomic_write_no_partial_file(tmp_storage):
    tmp_storage._write_json("best", {"version": 1, "best": {"初级": 42}})
    # 目标文件存在且为合法 JSON；无残留 .tmp
    data = tmp_storage._read_json("best", {"version": 1, "best": {}})
    assert data["best"]["初级"] == 42
    leftover = [f for f in os.listdir(tmp_storage.base_dir) if f.endswith(".tmp")]
    assert leftover == []


def test_corrupt_file_falls_back_to_default(tmp_storage):
    path = os.path.join(tmp_storage.base_dir, "best.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ this is not json ")
    data = tmp_storage._read_json("best", {"version": 1, "best": {}})
    assert data == {"version": 1, "best": {}}   # 回退默认，不崩


def test_missing_file_falls_back_to_default(tmp_storage):
    data = tmp_storage._read_json("settings", {"version": 1, "theme": "light"})
    assert data["theme"] == "light"


def test_version_migration_adds_missing_fields(tmp_storage):
    # 写入低版本（缺字段），读时应补默认值（向前兼容）
    path = os.path.join(tmp_storage.base_dir, "settings.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "theme": "dark"}, f)
    data = tmp_storage._read_json(
        "settings",
        {"version": 1, "theme": "light", "question_enabled": True,
         "reduce_motion": False, "colorblind": False})
    assert data["question_enabled"] is True   # 缺失字段补齐


def test_base_dir_returns_string():
    assert isinstance(StorageBackend.base_dir(), str)


# ----------------------------------------------------------------------
# 高层访问器（best / achievements / daily / settings / save-load）
# ----------------------------------------------------------------------
def test_best_min_semantics(tmp_storage):
    tmp_storage.set_best("初级", 100)
    tmp_storage.set_best("初级", 50)
    tmp_storage.set_best("初级", 80)        # 较差，不覆盖
    assert tmp_storage.get_best("初级") == 50
    assert tmp_storage.get_best("简单") is None


def test_achievements_persist_and_query(tmp_storage):
    tmp_storage.unlock("ach_first_win", 5)
    assert tmp_storage.is_unlocked("ach_first_win")
    rec = tmp_storage.get_achievements()["ach_first_win"]
    assert rec["unlocked"] is True and rec["progress"] == 5
    # 重复 unlock 幂等（unlocked_at 不回退为 None）
    tmp_storage.unlock("ach_first_win", 9)
    assert tmp_storage.get_achievements()["ach_first_win"]["progress"] == 9


def test_daily_best_and_completed(tmp_storage):
    tmp_storage.set_daily_best("2025-09-25", 120)
    tmp_storage.set_daily_best("2025-09-25", 90)   # 更优
    assert tmp_storage.get_daily_best("2025-09-25") == 90
    tmp_storage.set_daily_completed("2025-09-25", True)
    assert tmp_storage.get_daily_completed("2025-09-25") is True
    assert tmp_storage.get_daily_best("2025-09-26") is None


def test_settings_get_set(tmp_storage):
    tmp_storage.set_setting("theme", "dark")
    assert tmp_storage.get_setting("theme") == "dark"
    assert tmp_storage.get_setting("question_enabled", True) is True  # 默认


def test_save_and_load_roundtrip(tmp_storage):
    tmp_storage.set_best("中级", 42)
    tmp_storage.save()
    assert tmp_storage.get_best("中级") == 42
    tmp_storage.load()
    assert tmp_storage.get_best("中级") == 42


def test_migrate_non_dict_falls_back(tmp_storage):
    import json
    with open(os.path.join(tmp_storage.base_dir, "settings.json"), "w",
              encoding="utf-8") as f:
        json.dump([1, 2, 3], f)              # 非 dict → 回退默认
    data = tmp_storage.get_settings()
    assert data["theme"] == "light"


def test_storage_backend_override():
    StorageBackend.set_base_dir("/tmp/ms_override_test")
    try:
        assert StorageBackend.base_dir() == "/tmp/ms_override_test"
    finally:
        StorageBackend._override = None       # 还原，避免影响其他用例
