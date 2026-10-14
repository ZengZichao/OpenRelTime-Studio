"""测试套件的能力探测：Qt 绑定与引擎发行版是否可导入。

放在包内（``openreltime_studio/tests/``）而不是仓库根，安装版
``python -m pytest --pyargs openreltime_studio.tests`` 才拿得到同一套判据。

本模块**不导入** Qt 或引擎的名字之外的任何东西：它只探测、只汇报，
绝不替调用方 import，因此可以在任何环境下安全加载。

两条判据各自对应一类跳过，粒度都是**单个测试**而不是整个目录：

``requires_qt``
    需要 Qt 绑定（构造 ``QWidget`` / ``QSettings`` / ``QPixmap``）。缺
    PySide6 时跳过，理由里给出成因与修复命令。

``requires_engine``
    需要引擎发行版 ``openreltime``。缺它时跳过；跳过是**显式**的（原因
    里点名是哪个模块、哪条 import 失败），绝不静默通过。

``pytest_report_header``（见同目录 ``conftest.py``）在每次 run 开头把两条
判据的实际结果打印出来，所以「跳过了多少、为什么」在 ``-q`` 下也看得见。
"""

from __future__ import annotations

import importlib
import os
import re
from typing import Optional

__all__ = [
    "ENGINE_DIST",
    "ENGINE_INSTALL",
    "QT_DIST",
    "QT_INSTALL",
    "HAVE_ENGINE",
    "HAVE_QT",
    "engine_problem",
    "qt_problem",
    "require_engine",
    "require_qt",
    "report_lines",
    "skip_reason_for_engine",
    "skip_reason_for_qt",
]

#: Qt 绑定的发行版名（``PySide6`` 顶层包）。
QT_DIST = "PySide6"

#: 引擎发行版名 —— 适配层唯一允许 import 的外部包。
ENGINE_DIST = "openreltime"

#: 修复 Qt 缺失的命令（与 ``pyproject.toml`` 的 ``PySide6>=6.5`` 一致）。
QT_INSTALL = 'python -m pip install "PySide6>=6.5"'

#: 修复引擎缺失的方式：装发行版，或把源码检出的仓库根目录挂进 PYTHONPATH。
ENGINE_INSTALL = (
    "python -m pip install \"openreltime[plot] @ "
    "git+https://github.com/ZengZichao/OpenRelTime.git@v0.1.0\""
)


def _probe(module: str) -> Optional[str]:
    """返回 ``None`` 表示可导入；否则返回导入失败的原始信息。"""
    try:
        importlib.import_module(module)
    except ImportError as exc:  # 只按导入错误判定，其余异常照实抛出
        return f"{type(exc).__name__}: {exc}"
    return None


#: 子进程里构造 ``QApplication`` 的最小脚本；``offscreen`` 是无头 CI 的标准平台插件。
_QT_SMOKE = (
    "import os\n"
    "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')\n"
    "from PySide6.QtWidgets import QApplication\n"
    "app = QApplication([])\n"
    "assert app is not None\n"
)


