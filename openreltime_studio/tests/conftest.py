"""GUI 用例的公共夹具与按用例粒度的能力门控。

放在包内而不是仓库根，测试才能随发行版一起运行
（``python -m pytest --pyargs openreltime_studio.tests``）。

门控策略（按**单个用例**粒度，不再整目录 ``collect_ignore_glob``）：

* 构造任何 QWidget 之前必须先有 ``QApplication``，否则进程直接 abort；
  会话级 ``QApplication`` 由本文件的 ``_qsession`` 夹具建立，Qt 不可用时
  它退化成空夹具，**不**牵连不依赖 Qt 的用例。
* 需要 Qt 绑定的用例逐个/整模块标 ``pytest.mark.requires_qt``；需要引擎
  ``openreltime`` 的标 ``pytest.mark.requires_engine``。缺哪个就跳过哪个，
  理由里点名成因与修复命令（见 ``_availability``）。
* 打包、内置示例资源、文档卫生、i18n 目录静态检查这些**不依赖 Qt 也不
  依赖引擎**的用例因此在任何机器上都会被收集 —— 与
  ``test_i18n_catalogs.py`` 开头那句「不依赖 Qt，甚至没装 PySide6 的机器上
  也能跑」保持一致。
* ``smoke_gui.py`` 是手工脚本，永远不参与收集（见 ``collect_ignore`` 与该
  文件自身的导入守卫）。
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Optional

import pytest

from openreltime_studio.tests import _availability as av

#: 手工离屏冒烟脚本：只在命令行显式运行，绝不作为测试收集。
collect_ignore = ["smoke_gui.py"]

if av.HAVE_QT:  # pragma: no cover - 环境相关
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_configure(config: pytest.Config) -> None:
    """登记标记，使安装版在别人的 ini 下运行同样有效（pyproject 里也有一份）。"""
    config.addinivalue_line(
        "markers",
        "requires_qt: 需要 Qt 绑定（PySide6）；未安装时跳过并给出修复命令",
    )
    config.addinivalue_line(
        "markers",
        "requires_engine: 需要引擎发行版 openreltime；不可导入时显式跳过并给出修复命令",
    )


def pytest_report_header(config: pytest.Config) -> list[str]:
    """把两条判据的实际结果打进 run 头部（``-v`` 下可见）。"""
    return [f"test gating — {line}" for line in av.report_lines()]


def pytest_terminal_summary(
    terminalreporter: object, config: pytest.Config
) -> None:
    """缺依赖时在 run 末尾再喊一次。

    ``-q``（本仓库 ``addopts`` 的默认档）会省掉整个头部，只看结尾；把同样的
    信息写在结尾，跳过就绝不是静默的：跳过条数 + 成因 + 修复命令。
    """
    if av.HAVE_QT and av.HAVE_ENGINE:
        return
    stats = terminalreporter.stats  # type: ignore[attr-defined]
    skipped = len(stats.get("skipped", []))
    failed = len(stats.get("failed", [])) + len(stats.get("error", []))
    terminalreporter.write_line("")  # type: ignore[attr-defined]
    for line in av.report_lines():
        terminalreporter.write_line(f"gating: {line}")  # type: ignore[attr-defined]
    if skipped:
        terminalreporter.write_line(  # type: ignore[attr-defined]
            f"gating: {skipped} skipped because a capability is missing "
            f"(run with -rs for the per-test reason; failures={failed})"
        )


def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    """把 ``requires_*`` 标记翻译成显式跳过。

    两个标记都不缺时什么都不做；缺哪个就把挂了对应用例的项标成 skip，
    理由点名成因与修复。这里不做「静默通过」，也不整目录消失。
    """
    if av.HAVE_QT and av.HAVE_ENGINE:
        return
    for item in items:
        if not av.HAVE_QT and item.get_closest_marker("requires_qt"):
            item.add_marker(pytest.mark.skip(reason=av.skip_reason_for_qt(item.nodeid)))
        if not av.HAVE_ENGINE and item.get_closest_marker("requires_engine"):
            item.add_marker(
                pytest.mark.skip(reason=av.skip_reason_for_engine(item.nodeid))
            )


@pytest.fixture(scope="session", autouse=True)
def _qsession() -> Iterator[Optional[object]]:
    """会话级 ``QApplication``：Qt 在场才构造，缺席时退化为 ``None``。

    之所以是 autouse：部分回归用例直接 ``CalibrationEditor()`` 而不写
    ``qapp`` 形参，靠的就是这里已经把 app 建好。
    """
    if not av.HAVE_QT:  # pragma: no cover - 环境相关
        yield None
        return
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    # ``QCoreApplication.instance()`` 的返回类型是父类，mypy 看不见
    # ``setStyle``；这里刚刚建好的必然是 ``QApplication``，收窄给类型检查器。
    assert isinstance(app, QApplication)
    app.setStyle("Fusion")
    yield app


@pytest.fixture(scope="session")
def qapp(_qsession: Optional[object]) -> object:
    """需要真实 ``QApplication`` 的用例显式请求它；Qt 缺席时显式跳过。"""
    av.require_qt()
    assert _qsession is not None, av.skip_reason_for_qt()
    return _qsession
