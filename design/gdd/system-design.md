# 扫雷 · 安卓版 系统设计文档（Phase 2 · Lean）

- **阶段**：Phase 2 系统设计（lean 评审，结论先行、可直接落地）
- **技术栈**：Python + Kivy（打包 apk，本期聚焦 Android）
- **作者**：文策渊（设计策略师 / 设计+叙事）
- **评审强度**：lean（合并为单文档，保留逐系统八节结构）
- **上游真源**：`minesweeper.py`（`LEVELS`/`THEMES`/核心逻辑）、概念文档、美术圣经（移动端）
- **配套代码**：`E:/youxi/minesweeper/minesweeper.py`（24KB，含完整注释）

---

## 0. 结论先行（TL;DR）

1. **内核零重写、逻辑/UI 解耦**：把 `minesweeper.py` 玩法逻辑拆为 `core/` 纯逻辑包（board / timer / daily / storage / achievements / events / theme / config / game），UI 层（Kivy）只做渲染与手势映射。本期是「逻辑复用 + UI 重写」，不是重做游戏。
2. **唯一数值真源 = `LEVELS`（代码）**：README 旧难度表（入门 8×8/10、专家 20×30/150 等）**全部作废**，本设计 §2.1 数值节列出正确 10 档表，端口以本表为准。
3. **三大改造点**（防移动端崩溃 / 适配触屏 / 铺路新功能）：
   - 洪水 `reveal` 由**递归改显式栈（iterative BFS）**，消除 Android 递归栈溢出（风险 R4）。
   - `place_mines` 的 RNG **可注入**（`random.Random(seed)`），为每日挑战铺路。
   - `check_win`/`踩雷`/`chord`/`计时` 处**抛事件**，成就系统纯监听，核心数值不动。
4. **用户拍板已落入设计**：
   - 本期新功能 = **每日挑战 + 成就系统**；提示与复盘、本地排行榜列入路线图（不做）。
   - 标记交互 = **长按插旗 + 工具栏模式切换「两者都提供」**，设置里用户自选默认（长按为主 / 模式按钮为主），双方案并存不冲突。
   - 商业模式 = **纯免费无内购**，商城类功能全部后置。
5. **三大支柱不漂移**：新功能只在外围（种子、成就徽章）扩展，**绝不改动 P1 核心数值规则**（首击安全、洪水、chord、胜负、计时、10 难度一个不少、数值完全一致）。
6. **存储只定义结构**：Android 具体内部存储路径由工程负责人 Phase 3 定；本设计 §2.5 给出 best/成就/每日榜/设置的 JSON schema 与读写契约，不含路径硬编码。

---

## 1. 系统拆解与依赖排序

### 1.1 现有代码 → core/ 模块映射

| 现有 `minesweeper.py` 逻辑 | 归属模块（新建） | 关键改造 |
|----------------------------|------------------|----------|
| `LEVELS` 字典、常量 | `core/config.py` | 难度唯一真源；新增 `DAILY_CONFIG`、交互/动画常量 |
| `THEMES` 字典 | `core/theme.py` | 仅数据；供 UI 取令牌，不做绘制 |
| `place_mines(safe_r,safe_c)`（首击安全 3×3 禁区） | `core/board.py` | RNG 可注入（默认 `random`，daily 传 `random.Random(seed)`） |
| `reveal()` 递归洪水 | `core/board.py` | **改显式栈 iterative BFS**（R4） |
| `chord()` 数字格连开 | `core/board.py` | 保留原判定（board>0 且旗数==数字） |
| `on_right()` 无→旗→?→无 循环 | `core/board.py`：新增 `cycle_mark(r,c)` | 抽为纯逻辑，供触屏长按/模式按钮共用 |
| `check_win()` / `lose_game()` | `core/board.py`：`check_win()` / `lose_game()` | 胜利/失败**抛事件**（成就钩子） |
| `start_timer()` / `_tick()`（封顶 999） | `core/timer.py` | **接 Android 生命周期暂停/恢复**（R6） |
| 每日挑战 seed 注入 | `core/daily.py` | 日期→seed，提供注入用的 `random.Random(seed)` |
| 最佳成绩 `best.json` | `core/storage.py` | 抽象 `Storage` 接口 + JSON 实现（原子写） |
| 成就事件钩子 | `core/events.py`（事件总线）+ `core/achievements.py`（引擎） | 在胜负/chord/计时处订阅事件 |
| `MineSweeper` 编排（新局/重绘/UI） | `core/game.py`（GameSession）+ Kivy UI 层 | 逻辑与 UI 彻底分离 |

