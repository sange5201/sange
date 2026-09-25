# ADR-05：洪水展开采用显式栈（防 Android 递归栈溢出）

- **状态**：Accepted
- **日期**：Phase 3
- **作者**：程基岩（工程负责人）
- **关联**：风险 R4（递归洪水栈溢出）、系统设计 §1.4/§2.1、架构 `architecture.md` §3.2①

## 上下文（Context）

`minesweeper.py` 的 `reveal()` 用**递归**展开 0 值邻域：
```python
def reveal(self, r, c):
    if not in_bounds or revealed or flagged: return
    revealed[r][c] = True; refresh_cell(...)
    if board==-1: lose_game; return
    if board==0:
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                self.reveal(r+dr, c+dc)   # 递归
```

在「地狱」30×30 大空区，一次首击可能展开数百格，**递归深度可达数百**。Android 上的 CPython 与桌面**共用默认递归上限 `sys.getrecursionlimit()` ≈ 1000**，但移动端 C 栈更小，深度递归极易触发 `RecursionError` 甚至 C 级栈溢出崩溃（概念文档 R4：移动端 Python 递归上限，大空区崩溃）。

目标：保持洪水语义**完全等价**，消除递归深度风险。

## 决策（Decision）

**将 `reveal()` 改写为显式栈（iterative BFS / DFS），用 `list` 作栈，零递归：**
```python
def reveal(self, r, c):
    changed = []
    stack = [(r, c)]
    while stack:
        cr, cc = stack.pop()
        if not (0 <= cr < rows and 0 <= cc < cols): continue
        if revealed[cr][cc] or flagged[cr][cc]: continue
        revealed[cr][cc] = True; changed.append((cr, cc))
        if board[cr][cc] == -1:
            self.lose_game(cr, cc)
            return {"result": "lose", "changed": changed, "triggered": (cr, cc)}
        if board[cr][cc] == 0:               # 仅 0 值格继续展开邻域
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0: continue
                    stack.append((cr + dr, cc + dc))
    return {"result": "reveal", "changed": changed, "triggered": None}
```
语义与原递归**逐格一致**：0 值格展开邻域、数字格不递归、雷格触发失败、`flagged` 优先跳过。`chord()` 复用 `reveal` 连锁，无需改递归。

## 备选方案与权衡（Alternatives Considered）

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **显式栈（选中）** | 无递归深度上限，彻底防栈溢出；语义等价；内存可控（栈长 ≤ 格数） | 需重写（一次性） | **采用** |
| 调高 `sys.setrecursionlimit` | 改动最小 | 治标不治本：C 栈仍可能溢出导致**进程崩溃**（非可捕获异常）；Android C 栈更小，更危险 | 弃：脆弱、有崩溃风险 |
| 分块/迭代混合 | 略 | 复杂且无必要；显式栈已足够清晰 | 弃：过度 |

## 后果（Consequences）

- **正面**：
  - 彻底消除 R4 崩溃风险，30×30 大空区安全展开。
  - 语义等价保证 P1 数值规则不变（洪水展开行为一致）；单测可与递归参考实现对照（架构 §6.4 `test_board`）。
  - `changed` 列表天然支持表现层增量重绘（ADR-02）与洪水级联动画（美术圣经 §7）。
- **负面/约束**：
  - 旧代码 `reveal` 内的 `refresh_cell` 调用上移为「返回 changed，由表现层重绘」，符合 core 零 UI 依赖原则（ADR-03）。
  - 须保留 `board==0` 才入栈的判定（数字格不入栈，避免无意义展开），与原递归一致。

## 参考（References）
- `architecture.md` §3.2①（改写点）、§4.1（R4 缓解）、§6.4（test_board 等价性）
- 系统设计 §1.4（R4 说明）、§2.1 算法（reveal 显式栈）
- 概念文档 §7 R4
