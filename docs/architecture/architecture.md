# 扫雷 · 安卓版（Kivy）架构设计

- **阶段**：Phase 3 技术搭建（lean 评审，结论先行、可直接落地）
- **技术栈**：Python + Kivy（打包 apk，本期聚焦 Android）
- **作者**：程基岩（工程负责人 / 技术 + 引擎）
- **输入真源**：`minesweeper.py`（Tkinter 单文件）、概念文档、美术圣经、Phase 2 系统设计（`design/gdd/system-design.md`）
- **配套 ADR**：`adr-01`~`adr-05`（同目录，本文件 §7 索引）

---

## 0. 结论先行（TL;DR）

1. **三层架构**：`core/`（纯逻辑包，零 UI 依赖）→ `presentation/`（Kivy 表现层，渲染 + 手势）→ `platform/`（Android 生命周期 / 内部存储封装）。UI 与逻辑彻底解耦，核心数值规则逐字节复用 P1。
2. **内核零重写、逻辑复用**：把 `minesweeper.py` 玩法逻辑拆进 `core/board.py` 等 9 个模块；**仅 3 处结构性改造**——① 洪水 `reveal` 递归→显式栈（ADR-5）；② `place_mines` 注入 `rng`（每日挑战）；③ 胜负/chord/计时 `emit` 事件（ADR-3）。其余原样搬。
3. **用户拍板已落到架构**：每日挑战=**自由首击 + 默认中级 16×16/40**（覆盖 system-design §2.3 推荐的固定中心方案）；标记交互=长按插旗 + 模式按钮**双方案并存、设置自选默认**；存储=**Android 内部存储**（`app.user_data_dir`，无需权限）；纯免费无内购。
4. **性能与稳定对策**：单 Canvas 棋盘重绘（ADR-2，解决 R3 900 Widget 卡顿）；显式栈防洪（ADR-5，解决 R4）；`timer.pause/resume` + `App.on_pause/on_resume`（解决 R6）。
5. **打包方案（本机 Win10/4GB）**：本地只做桌面开发/单测；**apk 实际构建走云 CI**（GitHub Actions / Codemagic），绕开 4GB 内存与 WSL2 编译压力（§6.3）。
6. **测试策略**：`core/` 用 pytest 全覆盖（≥90%）；UI 用 Kivy headless/smoke 烟雾测试（§6.4）。

> 本文件是 lean 单文档，下面 §1 分层、§2 模块图、§3 迁移策略、§4 评审、§5 控制清单、§6 脚手架，ADR 见单独文件。

---

## 1. 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  presentation/  (Kivy 表现层)                                │
│   ui/board_widget.py   单 Canvas 棋盘重绘（ADR-2）           │
│   ui/hud.py            底部 HUD（笑脸/雷数/计时，P2 底部化） │
│   ui/drawer.py         底部难度抽屉                          │
│   ui/settings.py       设置/主题/徽章墙                      │
│   touch/interaction.py 手势→动作 + 撤销（tap/长按/双击）     │
│   main.py              App 生命周期 on_pause/on_resume      │
├─────────────────────────────────────────────────────────────┤
│  core/  (纯逻辑包 · 零 UI 依赖 · P1 数值真源)                │
│   board / timer / daily / storage / achievements /          │
│   events / theme / config / game                            │
├─────────────────────────────────────────────────────────────┤
│  platform/  (Android 适配)                                   │
│   android_storage.py 内部存储路径封装（ADR-4）              │
│   lifecycle.py       on_pause/on_resume 钩子适配            │
└─────────────────────────────────────────────────────────────┘
```

**依赖方向单向**：`presentation → core → platform`（platform 仅被 core/storage 在运行时解析路径时调用，不反向）。`core` 不 `import` 任何 Kivy / `presentation` 符号；成就通过事件总线单向订阅（ADR-3），`board` 永不 `import achievements`。

---

## 2. core/ 模块依赖图（细化 Phase 2 + 接口签名）

### 2.1 模块依赖（ASCII，细化版）

```
[Leaf · 无内部依赖]
   config.py    LEVELS(唯一真源) / DAILY_CONFIG / 交互·动画常量 / validate_level()
   theme.py     THEMES 双主题令牌（仅数据）
   events.py    EventBus + GameEvent 类型