### 1.2 模块依赖图（ASCII）

```
[Leaf · 无依赖]
   config.py    LEVELS / DAILY_CONFIG / 交互·动画常量
   theme.py     THEMES 双主题令牌
   events.py    事件总线 + 事件类型（win/lose/chord/reveal/flag/tick）

[Core 逻辑层]
   board.py         → config（维度校验）, events（胜负/chord 抛事件）, 注入 rng
   timer.py         → events（tick 事件）, Android 生命周期 on_pause/on_resume
   daily.py         → config（DAILY_CONFIG）, random（种子 RNG）
   storage.py       → 文件系统接口（路径由工程 Phase3 提供）
   achievements.py  → events（订阅）, storage（持久化）, config（阈值）

[Orchestration 层]
   game.py (GameSession)  → board, timer, daily, storage, achievements, events, theme(取数据)

[Presentation 层 · Kivy]
   touch/interaction.py  手势→动作 + 撤销   → game, storage(读偏好)
   ui/board_widget.py    单 Canvas 重绘      → game, board, theme, timer
   ui/hud.py             底部 HUD 三件套     → game, timer, theme, storage
   ui/drawer.py          难度底部抽屉        → game, storage
   ui/settings.py        设置/主题/徽章墙    → game, storage, theme
```

### 1.3 依赖排序（构建/实现顺序，拓扑）

```
① config → ② theme → ③ events
        （并行leaf，可最先实现）
④ board（需 config+events）     ⑤ timer（需 events）     ⑥ daily（需 config）
⑦ storage（独立，仅依赖 fs 接口）
⑧ achievements（需 events+storage+config）
⑨ game（汇聚 ④⑤⑥⑦⑧ + theme）
⑩ touch / ui/board_widget / ui/hud / ui/drawer / ui/settings（均依赖 ⑨，彼此松耦合）
```

> 工程实现建议：先落 ①②③④（内核），即可跑通无 UI 的命令行可玩验证；再 ⑤⑥⑦⑧⑨；最后 ⑩ 做 Kivy 表现层。

### 1.4 关键改造点说明

- **R4 递归→显式栈**：`reveal` 在 30×30 大空区递归深度可达数百，移动端 Python 默认递归上限（约 1000）易溢出。改为 `stack = [(r,c)]` + `while stack` 弹出 BFS，遇 0 值邻格入栈，封顶安全。
- **RNG 注入**：`board.place_mines(safe_r, safe_c, rng=random)`，普通局用模块级 `random`；每日挑战传 `random.Random(seed)`，保证布局确定性。
- **事件钩子**：`board` 在 `check_win` 成功、`lose_game` 触发、`chord` 成功执行时，向 `events` 总线 `emit`；`achievements` 仅订阅，核心**不 import 成就模块**（单向依赖，零耦合风险）。
- **R6 Android 生命周期**：`timer` 暴露 `pause()/resume()`；App 类在 `on_pause`/`on_resume` 调用，暂停时冻结 `elapsed` 与 tick 调度，恢复后续计，避免切后台计时错乱。

---

## 2. 逐系统 GDD（八节：概述/输入/机制/状态/算法/数值/边界/依赖）

> 八节统一顺序：**概述 → 输入 → 机制 → 状态 → 算法 → 数值 → 边界 → 依赖**

### 2.1 核心玩法系统（Core Gameplay）

**概述**：纯逻辑、无 UI，封装桌面内核全部玩法。负责棋盘生成（首击安全）、邻接计数、洪水展开、chord、胜负判定。安卓版仅替换调用方（UI/触屏），玩法数值与桌面版**逐字节一致**（P1 红线）。

**输入（核心 API）**：
- `Board.new_game(rows, cols, mines)`：初始化空盘与状态矩阵。
- `Board.first_click(r, c)`：首击 → 调 `place_mines(r,c)` + 启动计时（通过事件）；返回本次揭示格集合。
- `Board.reveal(r, c)`：翻开单格（若点已翻开数字格则内部转 chord 由触屏层调用，核心不在此处理双击语义）。返回 `{result: 'reveal'|'lose'|'noop', changed: [...], triggered: (r,c)|None}`。
- `Board.chord(r, c)`：对已翻开数字格执行连开。返回 `{result:'chord'|'noop'|'lose', changed:[...]}`。
- `Board.cycle_mark(r, c)`：循环标记 `无→旗→?→无`（受 `question_enabled` 开关约束时退化为 `无→旗→无`）。
- `Board.check_win()`：判定胜利。
- 查询：`is_flagged/is_revealed/is_marked/number_at/is_mine`。

