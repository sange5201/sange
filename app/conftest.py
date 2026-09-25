"""app/conftest.py — 让 `core` / `presentation` 在 pytest 下可直接 import。

pytest 以本文件所在目录（app/）为 rootdir；将其加入 sys.path 首部，
使 `from core.xxx import ...` 在 tests/ 下任意测试文件中可用，无需安装包。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
