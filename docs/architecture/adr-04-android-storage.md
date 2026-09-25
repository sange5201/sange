# ADR-04：Android 存储封装（内部存储 + JSON 原子写容错）

- **状态**：Accepted
- **日期**：Phase 3
- **作者**：程基岩（工程负责人）
- **关联**：系统设计 §2.5 存储系统、架构 `architecture.md` §2.2/§3.1、用户拍板（Android 内部存储）

## 上下文（Context）

需持久化 4 类数据（系统设计 §2.5 schema，`version=1`）：
- `best.json`：各难度最短通关（int 秒，封顶 999，`null`=未记录）。
- `achievements.json`：`{id:{unlocked,unlocked_at,progress}}`。
- `daily.json`：`{date_str:{best,completed}}`。
- `settings.json`：`theme / default_mark_mode / toolbar_mode / question_enabled / reduce_motion / colorblind`。

设计文档明确「**Android 内部存储具体路径由工程 Phase 3 定**」。需确定：
1. 存储位置（内部 vs 共享存储）——影响权限申请。
2. 读写契约：原子写、损坏容错、版本迁移。
3. 桌面开发期路径（本地 `python main.py` 调试）。

## 决策（Decision）

**采用 App 内部存储（app-specific，无需权限）+ 分文件 JSON + 原子写。**

- **路径**：`StorageBackend.base_dir()` ——
  - Android：`App.user_data_dir`（Kivy 封装，映射 `/data/data/<package>/files`，app-specific 内部存储，**无需 `READ/WRITE_EXTERNAL_STORAGE` 权限**，API 21+ 即免权限）。
  - 桌面开发：`os.path.expanduser("~/MineSweeper")`（沿用旧 `BEST_FILE` 习惯，便于本地调试）。
  - 用 `platform/android_storage.py` 薄封装，避免 core 直接调 Kivy（core 仍零 Kivy 依赖：路径在 `GameSession` 构造时由表现层传入或经 `platform` 解析）。
- **文件布局**：4 个独立 JSON 文件（`best/achievements/daily/settings`），便于独立读写、降低单文件损坏爆炸半径。
- **原子写**：`write` 先写 `<name>.tmp` 再 `os.replace(tmp, target)`（`os.replace` 原子重命名，POSIX/Win 均保证），防中断（切后台/崩溃）写半截损坏。
- **容错读**：`read` 包 `try/except`：文件缺失/JSON 损坏 → 回退对应默认结构（游戏继续不崩）；读时若缺字段或 `version` 低 → 用默认值补齐（向前兼容，不破坏既有解锁）。
- **生命周期**：Kivy 单线程；`App.on_pause` 强制 `storage.flush()`（架构 `main.py` `on_pause`），避免切后台丢失。

## 备选方案与权衡（Alternatives Considered）

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **内部存储 + 分文件 JSON 原子写（选中）** | 免权限；原子写防损；损坏局部化；桌面/安卓统一抽象 | 需自写薄封装与迁移逻辑 | **采用** |
| 共享存储（/sdcard/...） | 用户可用文件管理器导出 | 需申请权限（Android 10+ 分区存储更繁琐）；本期无导出需求；违反「本期不碰共享存储」（系统设计 §2.5 边界 4） | 弃：过度且需权限 |
| SQLite | 强一致、便于查询 | 本期数据极小（单值/小表），SQLite 过度工程；跨文件原子写需求弱 | 弃：ROI 不匹配 |
| 单文件大 JSON | 实现简单 | 原子写失败则全损；迁移难；读写互相阻塞 | 弃：损坏爆炸半径大 |

## 后果（Consequences）

- **正面**：零权限申请（Google Play 友好）；中断安全（原子写 + on_pause flush）；损坏不崩（容错读）；`version` 字段支持成就/设置向后兼容（系统设计 §2.4 边界 5）。
- **负面/约束**：
  - 路径解析经 `platform`，core 仍保持零 Kivy 依赖——`StorageBackend` 的具体 `user_data_dir` 取值由表现层/平台层提供，core 只接收字符串目录。
  - 作弊防护不在本期（系统设计 §2.4 边界 6）：本地 JSON 可改，成就定位「荣誉徽章」不作排行榜资格，在线期再服务端校验。

## 参考（References）
- `architecture.md` §2.2（storage 签名）、§3.1（迁移）、§5.1（契约）
- 系统设计 §2.5（storage schema 与边界 1–6）
- 用户拍板：本期用 Android 内部存储
