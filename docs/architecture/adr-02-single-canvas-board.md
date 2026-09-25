# ADR-02：单 Canvas / 单 Widget 棋盘重绘策略

- **状态**：Accepted
- **日期**：Phase 3
- **作者**：程基岩（工程负责人）
- **关联**：风险 R3（Kivy 大棋盘性能）、美术圣经 §9.3 渲染管线、架构 `architecture.md` §1/§5.2

## 上下文（Context）

最高难度「地狱」为 30×30 = **900 格**。若每格一个独立 Kivy `Widget`（Tkinter 版即如此：`new_game` 里 `grid` 里塞 900 个 `Canvas`），会带来：

- 900 个 Widget 的布局/树遍历/触摸分发开销，单格状态变更触发整树重排。
- 触屏拖动/洪水展开时帧率掉到不可接受（概念文档 R3：卡顿/掉帧）。
- Kivy 虽比 Tkinter 轻，但 900 个带 `Canvas` 的 Widget 仍超出中端安卓性能预算（美术圣经 §9.3：单屏绘制调用 <2000，但 900 Widget 的固有开销远超绘制指令本身）。

目标：在保持「每格 bevel/图标程序化绘制」的前提下，把渲染开销压到仅与**变更格**和**可见视口**相关。

## 决策（Decision）

**采用单个 `BoardWidget`（一个 `Widget` + 一块 `Canvas`），所有格子用 Canvas 指令绘制；状态变更时仅重绘 `changed` 格，洪水展开批量节流级联。** 大棋盘（如 30×30）时把 `BoardWidget` 置于 `ScrollView` 内，仅可见视口参与绘制（懒渲染）。

- 维护 `cell_groups: dict[(r,c), InstructionGroup]`（或脏列表 `dirty: set`），`refresh_cell(r,c)` 仅重建该格指令；`refresh_all` 重建整块。
- 洪水展开：core 返回 `changed` 列表 → 表现层把变更格批量入 `dirty`，用 `Clock.schedule` 节流（每格 +20ms，总 ≤400ms，美术圣经 §7），避免一次性重绘 900 格。
- 不用 900 独立 Widget；`on_touch_*` 在 `BoardWidget` 上集中分发（由 `touch/interaction.py` 计算 `(r,c)` = `floor(local_y/cell_dp)` 等）。

## 备选方案与权衡（Alternatives Considered）

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **单 Widget + 单 Canvas（选中）** | 零 Widget 树开销；增量重绘仅变更格；ScrollView 懒渲染天然适配大棋盘；与美术圣经程序化绘制一致 | 需自行实现格→坐标命中与脏重绘逻辑（一次性成本） | **采用** |
| 900 个独立 Widget（Tkinter 移植） | 移植最简单，每格自带 Canvas | R3 性能灾难；洪水全量重绘卡顿；触摸分发慢 | 弃：直接触发 R3 |
| GPU/Shader 全屏绘制 | 极致性能 | 过度工程；像素 bevel/图标的程序化逻辑用 shader 重写成本高、难维护 | 弃：ROI 不匹配本期 |

## 后果（Consequences）

- **正面**：中端安卓 60fps 可达；绘制调用随棋盘尺寸仅受可见视口约束；`refresh_cell` 与 `minesweeper.py` 语义对齐（原 `refresh_cell` 即单格重绘），迁移平滑。
- **负面/约束**：
  - `BoardWidget` 需自行处理坐标→格映射与脏重绘缓存；这是本期实现重点之一。
  - `cell_dp` 计算（美术圣经 §4.1）须在 `BoardWidget.size` 变化时重算；`<44dp` 时切 `ScrollView` + `pinch-zoom`（R2），但仍是单 Canvas，不退回多 Widget。
  - 屏幕旋转：重算 `cell_dp` 重建布局，**不重置对局状态**（架构 §2.2 UI 边界 5）。

## 参考（References）
- `architecture.md` §2.2（board_widget 依赖）、§5.2（Kivy 结构）、§6.1（目录）
- 美术圣经 §9.3（渲染管线预算）、§4.1（cell_dp 计算）、§7（动效级联）
- 概念文档 §7 R3