**机制**：
- 首击安全：首次点击及其周围 8 格（3×3）必非雷，雷只布在其外。
- 邻接计数：8 邻域雷数，0–8。
- 洪水展开：翻开 0 值格时级联展开其 0 值邻域；数字格不递归。
- chord：仅对 `board[r][c] > 0` 的**已翻开**数字格；统计旗数，若 `旗数 == 数字` 则翻开全部未插旗邻格（可能触发失败/级联）。
- 胜利：全部非雷格已翻开。
- 失败：翻开雷格 → 揭示全盘雷、`is_triggered` 标记触发格；已插旗但非雷处标错误旗。

**状态**：
- `board[r][c]`：`-1` 雷 / `0–8` 邻雷数。
- `revealed[r][c]`、`flagged[r][c]`、`marked[r][c]`（问号）。
- `mines_placed`、`game_over`、`win`、`is_triggered`、`question_enabled`。

**算法**：
- `place_mines`：构建 `forbidden = 3×3 around (safe_r,safe_c)`（越界 clamp）→ `candidates = all cells \ forbidden` → `rng.sample(candidates, mines)` → 布 `-1` → 8 邻域计数。
- `reveal`（显式栈）：`stack=[(r,c)]`；`while stack: (r,c)=pop; if 越界/已翻开/已插旗: continue; 标记 revealed; if 雷: lose_game 返回; if 数字: continue(不展开); if 0: 将 8 邻域入栈`。替代原递归。
- `chord`：若 `board[r][c]<=0` 或 `not revealed[r][c]` → noop；统计 `flagged` 邻数 `f`；若 `f==board[r][c]`：对未插旗邻格逐个 `reveal`（连锁）。

**数值（唯一真源 = `LEVELS`，README 旧表作废）**：

| 难度 | rows | cols | mines | 备注 |
|------|------|------|-------|------|
| 入门 | 9  | 9  | 8   | 首击禁区 9 格 < 81，安全 |
| 简单 | 9  | 9  | 12  | |
| 初级 | 12 | 12 | 20  | |
| 中级 | 16 | 16 | 40  | |
| 进阶 | 16 | 16 | 56  | |
| 高级 | 16 | 30 | 99  | |
| 专家 | 20 | 30 | 140 | |
| 大师 | 24 | 30 | 190 | |
| 地狱 | 30 | 30 | 250 | 大棋盘，触发 R2/R3/R4 |
| 自定义 | r×c | — | ≤ r×c−9 | `max_mines = rows*cols - 9`（首击安全下限） |

**边界**：
1. **自定义棋盘过小**：`rows*cols - 9 < 1` → 拒绝并提示（复用 `ask_custom` 逻辑）。
2. **首击在边界**：3×3 禁区越界格 `clamp` 到棋盘内，禁区可能 <9 格，仍合法。
3. **mines > 候选格**：理论上不会（由难度表/自定义上限保证），`rng.sample` 前加 `assert mines <= len(candidates)`，否则回退拒绝。
4. **chord 条件不足**：`f != 数字` → 不展开（与原版一致，避免误开）。
5. **reveal 插旗格**：忽略（`flagged` 优先于 `revealed`）。
6. **reveal 已翻开非数字格**：noop（仅数字格可 chord）。
7. **胜利后**：自动给剩余雷插旗（`flagged=True`），雷数计数器归零显示。
8. **错误旗**：游戏结束且 `flagged 但非雷` → 渲染红叉（`draw_wrong_flag`）。

**依赖**：`config`（维度/上限校验）、`events`（胜负/chord 抛事件）、可注入 `rng`（daily 用）。**不依赖任何 UI。**

---

### 2.2 触屏交互系统（Touch Interaction）

**概述**：将桌面鼠标操作映射为触屏手势，解决「无右键」（R1）。提供**双标记方案并存 + 双击 chord + 撤销一步救误触**，全部单手可达（P2）。

**输入（手势 → 动作）**：
- **单指点按（tap）**：`reveal(r,c)`。若 `flagged` → 忽略；若 `marked` → 先清 `?` 再 `reveal`。
- **长按 ≈350ms（环形进度 + 轻震动）**：`cycle_mark(r,c)`（无→旗→?→无）。
- **双击已翻开数字格**：`chord(r,c)`（独立于模式，仅对已翻开数字格有效）。
- **点按笑脸按钮**：`game.new_game()`。
- **工具栏「挖掘/标记」模式切换按钮**：标记模式下，tap = `cycle_mark`（而非 reveal）；切回挖掘模式恢复 tap=reveal。**与长按方案并存，不冲突**。

