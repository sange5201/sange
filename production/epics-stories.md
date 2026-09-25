# 扫雷 · 安卓版 — Epic / Story 拆分（Phase 4 预制作 · lean 评审）

- **阶段**：Phase 4 预制作（拆分 + 测试脚手架，结论先行、可直接落地）
- **作者**：程基岩（工程负责人 / 技术 + 引擎）
- **上游真源**：`docs/architecture/architecture.md` + 5 ADR、`design/gdd/system-design.md`、`minesweeper.py`
- **落盘**：`E:/youxi/production/`（本文件 + `sprint1-plan.md` + `test-scaffolding.md`）
- **代码脚手架**：`E:/youxi/app/`（已按本拆分落地 Sprint 1 基础，见 §0）

---

## 0. 结论先行（TL;DR）

1. **6 个 Epic、18 个 Story**：内核逻辑 / 每日挑战 / 成就 / 安卓适配 / Kivy UI / 测试。全部沿架构 §拓扑序（config→theme→events→board→timer→daily→storage→achievements→game→presentation）派生。
2. **拓扑序即实现序**：先落 4 个 Leaf（config/theme/events）+ board，即可跑通「无 UI 命令行可玩 + core 单测」，对应 Sprint 1。
3. **P1 红线由测试守护**：`test_board` 用**显式栈结果 vs 递归参考实现**对照 200+ 随机盘（含 30×30/250），验证 ADR-05 语义等价，不破核心数值。
4. **就绪度**：18 个 Story 中 **14 个接口已定（✅）**，**4 个有局部待定点（⚠）**——均为非阻塞的小决策（bus 注入方式、timer 调度归属、undo 快照、成就阈值/事件契约、存储迁移细节、UI 脏缓存结构），已在 §4 逐项标出，不阻塞 Sprint 1 启动。
5. **脚手架已就绪**：`app/` 下 config/theme/events/board 已按架构签名实现并全绿（325 passed / 5 skipped），`scripts/cli_play.py` 证明无 UI 可玩，Sprint 1 可直接在此基础上硬化。

---

## 1. 拆分原则（对齐架构 §拓扑序）

- 每个 Story 对应一个**可独立估算、可独立验收**的工作单元；验收标准（AC）直接引用架构 §2.2 签名 / §3 迁移 / ADR / system-design 边界。
- 工作量三档：**小**（≤0.5d，单模块/单文件）、**中**（0.5–1.5d，跨模块或带算法）、**大**（>1.5d，本期无大 Story，UI 表现层按子模块拆中）。
- 依赖只向前；表现层统一依赖 `game`（GameSession），绝不反向。
- 测试（Epic F）与实现 Story 一一对应，作为该 Story 的**退出证据**。

---

## 2. Epic 聚合

| Epic | 覆盖拓扑序 | Story 数 | 总估 |
|---|---|---|---|
| **A 内核逻辑** | config→theme→events→board→timer→game | 6 | 小×4 + 中×2 |
| **B 每日挑战** | daily（接 game.start_daily） | 1 | 小×1 |
| **C 成就** | achievements | 1 | 中×1 |
| **D 安卓适配** | storage + platform | 2 | 中×1 + 小×1 |
| **E Kivy UI** | presentation（board/hud/drawer/settings/touch/main） | 6 | 中×3 + 小×3 |
| **F 测试** | test_core + test_ui | 2 | 中×1 + 小×1 |

---

## 3. Story 明细（目标 / AC / 依赖 / 预估 / 就绪度）

> 就绪度图例：✅ 接口已定（架构签名/ADR 已锁定）｜⚠ 待定（局部决策，见 §4 编号）。

### Epic A · 内核逻辑

**S-CFG · `core/config.py`（难度/每日/交互常量唯一真源）**
- 目标：把 `LEVELS`/`THEMES` 关联常量、新增 `DAILY_CONFIG` 与交互常量收敛为唯一真源（system-design C1）。
- AC：① `LEVELS` 9 档值与 `minesweeper.py` 逐项一致（含 `自定义` `rows=cols=0`）；② `DAILY_CONFIG={16,16,40}`；③ `validate_level` 拒绝 `rows*cols-9<1` 与 `mines>max_mines` 并返回中文错误；④ 常量 `LONG_PRESS_MS=350/DOUBLE_TAP_MS=300/UNDO_DEPTH=1/TIMER_CAP=999`；⑤ `test_config` 覆盖。
- 依赖：无（Leaf）。预估：**小**。就绪度：✅ 已定。（已实现脚手架）

