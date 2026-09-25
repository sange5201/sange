# Sprint 1 QA 计划 — 扫雷·安卓版（Phase 5 · Sprint 1 · 质量负责人）

- **文档**：Sprint 1 QA 计划（含烟雾方案 / 回归清单 / 本机约束对策 / CI 建议 / Bug 分级）
- **作者**：严守真（质量负责人 / QA & 测试）
- **输入**：`sprint1-plan.md`、`epics-stories.md`、`test-scaffolding.md`、`docs/architecture/`（ADR-02/03/05 + §6.4）、`design/gdd/system-design.md`、`design/ux/ux-spec.md`、`app/`（config/theme/events/board 已落地，pytest 325 passed/5 skipped 由工程侧声明）
- **结论先行（TL;DR）**：
  1. **本机无法自验**：本会话环境为 Python 3.13.14，**未装 pytest / kivy / pytest-cov**，工程侧声明的「325 passed / 5 skipped」在本机不可复现；**唯一可信执行源是 CI**（GitHub Actions / Codemagic，钉 Python 3.11 + Kivy 2.3.x）。QA 门禁以 CI 为准。
  2. **覆盖率门禁有真实缺口**：当前 `config.py`(`validate_level`/`max_mines`)、`theme.py`(`get_theme`/`available_themes`) **零单测**，且 `board.py` 的 `reveal/chord` 多个 `noop` 分支未覆盖 → `core` 实际覆盖大概率 **<90%**。必须先补 `test_config.py`/`test_theme.py` + `board` noop 分支用例，否则门禁不达标。**（已列入回归清单与待办）**
  3. **UI 烟雾须防「提前报错」**：`test_smoke.py` 现有 `importorskip("kivy")` 之后直接 `from core.game / presentation...` 导入——若 CI 装了 kivy 但 Epic E 未落地（presentation 为空），会**收集期 ImportError 而非跳过**。要求给 `test_smoke.py` 增加模块级 `importorskip` 守卫（见 §3.4）。
  4. **P1 内核零风险由等价性测试守护**：`test_board::test_flood_explicit_stack_equals_recursive` 已覆盖 200 随机盘（含 30×30/250），但**仅校验首击洪水**；需补充「chord 连锁 / 已翻开格再 reveal」的等价断言，并扩展到 250+ 含全部档位，作为 P1 红线守护底线。
  5. **交付物**：本文件（主计划）+ `app/tests/qa/regression-suite.md`（P1 回归清单）+ `app/tests/qa/smoke-plan.md`（UI 烟雾步骤与断言）+ `.github/workflows/ci.yml`（可直接移交 CI 的钉版配置）。

---

## 1. 测试策略（Test Strategy）

### 1.1 分层与对应 Story
| 层 | 测试类型 | 目录 | 守护 Story | 跑在什么环境 |
|---|---|---|---|---|
| core 纯逻辑 | 单元 + 等价性 | `app/tests/test_core/` | S-CFG/S-THM/S-EVT/S-BRD/S-TMR/S-DLY/S-STOR/S-ACH/S-GAME | 任意（零 Kivy，CI 必跑） |
| UI 表现 | 烟雾（非覆盖率） | `app/tests/test_ui/` | S-TEST-UI / S-UI-* | 仅 CI（Kivy headless + xvfb） |
| 无 UI 可玩 | 手动/烟囱 | `app/scripts/cli_play.py` | Sprint 1 退出证明 | 任意（手动一次） |

### 1.2 测试类型分配（自动 vs 手动）
- **自动（CI 门禁）**：全部 `test_core`（含 P1 等价性、确定性、原子写、容错、幂等）；UI 烟雾（`test_ui`）在 CI 单独 job。
- **手动（人审/Playtest）**：`cli_play.py` 一局流程（开局→揭示→胜负判定）；手势 350/300ms 计时在 `S-TOUCH` 单测层验证（非烟雾职责）；真机中端安卓验证（S-PLAT）留待 Epic E/D 收尾。
- **不卡覆盖率**：UI 烟雾只验证「能起来 + 关键交互不崩」，覆盖率仅对 `core` 门禁。

