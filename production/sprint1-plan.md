# Sprint 1 计划 — 无 UI 命令行可玩 + core 单测（Phase 4 预制作）

- **阶段**：Phase 4 · Sprint 1（内核起步，结论先行、可直接落地）
- **作者**：程基岩（工程负责人）
- **目标**：沿拓扑序落地 `config → theme → events → board` + `test_core` 骨架 + 无 UI CLI，跑通「命令行可玩 + core 单测全绿」，守护 P1 数值红线。
- **输入**：`docs/architecture/architecture.md` §拓扑序、`production/epics-stories.md` S-CFG/S-THM/S-EVT/S-BRD/S-TEST-CORE。

---

## 0. 结论先行

1. **Sprint 1 Story 集**：S-CFG + S-THM + S-EVT + S-BRD + S-TEST-CORE（部分）+ CLI 证明。
2. **脚手架已提前落地**：`E:/youxi/app/` 下 4 个 Leaf + board 已按架构签名实现，`scripts/cli_play.py` 已证明无 UI 可玩，**325 passed / 5 skipped** 已验证。Sprint 1 实际剩余工作 = 硬化 + 补齐边界 AC + 接入 `game` 之外的收尾。
3. **退出即里程碑**：core 单测全绿且 `test_board` 200+ 随机盘等价性通过 → P1 内核零风险，后续 Epic 可安全叠加每日/成就/UI。

---

## 1. Sprint 1 目标

在**不引入任何 Kivy/UI 依赖**的前提下，使纯逻辑内核（`core/`）达到：
- 可被命令行驱动完成一局（揭示/标记/胜负）；
- 被 pytest 全覆盖核心规则，且**显式栈洪水与递归参考实现逐格等价**（P1 红线 #1 守护）。

## 2. Sprint 1 范围（Story 与任务）

| Story | 任务 | 预估 | 状态 |
|---|---|---|---|
| S-CFG | `core/config.py`：LEVELS/DAILY_CONFIG/常量/validate_level | 小 | ✅ 已落地脚手架 |
| S-THM | `core/theme.py`：THEMES/get_theme/available_themes | 小 | ✅ 已落地脚手架 |
| S-EVT | `core/events.py`：EventBus/GameEvent（异常隔离） | 小 | ✅ 已落地脚手架 |
| S-BRD | `core/board.py`：place_mines(rng)/显式栈 reveal/chord/cycle_mark/check_win/查询 + 事件 | 中 | ✅ 已落地脚手架（待硬化） |
| S-TEST-CORE | `tests/test_core/`：test_board(等价性)/test_events + 其余文件 importorskip 就绪 | 中 | ✅ 脚手架落地（board/events 全绿） |
| — | `scripts/cli_play.py`：无 UI 命令行可玩证明 | 小 | ✅ 已落地 |

**Sprint 1 内待完成（在已落地脚手架上）**：
1. S-BRD 硬化：补 `reveal` 已翻开格 noop 显式返回、`chord` 连锁 REVEAL 计数、`check_win` 胜利自动插旗的 AC 单测闭环（脚手架已含，需 review 通过）。
2. 拍板待定点 **B-1**（bus 注入方式）：建议 `Board(bus=None)` 兜底内部总线，GameSession 传共享总线——已写入脚手架，Sprint 1 启动会确认。
3. 覆盖率门禁：装 `pytest-cov`，确认 `core` 覆盖率 ≥90%（当前 board/events/config/theme 均覆盖；board 为核心重点）。
4. 文档同步：将脚手架实现回写架构 §6.2 骨架，标注「已实现」。

**明确不在 Sprint 1**（留给后续 Sprint）：S-TMR(timer)、S-GAME(game)、S-DLY、S-ACH、S-STOR、S-PLAT、Epic E 全部 UI、S-TEST-UI。`test_timer/test_daily/test_storage/test_achievements` 以 `importorskip` 就绪，模块实现后自动生效（不阻断 Sprint 1 绿灯）。

## 3. Sprint 1 退出标准（Definition of Done）

- [ ] `config/theme/events/board` 四模块按架构 §2.2 签名落地，且 `board` 不 `import` 任何 Kivy/UI/achievements（静态断言通过）。
- [ ] `pytest` 在 `app/` 下**全绿**（325→预期随硬化略增；`importorskip` 项跳过不计失败）。
- [ ] **P1 等价性**：`test_flood_explicit_stack_equals_recursive` 覆盖 ≥200 随机盘（含 30×30/250）显式栈 == 递归参考，全部通过。
- [ ] `core` 覆盖率 ≥90%（`pytest --cov=core --cov-report=term-missing`）。
- [ ] 无 UI 可玩证明：`python scripts/cli_play.py --level 中级 --seed 42` 能开局、揭示、判胜负（手动验证一次）。
- [ ] 控制清单 §5.1 前 4 项（config/board/events）可勾；B-1 已拍板并记录。
- [ ] 架构 §6.2 骨架标注「Sprint 1 已实现」，与代码一致。

## 4. 执行顺序（建议）

1. 启动会 30min：拍板 B-1（bus 注入），确认脚手架即 Sprint 1 基础。
2. Review + 硬化 `core/board.py`（对照 S-BRD 的 8 条 AC）。
3. 跑 `pytest` + `pytest-cov`，补遗漏分支至 ≥90%。
4. 手测 `cli_play.py`。
5. 回写架构 §6.2 + 关闭 Sprint 1。

---

*—— 程基岩 / 工程负责人 · Sprint 1 计划 · 落盘 `E:/youxi/production/`*
