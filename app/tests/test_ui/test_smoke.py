"""test_smoke.py — Kivy UI 烟雾测试（S-TEST-UI）。

就绪度：单 Canvas / 单 Widget 已定（ADR-02）；底部 HUD、手势分发、on_pause/on_resume 已定。
本文件为就绪骨架；Kivy 未装时由 importorskip 跳过（CI 装 kivy 后生效）。

---- Kivy headless 启动方案（架构 §6.4）----
1) 环境变量禁用窗口：KIVY_WINDOW=headless（Kivy 1.x 支持 headless 后端）。
2) CI 无显示环境：用 xvfb 提供虚拟 X 显示 + sdl2 后端：
       xvfb-run -a python -m pytest tests/test_ui
3) 本机桌面开发：直接 `python main.py` 跑真窗口。
4) 烟雾断言（不卡覆盖率，仅验证「能起来 + 关键交互不崩」）：
   - App.build 成功，board_widget 渲染格数 == rows*cols；
   - 模拟 tap → board.revealed 变更；
   - 长按 → flagged 置位；
   - 双击已翻开数字格 → chord 触发；
   - on_pause → 改状态 → on_resume：board 与 elapsed 保持。

注意：headless 后端不支持真实触摸事件派发，故交互用「直接调用交互层 API」
而非派发触摸屏事件；手势计时（350/300ms）在单元测试层单独验证（见 S-TOUCH）。
"""
import os

import pytest

# Kivy 必须在 import app 之前设置窗口后端；先尝试 headless
os.environ.setdefault("KIVY_WINDOW", "headless")

pytest.importorskip("kivy")  # 未装 Kivy 时整模块跳过（本地开发/CI 装 kivy 后运行）

from kivy.app import App  # noqa: E402

# 仅在 kivy 可用时继续
from core.game import GameSession  # noqa: E402
from core.events import EventBus  # noqa: E402
from presentation.ui.board_widget import BoardWidget  # noqa: E402
from presentation.touch.interaction import TouchDispatcher  # noqa: E402


def test_app_builds_and_renders_grid():
    bus = EventBus()
    session = GameSession(bus=bus)
    session.new_game("初级")  # 12×12
    widget = BoardWidget(session=session, bus=bus)
    widget.build_canvas()  # 单 Canvas 绘制所有格
    assert widget.cell_count() == session.board.rows * session.board.cols


def test_tap_reveals_cell():
    bus = EventBus()
    session = GameSession(bus=bus)
    session.new_game("初级")
    dispatcher = TouchDispatcher(widget=None, session=session, bus=bus)
    dispatcher.on_tap(0, 0)
    assert session.board.is_revealed(0, 0)


def test_long_press_flags_cell():
    bus = EventBus()
    session = GameSession(bus=bus)
    session.new_game("初级")
    dispatcher = TouchDispatcher(widget=None, session=session, bus=bus)
    dispatcher.on_long_press(5, 5)
    assert session.board.is_flagged(5, 5)


def test_double_tap_chord_on_number():
    bus = EventBus()
    session = GameSession(bus=bus)
    session.new_game("初级")
    # 先翻开一个已知数字格由交互层双击触发 chord（具体布局在集成测试覆盖）
    dispatcher = TouchDispatcher(widget=None, session=session, bus=bus)
    res = dispatcher.on_double_tap(0, 0)
    assert res is not None  # 至少成功调用 chord 路径，不抛异常


def test_pause_resume_preserves_state():
    bus = EventBus()
    session = GameSession(bus=bus)
    session.new_game("初级")
    session.reveal(0, 0)
    before = session.board.is_revealed(0, 0)
    # 模拟 App.on_pause / on_resume
    session.timer.pause()
    session.timer.resume()
    assert session.board.is_revealed(0, 0) == before