### 1.3 关键路径 ↔ 测试映射（质量门锚点）
| 关键路径 | 自动断言落点 | 门禁等级 |
|---|---|---|
| 首击安全（3×3 禁区无雷） | `test_board::test_first_click_safe_3x3` + `test_first_click_safe_in_daily` | P1 必过 |
| 洪水显式栈 ≡ 递归 | `test_board::test_flood_explicit_stack_equals_recursive`（≥200 盘） | P1 必过 |
| chord（旗数==数字） | `test_board::test_chord_success/noop_*` | P1 必过 |
| 胜负判定 | `test_board::test_check_win_flags_remaining_mines` / `test_reveal_mine_triggers_loss` | P1 必过 |
| 计时封顶 999 | `test_timer::test_elapsed_caps_at_999`（待 timer 落地） | P1 必过 |
| 10 档数值 | `test_config::test_levels_match_reference`（新增） | P1 必过 |
| 每日种子确定性 | `test_daily::test_same_seed_same_first_click_same_board`（待 daily 落地） | P1 必过（Epic B） |

---

## 2. 准入 / 准出标准（Sprint 1 Definition of Done, QA 视角）

### 2.1 准入（Entry / 开工门）
- [ ] `core/config.py`、`core/theme.py`、`core/events.py`、`core/board.py` 代码评审通过（签名对齐 `architecture §2.2`）。
- [ ] **静态断言**：`core/board.py` 不 `import achievements` / `presentation` / `kivy`（控制清单 §5.1，建议加 `test_core` 内的 `ast` 扫描用例，见回归清单 R-ST-01）。
- [ ] 待定点 **B-1**（bus 注入方式）已拍板并落文档（`Board(bus=None)` 兜底已落地，确认即可）。
- [ ] `pytest` 在 CI 可收集（即便本机无 pytest，CI 安装后必须能 `collect` 全绿）。

### 2.2 准出（Exit / 发布门，advisory 门禁）
- [x] `config/theme/events/board` 四模块按签名落地，且 `board` 不 `import` 任何 Kivy/UI/achievements（静态断言通过）。
- [ ] **`pytest` 在 CI 下 core 全绿**：已实现模块全过；`importorskip` 项（timer/daily/storage/achievements/game）跳过 **不计失败**，但若对应模块已落地则必须全过。
- [ ] **P1 等价性**：`test_flood_explicit_stack_equals_recursive` 覆盖 **≥200** 随机盘（含 30×30/250）显式栈 == 递归参考，全部通过（建议扩到 250+ 且每档位都有样本）。
- [ ] **覆盖率门禁**：`core` ≥ **90%**（`pytest --cov=core --cov-fail-under=90`）。**当前缺口见 §4.2，必须补 `test_config`/`test_theme` + board noop 分支后方达标。**
- [ ] 无 UI 可玩证明：`python scripts/cli_play.py --level 中级 --seed 42` 能开局、揭示、判胜负（CI 或本地手动一次）。
- [ ] 控制清单 §5.1 前 4 项（config/board/events）可勾；B-1 已拍板并记录。
- [ ] 架构 §6.2 骨架标注「Sprint 1 已实现」，与代码一致。

> 质量门为**建议性门控（advisory）**：QA 给出 PASS / CONCERNS / FAIL 判定，最终放行由主理人决定。发布签字（真机/上线）须人工审批。

---

## 3. UI 烟雾测试方案（Smoke，可移交 CI）

> 完整步骤 + 断言见 `app/tests/qa/smoke-plan.md`；本节约要。

### 3.1 启动方式（三环境）
1. **CI 无显示**：`KIVY_WINDOW=headless` + `xvfb-run -a python -m pytest tests/test_ui`（虚拟 X + sdl2；需 apt 装 `xvfb`/`libgl1`/`mesa`）。
2. **本机桌面**：`python main.py` 跑真窗口（开发用）。
3. **headless 后端限制**：Kivy headless 不支持真实触摸事件派发 → 交互用「**直接调用交互层 API**」（如 `TouchDispatcher.on_tap/on_long_press/on_double_tap`）；手势计时（350/300ms）在 `S-TOUCH` 单测层单独验证，不在烟雾职责内。