[Core 逻辑层 · 依赖 Leaf]
   board.py     → config(校验), events(抛事件), 注入 rng
   timer.py     → events(tick), 暴露 pause/resume
   daily.py     → config(DAILY_CONFIG), random(种子 RNG)
   storage.py   → 文件系统接口（路径由 platform/android_storage 提供）
   achievements.py → events(订阅), storage(持久化), config(阈值)

[Orchestration 层]
   game.py (GameSession) → board, timer, daily, storage, achievements, events, theme(读数据)

[Presentation 层 · Kivy，依赖 core]
   touch/interaction.py → game, storage(读偏好)
   ui/board_widget.py   → game, board, theme, timer
   ui/hud.py            → game, timer, theme, storage
   ui/drawer.py         → game, storage
   ui/settings.py       → game, storage, theme
```

### 2.2 关键接口签名（实现契约，详见 §6.2 骨架）

```python
# core/config.py
LEVELS: dict                      # 10 档，唯一真源（README 旧表作废）
DAILY_CONFIG = {"rows":16,"cols":16,"mines":40}   # 用户拍板：默认中级
LONG_PRESS_MS = 350; DOUBLE_TAP_MS = 300; UNDO_DEPTH = 1; TIMER_CAP = 999
def validate_level(rows, cols, mines) -> tuple[bool, str|None]

# core/theme.py
THEMES: dict                      # light/dark 令牌表（数据，不做绘制）
def get_theme(name: str) -> dict

# core/events.py
class GameEvent: WIN, LOSE, CHORD, REVEAL, FLAG, TICK, NEW_GAME, DAILY_COMPLETE
class EventBus:
    def subscribe(self, etype, handler) -> int
    def emit(self, etype, payload=None)
    def clear(self)

# core/board.py
class Board:
    def __init__(self, rows, cols, mines, rng=random, question_enabled=True)
    def first_click(self, r, c) -> dict     # place_mines(rng) + reveal，emit REVEAL
    def reveal(self, r, c) -> dict          # 显式栈洪水，emit REVEAL/LOSE
    def chord(self, r, c) -> dict           # emit CHORD（成功）
    def cycle_mark(self, r, c) -> None      # 无→旗→?→无（question 关则退化）
    def check_win(self) -> bool             # 胜则 emit WIN
    # 查询
    def number_at(self,r,c); is_mine; is_flagged; is_revealed; is_marked
# 返回结构：{"result":"reveal"|"lose"|"noop","changed":[(r,c),...],"triggered":(r,c)|None}

# core/timer.py
class GameTimer:
    def __init__(self, bus: EventBus)
    def start(self); def pause(self); def resume(self); def stop(self)
    @property
    def elapsed(self) -> int        # 封顶 TIMER_CAP=999，每秒 emit TICK

# core/daily.py
class DailyProvider:
    @staticmethod
    def seed_for(date) -> int                  # int(YYYYMMDD)
    @staticmethod
    def make_rng(date) -> random.Random       # 注入 board.place_mines
    @staticmethod
    def config() -> dict                       # DAILY_CONFIG

# core/storage.py
class Storage(ABC):                            # load/save 原子写；best/ach/daily/settings 访问器
class JsonStorage(Storage): ...                # .tmp + os.replace；损坏回退默认；version 迁移
class StorageBackend:                          # 解析平台路径
    @staticmethod
    def base_dir() -> str                      # Android=app.user_data_dir；桌面=~/MineSweeper

# core/achievements.py
ACHIEVEMENTS: list[dict]        # id/name/condition/category + 阈值（60s/20chord/50flag 初值）
class AchievementEngine:
    def __init__(self, bus: EventBus, storage: Storage)
    def subscribe(self)                       # 订阅 WIN/LOSE/CHORD/TICK/DAILY_COMPLETE

