"""presentation/ui/onboarding.py — 首玩引导 3 步（闭环 Phase 2 认知过载⚠）。

UX §4：首启触发（`onboarded` 未置位）、可跳过、完成写 `onboarded=true`。
三步内容（UX §4.2）：
    1) 点按翻开
    2) 长按约 0.3 秒 → 插旗 / 循环标记
    3) 快速双击数字格 → 连开（chord）
"""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

STEPS = [
    "第 1 步 / 共 3 步\n\n轻点一格 → 翻开它\n（首击保证安全，绝不踩雷）",
    "第 2 步 / 共 3 步\n\n按住一格约 0.3 秒 → 插旗\n再按住可循环：旗 → ? → 无",
    "第 3 步 / 共 3 步\n\n对已翻开数字格快速双击 → 连开周围\n（旗数 = 数字时才会连开）",
]


class OnboardingOverlay(ModalView):
    """三步引导覆盖层。完成或跳过后回调 `on_finish(completed: bool)`。"""

    def __init__(self, steps=None, on_finish=None, **kwargs):
        kwargs.setdefault("size_hint", (0.92, 0.55))
        kwargs.setdefault("pos_hint", {"center_x": 0.5, "center_y": 0.5})
        kwargs.setdefault("auto_dismiss", False)      # 必须显式完成/跳过
        kwargs.setdefault("background_color", (0, 0, 0, 0.72))
        super().__init__(**kwargs)
        self.steps = list(steps or STEPS)
        self.on_finish = on_finish
        self.index = 0

        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        self.label = Label(text=self.steps[0], halign="center", valign="middle")
        root.add_widget(self.label)

        bar = BoxLayout(orientation="horizontal", spacing=dp(10),
                        size_hint=(1, None), height=dp(52))
        skip = Button(text="跳过")
        skip.bind(on_release=lambda *_: self._done(False))
        self.next_btn = Button(text="知道了")
        self.next_btn.bind(on_release=lambda *_: self.next())
        bar.add_widget(skip)
        bar.add_widget(self.next_btn)
        root.add_widget(bar)
        self.add_widget(root)

    def next(self) -> None:
        """下一步；最后一步后完成。"""
        self.index += 1
        if self.index >= len(self.steps):
            self._done(True)
            return
        self.label.text = self.steps[self.index]
        if self.index == len(self.steps) - 1:
            self.next_btn.text = "开始游戏"

    def _done(self, completed: bool) -> None:
        self.dismiss()
        if self.on_finish is not None:
            self.on_finish(completed)