**机制**：
- **双方案并存、设置可选默认**：
  - 方案 A「长按为主」：默认 tap=翻开、长按=标记（贴近桌面右键直觉）。
  - 方案 B「模式按钮为主」：底部工具栏「挖掘/标记」切换，标记模式下 tap=标记。
  - 设置项 `default_mark_mode ∈ {longpress, button}` 让用户自选默认；两种能力始终都在，可叠加使用（如标记模式中点长按仍插旗）。
- **双击 chord**：与原版「单点已翻开数字=chord」不同——触屏改为**双击**，避免单手误触误连开（输入映射适配，核心数值不变，P1 不破）。单点已翻开数字格在触屏下为 noop。
- **撤销一步**：每次可变操作（reveal/chord/cycle_mark）前压入操作快照；撤销弹栈还原**棋盘状态**（不含计时，见边界 7）。

**状态**：
- `tool_mode ∈ {dig, mark}`（仅当启用模式按钮方案时生效；长按方案下恒为 dig）。
- 长按检测态：pointer-down 起 350ms 计时器 + 环形进度 + haptic。
- 双击检测态：`last_tap_time`、`last_tap_cell`；同格 300ms 内第二次 tap → chord。
- `undo_stack`（操作快照，深度 `UNDO_DEPTH`，默认 1）。

**算法**：
- 长按判定：`on_touch_down` 启动 350ms `Clock` 计时（显示环形进度 + 轻震动）；`on_touch_up` 前若未到阈值 → 视为 tap；到阈值 → 触发 `cycle_mark` 并消费该次 down（不再触发 tap）。
- 双击判定：记录 `(cell, t)`；新 tap 若 `cell==last_cell and t-last_tap_time ≤ 300ms` 且该格 `revealed and number>0` → `chord`；否则常规处理。
- 撤销：`snapshot = deepcopy(relevant cell states)`（或 op 反向记录）压栈；`undo()` 还原并 `refresh` 变更格。

**数值**：
- 长按阈值 **350ms**（美术圣经附录 A）；双击窗口 **300ms**；长按轻震动（haptic）。
- `UNDO_DEPTH` 默认 **1**（「撤销一步救误触」），可配置为 N（建议 ≤5）。
- 标记循环受 `question_enabled`（设置，默认开；关→退化 无→旗→无）。

**边界**：
1. **长按 vs 点按冲突**：早于 350ms 抬起 = tap，杜绝「想翻开却插旗」。
2. **长按已插旗格**：继续循环（旗→?→无），与桌面右键一致。
3. **双击未翻开格 / 非数字格**：不 chord（chord 仅对已翻开数字格）。
4. **双击在标记模式**：仍可 chord（双击独立于 `tool_mode`），避免模式锁死连开。
5. **撤销在 game_over 后**：禁用（胜/负不可撤销，亦防成就结算被篡改）。
6. **new_game 时**：清空 `undo_stack` 与双击/长按检测态。
7. **撤销不回退计时**：`elapsed` 不受影响（撤销只救误触的棋盘状态，时间已真实流逝，防刷纪录）。
8. **模式切换与长按并存**：即便在挖掘模式，长按仍插旗（方案 A 永远可用）——双方案互补不互斥。

**依赖**：`核心玩法系统`（reveal/chord/cycle_mark）、`storage`（读交互偏好与 `question_enabled`）、`theme`（长按环形进度视觉）、`ui/hud`（底部工具栏/撤销按钮/笑脸）。

---

### 2.3 每日挑战系统（Daily Challenge）

**概述**：每日全网同盘（本期本地实现），按**日期种子**生成确定性棋盘，复用全部核心逻辑；本地存每日最佳。复杂度低、耦合高（直接复用布雷/洪水/chord/胜负），ROI 最高（概念 §6 候选 1）。

**输入**：
- `DailyProvider.seed_for(date)` → `int`（日期→种子）。
- `DailyProvider.make_rng(date)` → `random.Random(seed)`（注入 `board.place_mines`）。
- `game.start_daily(date=None)`：用 `DAILY_CONFIG` + 种子 RNG 开局。
- `storage.set_daily_best(date_str, time)` / `get_daily_best(date_str)`。

**机制**：
- 种子由日期决定，`random.Random(seed)` 完全确定性地布雷 → 同日玩家棋盘一致。
- 其余规则（首击安全、洪水、chord、胜负、计时）与常局**完全相同**。
- 胜利后记录该日期最佳（取最短），失败不记录。