# core/game.py
class GameSession:
    def __init__(self, bus, timer, storage, daily=None)
    def new_game(self, level="初级", custom=None)
    def start_daily(self, date=None)          # 用 DAILY_CONFIG + DailyProvider.make_rng
    def reveal(self, r, c); chord(...); cycle_mark(...); undo()
```

---

## 3. 从 minesweeper.py 抽取核心逻辑的迁移策略

### 3.1 类/函数 → 模块映射（原样搬 vs 要改）

| `minesweeper.py` 来源 | 目标 | 动作 |
|---|---|---|
| `LEVELS` | `core/config.py::LEVELS` + `DAILY_CONFIG` + 交互常量 | **原样搬**（数据），补 `DAILY_CONFIG`、`LONG_PRESS_MS` 等 |
| `THEMES` | `core/theme.py::THEMES` | **原样搬**；删除 `_apply_theme_globals`（UI 全局重绑属于表现层，UI 直接读 dict） |
| `place_mines(safe_r,safe_c)` | `core/board.py::Board.place_mines` | **要改**：增 `rng=random` 形参；首击安全 3×3 禁区逻辑原样保留 |
| `reveal()` 递归 | `core/board.py::Board.reveal` | **要改（重写）**：递归→**显式栈 BFS**（ADR-5），返回 `changed` 列表 |
| `chord()` | `core/board.py::Board.chord` | **原样搬**逻辑；成功时 `emit(CHORD)` |
| `on_right()` 循环 | `core/board.py::Board.cycle_mark` | **抽纯逻辑**：无→旗→?→无（`question_enabled` 关退化） |
| `check_win()` / `lose_game()` | `core/board.py` | **原样搬**；胜/败 `emit(WIN/LOSE)` |
| `start_timer()/_tick()` | `core/timer.py::GameTimer` | **要改**：拆出 `pause()/resume()`（R6）；每秒 `emit(TICK)` |
| `BEST_FILE` 路径逻辑 | `core/storage.py` + `platform/android_storage.py` | **要改**：抽象 `Storage` + `JsonStorage`（原子写/容错）；路径用 `StorageBackend` |
| `load_best/save_best` | `core/storage.py::JsonStorage` | **原样搬**原子写思路（`.tmp`+`os.replace`）；加损坏回退 |
| `ask_custom` 上限逻辑 | `core/config.py::validate_level` + UI 弹窗 | **要改**：`max_mines = rows*cols-9` 校验抽进 config；UI 仅包调用 |
| `MineSweeper.new_game` 编排 | `core/game.py::GameSession.new_game` | **抽纯编排**：去掉所有 UI 调用，改为驱动 core 状态 + emit `NEW_GAME` |
| `on_left/on_right`（输入） | `touch/interaction.py` | **搬到表现层**：手势→动作映射 |
| `refresh_cell/refresh_all`、`draw_*`、`update_mine_counter` | `ui/board_widget.py` / `ui/hud.py` | **搬到表现层**：用 Kivy Canvas 重写绘制（保留归一化坐标与 bevel 算法，见美术圣经） |
| `show_best` / 菜单 | `ui/settings.py` / `ui/drawer.py` | **搬到表现层** |

### 3.2 三处结构性改造（防崩溃 / 适配触屏 / 铺路新功能）

**① 洪水递归 → 显式栈（ADR-5）**
原因：30×30 大空区递归深度可达数百，Android Python 递归上限（默认 1000）易栈溢出崩。改为：
```python
stack = [(r, c)]
while stack:
    cr, cc = stack.pop()
    if not in_bounds(cr,cc): continue
    if revealed[cr][cc] or flagged[cr][cc]: continue
    revealed[cr][cc] = True; changed.append((cr,cc))
    if board[cr][cc] == -1: lose_game(cr,cc); return {"result":"lose","changed":changed,"triggered":(cr,cc)}
    if board[cr][cc] == 0:
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                stack.append((cr+dr, cc+dc))
```
等价语义，零递归风险。

**② `place_mines` RNG 可注入**
```python
def place_mines(self, safe_r, safe_c, rng=random):
    forbidden = {(safe_r+dr, safe_c+dc) for dr in (-1,0,1) for dc in (-1,0,1)
                 if 0<=safe_r+dr<rows and 0<=safe_c+dc<cols}
    candidates = [(r,c) for r in range(rows) for c in range(cols) if (r,c) not in forbidden]
    assert self.mines <= len(candidates), "mines exceed safe candidates"
    for (r,c) in rng.sample(candidates, self.mines):   # 常局用模块 random；每日用 random.Random(seed)
        board[r][c] = -1
    # 8 邻域计数（原样）
