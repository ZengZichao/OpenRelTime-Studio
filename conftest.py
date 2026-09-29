"""Pytest 收集守卫。

GUI 夹具在 ``openreltime_studio/tests/conftest.py`` 里（随包发行，安装后也能
单独跑测试）。根级只保留一件事：没装 PySide6（可选的 GUI 依赖）时跳过 GUI
用例的收集，而不是让整个 run 报错。
"""

from __future__ import annotations

try:  # pragma: no cover - 环境相关
    import PySide6  # noqa: F401

    _HAVE_PYSIDE = True
except ImportError:
    _HAVE_PYSIDE = False

collect_ignore_glob = [] if _HAVE_PYSIDE else ["openreltime_studio/tests"]
