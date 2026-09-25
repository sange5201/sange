"""presentation — Kivy 表现层（渲染 + 手势）。

依赖方向（ADR-03，单向）：presentation → core。
core 永不 import 本包；本包各模块除标注外均不反向依赖 core 内部实现细节，
仅通过 GameSession / EventBus 公开接口交互。

子包：
- touch/：手势识别（gesture.py 纯逻辑，零 Kivy；interaction.py 绑定 Kivy 事件）
- ui/：单 Canvas 棋盘（ADR-02）、底部 HUD、难度抽屉、设置/成就墙、首玩引导
"""