### 3.2 必过断言（不卡覆盖率，仅验证「能起来 + 关键交互不崩」）
| # | 步骤 | 断言 |
|---|---|---|
| S1 | `App.build` + `new_game("初级")` + `BoardWidget.build_canvas()` | `widget.cell_count() == rows*cols`（12×12=144） |
| S2 | 模拟 tap(0,0) | `session.board.is_revealed(0,0)` 变 True |
| S3 | 模拟长按(5,5) | `session.board.is_flagged(5,5)` 置位 |
| S4 | 双击已翻开数字格 | `dispatcher.on_double_tap` 不抛异常且命中 chord 路径 |
| S5 | `reveal(0,0)` → `timer.pause()` → `timer.resume()` | `board.is_revealed(0,0)` 与 `elapsed` 保持（R6 生命周期） |
| S6 | HUD 渲染 | 雷数 LCD / 计时 LCD / 笑脸控件存在且 ≥44dp（P2 热区） |

### 3.3 CI 分离 job（关键）
UI 烟雾必须放在**独立 CI job**（与 core job 并行/串行均可），因为：
- 需要装 Kivy + xvfb（重、慢）；
- 在 Epic E 未落地前不应阻断 core 绿灯。

### 3.4 ⚠ 必修硬化（防止 CI 提前报错）
`app/tests/test_ui/test_smoke.py` 当前结构：
```python
os.environ.setdefault("KIVY_WINDOW", "headless")
pytest.importorskip("kivy")          # 仅当 kivy 缺失时整模块跳过
from core.game import GameSession    # ← kivy 存在但 game 未实现时会 ImportError（收集失败）
...
```
**QA 要求**：在 `importorskip("kivy")` **之后**补模块级守卫，使「kivy 已装但 presentation 未落地」也干净跳过：
```python
pytest.importorskip("kivy")
pytest.importorskip("core.game")
pytest.importorskip("presentation.ui.board_widget")
pytest.importorskip("presentation.touch.interaction")
```
否则 Epic A–D 阶段一旦 CI 装了 kivy，UI job 会 **ERROR（非 skip）**，误伤流水线。此条列入回归清单 R-UI-01 跟踪。

---

## 4. 本机约束对策 + 覆盖率门禁

### 4.1 本机约束（本会话实测）
| 项 | 本机状态 | 对策 |
|---|---|---|
| Python | 3.13.14 | 本地仅写代码/文档；**运行交给 CI（钉 3.11）** |
| pytest | **未安装** | CI 装 `pytest`；本机不跑，声明「325 passed」不可自验 |
| kivy | **未安装** | UI 烟雾本地自动跳过；CI 钉 `kivy==2.3.*` + xvfb 跑 |
| pytest-cov | **未安装** | CI 装 `pytest-cov`；门禁 `--cov=core --cov-fail-under=90` |

### 4.2 覆盖率缺口（必达 ≥90% 的前置项）
读 `app/tests/test_core/` 后确认以下**无单测**，是当前最大的门禁风险：

| 模块 | 缺失覆盖 | 必须新增 |
|---|---|---|
| `core/config.py` | `validate_level` / `max_mines` / `LEVELS` 逐项 / `DAILY_CONFIG` / 常量 | **新增 `test_config.py`**（S-CFG AC⑤ 要求但当前缺失） |
| `core/theme.py` | `get_theme` 未知回退 / `available_themes` / `THEMES` 对齐 | **新增 `test_theme.py`**（S-THM AC 要求但当前缺失） |
| `core/board.py` | `reveal` 的 `game_over`/`越界` noop 分支；`chord` 的 `game_over` noop；`remaining_mines`；`check_win` 非胜早退 | 补 board noop 分支用例（Sprint 1 硬化项①） |
| `core/events.py` | 已较好覆盖 | — |

> **判定**：在补齐 `test_config`/`test_theme` + board noop 分支前，`core` 覆盖率**不达标（<90%）**。这两份测试文件是 Sprint 1 退出门禁的硬阻塞项，已列入回归清单 R-COV-01/02。

