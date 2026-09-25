"""presentation/ui/hud.py — 底部 HUD（笑脸 / LCD 雷数 / LCD 计时 / 工具行）。

UX §2.4：高频操作全底部化（R5 单手可达）
- Row1（56dp）：[剩余雷数 LCD] [笑脸重开] [计时 LCD]
- Row2（48dp）：[撤销] [模式切换 挖掘/标记] [最佳成绩]

LCD 与笑脸均由 icons.py 程序化绘制（七段数码管 + 像素笑脸），零位图。
"""
from kivy.graphics import InstructionGroup
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget

from presentation.ui import icons
from presentation.ui.layout import HUD_ROW1_DP, HUD_ROW2_DP, MIN_TAP_DP


class LcdDisplay(Widget):
    """七段数码管计数器（黑底红字，经典扫雷）。"""

    value = NumericProperty(0)
    digits = NumericProperty(3)
    theme_name = StringProperty("light")

    def __init__(self, value=0, digits=3, theme="light", **kwargs):
        super().__init__(**kwargs)
        self.theme_name = theme
        self.digits = digits
        self.value = value
        self.size_hint = (None, None)
        self.size = (dp(30) * digits, dp(38))
        self.bind(value=self._redraw, digits=self._redraw,
                  theme_name=self._redraw, pos=self._redraw, size=self._redraw)

    def _redraw(self, *args) -> None:
        self.canvas.clear()
        c = icons.theme_colors(self.theme_name)
        grp = InstructionGroup()
        icons.draw_lcd(grp, int(self.value), self.x, self.y,
                       self.width, self.height, c["lcd_fg"], c["lcd_bg"],
                       digits=int(self.digits))
        self.canvas.add(grp)


class FaceButton(ButtonBehavior, Widget):
    """笑脸重开按钮（四态：smile / wow / cool / dead）。"""

    face_state = StringProperty("smile")
    theme_name = StringProperty("light")

    def __init__(self, theme="light", on_press_cb=None, **kwargs):
        super().__init__(**kwargs)
        self.theme_name = theme
        self.face_state = "smile"
        self.on_press_cb = on_press_cb
        self.size_hint = (None, None)
        self.size = (dp(MIN_TAP_DP), dp(MIN_TAP_DP))
        self.bind(face_state=self._redraw, theme_name=self._redraw,
                  pos=self._redraw, size=self._redraw)

    def on_release(self):
        if self.on_press_cb is not None:
            self.on_press_cb()

    def _redraw(self, *args) -> None:
        self.canvas.clear()
        c = icons.theme_colors(self.theme_name)
        grp = InstructionGroup()
        icons.draw_face(grp, self.x, self.y, self.width,
                        c["yellow"], c["black"], self.face_state)
        self.canvas.add(grp)


class HudBar(BoxLayout):
    """底部 HUD 容器（Row1 + Row2，共 104dp）。"""

    def __init__(self, session=None, bus=None, theme="light",
                 on_face=None, on_undo=None, on_toggle_mode=None,
                 show_toolbar: bool = True, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.session = session
        self.bus = bus
        self.theme_name = theme
        self.size_hint = (1, None)
        self.height = dp(HUD_ROW1_DP + HUD_ROW2_DP)

        # ---- Row1：LCD 雷数 | 笑脸 | LCD 计时 ----
        row1 = BoxLayout(orientation="horizontal", size_hint=(1, None),
                         height=dp(HUD_ROW1_DP), padding=dp(8), spacing=dp(8))
        self.mine_lcd = LcdDisplay(value=0, digits=3, theme=theme)
        self.face = FaceButton(theme=theme, on_press_cb=on_face)
        self.time_lcd = LcdDisplay(value=0, digits=3, theme=theme)
        row1.add_widget(self.mine_lcd)
        row1.add_widget(Widget())                 # 弹性间隔（笑脸居中）
        row1.add_widget(self.face)
        row1.add_widget(Widget())
        row1.add_widget(self.time_lcd)
        self.add_widget(row1)

        # ---- Row2：撤销 | 模式切换 | 最佳 ----
        self.row2 = BoxLayout(orientation="horizontal", size_hint=(1, None),
                              height=dp(HUD_ROW2_DP), padding=dp(8), spacing=dp(8))
        self.undo_btn = Button(text="撤销", size_hint=(None, None),
                               size=(dp(72), dp(MIN_TAP_DP)))
        self.undo_btn.bind(on_release=lambda *_: on_undo() if on_undo else None)
        self.mode_btn = Button(text="挖掘", size_hint=(None, None),
                               size=(dp(72), dp(MIN_TAP_DP)))
        self.mode_btn.bind(on_release=lambda *_: on_toggle_mode() if on_toggle_mode else None)
        self.best_btn = Button(text="最佳 —", size_hint=(1, None),
                               height=dp(MIN_TAP_DP))
        self.row2.add_widget(self.undo_btn)
        self.row2.add_widget(self.mode_btn)
        self.row2.add_widget(self.best_btn)
        self.row2.opacity = 1 if show_toolbar else 0
        self.row2.disabled = not show_toolbar
        self.add_widget(self.row2)

    # ------------------------------------------------------------------
    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self.mine_lcd.theme_name = name
        self.time_lcd.theme_name = name
        self.face.theme_name = name

    def set_toolbar_visible(self, visible: bool) -> None:
        """toolbar_mode 开关（UX §3.5 T1：默认 true）。

        隐藏时整条 HUD 收起 Row2 高度（棋盘区相应变高）。
        """
        self.row2.opacity = 1 if visible else 0
        self.row2.disabled = not visible
        self.height = dp(HUD_ROW1_DP + (HUD_ROW2_DP if visible else 0))

    def set_mode_text(self, mode: str) -> None:
        self.mode_btn.text = "标记" if mode == "dig" else "挖掘"

    def set_face(self, state: str) -> None:
        self.face.face_state = state

    def set_best_text(self, text: str) -> None:
        self.best_btn.text = text

    def refresh(self) -> None:
        """从 session 同步雷数 / 计时 / 笑脸 / 最佳。"""
        if self.session is None:
            return
        b = self.session.board
        if b is not None:
            self.mine_lcd.value = b.remaining_mines()
        self.time_lcd.value = self.session.timer.elapsed
