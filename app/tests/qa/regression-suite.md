# P1 数值红线回归清单（Regression Suite）— Sprint 1 / 全周期守护

- **用途**：作为 CI 与发布评审的 **P1 回归门禁**。任何一条失败 → 定级 S1（见 `production/qa-plan.md` §5）→ 阻断发布。
- **真源**：`docs/architecture/architecture.md §4.2`（P1 红线）、`design/gdd/system-design.md §2.1`（数值）、`epics-stories.md`（Story 验收）、ADR-05（显式栈等价）。
- **执行**：CI core job 自动跑 `tests/test_core`；本清单每项映射到具体测试名/用例；`[待补]` 为 Sprint 1 必须补齐项。

---

## R-ST 静态契约（解耦红线）

- [ ] **R-ST-01** `core/board.py` 不 `import achievements` / `presentation` / `kivy`。
  - 形式：在 `test_core` 新增 `test_board_no_forbidden_imports`，用 `ast` 解析 `board.py` 源码，断言无 `import achievements` / `from ... import ...presentation` / `import kivy` 等语句。
  - 依据：ADR-03 单向解耦、控制清单 §5.1。
- [ ] **R-ST-02** `core/` 全部模块零 Kivy 依赖（目录级扫描）：任何 `core/**/*.py` 不含 `import kivy`。

---

## R-EQ 洪水显式栈 ≡ 递归（P1 红线 #1，ADR-05）

- [x] **R-EQ-01** `test_board::test_flood_explicit_stack_equals_recursive`：覆盖 **≥200** 随机盘（含 `30×30/250`），显式栈 `revealed` 集合 == 递归参考实现集合，且翻开格均非雷。
  - 现状：`parametrize("seed", range(200))` 已落，档位随机抽，含地狱大棋盘。
  - 提升项（Sprint 1 硬化）：扩到 `range(250)` 且**显式保证每档位至少 N 个样本**（避免随机漏掉某档）。
- [ ] **R-EQ-02** `[待补]` 等价性扩展到 **chord 连锁 + 已翻开格再 reveal**：
  - 构造手工盘 → 先 `reveal` 洪水 → 对数字格 `chord` → 断言「显式栈 chord 连锁翻开集合」==「递归参考 chord 连锁翻开集合」；
  - 已翻开数字格 `reveal` 再调用返回 `noop`（边界 6）。
  - 依据：当前等价性**仅校验首击洪水**，chord 连锁的等价未守，属 P1 守护盲区。
- [ ] **R-EQ-03** `[待补]` 大棋盘压测：独立用例 `test_flood_30x30_250_no_recursion_error`（确认显式栈在 30×30/250 不会触发 `RecursionError`，且深度与递归参考一致）。

---

## R-FS 首击安全（3×3 禁区无雷，P1 红线 #2）

- [x] **R-FS-01** `test_board::test_first_click_safe_3x3`：常局（中级）首击 3×3 邻域无雷，50 seed。
- [ ] **R-FS-02** `[待补]` 边界首击（角落/边缘）：首击 `(0,0)` / `(rows-1,cols-1)` → 3×3 禁区 clamp 后仍无雷（系统-design 边界 2）。
- [ ] **R-FS-03** `[待补]` 自定义最小盘：9×9 以下但 `≥10` 格（如 5×5，mine≤16）→ 首击安全不崩（`max_mines=16`）。

---

## R-CH chord 连开（旗数==数字，P1 红线 #3）

- [x] **R-CH-01** `test_board::test_chord_success`：旗数==数字 → 翻开全部未插旗邻格，雷格保持 flagged 不动。
- [x] **R-CH-02** `test_board::test_chord_noop_when_flags_insufficient`：旗数≠数字 → noop。
- [x] **R-CH-03** `test_board::test_chord_noop_on_zero_cell`：`board<=0` 或 `not revealed` → noop（边界 4）。
- [ ] **R-CH-04** `[待补]` chord 触发踩雷：邻格含未插旗雷 → `chord` 返回 `lose` 且 `is_triggered` 正确（核心失败路径）。
- [ ] **R-CH-05** `[待补]` chord 计数幂等：仅成功 chord 时 `chord_count+1`（条件不足不计）。

---

## R-WIN 胜负判定（P1 红线 #4）