**状态**：`daily_seed`、`daily_rng`、`daily_best: {date_str: seconds|null}`、`daily_completed: {date_str: bool}`。

**算法**：
- `seed = int(date.strftime("%Y%m%d"))`（或 `date.toordinal()`；二选一，推荐前者可读）。
- `rng = random.Random(seed)`；`board.place_mines(safe_r, safe_c, rng=rng)`。
- 首击安全仍生效（3×3 禁区）；胜利 → `daily_best[date_str] = min(existing or ∞, t)`。

> **⚠ 待主理人确认 · 每日确定性关键决策**：常局首击安全依赖「玩家首击位置」→ 不同玩家首击不同格，盘面会微差。为达成「全网同盘」，本设计**推荐每日挑战固定开局格 = 棋盘中心**，并在开局即用种子生成全盘（中心 3×3 设为禁区），首击安全由中心安全区天然保证、且全场一致。备选：允许自由首击（盘面对近似同盘、按开局格微差）。**推荐采用固定中心开局**以保证真正的同盘可比性。

**数值**：
- `DAILY_CONFIG`（固定维度+雷数，候选值见下；**待确认**）：推荐 `{"rows":16,"cols":16,"mines":40}`（中级，平衡难度）；亦可取 `16×30/99`（高级）。一经确定即全量玩家一致。
- 种子公式、`daily_best` 单位为**秒（int，封顶 999）**。

**边界**：
1. **时区**：seed 取**用户本地日期**；跨时区可比性为尽力而为（在线排行榜期再统一 canonical 时区）。标注。
2. **未完成不记录**：仅胜利且通关后写 `daily_best`；失败/中途退出不写。
3. **同日重复玩**：取最短（`min`），非平均。
4. **跨日进行中旧局**：日期变更后新种子生效；进行中的旧局仍记入旧日期（不强行中断）。
5. **RNG 纯净**：daily 局内 `place_mines` 只用注入的 `random.Random(seed)`，不得混用全局 `random`，否则破坏确定性。
6. **种子唯一性**：`YYYYMMDD` 每日唯一，无碰撞。

**依赖**：`核心玩法系统`（注入 rng）、`storage`（每日榜）、`timer`（计时）、`events`（win 事件触发记录）、`config`（`DAILY_CONFIG`）。

---

### 2.4 成就系统（Achievements）

**概述**：监听核心事件（胜利/踩雷/chord 计数/计时/难度）解锁徽章，本地成就表持久化，徽章墙 UI 展示。低成本补强 MDA 的 Accomplishment 美学，与内核天然契合（概念 §6 候选 2）。**核心数值零改动**。

**输入（事件订阅）**：
- `on_game_win(level, time, flags_wrong)` → 结算胜利类成就。
- `on_game_lose(level, triggered)` → 结算（无负向成就，仅统计，可选）。
- `on_chord(session_chord_count)` → 单局 chord 累计达阈值解锁。
- `on_timer_tick / win_time` → 计时类成就（用时阈值）。
- `on_daily_complete(date)` → 每日首胜类。

**机制**：
- `events` 总线在 `check_win`/`lose_game`/`chord` 成功执行/`win` 计时处 `emit`；`AchievementEngine` 单向订阅。
- 成就分**单局型**（本局内达成）与**累计型**（跨局累计，存进度）；结算幂等（重复不重复记录）。
- 解锁即持久化 + 触发 UI 弹窗/徽章亮起（期望层动效）。

**状态**：`achievements: {id: {unlocked:bool, unlocked_at: ISO8601|null, progress:int}}`；`session_counters`（chord 数、插旗数等，开局清零）。

**算法**：事件驱动评估。示例成就集（id / 条件 / 类别）：

| id | 名称 | 条件 | 类别 |
|----|------|------|------|
| ach_first_win | 初次通关 | 任意难度胜利 1 次 | 累计 |
| ach_rookie | 入门通关 | 胜利「入门」 | 单局 |
| ach_expert | 专家征服 | 胜利「专家」 | 单局 |
| ach_hell | 地狱征服 | 胜利「地狱」 | 单局 |
| ach_lightning | 闪电思维 | 任意胜利 ≤ 60s | 单局 |
| ach_chord_master | 连开大师 | 单局 chord ≥ 20 次 | 单局 |
| ach_flawless | 零误旗 | 胜利且 `flags_wrong==0` | 单局 |
| ach_daily_first | 每日首胜 | 完成当日每日挑战 | 单局 |
| ach_flag_forest | 旗帜如林 | 单局插旗 ≥ 50 | 单局 |