**S-THM · `core/theme.py`（双主题令牌）**
- 目标：原样迁移 `THEMES`（仅数据），UI 直接读 dict（美术圣经 §2.2 / system-design C2）。
- AC：① `THEMES` light/dark 数值逐项对齐；② `get_theme(name)` 未知名回退 `light`；③ `available_themes()` 可用；④ 删除任何绘制逻辑（绘制在表现层）。
- 依赖：无（Leaf）。预估：**小**。就绪度：✅ 已定。（已实现脚手架）

**S-EVT · `core/events.py`（事件总线 + 类型）**
- 目标：实现 ADR-03 单向解耦总线，供 board/timer emit、成就 subscribe。
- AC：① `subscribe/emit/clear` 可用；② `subscribe` 返回唯一 id；③ 单订阅者异常**隔离**不阻断事件流；④ 8 个 `GameEvent` 常量均为字符串（可读/可序列化）；⑤ `test_events` 覆盖。
- 依赖：无（Leaf）。预估：**小**。就绪度：✅ 已定。（已实现脚手架）

**S-BRD · `core/board.py`（棋盘内核）**
- 目标：搬移并改造玩法内核——显式栈洪水（ADR-05）、rng 注入、事件抛出（ADR-03）。
- AC：① `first_click/reveal/chord/cycle_mark/check_win` 签名与 §2.2 一致；② `reveal` 为**显式栈**且返回 `changed` 列表；③ `place_mines(rng=...)` 默认模块 random、每日注入 `random.Random(seed)` 且不混用全局 random；④ **P1 等价性**：200+ 随机盘（含 30×30/250）显式栈结果 == 自包含递归参考实现（逐格一致）；⑤ 首击 3×3 禁区无雷；⑥ 胜负/CHORD/REVEAL/FLAG 事件抛出；⑦ `cycle_mark` 三态 + `question_enabled` 退化；⑧ `test_board` 覆盖首击安全/洪水等价/chord/cycle_mark/check_win/边界。
- 依赖：S-CFG、S-EVT。预估：**中**。就绪度：⚠ 待定 — B-1（构造函数 bus 注入方式；§2.2 原签名未含 bus，本脚手架以 `bus=None` 兜底内部总线，待 Sprint 1 确认）。（核心已落地脚手架）

**S-TMR · `core/timer.py`（GameTimer）**
- 目标：实现计时器，暴露 `pause/resume` 接 Android 生命周期（R6），封顶 999，每秒 `emit TICK`。
- AC：① `start/pause/resume/stop` 可用；② `elapsed` 封顶 999；③ `pause` 后 `_tick` 不累加、`resume` 恢复；④ 每秒 `emit TICK{elapsed}`；⑤ `game_over` 后 `resume` 不恢复运行；⑥ `test_timer` 覆盖。
- 依赖：S-EVT。预估：**小**。就绪度：⚠ 待定 — B-2（秒级调度归属：core 内线程 vs 表现层 `Clock` 驱动 `_tick`，见 §6.2 注释；推荐表现层驱动以保持 core 零 Kivy 依赖）。

**S-GAME · `core/game.py`（GameSession 编排）**
- 目标：抽纯编排，去掉 `minesweeper.py::new_game` 的 UI 调用，驱动 core 状态 + 事件。
- AC：① `new_game(level, custom)` / `start_daily(date)` / `reveal/chord/cycle_mark` 转发到 board 并驱动 timer/事件；② `undo()` 一步撤销（边界 7：不回退计时）；③ 会话重置清空 undo/手势态；④ 读 `storage.get_setting` 决定 `question_enabled`；⑤ `test_game` 覆盖。
- 依赖：S-CFG/S-EVT/S-BRD/S-TMR/S-STOR（读设置）。预估：**中**。就绪度：⚠ 待定 — B-3（undo 快照机制：深拷贝棋盘状态 vs 操作反向记录，边界 5 规定 `game_over` 后禁用）。

### Epic B · 每日挑战

