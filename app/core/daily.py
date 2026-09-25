"""core/daily.py — DailyProvider（每日挑战确定性种子 RNG · 零 UI 依赖）。

S-DLY 验收（架构 §2.2 / §3.3）。

用户拍板：每日挑战 = **自由首击 + 默认中级 16×16/40**（覆盖 system-design
§2.3 推荐的固定中心方案；架构 §3.3 已落定）。

确定性保证（边界 5：RNG 纯净）：
- `seed_for(date)` → `int(YYYYMMDD)`，每日唯一、可读。
- `make_rng(date)` → `random.Random(seed)`，与全局 `random` **完全隔离**。
- 同日期 + 同首击格 → 棋盘**完全相同**（布雷逻辑在 Board，注入本 rng）。
- 首击安全由 Board.place_mines 的 3×3 禁区保证，与常局同算法。

依赖：config（DAILY_CONFIG）、标准库 random/datetime。不依赖 UI / 文件系统。
"""
import datetime
import random

from .config import DAILY_CONFIG


class DailyProvider:
    """每日挑战种子与配置提供器（静态方法集合）。"""

    @staticmethod
    def seed_for(date: datetime.date) -> int:
        """日期 → 种子（int(YYYYMMDD)）。每日唯一。"""
        return int(date.strftime("%Y%m%d"))

    @staticmethod
    def make_rng(date: datetime.date) -> random.Random:
        """返回确定性的 `random.Random(seed)`。全程不混用全局 random。"""
        return random.Random(DailyProvider.seed_for(date))

    @staticmethod
    def config() -> dict:
        """每日挑战棋盘配置（默认中级 16×16/40，用户拍板）。"""
        return dict(DAILY_CONFIG)