```
每日挑战：`DailyProvider.make_rng(date)` 返回 `random.Random(int(YYYYMMDD))`，经 `board.first_click` 注入，**全程不混用全局 random**（system-design 边界 5）。

**③ 胜负 / chord / 计时 抛事件（ADR-3）**
`board.check_win` 成功 → `bus.emit(GameEvent.WIN, {...})`；`lose_game` → `emit(LOSE)`；`chord` 成功 → `emit(CHORD, {session_chord_count})`；`timer` 每秒 → `emit(TICK, {elapsed})`。`AchievementEngine` 仅 `subscribe`，核心不 import 成就模块。

### 3.3 每日挑战确定性（用户拍板：自由首击 + 16×16/40）

> 用户拍板采用 **自由首击**（覆盖 system-design §2.3 推荐固定中心方案）。工程侧确定性实现：

- `seed = int(date.strftime("%Y%m%d"))` → `rng = random.Random(seed)`。
- `board.first_click(r,c)` 用该 `rng` 注入 `place_mines`，首击安全 3×3 禁区**与常局同算法**。
- **确定性结论**：同日期 **且** 同首击格 → 棋盘**完全相同**；不同首击格 → 仅 3×3 禁区差异（≤9 格），属 system-design 已确认之「近似同盘」方案（不破坏可比性，首击位置可由 UI 引导一致）。
- `DAILY_CONFIG = {"rows":16,"cols":16,"mines":40}`（用户拍板默认中级）；胜利记录 `daily_best[date] = min(existing, t)`，失败/中途退出不写。
- ⚠ 时区：seed 取**用户本地日期**；跨时区统一 canonical 时区留在线排行榜期（标注，同 system-design 边界 1）。

---

## 4. 架构评审：R1–R9 工程侧落地缓解 + P1 红线确认

### 4.1 风险缓解对照表

| 风险 | 工程侧落地缓解 | 落点 |
|---|---|---|
| **R1 触屏无右键** | `interaction.py`：tap=reveal；长按350ms=cycle_mark；双击已翻开数字=chord；底部「挖掘/标记」模式按钮（与长按并存）；设置 `default_mark_mode` 自选默认。核心 `cycle_mark` 纯逻辑。 | §2.2 board/§3.1 |
| **R2 大棋盘格子过小** | `cell_dp = clamp(round(avail/max(rows,cols)), CELL_MIN, CELL_MAX)`；`<44dp` 时 `ScrollView` 双轴滚动 + `pinch-zoom` 放大到 ~48dp，**不压缩热区**。 | ui/board_widget |
| **R3 Kivy 大棋盘性能** | **ADR-2 单 Canvas / 单 Widget**：不用 900 独立 Widget；单 `BoardWidget` Canvas 仅重绘 `changed` 格，洪水批量节流。 | ADR-02 |
| **R4 递归洪水栈溢出** | **ADR-5 显式栈 BFS**，见 §3.2①。 | ADR-05 |
| **R5 单手可达性** | HUD（笑脸/雷数 LCD/计时）+ 难度抽屉**全部底部化**，`hud.py` 置于屏幕底部，热区 ≥44dp。 | ui/hud, ui/drawer |
| **R6 Android 生命周期** | `timer.pause()/resume()` 冻结 `elapsed` 与 tick；`App.on_pause/on_resume` 调用；`on_pause` 强制 `storage.flush()`。 | core/timer, main.py |
| **R7 像素图标 high-DPI 模糊** | Canvas 矢量图元（Line/Rect/Ellipse/Triangle）按 `cell_dp` 绘制，禁用位图模糊，`bevel_dp=max(2,round(cell/10))`；归一化坐标同 `minesweeper.py`。 | ui/board_widget（美术圣经 §3/§4） |
| **R8 README/代码难度不一致** | `LEVELS` 为唯一真源钉在 `core/config.py`；UI/存储/每日全部引用它；README 旧表**作废**（system-design C1）。 | core/config |
| **R9 首击安全 + 自定义上限** | `validate_level` 复用 `max_mines=rows*cols-9`；`rows*cols-9<1` 拒绝并提示；`rng.sample` 前 `assert mines<=len(candidates)`。 | core/config, board |

### 4.2 设计红线（P1 数值规则不可砍）确认

| P1 规则 | 架构保障 | 结论 |
|---|---|---|
| 首击安全（3×3 禁区） | `board.place_mines` 逻辑原样保留 + rng 可注入 | ✅ 不破 |
| 洪水展开（0 值级联） | 显式栈**等价**原递归语义（§3.2①） | ✅ 不破 |
| chord（旗数==数字连开） | `board.chord` 原样搬判定 | ✅ 不破 |
| 胜负判定（全非雷翻开=胜） | `board.check_win` 原样搬 | ✅ 不破 |
| 计时封顶 999 | `GameTimer.elapsed` 封顶 + UI/存储统一 int 秒 | ✅ 不破 |
| 10 档难度 + 数值 | `LEVELS` 唯一真源，沿用 `minesweeper.py` 值 | ✅ 不破 |
| 每日/成就**不改核心数值** | 仅在外围加 seed/事件；`board` 不 import 成就 | ✅ 不破 |

> **结论**：新功能（每日挑战、成就）为**纯外围扩展**，核心数值内核零改动，P1 红线无违反。认知过载（system-design 四忌⚠项）由「默认单选 + 首玩引导（期望层）+ 单步撤销」缓解，引导落地建议进 Phase 4 UX 规格。

---

## 5. 控制清单（实现前 checklist）

### 5.1 core/ 接口契约（合并前必过）
- [ ] `config.LEVELS` 值与 `minesweeper.py` 逐项一致（9/9/8…30/30/250）；README 旧表不引用。
- [ ] `board.first_click/reveal/chord/cycle_mark/check_win` 签名与 §2.2 一致；`reveal` 返回 `changed` 列表且为**显式栈**。
- [ ] `board.place_mines(rng=...)` 默认 `random`，每日注入 `random.Random(seed)`，且每日局内**不混用**全局 random。
- [ ] `timer` 暴露 `pause/resume`；`elapsed` 封顶 999；每秒 `emit(TICK)`。
- [ ] `events.EventBus.subscribe/emit/clear` 单向；`board` 不 import `achievements`/`ui`。
- [ ] `storage.JsonStorage` 原子写（`.tmp`+`os.replace`）；损坏回退默认；`version` 字段迁移。
- [ ] `StorageBackend.base_dir()`：Android → `app.user_data_dir`；桌面 → `~/MineSweeper`（§6.1 ADR-4）。
- [ ] `achievements` 阈值初值沿用（60s / chord≥20 / 插旗≥50）；`game_over` 后撤销禁用，成就结算幂等。

### 5.2 Kivy 项目结构（见 §6.1）
- [ ] `presentation/ui/board_widget.py` 为**单 Canvas / 单 Widget**（ADR-2），无 900 独立子 Widget。
- [ ] `ui/hud.py` 底部化；`draw_*` 用 Kivy Canvas 图元，禁用位图；`bevel_dp` 按 dp 缩放。
- [ ] `touch/interaction.py` 分发 tap/长按350/双击300；双击 chord 仅对已翻开数字格。
- [ ] `main.py` 实现 `on_pause`/`on_resume`（接 `timer` + `storage.flush`）。

### 5.3 buildozer 打包 apk（本机 Win10/4GB 方案，见 §6.3）
- [ ] 本地**仅**桌面开发/单测；apk 走**云 CI**（GitHub Actions / Codemagic），不硬刚 4GB。
- [ ] `buildozer.spec`：`requirements = python3,kivy`；`android.permissions =`（空，内部存储免权限）；`android.api`/`minapi` 设 21+；`source.dir`/`source.include_exts`。
- [ ] 桌面 `python main.py` 可跑通；CI 产物 `bin/*.apk` 可装真机验证。

### 5.4 测试策略（见 §6.4）
- [ ] `core/` pytest 覆盖 ≥90%：首击安全/洪水等价/chord/cycle_mark/check_win/边界。
- [ ] `daily` 确定性：同 seed 同首击 → 同盘；自由首击安全。
- [ ] `storage` 原子写 / 损坏回退 / version 迁移。
- [ ] UI smoke：启动→渲染格数正确→tap 揭示→长按标记→双击 chord→`on_pause/on_resume` 状态保持。

---

## 6. 实现脚手架

### 6.1 目录结构（建议落盘布局）

```
E:/youxi/
├── minesweeper/                 # 旧 Tkinter 单文件（参考，不删）
│   └── minesweeper.py
├── app/                         # 新 Kivy 工程（打包根）
│   ├── main.py                  # Kivy App + 生命周期（§6.3 线框）
│   ├── buildozer.spec
│   ├── core/                    # 纯逻辑包（零 Kivy 依赖）
│   │   ├── __init__.py
│   │   ├── config.py            # LEVELS / DAILY_CONFIG / 常量 / validate_level
│   │   ├── theme.py             # THEMES（数据）
│   │   ├── events.py            # EventBus + GameEvent
│   │   ├── board.py             # Board（显式栈 reveal + rng 注入 + 事件）
│   │   ├── timer.py             # GameTimer（pause/resume + TICK）
│   │   ├── daily.py             # DailyProvider（种子 RNG）
│   │   ├── storage.py           # Storage/JsonStorage/StorageBackend
│   │   ├── achievements.py      # AchievementEngine + ACHIEVEMENTS
│   │   └── game.py              # GameSession（编排）
│   ├── presentation/
│   │   ├── __init__.py
│   │   ├── touch/interaction.py # 手势→动作 + 撤销
│   │   └── ui/
│   │       ├── board_widget.py  # 单 Canvas 重绘
│   │       ├── hud.py           # 底部 HUD
│   │       ├── drawer.py        # 难度抽屉
│   │       └── settings.py      # 设置/主题/徽章墙
│   ├── platform/
│   │   ├── __init__.py
│   │   └── android_storage.py   # 内部存储路径封装（ADR-4）
│   └── tests/
│       ├── test_core/           # pytest：board/timer/daily/storage/achievements/events
│       └── test_ui/             # Kivy smoke
└── docs/architecture/           # 本目录
```

### 6.2 core/ 包骨架（关键签名，不必写全实现）

```python
# core/board.py（节选骨架）
import random
from .events import EventBus, GameEvent

class Board:
    def __init__(self, rows, cols, mines, rng=random, question_enabled=True):
        self.rows, self.cols, self.mines = rows, cols, mines
        self.rng = rng
        self.question_enabled = question_enabled
        self.board = [[0]*cols for _ in range(rows)]
        self.revealed = [[False]*cols for _ in range(rows)]
        self.flagged  = [[False]*cols for _ in range(rows)]
        self.marked   = [[False]*cols for _ in range(rows)]
        self.mines_placed = self.game_over = self.win = False
        self.is_triggered = None

    def first_click(self, r, c):
        if not self.mines_placed:
            self.place_mines(r, c)            # 注入 self.rng
        return self.reveal(r, c)

    def place_mines(self, safe_r, safe_c, rng=None):
        rng = rng or self.rng
        # 3×3 禁区 + rng.sample（同 minesweeper.py，详见 §3.2②）
        self.mines_placed = True

    def reveal(self, r, c):                   # 显式栈，见 §3.2①
        changed = []
        stack = [(r, c)]
        # ...while stack... 遇雷 lose_game→emit(LOSE)；否则 emit(REVEAL,{changed})
        if self.check_win(): pass
        return {"result": "reveal", "changed": changed, "triggered": None}

    def chord(self, r, c):
        # board[r][c]>0 且 revealed 且 旗数==数字 → 翻开邻格；成功 emit(CHORD)
        ...

    def cycle_mark(self, r, c):
        # 无→旗→(?→无)；question_enabled 关则 无→旗→无
        ...

    def check_win(self):
        if all(self.revealed[r][c] or self.board[r][c]==-1
               for r in range(self.rows) for c in range(self.cols)):
            self.win = self.game_over = True
            # 剩余雷插旗 + emit(WIN)
            return True
        return False
```

```python
# core/timer.py（节选骨架）
from .events import EventBus, GameEvent
from kivy.clock import Clock  # 注意：core 不应依赖 kivy！见下方说明

# ⚠ 修正：core 零 Kivy 依赖，故用标准库调度，由表现层驱动 tick：
import threading, time
class GameTimer:
    def __init__(self, bus: EventBus):
        self.bus, self.elapsed, self._running = bus, 0, False
    def start(self): self._running = True
    def pause(self): self._running = False          # on_pause 调用
    def resume(self):                               # on_resume 调用
        if not self.game_over: self._running = True
    def stop(self): self._running = False
    @property
    def elapsed(self): return min(self._elapsed, 999)
    # 每秒由表现层 Clock 或线程调用 _tick() → bus.emit(TICK,{elapsed})
```

> ⚠ **core 零 Kivy 依赖提醒**：`GameTimer` 的「每秒」调度由 `presentation` 用 Kivy `Clock` 驱动（或 `threading.Timer`），**core 内不得 `import kivy`**。上例 `from kivy.clock` 仅为示意，实际调度在表现层。

```python
# core/game.py（GameSession 编排骨架）
from .board import Board
from .timer import GameTimer
from .events import EventBus
from .config import LEVELS, DAILY_CONFIG
from .daily import DailyProvider
from .storage import JsonStorage, StorageBackend

class GameSession:
    def __init__(self, bus=None, storage=None):
        self.bus = bus or EventBus()
        self.storage = storage or JsonStorage(StorageBackend.base_dir())
        self.timer = GameTimer(self.bus)
        self.board = None

    def new_game(self, level="初级", custom=None):
        cfg = custom or LEVELS[level]
        self.board = Board(cfg["rows"], cfg["cols"], cfg["mines"],
                           question_enabled=self.storage.get_setting("question_enabled", True))
        self.timer = GameTimer(self.bus); self.timer.start()
        self.bus.emit(GameEvent.NEW_GAME, {"level": level})

    def start_daily(self, date=None):
        date = date or datetime.date.today()
        rng = DailyProvider.make_rng(date)          # random.Random(seed)
        cfg = DailyProvider.config()                # 16×16/40
        self.board = Board(cfg["rows"], cfg["cols"], cfg["mines"], rng=rng,
                           question_enabled=...)
        self.timer.start()

    # reveal/chord/cycle_mark 转发到 self.board，并驱动 timer/achievements 通过事件
```

### 6.3 Kivy main.py 线框（生命周期 + 手势分发 + 底部 HUD）

```python
# app/main.py
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.clock import Clock
from core.game import GameSession
from core.events import EventBus, GameEvent
from presentation.ui.board_widget import BoardWidget
from presentation.ui.hud import HudBar
from presentation.touch.interaction import TouchDispatcher

class MineSweeperApp(App):
    def build(self):
        self.bus = EventBus()
        self.session = GameSession(bus=self.bus)
        self.session.new_game("初级")

        root = BoxLayout(orientation="vertical")
        self.board_widget = BoardWidget(session=self.session, bus=self.bus)
        self.hud = HudBar(session=self.session, bus=self.bus)   # 底部 HUD
        root.add_widget(self.board_widget)                      # 上：棋盘
        root.add_widget(self.hud)                              # 下：HUD（P2 底部化）

        # 手势分发：tap / 长按350ms / 双击300ms
        self.dispatcher = TouchDispatcher(self.board_widget, self.session, self.bus)
        self._tick_evt = Clock.schedule_interval(self._on_tick, 1.0)  # 驱动 timer
        return root

    def _on_tick(self, dt):
        if self.session.timer._running:
            self.session.timer._elapsed += 1
            self.bus.emit(GameEvent.TICK, {"elapsed": self.session.timer.elapsed})

    # ---- Android 生命周期（R6）----
    def on_pause(self):
        self.session.timer.pause()
        self.session.storage.save(self.session.storage._cache)  # 强制 flush
        return True                     # True=允许挂起
    def on_resume(self):
        self.session.timer.resume()

if __name__ == "__main__":
    MineSweeperApp().run()
```

> 手势分发（`presentation/touch/interaction.py`）关键逻辑：
> - `on_touch_down`：记录 `(cell, t)`，起 350ms `Clock` 计时（长按进度 + haptic）；<350ms 抬起 = tap。
> - tap：若 `tool_mode==mark`（模式按钮开启）且默认标记 → `cycle_mark`；否则 `reveal`。双击同格（≤300ms）且 `revealed and number>0` → `chord`。
> - 长按到阈值 → `cycle_mark`（消费该次 down，不触发 tap）。与模式按钮**并存不互斥**（system-design §2.2 边界 8）。

### 6.4 测试策略（落地要点）

**core 单测（pytest，`app/tests/test_core/`）**
- `test_board.py`：首击安全（3×3 无雷）；显式栈洪水与递归参考实现**结果一致**；chord 成功/条件不足；cycle_mark 三态与 `question_enabled` 退化；check_win/lose；边界（自定义过小拒绝、`flagged` 优先于 `revealed`、胜利后自动插旗）。
- `test_timer.py`：封顶 999；`pause/resume` 冻结/恢复 `elapsed`；每秒 `emit TICK`。
- `test_daily.py`：同 seed + 同首击 → `board` 完全相同（确定性）；自由首击安全；不混用全局 random。
- `test_storage.py`：`.tmp`+`os.replace` 原子写；文件损坏/缺失回退默认；`version` 低版补字段。
- `test_achievements.py`：WIN 解锁且幂等；阈值（60s/20chord/50flag）触发；`game_over` 后撤销不影响已结算。
- `test_events.py`：`subscribe/emit/clear` 单向；`board` 不 import 成就（可静态断言）。

**UI 烟雾测试（`app/tests/test_ui/`）**
- 用 Kivy headless（`KIVY_WINDOW=headless` 或 CI 下 `xvfb` + `sdl2`）启动 `MineSweeperApp`。
- 断言：`board_widget` 渲染格数 == `rows*cols`；HUD 显示雷数/计时/笑脸。
- 模拟 tap → `board.revealed` 变更；长按 → `flagged` 置位；双击数字格 → `chord` 触发。
- `on_pause`→改状态→`on_resume`：棋盘与 `elapsed` 保持。
- 覆盖率门禁：`core` ≥ 90%；UI 仅烟雾（不卡覆盖率）。

---

## 7. ADR 索引（同目录）

| 文件 | 主题 | 决策 |
|---|---|---|
| `adr-01-kivy-ui-framework.md` | Kivy 作为安卓 UI 框架 | 选中 Kivy（对比 BeeWare/Flutter/Web 打包 apk） |
| `adr-02-single-canvas-board.md` | 单 Canvas / 单 Widget 棋盘重绘 | 选中单 Widget+Canvas 增量重绘（解 R3） |
| `adr-03-logic-ui-decoupling-eventbus.md` | 逻辑/UI 解耦 + 事件总线 | 选中事件总线，成就纯监听（核心数值不动） |
| `adr-04-android-storage.md` | Android 存储封装 | 内部存储 `app.user_data_dir` + JSON 原子写容错 |
| `adr-05-floodfill-explicit-stack.md` | 洪水显式栈 | 选中显式栈 BFS（防 Android 递归栈溢出） |

---

*—— 程基岩 / 工程负责人 · Phase 3 Lean 评审稿 · 落盘 `E:/youxi/docs/architecture/`*