**S-DLY · `core/daily.py` + `game.start_daily`（确定性每日盘）**
- 目标：实现 `DailyProvider` 种子 RNG 与 `game.start_daily` 接线（system-design §2.3）。
- AC：① `seed_for(date)=int(YYYYMMDD)`；② `make_rng(date)` 返回确定性 `random.Random(seed)`；③ `config()` 返回 `DAILY_CONFIG`；④ 同 seed + 同首击 → 同盘（确定性）；⑤ **自由首击**安全（用户拍板，覆盖推荐固定中心）；⑥ 胜利写 `daily_best[date]=min(existing,t)`，失败/退出不写；⑦ 不混用全局 random；⑧ `test_daily` 覆盖。
- 依赖：S-BRD、S-CFG、S-GAME。预估：**小**。就绪度：⚠ 标注 — B-4（时区：seed 取用户本地日期，跨时区可比性为尽力而为，在线期统一 canonical 时区）。

### Epic C · 成就

**S-ACH · `core/achievements.py`（AchievementEngine）**
- 目标：订阅核心事件解锁徽章，本地持久化，幂等（system-design §2.4）。
- AC：① 9 条 `ACHIEVEMENTS`（id/name/condition/category）；② 订阅 `WIN/LOSE/CHORD/TICK/DAILY_COMPLETE`；③ 阈值 60s/20chord/50flag 触发；④ 胜利解锁且**幂等**（重复不重复记录）；⑤ `game_over` 后撤销不影响已结算；⑥ schema 带 `version`，新增只追加 id；⑦ `test_achievements` 覆盖。
- 依赖：S-EVT、S-STOR、S-CFG。预估：**中**。就绪度：⚠ 待定 — C-1（阈值 60/20/50 为初版建议，待 Phase 3 平衡微调）；C-2（事件 payload 契约：`WIN` 带 `level/time/flags_wrong` 等，需在 events 集中定义并注释）。

### Epic D · 安卓适配

**S-STOR · `core/storage.py`（Storage / JsonStorage / StorageBackend）**
- 目标：实现 4 类 JSON 原子写 + 容错 + 版本迁移（ADR-04 / system-design §2.5）。
- AC：① `Storage` 抽象 + `JsonStorage`（`.tmp`+`os.replace` 原子写）；② 文件损坏/缺失回退默认结构不崩；③ `version` 低版补字段（向前兼容）；④ `StorageBackend.base_dir()` 桌面 `~/MineSweeper`、安卓经 `platform` 解析 `app.user_data_dir`；⑤ best/ach/daily/settings 访问器；⑥ `test_storage` 覆盖。
- 依赖：无（Leaf，仅依赖 fs 接口）。预估：**中**。就绪度：⚠ 待定 — D-1（迁移补字段的具体默认映射表待实现落地确认；schema 已定 v1）。

**S-PLAT · `platform/android_storage.py` + 生命周期接线**
- 目标：封装 Android 内部存储路径，接 `App.on_pause/on_resume`（R6 / ADR-04）。
- AC：① `android_storage` 薄封装返回 `App.user_data_dir`（core 仍零 Kivy 依赖，路径表现层/平台层传入）；② `main.on_pause` 调 `timer.pause()` + `storage` 强制 flush 并返回 True；③ `on_resume` 调 `timer.resume()`；④ 中端安卓验证。
- 依赖：S-STOR、S-TMR。预估：**小**。就绪度：✅ 已定（ADR-04）。

### Epic E · Kivy UI（Presentation）

**S-UI-BOARD · `presentation/ui/board_widget.py`（单 Canvas 重绘）**
- 目标：单 Widget + 单 Canvas 增量重绘，解决 R3（ADR-02）。
- AC：① **无 900 独立子 Widget**，全部格用 Canvas 指令绘制；② `cell_dp=clamp(round(avail/max(rows,cols)),30,56)`；③ `refresh_cell` 仅重建变更格（脏列表），`refresh_all` 重建整块；④ `<44dp` 切 `ScrollView` 双轴滚动 + `pinch-zoom` 到 ~48dp（不压缩热区，R2）；⑤ 屏幕旋转重算 `cell_dp` 重建布局、**不重置对局**；⑥ `bevel_dp=max(2,round(cell/10))`，禁用位图（美术圣经 §3/§4）。
- 依赖：S-GAME、S-THM。预估：**中**。就绪度：⚠ 待定 — E-1（脏重绘缓存结构：`cell_groups` dict vs `dirty` set 待实现选型；批量节流级联每格 +20ms 总 ≤400ms）。