def _qt_usable() -> Optional[str]:
    """可导入 ≠ 可用：真正试着建一个 ``QApplication``，返回 ``None`` 表示可用。

    必须在**子进程**里探测。Qt 在拿不到窗口会话的环境里是直接 ``SIGABRT``
    终止进程的（不是抛 Python 异常），在本进程里探测会把 pytest 一起带走；
    子进程既保住了本模块「不在进程内导入 Qt」的性质，又能把 abort 收敛成
    一条可读的判据。结果用环境变量缓存，避免同一次 run 里重复起进程。
    """
    cached = os.environ.get("_ORT_QT_USABLE_CACHE")
    if cached is not None:
        return None if cached == "ok" else cached
    import subprocess
    import sys

    problem: Optional[str]
    try:
        run = subprocess.run(
            [sys.executable, "-c", _QT_SMOKE],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - 探测本身失败
        problem = f"{type(exc).__name__}: {exc}"
    else:
        if run.returncode == 0:
            problem = None
        else:
            lines = [ln for ln in (run.stderr or "").strip().splitlines() if ln]
            # Qt 的告警里，"two sets of Qt binaries" / "Could not load the Qt
            # platform plugin" 才是成因；末行往往只是复读可用插件清单。
            informative = next(
                (
                    ln
                    for ln in lines
                    if re.search(
                        r"two sets of Qt binaries|Could not load the Qt platform"
                        r"|failed to start|abort",
                        ln,
                        re.I,
                    )
                ),
                lines[-1] if lines else f"exit code {run.returncode}",
            )
            problem = (
                "importable, but a QApplication cannot be constructed in this "
                f"environment ({informative})"
            )
            if not os.environ.get("QT_QPA_PLATFORM"):
                problem += "; QT_QPA_PLATFORM is unset, try offscreen"
    os.environ["_ORT_QT_USABLE_CACHE"] = "ok" if problem is None else problem
    return problem


_QT_PROBLEM = _probe(QT_DIST) or _qt_usable()
_ENGINE_PROBLEM = _probe(ENGINE_DIST)

HAVE_QT = _QT_PROBLEM is None
HAVE_ENGINE = _ENGINE_PROBLEM is None


def qt_problem() -> Optional[str]:
    """Qt 绑定不可导入时的原始报错文本；可导入时为 ``None``。"""
    return _QT_PROBLEM


def engine_problem() -> Optional[str]:
    """引擎不可导入时的原始报错文本；可导入时为 ``None``。"""
    return _ENGINE_PROBLEM


def skip_reason_for_qt(nodeid: str = "") -> str:
    """``requires_qt`` 的跳过说明：点名成因与修复。"""
    where = f"（{nodeid}）" if nodeid else ""
    return (
        f"需要 Qt 绑定 {QT_DIST}{where}：本环境用不了它 —— "
        f"{_QT_PROBLEM or 'unavailable'}。该用例真的会构造 QWidget/"
        "QSettings/QPixmap，不是可选检查。修复："
        f"{QT_INSTALL}（或 python -m pip install -e \".[dev]\"）；"
        "若 PySide6 已装但本机没有窗口会话，请设 "
        "QT_QPA_PLATFORM=offscreen 或到有会话的终端下运行。"
    )


def skip_reason_for_engine(nodeid: str = "") -> str:
    """``requires_engine`` 的跳过说明：点名成因与修复。

    这里**不**允许静默通过：适配层是 Studio 唯一的计算入口，它起不来时
    必须看得见是谁的哪条 import 失败、以及两条修复路径。
    """
    where = f"（{nodeid}）" if nodeid else ""
    return (
        f"需要引擎发行版 {ENGINE_DIST}{where}：本环境无法导入它 —— "
        f"{_ENGINE_PROBLEM or 'import failed'}。适配层 "
        "openreltime_studio/adapters/openreltime_adapter.py 只通过引擎公共 "
        f"Python API 对话，缺它这些用例无路可走。修复：{ENGINE_INSTALL}；"
        f"或在源码检出下把引擎仓库根目录加入 PYTHONPATH，例如 "
        f"PYTHONPATH=<engine checkout root> python -m pytest -q。"
    )


def require_qt() -> None:
    """模块级用法：Qt 不可用时把整个模块显式跳过。"""
    import pytest

    if not HAVE_QT:
        pytest.skip(skip_reason_for_qt(), allow_module_level=True)


def require_engine() -> None:
    """模块级用法：引擎不可用时把整个模块显式跳过。"""
    import pytest

    if not HAVE_ENGINE:
        pytest.skip(skip_reason_for_engine(), allow_module_level=True)


def report_lines() -> list[str]:
    """给 ``pytest_report_header`` / 终端摘要用的一行式环境说明。"""
    qt = (
        f"{QT_DIST}: usable (GUI tests run)"
        if HAVE_QT
        else (
            f"{QT_DIST}: UNUSABLE -> 'requires_qt' SKIP"
            f"({_QT_PROBLEM}); fix: {QT_INSTALL}"
        )
    )
    engine = (
        f"{ENGINE_DIST}: importable (adapter/engine tests run)"
        if HAVE_ENGINE
        else (
            f"{ENGINE_DIST}: NOT importable -> 'requires_engine' SKIP"
            f"({_ENGINE_PROBLEM}); fix: {ENGINE_INSTALL} "
            "or PYTHONPATH=<engine checkout root>"
        )
    )
    return [f"qt: {qt} | engine: {engine}"]
