"""OpenRelTime Studio — 原生桌面 GUI 入口。

定位：面向不写代码的研究者，把 OpenRelTime 的公共 API 包成独立桌面软件。
所有计算都走 ``import openreltime``（经由适配层），GUI 不重写任何算法。

运行（开发态）::

    # 引擎尚未发布到包索引，先装 Release 的 wheel
    python -m pip install "openreltime[plot] @ https://github.com/ZengZichao/OpenRelTime/releases/download/v0.1.0/openreltime-0.1.0-py3-none-any.whl"
    python -m pip install -e ".[dev]"           # 引擎已就位，依赖可直接解析
    openreltime-studio                          # 或 python -m openreltime_studio

打包成独立可执行文件（双击即用，终端用户无需 Python）::

    python -m pip install pyinstaller
    pyinstaller openreltime_studio/resources/OpenRelTimeStudio.spec

功能模块：
    - RRF 速率 + 时间分析（M0 基础）
    - 交互式校正点（M1：在树上点选节点设校正）
    - 置信区间（CI）
    - CorrTest 速率自相关检验
    - ddBD 分化树先验
    - 导出 CSV/NEXUS/JSON/PNG + 等效 CLI 脚本
    - 中英文界面即时切换、亮/暗主题即时切换（偏好持久化）
"""

from __future__ import annotations

import logging
import sys
import threading

__all__ = ["LOG_COLLECTOR", "main", "self_check"]


class _LogCollector(logging.Handler):
    """收集 openreltime 引擎日志（GUI 无控制台也能看到告警）。

    ``emit`` 可能来自 Worker 线程，而 GUI 线程会读取告警列表，因此列表的
    读写全部在 ``self._lock`` 下进行；对外只暴露快照（``records`` /
    ``count``），调用方拿到的永远是副本，可以安全遍历与拼接。
    """

    def __init__(self, capacity: int = 500) -> None:
        super().__init__()
        self.capacity = capacity
        self._lock = threading.Lock()
        self._records: list[str] = []
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001 - logging 回调绝不抛出
            return
        with self._lock:
            self._records.append(line)
            overflow = len(self._records) - self.capacity
            if overflow > 0:
                del self._records[:overflow]

    @property
    def records(self) -> list[str]:
        """当前告警的快照副本。"""
        with self._lock:
            return list(self._records)

    def count(self) -> int:
        """当前告警条数（不复制列表）。"""
        with self._lock:
            return len(self._records)

    def clear(self) -> None:
        """清空告警（载入新树/新会话时用）。"""
        with self._lock:
            self._records.clear()


#: 模块级单例：main() 里挂到 "openreltime" logger，主窗口读取展示
LOG_COLLECTOR = _LogCollector()


def self_check() -> int:
    """打包自检：确认包内资源都能按包内路径取到，不开窗口。

    给冻结产物（PyInstaller 的 ``.app``）用：源码态测试通过不代表 locales、
    内置示例与图标在 bundle 里也解析得到。全部命中时返回 0。
    """
    from openreltime_studio import examples, i18n, themes
    from openreltime_studio.appicon import symbolic_svg_path

    problems: list[str] = []

    for lang in i18n.LANGUAGES:
        try:
            keys = i18n.catalog_keys(lang)
        except OSError as exc:  # pragma: no cover - 目录缺失
            problems.append(f"catalog {lang}: {exc}")
            continue
        if not keys:
            problems.append(f"catalog {lang} is empty")

    try:
        for kind, path in examples.example_files().items():
            if path.stat().st_size == 0:
                problems.append(f"example {kind} is empty")
    except (FileNotFoundError, OSError) as exc:
        problems.append(f"examples: {exc}")

    for path in (themes.icon_svg_path(), symbolic_svg_path()):
        if not path.is_file():
            problems.append(f"icon missing: {path.name}")

    for line in problems:
        print(f"FAIL {line}")
    if not problems:
        print(
            "OK bundled resources resolve: "
            f"{len(i18n.catalog_keys('en'))} en + {len(i18n.catalog_keys('zh'))} zh keys, "
            "2 example files, 2 icon variants"
        )
    return 1 if problems else 0


def main():
    """Studio 入口：创建 QApplication 并显示主窗口。"""
    if "--self-check" in sys.argv:
        sys.exit(self_check())
    # 在 QApplication 之前设置 matplotlib 后端，避免 GUI 后端冲突
    import matplotlib

    matplotlib.use("Agg")

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from openreltime_studio import i18n, themes
    from openreltime_studio.appicon import app_icon

    # Route engine warnings into the in-window log collector: a windowed .app
    # has no stderr at all, so without this the user would never see them.
    ort_logger = logging.getLogger("openreltime")
    ort_logger.addHandler(LOG_COLLECTOR)
    if ort_logger.level == logging.NOTSET or ort_logger.level > logging.WARNING:
        ort_logger.setLevel(logging.WARNING)

    app = QApplication(sys.argv)
    app.setApplicationName("OpenRelTime Studio")
    app.setOrganizationName("OpenRelTime")
    app.setApplicationDisplayName("OpenRelTime Studio")
    app.setWindowIcon(app_icon())

    # Fusion 风格保证全局样式表在各平台表现一致（macOS 原生风格会忽略部分 QSS）
    app.setStyle("Fusion")

    # 全局字体
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    # 主题与语言：沿用上次保存的偏好（首次运行为浅色 + 英文）
    themes.apply_to_app(app)
    themes.set_theme(themes.configured_theme(), persist=False)
    i18n.set_language(i18n.configured_language(), persist=False, notify=False)

    from openreltime_studio.windows.main_window import MainWindow

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
