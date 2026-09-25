# ADR-03：逻辑/UI 解耦 + 事件总线

- **状态**：Accepted
- **日期**：Phase 3
- **作者**：程基岩（工程负责人）
- **关联**：系统设计 §1.1/§1.4、成就系统 §2.4、架构 `architecture.md` §1/§3.2③

## 上下文（Context）

需同时满足：
1. **P1 数值内核不可改**：核心玩法（布雷/洪水/chord/胜负/计时）数值与桌面版逐字节一致，且不能因为新功能（成就/每日）被污染。
2. **成就系统纯监听**：成就基于胜利/踩雷/chord 计数/计时解锁，但**核心数值层绝不能反向依赖成就模块**（否则耦合风险 + 破坏 P1）。
3. **UI 与逻辑彻底分离**：UI 重写（Kivy）不应污染纯逻辑；逻辑包须可脱离 Kivy 跑命令行/单测（概念文档 §0：本期是「逻辑复用 + UI 重写」）。

`AchievementEngine` 需要感知 `board` 的胜利/失败/chord/计时，但 `board` 不应 `import achievements`。如何用最小耦合实现？

## 决策（Decision）

**采用 `core/events.py` 的轻量 `EventBus`（发布/订阅），实现单向解耦：**
- `board` / `timer` 在关键节点 `bus.emit(GameEvent.WIN/LOSE/CHORD/REVEAL/TICK/...)`。
- `AchievementEngine` 仅 `bus.subscribe(...)` 订阅，**核心层永不 import 成就/UI 模块**。
- 依赖方向严格单向：`presentation → core → (events 为 core 内部 leaf)`；`achievements` 依赖 `events`（订阅）+ `storage`（持久化）+ `config`（阈值），**不被 `board` 依赖**。

事件类型：`WIN, LOSE, CHORD, REVEAL, FLAG, TICK, NEW_GAME, DAILY_COMPLETE`。

## 备选方案与权衡（Alternatives Considered）

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **事件总线（选中）** | 单向解耦；成就纯监听；核心数值零改动（P1 安全）；易单测（mock bus） | 需定义事件契约；调试需追事件流 | **采用** |
| 核心直接调 UI/成就回调 | 简单直接 | 核心反向依赖表现层，破坏解耦；P1 数值层被拖累；无法脱离 Kivy 单测 | 弃：违反 ADR 目标 |
| UI 每帧轮询核心状态 | 无事件契约 | 成就难精准挂钩 chord 计数/胜利瞬间；性能差；时序不精确 | 弃：不满足成就精确结算 |

## 后果（Consequences）

- **正面**：
  - 成就系统是「纯插件」——增删成就只动 `achievements.py`，核心零改，P1 红线 100% 守住。
  - `core/` 零 Kivy 依赖，可 `pytest` 脱离 UI 验证全部玩法（架构 §6.4 测试策略）。
  - 撤销机制与成就无冲突：`game_over` 后撤销禁用（系统设计 §2.2 边界 5），成就基于 `game_over` 结算，幂等（§2.4 边界 2/3）。
- **负面/约束**：
  - 必须静态断言 `core/board.py` 不 `import` `achievements`/`presentation`（写入控制清单 §5.1）。
  - 事件契约需稳定：`board` 抛出的 payload 字段（如 `WIN` 带 `level/time/flags_wrong`）一旦定下，成就侧依赖，故在 `events.py` 集中定义并注释。

## 参考（References）
- `architecture.md` §2.2（events 签名）、§3.2③（抛事件改造）、§4.2（P1 确认）
- 系统设计 §1.4（事件钩子说明）、§2.4（成就事件订阅）
- 概念文档 §6 候选 2（成就 ROI）