> 阈值（60s / 20 次 / 50 旗）为初版建议值，可经 Phase 3 平衡微调。

**数值**：阈值表见上；`chord ≥ 20` 采自概念文档；时间为秒（int）。

**边界**：
1. **事件只在合法态抛**：胜利/失败在 `game_over` 时结算；chord 计数在**每次成功 chord** 时 +1（非每次尝试）。
2. **撤销不影响已结算成就**：成就基于 `game_over` 结算，而 `game_over` 后撤销禁用（2.2 边界 5），无冲突。
3. **重复解锁幂等**：`unlocked` 已 true 则跳过写。
4. **跨难度语义**：明确标注每条是单局还是累计，避免歧义。
5. **版本兼容**：schema 带 `version`，新增成就只追加 `id`，旧成就状态保留（不破坏既有解锁）。
6. **作弊防护（标注）**：本地成就无法防作弊，定位为「荣誉徽章」，**不作为排行榜资格**；在线期再考虑服务端校验。

**依赖**：`events`（必，订阅）、`storage`（持久化成就表）、`config`（阈值）、`核心玩法系统`（状态读取）、`timer`（time 值）。

---

### 2.5 存储系统（Storage）

**概述**：本地 JSON 持久化 best / 成就 / 每日榜 / 设置。**Android 内部存储具体路径由工程负责人 Phase 3 定**；本设计只定义数据结构、读写契约与容错，不硬编码路径。

**输入（Storage 接口）**：
- `load()` / `save()`（原子写）。
- `get_best(level)` / `set_best(level, t)`（胜利最短用时）。
- `get_achievements()` / `unlock(id, progress)`。
- `get_daily_best(date_str)` / `set_daily_best(date_str, t)` / `get_daily_completed`。
- `get_settings()` / `set_setting(key, value)`。

**机制**：抽象 `Storage` 接口 + JSON 文件实现；单文件或多文件均可（推荐分文件便于独立读写）。**原子写**：先写临时文件再 `rename`，防中断损坏。

**状态**：磁盘 JSON；内存缓存（启动时 `load`，变更即 `save`；`on_pause` 强制 flush）。

**算法**：`read` 用 `try/except`：文件缺失/损坏 → 回退默认结构（不崩）；`write` 先写 `.tmp` 再 `os.replace`。

**数值（JSON schema，version=1）**：

```json
// best.json
{ "version": 1,
  "best": { "入门": null, "简单": null, "初级": null, "中级": null,
            "进阶": null, "高级": null, "专家": null, "大师": null,
            "地狱": null,
            "custom_16x16": null } }   // 自定义按 "custom_{r}x{c}" 规格化 key

// achievements.json
{ "version": 1,
  "achievements": { "ach_first_win": {"unlocked": false, "unlocked_at": null, "progress": 0} } }

// daily.json
{ "version": 1,
  "daily": { "20250925": {"best": 123, "completed": true} } }

// settings.json
{ "version": 1,
  "theme": "light",
  "default_mark_mode": "longpress",   // longpress | button
  "toolbar_mode": false,              // 是否默认显示模式按钮
  "question_enabled": true,
  "reduce_motion": false,
  "colorblind": false }
```

**边界**：
1. **损坏/缺失**：回退默认，游戏可继续，不崩。
2. **版本迁移**：读时若缺字段/低 version → 用默认值补齐（向前兼容）。
3. **并发**：Kivy 单线程；`on_pause` 确保 flush，避免切后台丢失。
4. **Android 权限**：本期用 **App 内部存储**（`getFilesDir` / app-specific，无需权限）；若放共享存储才需申请——明确本期不碰共享存储。
5. **类型**：时间为 `int` 秒，封顶 999；`best`/`daily.best` 为 `null` 表示未记录。
6. **自定义 best key**：用 `custom_{rows}x{cols}` 规格化，避免与固定难度冲突。

**依赖**：无内部逻辑依赖（数据 leaf）；被 `game`/`achievements`/`daily`/`settings`/UI 调用。底层依赖 Android 文件系统 API（由工程 Phase 3 提供路径与封装）。

---

### 2.6 UI/HUD 系统（UI / HUD）

**概述**：Kivy 重写 UI 层；**HUD 底部化**（笑脸/雷数 LCD/计时，拇指可达，P2）；难度切换改**底部抽屉**（替代桌面顶栏菜单）；light/dark 双主题；单棋盘 Widget + Canvas 指令重绘（解决 R3 大棋盘性能）。

