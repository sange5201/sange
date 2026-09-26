[app]

# ---- 基础信息 ----
title = 扫雷
package.name = minesweeper
package.domain = org.qishuo.minesweeper
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = tests, build, dist, .buildozer
source.exclude = *.pyc, *.pyo, *~
version = 0.2.0
requirements = python3,kivy
# 版本钉定（架构建议 Kivy 2.3.x + Python 3.11；与 CI 的 setup-python 3.11 对齐）
# p4a 配方默认拉取 3.11 系列；显式声明避免漂移。
android.python_version = 3.11

# ---- 入口 ----
# buildozer 默认入口即 source.dir 下的 main.py，无需额外声明

# ---- 界面 ----
# 注意：buildozer 1.5.0 的 orientation 校验清单只有
# landscape/portrait/landscape-reverse/portrait-reverse 四种，不认 sensor/fullSensor。
# 故 orientation 仅填 portrait 通过校验；真正的自由旋转用 android.manifest.orientation
# = fullSensor（四向随传感器旋转，符合 UX §2.5：旋转不重置对局）。
orientation = portrait
android.manifest.orientation = fullSensor
fullscreen = 0

# ---- 权限 ----
# ADR-04：仅用内部存储（app.user_data_dir），**不需要**任何权限
android.permissions =

# ---- Android 目标 ----
android.api = 33
# minapi 24：稳妥下限（Python 3.11 在 Android 6.0 已覆盖绝大部分设备）。
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
# 复用云 CI（GitHub ubuntu runner）预装的完整 Android SDK，避免 buildozer 自建 SDK
# 时 cmdline-tools/sdkmanager 路径不被 p4a 识别。
android.sdk_path = /usr/local/lib/android/sdk
# 钉定 p4a 到 v2024.1.21：该版本 python3 配方默认 Python 3.11（Kivy/pyjnius/android
# 生态齐全）。buildozer 默认 clone 的 p4a master 锁了 Python 3.14，导致 pyjnius 等
# 无 cp314 轮子、构建失败。
p4a.branch = v2024.1.21

# ---- 图标（可选，缺失时 buildozer 用默认图标）----
# icon.filename = %(source.dir)s/data/icon.png
# presplash.filename = %(source.dir)s/data/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1

# 本机 Win10/4GB 不推荐本地构建（内存与 WSL2 编译压力大）；
# apk 构建走云 CI（GitHub Actions / Codemagic），见 .github/workflows/ci.yml