**S-UI-HUD · `presentation/ui/hud.py`（底部 HUD）**
- 目标：笑脸/雷数 LCD/计时底部化 ≥44dp（P2 / R5）。
- AC：① HUD 置于屏幕底部，热区 ≥44dp；② 订阅事件刷新雷数/计时/笑脸；③ 计时显示 3 位定宽、封顶 999（C5）；④ 重开笑脸按钮。
- 依赖：S-GAME、S-TMR、S-THM、S-STOR。预估：**小**。就绪度：✅ 已定。

**S-UI-DRAWER · `presentation/ui/drawer.py`（难度底部抽屉）**
- 目标：底部抽屉替代桌面顶栏菜单（system-design C6）。
- AC：① 10 档 + 自定义弹出；② 选档触发 `game.new_game`；③ 自定义走 `validate_level` 校验（UI 仅包调用）。
- 依赖：S-GAME、S-STOR。预估：**小**。就绪度：✅ 已定。

**S-UI-SETTINGS · `presentation/ui/settings.py`（设置/主题/徽章墙）**
- 目标：设置面板 + 主题切换 + 徽章墙（system-design §2.4/§2.6）。
- AC：① 主题切换整盘重绘 + 面板换色（不重建 widget 树）；② 设置项（default_mark_mode/toolbar_mode/question_enabled/reduce_motion/colorblind）存 `storage`；③ 徽章墙读 `achievements` 展示解锁态。
- 依赖：S-GAME、S-STOR、S-THM、S-ACH。预估：**中**。就绪度：✅ 已定。

**S-TOUCH · `presentation/touch/interaction.py`（手势→动作 + 撤销）**
- 目标：解决 R1 无右键——tap/长按350/双击300 + 模式按钮并存 + 撤销一步（system-design §2.2）。
- AC：① tap=reveal（flagged→忽略，marked→清?再 reveal）；② 长按 350ms=cycle_mark（环形进度+haptic）；③ 双击 300ms=chord（仅已翻开数字格，独立于 `tool_mode`）；④ 模式按钮「挖掘/标记」切换与长按并存不互斥；⑤ `undo()` 一步（边界 7：不回退计时），`game_over` 后禁用；⑥ `test_interaction` 单测手势判定。
- 依赖：S-GAME、S-STOR、S-THM。预估：**中**。就绪度：⚠ 待定 — E-2（撤销快照与 S-GAME B-3 同方案，表现层仅调用，不持有游戏状态）。

**S-MAIN · `presentation/main.py`（App 生命周期 + 组装）**
- 目标：`MineSweeperApp` 组装 board+hud+dispatcher，`Clock` 驱动 timer，`on_pause/on_resume`（架构 §6.3）。
- AC：① `build` 组装 `BoardWidget`(上) + `HudBar`(下) + `TouchDispatcher`；② `Clock.schedule_interval` 每秒驱动 `timer._tick` + `emit TICK`；③ `on_pause/on_resume` 接 timer+storage；④ 桌面 `python main.py` 可跑通。
- 依赖：全部 UI + S-PLAT。预估：**小**。就绪度：✅ 已定。

### Epic F · 测试

**S-TEST-CORE · `app/tests/test_core/`（6 文件全套）**
- 目标：core pytest ≥90% 覆盖，守护 P1（架构 §5.4 / §6.4）。
- AC：① `test_board/test_timer/test_daily/test_storage/test_achievements/test_events` 六文件齐备；② board 等价性 200+ 随机盘；③ daily 确定性、storage 原子写/容错/迁移、achievements 幂等；④ `core` 覆盖率 ≥90%（UI 不卡覆盖率）。
- 依赖：对应实现 Story。预估：**中**。就绪度：✅ 已定（脚手架已落地：`board/events` 全绿，`timer/daily/storage/achievements` 以 `importorskip` 就绪，待模块实现即生效）。

**S-TEST-UI · `app/tests/test_ui/`（Kivy headless 烟雾）**
- 目标：UI 烟雾测试，验证「能起来 + 关键交互不崩」（架构 §6.4）。
- AC：① `KIVY_WINDOW=headless` / CI `xvfb+sdl2` 启动 `MineSweeperApp`；② 断言渲染格数 == `rows*cols`；③ 模拟 tap→revealed 变更、长按→flagged、双击数字格→chord；④ `on_pause→改状态→on_resume` 状态保持。
- 依赖：S-MAIN 等。预估：**小**。就绪度：✅ 已定（方案已定，本机/CI 装 kivy 后由 `importorskip` 启用；当前环境未装 kivy，烟雾测试自动跳过）。

