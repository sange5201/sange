"""platform/android_bridge.py — Android 平台适配（存储路径 + 触感）。

ADR-04：Android 内部存储 `app.user_data_dir`（免权限）。
- 解析顺序：Android `mActivity.getFilesDir()` → Kivy 运行中 App 的
  `user_data_dir` → None（桌面沿用 core 默认 `~/MineSweeper`）。
- core 永不 import 本模块：由 main.py 在 `on_start` 注入 `StorageBackend`。

触感（UX §3.2 长按反馈）：Android Vibrator 服务，桌面静默降级。
"""
import os


def android_user_data_dir():
    """Android 内部存储目录；非 Android 返回 None。"""
    try:
        from android import mActivity          # p4a 提供的模块
        path = mActivity.getFilesDir().getAbsolutePath()
        return str(path)
    except Exception:
        return None


def kivy_user_data_dir():
    """Kivy 运行中 App 的 user_data_dir（桌面 / Android 均可用）。"""
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app is not None:
            return str(app.user_data_dir)
    except Exception:
        return None
    return None


def resolve_base_dir():
    """解析存储根目录（ADR-04）。返回 None 表示沿用 core 默认。"""
    return android_user_data_dir() or kivy_user_data_dir()


def bind_storage():
    """把解析到的路径注入 core 的 StorageBackend。返回实际目录。"""
    from core.storage import StorageBackend
    path = resolve_base_dir()
    if path:
        StorageBackend.set_base_dir(path)
        return StorageBackend.base_dir()
    return StorageBackend.base_dir()


def vibrate(ms: int = 15) -> bool:
    """轻震动反馈（长按命中 / 踩雷）。桌面无 Vibrator → 静默返回 False。"""
    try:
        from jnius import autoclass            # noqa: F401  pyjnius（p4a 提供）
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Context = autoclass("android.content.Context")
        vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
        if vibrator is None:
            return False
        vibrator.vibrate(int(ms))
        return True
    except Exception:
        return False


def is_android() -> bool:
    """是否运行在 Android（供 UI 决定是否显示 android-only 选项）。"""
    return ("ANDROID_ARGUMENT" in os.environ) or (android_user_data_dir() is not None)
