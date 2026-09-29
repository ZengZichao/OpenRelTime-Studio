"""GUI 用例的公共夹具。

放在包内而不是仓库根，测试才能随发行版一起运行
（``python -m pytest --pyargs openreltime_studio.tests``）。

构造任何 QWidget 之前必须先有 ``QApplication``，否则进程直接 abort；
没装 PySide6 时则跳过整个目录的收集。
"""

from __future__ import annotations

import os

try:  # pragma: no cover - 环境相关
    import PySide6  # noqa: F401

    _HAVE_PYSIDE = True
except ImportError:
    _HAVE_PYSIDE = False

collect_ignore_glob = [] if _HAVE_PYSIDE else ["test_*.py", "smoke_gui.py"]

if _HAVE_PYSIDE:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import pytest

    @pytest.fixture(scope="session", autouse=True)
    def qapp():
        """会话级 ``QApplication``：控件构造与语言/主题切换都依赖它。"""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        app.setStyle("Fusion")
        yield app
