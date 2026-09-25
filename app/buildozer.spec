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
orientation = sensor          # 支持横竖屏（UX §2.5：旋转不重置对局）
fullscreen = 0

# ---- 权限 ----
# ADR-04：仅用内部存储（app.user_data_dir），**不需要**任何权限
android.permissions =

# ---- Android 目标 ----
android.api = 33
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

# ---- 图标（可选，缺失时 buildozer 用默认图标）----
# icon.filename = %(source.dir)s/data/icon.png
# presplash.filename = %(source.dir)s/data/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1

# 本机 Win10/4GB 不推荐本地构建（内存与 WSL2 编译压力大）；
# apk 构建走云 CI（GitHub Actions / Codemagic），见 .github/workflows/ci.yml
