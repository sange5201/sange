"""platform — Android / 桌面平台适配层。

- android_bridge.py：内部存储路径解析（ADR-04）+ 触感反馈（震动）

本层是唯一允许触碰 Android API（jnius/pyjnius）的地方；core 永不 import 本层，
路径由 main.py 在 on_start 注入 `StorageBackend.set_base_dir()`。
"""