**输入**：
- 渲染：订阅 `board` 状态变更事件 → 重绘对应格。
- 手势：交给触屏交互系统（2.2）映射到核心动作。
- 底部栏控件：难度抽屉按钮、重开笑脸、主题切换、设置入口。

**机制**：
- **单 Canvas 重绘**（R3）：不用 900 个独立 Widget；单个棋盘 Widget 用 Canvas 指令，仅重绘变更格（对应 `refresh_cell`）；洪水批量重绘（节流级联）。
- **底部化 HUD**：笑脸 / 雷数 LCD / 计时 置于屏幕底部，热区 ≥44dp（R5）。
- **难度切换**：底部抽屉（drawer）弹出 10 档 + 自定义，替代桌面 `Menu`。
- **双主题**：取 `THEMES` 令牌，Kivy 按 `dp` 重绘；切换时整盘重绘 + 面板换色，不重建 widget 树。

**状态**：`current_theme`、`cell_dp`、棋盘渲染缓存、`hud`（mine_counter / timer / face_state）、`drawer_open`。

**算法**：
- `cell_dp` 计算（美术圣经 4.1）：`avail = min(viewport_w, viewport_h - 底部栏 - margins)`；`cell_dp = clamp(round(avail / max(rows,cols)), CELL_MIN, CELL_MAX)`；若 `cell_dp < MIN_TAP_DP`（大棋盘必触发）→ 启用 `ScrollView` 双轴滚动 + 可选 `pinch-zoom` 放大到 ~48dp（R2）。
- 重绘：`refresh_cell(r,c)` 对应核心状态；`new_game`/`theme` 切换 → `refresh_all`。
- 洪水级联：`Clock.schedule` 节流，每格 +20ms，总 ≤400ms（美术圣经 §7）。
- 屏幕旋转：重算 `cell_dp` 重建布局，**不重置游戏状态**。

**数值（美术圣经常量）**：
- `MIN_TAP_DP=44`、`CELL_MIN_DP=30`、`CELL_MAX_DP=56`、`FACE_DP=48`、`COUNTER 72×44`、`bevel_dp=max(2,round(cell/10))`。
- 长按 350ms、双击 300ms、计时封顶 999、LCD 3 位定宽。

**边界**：
1. **大棋盘 <44dp**：`ScrollView` 滚动 + `pinch-zoom` 到 ~48dp，**不压缩热区**（R2）。
2. **性能预算**：单 Canvas + 指令，仅可见视口参与绘制（ScrollView 懒渲染）；绘制调用 <2000、并发 Animation <50（R3）。
3. **主题切换**：整盘重绘 + 面板色，不重建 widget 树。
4. **减少动态**：`reduce_motion` 开 → 关抖屏/缩放/级联，仅状态即时切换。
5. **屏幕旋转**：重算 `cell_dp`，重建布局，保留对局状态。
6. **暗主题数字提亮**：取 `THEMES['dark']['NUM']`（美术圣经 2.2）。
7. **色盲模式**（期望层开关）：`colorblind` 开 → Okabe-Ito 安全色板 + 形状/底点冗余；UX 规格引用美术圣经 §8.2。

**依赖**：`核心玩法系统`（状态）、`触屏交互系统`（手势→动作）、`theme`（THEMES）、`timer`（HUD 计时）、`storage`（settings/theme/best 读取）。

---

## 3. 跨 GDD 一致性评审

| # | 维度 | 现状 | 判定 |
|---|------|------|------|
| C1 | **难度数值真源** | README 旧表（入门 8×8/10、专家 20×30/150…）与代码 `LEVELS` 冲突 | ✅ 本设计 §2.1 以 `LEVELS` 为准，README 旧表**作废**；UI/存储/每日均引用同一表 |
| C2 | **配色一致性** | 代码 `THEMES` ↔ 美术圣经 2.2 数字/令牌表 | ✅ 逐项一致（light/dark 同令牌，仅对比度校正） |
| C3 | **手势映射** | 概念文档 / 美术圣经附录 A / 本设计 §2.2 | ✅ 三者一致：点按=翻开、长按350=标记、双击=chord、笑脸=重开 |
| C4 | **首击安全** | 核心 3×3 ↔ 每日挑战 | ✅ 每日同样首击安全（固定中心开局方案保证确定性，待确认） |
| C5 | **计时封顶 999** | 核心 `_tick` ↔ UI LCD ↔ 存储 | ✅ 三处统一 int 秒、封顶 999、3 位显示 |
| C6 | **难度切换位置** | 桌面 `Menu` 顶栏 → 移动底部抽屉 | ✅ 仅位置变更，数据/逻辑不变，不冲突 |
| C7 | **双主题** | 核心 `THEMES` ↔ UI 取令牌重绘 | ✅ 一致，UI 不另设配色 |
| C8 | **标记循环语义** | 桌面 `on_right` 无→旗→?→无 ↔ 触屏 `cycle_mark` | ✅ 同语义；`question_enabled` 关时退化为无→旗→无，已在边界标注 |