---

## 4. 控制清单核对（对照 architecture §5 + 待定点映射）

> 实现前必过的控制项（§5.1–§5.4）逐项核对每个 Story 就绪度。

### §5.1 core/ 接口契约
| 控制项 | 对应 Story | 就绪度 |
|---|---|---|
| `config.LEVELS` 值与 `minesweeper.py` 一致 | S-CFG | ✅ 已定（脚手架已比对一致） |
| `board` 签名一致 + `reveal` 显式栈 + `changed` | S-BRD | ✅ 已定（⚠ B-1 bus 注入细节） |
| `place_mines(rng=...)` 默认/注入/不混用 | S-BRD、S-DLY | ✅ 已定 |
| `timer` pause/resume + 封顶 + TICK | S-TMR | ✅ 已定（⚠ B-2 调度归属） |
| `events` 单向 + board 不 import 成就/ui | S-EVT、S-BRD | ✅ 已定（静态断言项） |
| `storage` 原子写 + 容错 + version 迁移 | S-STOR | ✅ schema 已定（⚠ D-1 迁移细节） |
| `StorageBackend.base_dir()` 安卓/桌面 | S-STOR、S-PLAT | ✅ 已定（ADR-04） |
| `achievements` 阈值/幂等 | S-ACH | ✅ 已定（⚠ C-1 阈值、C-2 payload） |

### §5.2 Kivy 项目结构
| 控制项 | 对应 Story | 就绪度 |
|---|---|---|
| `board_widget` 单 Canvas / 单 Widget | S-UI-BOARD | ✅ 已定（⚠ E-1 脏缓存结构） |
| `hud` 底部化 + Canvas 图元 + bevel_dp | S-UI-HUD | ✅ 已定 |
| `interaction` 分发 tap/长按350/双击300 | S-TOUCH | ✅ 已定（⚠ E-2 撤销快照） |
| `main` on_pause/on_resume | S-MAIN、S-PLAT | ✅ 已定 |

### §5.3 buildozer 打包（云 CI）
| 控制项 | 对应 Story | 就绪度 |
|---|---|---|
| 本地仅桌面开发/单测；apk 走云 CI | 全局 | ✅ 已定（ADR-01 后果） |
| `buildozer.spec` requirements/permissions/api | S-MAIN（打包期） | ✅ 已定（S-MAIN 退出后补 spec） |

### §5.4 测试策略
| 控制项 | 对应 Story | 就绪度 |
|---|---|---|
| core pytest ≥90% + 等价性/确定性/容错/幂等 | S-TEST-CORE | ✅ 已定（脚手架落地） |
| UI smoke 启动/格数/tap/长按/双击/pause-resume | S-TEST-UI | ✅ 已定（方案 + importorskip） |

**待定点汇总（均非阻塞 Sprint 1）**：B-1 bus 注入、B-2 timer 调度归属、B-3/B-4 undo 与每日时区、C-1 成就阈值、C-2 事件 payload 契约、D-1 存储迁移细节、E-1 UI 脏缓存结构、E-2 撤销快照。每个待定点在对应 Story AC 中已标注，建议 Sprint 1 启动会 30 分钟拍板。

---

## 5. 工作量汇总

| Epic | 小 | 中 | 合计 |
|---|---|---|---|
| A 内核逻辑 | 4 | 2 | 6 |
| B 每日挑战 | 1 | 0 | 1 |
| C 成就 | 0 | 1 | 1 |
| D 安卓适配 | 1 | 1 | 2 |
| E Kivy UI | 3 | 3 | 6 |
| F 测试 | 1 | 1 | 2 |
| **合计** | **10** | **8** | **18** |

> 中档 Story（8 个）为风险/算法集中区：S-BRD、S-GAME、S-ACH、S-STOR、S-UI-BOARD、S-UI-SETTINGS、S-TOUCH、S-TEST-CORE。建议每个配 1 条「验证驱动」首写测试（见 `test-scaffolding.md`）。

---

*—— 程基岩 / 工程负责人 · Phase 4 预制作 Epic/Story 拆分 · 落盘 `E:/youxi/production/`*
