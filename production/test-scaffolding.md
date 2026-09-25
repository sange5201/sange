# 测试框架脚手架（Phase 4 预制作 · lean）

- **阶段**：Phase 4 预制作 · 测试策略落地
- **作者**：程基岩（工程负责人）
- **输入**：架构 `architecture.md` §5.4 / §6.4、ADR-03、本仓库 `E:/youxi/app/`
- **结论先行**：`app/tests/` 目录结构与 pytest 配置已落地；`test_core` 六文件齐备（board/events 全绿，timer/daily/storage/achievements 以 `importorskip` 就绪）；`test_ui` 烟雾测试走 Kivy headless 方案；**当前 325 passed / 5 skipped**。

---

## 1. 目录结构（已落地）

```
E:/youxi/app/
├── conftest.py                      # 将 app/ 加入 sys.path，使 `from core.xxx` 可用
├── pytest.ini                       # testpaths=tests；addopts=-q（覆盖率见 §4）
├── core/                            # 纯逻辑包（零 Kivy）
│   ├── __init__.py
│   ├── config.py   ✅ Sprint1 落地   # LEVELS/DAILY_CONFIG/常量/validate_level
│   ├── theme.py    ✅ Sprint1 落地   # THEMES/get_theme
│   ├── events.py   ✅ Sprint1 落地   # EventBus/GameEvent
│   └── board.py    ✅ Sprint1 落地   # 显式栈 reveal/rng 注入/事件
├── scripts/
│   └── cli_play.py ✅ Sprint1 落地   # 无 UI 命令行可玩证明
├── presentation/                    # Kivy 表现层（Sprint 后续，待落地）
│   ├── touch/interaction.py
│   └── ui/{board_widget,hud,drawer,settings}.py
├── platform/                        # 安卓适配（S-PLAT）
│   └── android_storage.py
└── tests/
    ├── test_core/
    │   ├── __init__.py
    │   ├── test_events.py     ✅ 全绿（S-EVT 验收）
    │   ├── test_board.py      ✅ 全绿（S-BRD 验收 + P1 等价性核心）
    │   ├── test_timer.py      ⏸ importorskip(core.timer) 就绪
    │   ├── test_daily.py      ⏸ importorskip(core.daily) 就绪
    │   ├── test_storage.py    ⏸ importorskip(core.storage) 就绪
    │   └── test_achievements.py ⏸ importorskip(core.achievements) 就绪
    └── test_ui/
        ├── __init__.py
        └── test_smoke.py      ⏸ importorskip(kivy) 就绪（headless 方案见 §3）
```

> ⏸ = 模块未实现时由 `pytest.importorskip` 跳过，**不阻断 Sprint 1 绿灯**；模块落地后该文件自动生效。

## 2. test_core 文件清单与职责

| 文件 | 守护的 Story / 红线 | 关键用例 |
|---|---|---|
| `test_events.py` | S-EVT / ADR-03 | subscribe 唯一 id、emit 投递、clear、异常隔离、事件常量字符串化 |
| `test_board.py` | S-BRD / P1 红线 | **显式栈 == 递归参考（200+ 随机盘，含 30×30/250）**、首击 3×3 安全、邻接计数、确定性、踩雷 lose、chord 成功/noop、cycle_mark 三态+退化、flagged 优先、胜利自动插旗、事件抛出 |
| `test_timer.py` | S-TMR | pause 冻结 / resume 恢复、封顶 999、TICK 每秒、game_over 后 resume 无效 |
| `test_daily.py` | S-DLY | seed_for=YYYYMMDD、make_rng 确定性、config==DAILY_CONFIG、同 seed 同首击同盘、不混用全局 random、首击安全 |
| `test_storage.py` | S-STOR / ADR-04 | 原子写无残留 .tmp、损坏回退默认、缺失回退默认、version 迁移补字段、base_dir 字符串 |
| `test_achievements.py` | S-ACH | 首胜解锁、幂等、闪电 60s 阈值、连开大师 20 次、成就表 id 完整 |

### 2.1 P1 等价性核心（保障红线 #1）

`test_board.py::test_flood_explicit_stack_equals_recursive`：
- 自包含一份**递归参考实现** `_recursive_flood`（仅测试用，不进生产）；
- 对每个随机盘：构造 `Board` → `first_click(中心)` → 取显式栈 `revealed` 集合；
- 在同布局、同首击上跑递归参考，取递归 `revealed` 集合；
- 断言两集合**逐格相等**，且翻开格均非雷。

语义正确性依据：首击 3×3 禁区保证首击格为 0 值，洪水只在 0 值连通区展开、数字格不入栈、flagged 优先跳过——显式栈与递归完全一致（ADR-05）。覆盖 200 seed × 全档位（含 30×30/250 大棋盘压测）。

## 3. test_ui 烟雾测试 + Kivy headless 方案

`tests/test_ui/test_smoke.py` 已就绪，启动方案（架构 §6.4）：

1. **环境变量**：`KIVY_WINDOW=headless`（Kivy headless 后端，无真实窗口）。
2. **CI 无显示**：`xvfb-run -a python -m pytest tests/test_ui`（虚拟 X + sdl2）。
3. **本机桌面**：直接 `python main.py` 跑真窗口。
4. **断言**（不卡覆盖率，仅验证「能起来 + 关键交互不崩」）：
   - `build` 成功，`board_widget` 渲染格数 == `rows*cols`；
   - 模拟 tap → `board.revealed` 变更；长按 → `flagged` 置位；双击数字格 → `chord` 触发；
   - `on_pause → 改状态 → on_resume`：棋盘与 `elapsed` 保持。
5. **注意**：headless 后端不支持真实触摸派发，故交互用「直接调用交互层 API」而非派发触摸屏事件；手势计时（350/300ms）在 `S-TOUCH` 单测层单独验证。

> 当前环境未安装 Kivy，`test_smoke.py` 经 `importorskip("kivy")` 自动跳过；安装 Kivy（及 `xvfb` 于 CI）后即启用。

## 4. 运行与覆盖率

```bash
# 当前环境（Python313 已带 pytest）：
cd E:/youxi/app
python -m pytest                      # 全绿；未实现模块自动跳过

# 覆盖率（需先 pip install pytest-cov）：
python -m pytest --cov=core --cov-report=term-missing
# 门禁：core ≥ 90%；UI 不计入覆盖率

# 无 UI 可玩证明：
python scripts/cli_play.py --level 中级 --seed 42
```

**实测结果（本次落地验证）**：`325 passed, 5 skipped`。

## 5. 验证驱动（TDD）约定

每个中档 Story（S-BRD/S-GAME/S-ACH/S-STOR/S-UI-BOARD/S-UI-SETTINGS/S-TOUCH/S-TEST-CORE）开工时**先写测试再实现**：
- 参考 `test_board.py` 模式：先把 AC 转成可断言用例（如等价性、边界、事件），再补实现至全绿；
- 参考 `importorskip` 模式：未实现模块的测试文件先落地骨架（含完整断言），模块就绪即生效，避免「实现完再补测试」的遗漏。

---

*—— 程基岩 / 工程负责人 · 测试框架脚手架 · 落盘 `E:/youxi/production/`*
