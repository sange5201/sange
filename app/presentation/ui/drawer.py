"""presentation/ui/drawer.py — 难度抽屉（10 档 + 自定义）。

UX §2：难度切换走**底部抽屉**（低频导航在顶部入口，选择面板从底部滑入）。
数值真源 = `core.config.LEVELS`（README 旧表已作废，system-design C1）。
自定义输入用 `core.config.validate_level` 校验（首击安全上限 rows*cols-9）。
"""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.textinput import TextInput

from core.config import LEVELS, MIN_CUSTOM, MAX_CUSTOM, max_mines


class LevelDrawer(ModalView):
    """底部难度抽屉。回调 `on_pick(level_name, custom_dict_or_None)`。"""

    def __init__(self, on_pick=None, current="初级", **kwargs):
        kwargs.setdefault("size_hint", (1, None))
        kwargs.setdefault("height", dp(430))
        kwargs.setdefault("pos_hint", {"x": 0, "y": 0})
        kwargs.setdefault("auto_dismiss", True)
        super().__init__(**kwargs)
        self.on_pick = on_pick

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

        root.add_widget(Label(text="选择难度", size_hint=(1, None), height=dp(32)))

        grid = GridLayout(cols=3, spacing=dp(8), size_hint=(1, None), height=dp(210))
        self.level_btns = {}
        for name, cfg in LEVELS.items():
            if cfg.get("custom"):
                continue
            txt = f"{name}\n{cfg['rows']}×{cfg['cols']}·{cfg['mines']}"
            btn = Button(text=txt, halign="center")
            btn.bind(on_release=lambda b, n=name: self._pick(n, None))
            self.level_btns[name] = btn
            grid.add_widget(btn)
        root.add_widget(grid)

        # ---- 自定义 ----
        root.add_widget(Label(text=f"自定义（{MIN_CUSTOM}–{MAX_CUSTOM}，"
                                   f"雷数 ≤ 格数-9）",
                              size_hint=(1, None), height=dp(28)))
        form = BoxLayout(orientation="horizontal", spacing=dp(8),
                         size_hint=(1, None), height=dp(56))
        self.in_rows = TextInput(text="16", input_filter="int", multiline=False)
        self.in_cols = TextInput(text="16", input_filter="int", multiline=False)
        self.in_mines = TextInput(text="40", input_filter="int", multiline=False)
        for hint, ti in (("行", self.in_rows), ("列", self.in_cols), ("雷", self.in_mines)):
            box = BoxLayout(orientation="vertical", spacing=dp(4))
            box.add_widget(Label(text=hint, size_hint=(1, None), height=dp(20)))
            box.add_widget(ti)
            form.add_widget(box)
        root.add_widget(form)

        self.hint = Label(text="", size_hint=(1, None), height=dp(28))
        root.add_widget(self.hint)

        bar = BoxLayout(orientation="horizontal", spacing=dp(8),
                        size_hint=(1, None), height=dp(48))
        ok = Button(text="开始自定义")
        ok.bind(on_release=lambda *_: self._pick_custom())
        cancel = Button(text="取消")
        cancel.bind(on_release=lambda *_: self.dismiss())
        bar.add_widget(cancel)
        bar.add_widget(ok)
        root.add_widget(bar)

        self.add_widget(root)

    # ------------------------------------------------------------------
    def _pick(self, name, custom) -> None:
        self.dismiss()
        if self.on_pick is not None:
            self.on_pick(name, custom)

    def _pick_custom(self) -> None:
        """校验自定义输入；非法则原地提示，不关闭抽屉。"""
        from core.config import validate_level
        try:
            rows = int(self.in_rows.text or 0)
            cols = int(self.in_cols.text or 0)
            mines = int(self.in_mines.text or 0)
        except ValueError:
            self.hint.text = "请输入数字"
            return
        ok, msg = validate_level(rows, cols, mines)
        if not ok:
            self.hint.text = msg
            return
        self.hint.text = ""
        self._pick("自定义", {"rows": rows, "cols": cols, "mines": mines})