- [x] **R-WIN-01** `test_board::test_check_win_flags_remaining_mines`：全非雷翻开 → `win` + `game_over` + 剩余雷自动插旗（边界 7）。
- [x] **R-WIN-02** `test_board::test_reveal_mine_triggers_loss`：踩雷 → `lose`、全盘雷揭示、`is_triggered` 标记触发格、`game_over` 且 `not win`。
- [ ] **R-WIN-03** `[待补]` `check_win` 早退：存在任一未翻开非雷格 → 返回 False 且不置 `win`/`game_over`。
- [ ] **R-WIN-04** `[待补]` `game_over` 后 `reveal/chord` 全部 noop（不二次结算、不破成就幂等，系统-design §2.2 边界 5）。

---

## R-TMR 计时封顶 999（P1 红线 #5，待 timer 落地）

- [ ] **R-TMR-01** `[待补]` `test_timer::test_elapsed_caps_at_999`：`elapsed` 封顶 `TIMER_CAP=999`，不溢出（C5 三处统一）。
- [ ] **R-TMR-02** `[待补]` `pause` 冻结 / `resume` 恢复 `elapsed`；`game_over` 后 `resume` 无效（R6）。
- [ ] **R-TMR-03** `[待补]` 每秒 `emit TICK{elapsed}`（UI/存储统一 int 秒）。

---

## R-LVL 10 档难度数值（P1 红线 #6，唯一真源）

- [ ] **R-LVL-01** `[待补]` **新增 `test_config.py`**：`LEVELS` 9 个固定档值与 `minesweeper.py` 逐项一致（含 `自定义` `rows=cols=0`）；`DAILY_CONFIG=={16,16,40}`；常量 `LONG_PRESS_MS=350 / DOUBLE_TAP_MS=300 / UNDO_DEPTH=1 / TIMER_CAP=999`。**——当前缺失，覆盖率阻塞项（qa-plan §4.2）。**
- [ ] **R-LVL-02** `[待补]` `validate_level`：拒绝 `rows*cols-9<1`、拒绝 `mines>max_mines`、返回中文错误；`max_mines(rows,cols)=rows*cols-9`（R8/R9）。

---

## R-DAY 每日种子确定性（P1 红线 #7，Epic B）

- [ ] **R-DAY-01** `[待补/待 daily 落地]` `test_daily::test_same_seed_same_first_click_same_board`：同 seed + 同首击 → 同盘。
- [ ] **R-DAY-02** `[待补]` `seed_for(date)==int(YYYYMMDD)`；`make_rng` 确定性；**不混用全局 random**（系统-design 边界 5）。
- [ ] **R-DAY-03** `[待补]` 自由首击安全：每日同样 3×3 禁区无雷（ux-spec §5.3 已定自由首击）。

---

## R-COV 覆盖率门禁（Sprint 1 退出硬阻塞）

- [ ] **R-COV-01** `[待补]` 新增 `test_config.py`（覆盖 `config` 全部公共函数）→ `config` 覆盖 ≥90%。
- [ ] **R-COV-02** `[待补]` 新增 `test_theme.py`：`get_theme` 未知回退 `light`、`available_themes()`、`THEMES` light/dark `NUM` 键对齐（system-design C2）、无绘制逻辑。
- [ ] **R-COV-03** `[待补]` board noop 分支：`reveal` 的 `game_over`/越界 noop、`chord` 的 `game_over` noop、`remaining_mines`、`check_win` 早退 → board 覆盖 ≥90%。
- [ ] **R-COV-04** CI 门禁：`pytest --cov=core --cov-fail-under=90`；`core` 整体 ≥90%（后续 timer/daily/storage/achievements/game 落地后同样须达标）。

---

## R-UI UI 烟雾守护（Epic E 落地后启用）

- [ ] **R-UI-01** `[待补]` `test_smoke.py` 增加模块级 `importorskip` 守卫（`core.game` / `presentation.ui.board_widget` / `presentation.touch.interaction`），防 Epic A–D 阶段 CI 装 kivy 后收集 ERROR（qa-plan §3.4）。
- [ ] **R-UI-02** `[待补]` 烟雾必过断言 S1–S6（格数/ tap/ 长按/ 双击chord/ pause-resume/ HUD 热区），见 `smoke-plan.md`。

---

## 回归门禁判定规则
- 任一 `R-ST` / `R-EQ` / `R-FS` / `R-CH` / `R-WIN` / `R-TMR` / `R-LVL` / `R-DAY` 项 FAIL → **S1**，阻断发布。
- `R-COV` 不达标 → Sprint 1 退出门禁 FAIL（CONCERNS，须补齐后方可准出）。
- `R-UI` 项在 Epic E 落地前标记 N/A（不计入 Sprint 1 门禁）。

---

*—— 严守真 / 质量负责人 · 落盘 `E:/youxi/app/tests/qa/regression-suite.md` · 配套 `production/qa-plan.md` §3/§4*