> **结论**：跨 GDD 无数值/语义冲突。唯一需主理人拍板的是 §2.3 每日「固定中心开局 vs 自由首击」确定性方案。

---

## 4. 设计理论评审（三大支柱 + 红线）

### 4.1 支柱校验

| 支柱 | 本期表现 | 漂移？ |
|------|----------|--------|
| **P1 经典内核 fidelity** | 核心数值规则逐字节复用（`LEVELS`、首击安全、洪水、chord、胜负、计时、10 难度全在）；每日/成就只在外围扩展，**不改核心数值** | ✅ 不漂移 |
| **P2 触屏极简 / 单手友好** | 操作单手可达；HUD 底部化；撤销救误触；长按/模式双方案**可选默认**，不强制双手 | ✅ 不漂移 |
| **P3 复古像素 · 清晰演进** | light/dark 双主题；Canvas 硬边矢量；底部化不改变视觉语言；`bevel_dp` 按 dp 放大保体积感 | ✅ 不漂移 |

### 4.2 红线检查（设计理论四忌）

| 红线 | 检查 | 结论 |
|------|------|------|
| **主导策略（Dominant Strategy）** | 核心无；每日=同内核换种子，无新策略碾压；成就不影响数值/胜负。无单一玩法使其他失效 | ✅ 无 |
| **经济失衡（Economy Imbalance）** | 本期**纯免费无内购**（用户拍板），无货币/商城/资源循环；经济维度不存在失衡 | ✅ 无（商城后置路线图） |
| **认知过载（Cognitive Overload）** | 风险点：标记「长按 + 模式按钮」双方案并存。缓解：① 设置**单选默认**，另一方案为可选增强，新手无需同时理解两者；② 默认「长按为主」贴近桌面右键直觉；③ 首玩引导（期望层）只教长按 + 双击 + 笑脸；④ 撤销仅单步，界面元素克制 | ⚠ 可控（已缓解，需首玩引导落地） |
| **支柱漂移（Pillar Drift）** | 新功能（每日/成就）不破坏 P1 数值规则；触屏输入映射调整（双击 chord）不改变核心判定，仅改触发方式（明确标注为 R1 适配） | ✅ 无 |

### 4.3 评审结论
- 三大支柱保持，新功能为**纯外围扩展**，不触碰 P1 数值内核。
- 四忌中三项无风险；认知过载为唯一⚠项，已通过「默认单选 + 引导 + 单步撤销」缓解，建议在 Phase 3 UX 规格中落实首玩引导（期望层）以彻底闭环。

---

## 5. 待主理人 / 工程确认项 与 路线图

### 5.1 待确认（阻塞点）
1. **每日确定性方案**：固定中心开局（推荐，真·同盘）vs 自由首击（盘面对近似同盘）。→ 影响 `daily.py` 实现。
2. **DAILY_CONFIG 取值**：推荐 `16×16/40`（中级），或 `16×30/99`（高级）。→ 影响每日难度。
3. **Android 内部存储路径**：由工程负责人 Phase 3 在 `storage.py` 落 `getFilesDir` 封装；本设计不硬编码。
4. **成就阈值初值**：60s / chord≥20 / 插旗≥50 是否沿用，待 Phase 3 平衡。

### 5.2 路线图（本期不做，已排期）
- **提示与复盘**（概念候选 3，期望层）：安全格高亮提示 + 操作回放；中复杂度、高耦合，不阻塞 MVP。
- **本地排行榜**（概念候选 4，候补）：把 `best` 单值升级为可翻看榜单；本地低复杂，在线需后端，留平台扩展期。
- **联机对战 / 皮肤商城**：明确本期不做（偏离 P1 / 涉及内购变现，Kivy 链路复杂）。
- **屏幕阅读器播报**：美术圣经 §8.5 未来项，预留接口。

---

*—— 文策渊 / 设计策略师 · Phase 2 Lean 评审稿 · 待主理人确认 §5.1 后进入 Phase 3（core/ 实现 + Kivy UI 线框）*