### 4.3 覆盖率执行命令（CI）
```bash
python -m pytest tests/test_core \
  --cov=core --cov-report=term-missing --cov-fail-under=90
```
- UI 不计入覆盖率（`--cov=core` 仅 core 包）。
- 后续 Sprint 落地 timer/daily/storage/achievements/game 时，其覆盖率同样须 ≥90%，否则门禁失败。

---

## 5. Bug 分级标准（S1–S4）与上报模板

### 5.1 严重度定义
| 级 | 名称 | 定义 | 示例 | 处理时限 |
|---|---|---|---|---|
| **S1 Blocker** | 阻塞 | 崩溃/数据丢失/破坏 P1 数值红线/完全无法进入核心流程；无临时规避 | 递归栈溢出回归、首击踩雷、等价性测试失败、`board` 误 import 成就 | 立即，阻断发布 |
| **S2 Critical** | 严重 | 主要功能不可用，无可用规避；或数值偏差但未破 P1 内核边界 | 计时封顶失效、chord 误连开、存档损坏致无法启动 | 本 Sprint 内 |
| **S3 Major** | 重要 | 功能部分受损，有规避方案；或边界场景错误 | 自定义过小未拒绝、撤销在 game_over 后仍可用、`?` 退化错 | 下个 Sprint 或排期 |
| **S4 Minor** | 轻微 | 表现/文案/边缘；不影响玩法 | 数字色与主题不符、日志噪声、单测命名 |  backlog |

### 5.2 上报模板（每个 Bug 必填字段）
```
【Bug ID】BUG-<sprint>-<seq>         【严重度】S1|S2|S3|S4
【标题】一句话现象
【模块/Story】core.board / S-BRD / UI / ...
【环境】Python 3.11 / Kivy 2.3.x / CI(xvfb) / 真机(型号)
【前置条件】开局难度、种子、设置
【复现步骤】
  1. ...
  2. ...
【预期结果】...
【实际结果】...
【证据】截图/日志/失败测试名/pytest 输出片段
【影响面】是否破 P1 红线 / 是否阻塞发布
【建议优先级】P0(立即)/P1(本Sprint)/P2(排期)
【负责人】工程侧认领
```

### 5.3 红线违规特别通道
任何疑似**破坏 P1 数值内核**（首击安全 / 洪水语义 / chord / 胜负 / 计时封顶 999 / 10 档数值 / 每日确定性）的缺陷，**直接定级 S1** 并 `@工程负责人` + 主理人，不进入普通 backlog 排队。

---

## 6. 待主理人 / 工程侧决议与协作点

| # | 事项 | 影响 | 建议 |
|---|---|---|---|
| Q1 | 本机无 pytest/kivy/pytest-cov → 声明「325 passed」不可自验 | QA 判定依赖 CI | **CI 落地前 QA 门禁视为未验证**；优先合入 `.github/workflows/ci.yml` |
| Q2 | `test_config.py` / `test_theme.py` 缺失 | 覆盖率 <90% 阻塞退出 | 工程侧 Sprint 1 内补齐（已列 R-COV-01/02） |
| Q3 | `test_smoke.py` 缺模块级 importorskip 守卫 | Epic A–D 阶段 CI 装 kivy 会 ERROR | 工程侧按 §3.4 加守卫（R-UI-01） |
| Q4 | B-1 bus 注入 | Sprint 1 启动会确认项 | `Board(bus=None)` 兜底已落地，确认记录即可 |
| Q5 | P1 等价性仅覆盖首击洪水 | chord 连锁/再 reveal 等价未守 | 扩 `test_board` 等价断言（R-EQ-02） |

---

*—— 严守真 / 质量负责人 · Sprint 1 QA 计划 · 落盘 `E:/youxi/production/qa-plan.md`*
*配套：`app/tests/qa/regression-suite.md`（P1 回归清单）、`app/tests/qa/smoke-plan.md`（UI 烟雾步骤）、`.github/workflows/ci.yml`（CI 钉版配置）*
