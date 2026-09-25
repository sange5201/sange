# ADR-01：采用 Kivy 作为安卓 UI 框架

- **状态**：Accepted
- **日期**：Phase 3
- **作者**：程基岩（工程负责人）
- **关联**：概念文档 §1（内核可完整复用）、系统设计 §1.1、架构 `architecture.md` §1

## 上下文（Context）

本期目标是把 `minesweeper.py`（24KB 单文件 Tkinter）的玩法逻辑搬到安卓，打包 apk，本期聚焦 Android。现有内核 100% 是纯 Python（布雷/洪水/chord/判定/计时/持久化），**仅 UI 层（Tkinter Canvas 绘制 + 鼠标事件）需重写**。需在以下候选中选定安卓 UI 技术：

- **Kivy**：Python 跨平台 UI 框架，自带 Canvas/`Widget`/`Clock`，通过 python-for-android / buildozer 打包 apk。
- **BeeWare（Toga）**：Python 原生 UI，也走 python-for-android。
- **Flutter**：Dart 框架，打包 apk 成熟，但需把全部逻辑用 Dart 重写。
- **Web（PWA / pyodide）**：浏览器打包，非原生 apk。

## 决策（Decision）

**采用 Kivy。** 理由优先级：

1. **内核零重写**：core 逻辑包（纯 Python）可直接被 Kivy App `import`，无需跨语言移植——这是最大 ROI（概念文档 §0 结论 1、P1 红线要求数值逐字节一致）。
2. **程序化像素绘制契合美术圣经**：美术圣经要求「零位图资产、Canvas 矢量图元、硬边抗锯齿关闭」还原 3D bevel / 红旗 / 地雷 / 笑脸。Kivy `Canvas`（Line/Rectangle/Ellipse/Triangle/Polygon）可直接移植 `minesweeper.py` 的归一化坐标绘制函数，且支持 `mag_filter='nearest'` 保持硬边；BeeWare/Toga 的绘图 API 对精细像素 Canvas 控制不如 Kivy 成熟。
3. **移动端输入与生命周期完善**：Kivy 原生支持 `on_touch_down/up/move`、`Clock` 手势计时、`App.on_pause/on_resume`（解决 R1/R6），并有 `ScrollView`/`Scatter` 应对大棋盘缩放平移（R2）。
4. **打包链路成熟**：buildozer 一键产出 apk，社区对 python-for-android 的 recipe 完善。

## 备选方案与权衡（Alternatives Considered）

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **Kivy**（选中） | 内核零移植；Canvas 还原像素美术；手势/生命周期/ScrollView 完善；buildozer 成熟 | apk 体积偏大（含 Python 运行时 ~10–15MB）；纯 Python 性能不及原生 | **采用** |
| BeeWare / Toga | 更原生外观；同为 Python | 绘图 API 对像素 Canvas 控制弱；生态较新，移动端坑多；社区 recipe 少 | 弃：不满足美术圣经程序化像素绘制要求 |
| Flutter | 原生性能、apk 小、热重载好 | **必须 Dart 重写全部内核**，违反「逻辑复用 + P1 数值一致」且工作量巨大 | 弃：内核重写成本不可接受 |
| Web / PWA / pyodide | 跨平台、免安装 | 非真正 apk；pyodide 体积巨大、离线差、触屏手势需自行桥接 | 弃：与「打包 apk、聚焦 Android」目标不符 |

## 后果（Consequences）

- **正面**：core 逻辑直接复用，P1 数值内核零风险；美术圣经的程序化像素哲学可在 Kivy Canvas 完整落地；R1/R2/R6 有现成 API 支撑。
- **负面/约束**：
  - apk 体积需接受（~15–30MB），本期纯免费无内购，体积非硬性 KPI。
  - 须注意 `core/` 零 Kivy 依赖（见 ADR-03）；`GameTimer` 的秒级调度在表现层用 `Clock` 驱动，core 内不得 `import kivy`。
  - 本机 Win10/4GB：本地只跑桌面 `python main.py` 开发与单测；**apk 实际构建走云 CI**（见 `architecture.md` §6.3），不在本机硬扛 buildozer 编译。

## 参考（References）
- `architecture.md` §1 分层、§6.3 打包方案
- 美术圣经 §3/§4（程序化像素绘制）、附录 A（手势映射）
- 概念文档 §1（内核可复用）、§7 风险 R1/R2/R6
