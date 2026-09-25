# UI 烟雾测试方案（Smoke Plan）— Kivy headless / CI xvfb

- **用途**：Sprint 1 烟雾方案（可移交 CI 执行）。仅验证「能起来 + 关键交互不崩」，**不卡覆盖率**。
- **真源**：`docs/architecture/architecture.md §6.4`、`design/ux/ux-spec.md §3`（手势阈值）、ADR-02（单 Canvas）、R6（生命周期）。
- **本机约束**：本会话 Python 3.13.14 **无 kivy** → 本地自动跳过；本方案在 CI（钉 Python 3.11 + Kivy 2.3.x + xvfb）执行。

---

## 1. 三环境启动

| 环境 | 命令 / 变量 | 说明 |
|---|---|---|
| CI 无显示 | `KIVY_WINDOW=headless xvfb-run -a python -m pytest tests/test_ui -v` | 虚拟 X + sdl2；需 apt 装 `xvfb`/`libgl1-mesa-dri`/`xauth` |
| 本机桌面 | `python main.py` | 开发真窗口 |
| CI 分离 job | 见 §4 `.github/workflows/ci.yml` 的 `ui-smoke` job | 与 core job 独立，避免拖慢/误伤 |

> **headless 后端限制**：Kivy headless 不派发真实触摸事件 → 交互用「**直接调用交互层 API**」（`TouchDispatcher.on_tap/on_long_press/on_double_tap`），不派发触摸屏事件。手势计时（350/300ms）在 `S-TOUCH` 单测层验证，不在烟雾职责内。

---

## 2. 必过断言（S1–S6）

| # | 步骤 | 断言（伪代码） | 守护 |
|---|---|---|---|
| **S1** 渲染格数 | `session.new_game("初级")` → `BoardWidget(session,bus).build_canvas()` | `widget.cell_count() == rows*cols`（初级 12×12=144） | ADR-02 单 Canvas 渲染全部格 |
| **S2** tap 揭示 | `dispatcher.on_tap(0,0)` | `session.board.is_revealed(0,0) is True` | R1 点按=reveal |
| **S3** 长按标记 | `dispatcher.on_long_press(5,5)` | `session.board.is_flagged(5,5) is True` | 长按350=cycle_mark |
| **S4** 双击 chord | 翻出已知数字格后 `dispatcher.on_double_tap(r,c)` | 不抛异常；命中 chord 路径（返回非 None / 触发 CHORD 事件） | 双击300=chord（仅已翻开数字格） |
| **S5** 生命周期保持 | `reveal(0,0)` → `timer.pause()` → `timer.resume()` | `board.is_revealed(0,0)` 与 `elapsed` 保持 | R6 on_pause/on_resume |
| **S6** HUD 热区 | 构建 `HudBar` | 雷数 LCD / 计时 LCD / 笑脸控件存在且尺寸 ≥44dp | P2 底部化热区 ≥44dp |

> S4 在「首击即 0 值大空区」布局下可能无已翻开数字格 → 用例须**先构造一个已知数字格**（参考 `test_board::_set_layout` 手工铺盘），确保 chord 路径可达，避免假绿。

---

## 3. `test_smoke.py` 硬化要求（防 CI 提前报错）

现状（风险）：`importorskip("kivy")` 之后直接 `from core.game / presentation...`，若 kivy 已装但 Epic E 未落地 → **收集期 ImportError（ERROR 非 skip）**，误伤 Epic A–D 流水线。

**修复**：在 kivy 守卫后补模块级守卫，使「kivy 已装但 presentation 未实现」也干净跳过：
```python
import os, pytest
os.environ.setdefault("KIVY_WINDOW", "headless")
pytest.importorskip("kivy")
pytest.importorskip("core.game")
pytest.importorskip("presentation.ui.board_widget")
pytest.importorskip("presentation.touch.interaction")

from kivy.app import App                      # 此后才 import 表现层
from core.game import GameSession
from core.events import EventBus
from presentation.ui.board_widget import BoardWidget
from presentation.touch.interaction import TouchDispatcher
```
（对应回归清单 `R-UI-01`。）

---

## 4. CI 钉版配置（直接移交）

完整文件见仓库根 `.github/workflows/ci.yml`。要点：
- **Python 钉 3.11**（Kivy 2.3.x 兼容，避开本机 3.13 不可跑 kivy）。
- **Kivy 钉 2.3.x**（`kivy==2.3.*`）+ `painter`/`sdl2` 依赖；UI job 装 `xvfb`/`libgl1-mesa-dri`/`xauth`。
- **core job**：`pip install pytest pytest-cov` → `pytest tests/test_core --cov=core --cov-fail-under=90`。
- **ui-smoke job**：仅装 kivy+xvfb → `pytest tests/test_ui`；因 §3 守卫，Epic E 前自动 skip 不误伤。
- 覆盖率门禁 `--cov-fail-under=90` 失败即红。

---

## 5. 本机手动补充（无 UI 可玩证明）
```bash
cd E:/youxi/app
python scripts/cli_play.py --level 中级 --seed 42
# 指令：r/f/c <row> <col> | p 打印 | q 退出
# 手动确认：开局无雷首击安全、reveal 洪水、flag、chord、判胜负
```
（Sprint 1 退出标准之一；CI 亦可加一步 `python scripts/cli_play.py --level 中级 --seed 42 <<< "q"` 做启动冒烟。）

---

*—— 严守真 / 质量负责人 · 落盘 `E:/youxi/app/tests/qa/smoke-plan.md` · 配套 `production/qa-plan.md` §3、`.github/workflows/ci.yml`*
