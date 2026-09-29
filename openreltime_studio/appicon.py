"""应用图标：从包内 SVG 栅格化，大尺寸用主图、小尺寸用简化变体。

两个变体都在 ``resources/icons/``：

* ``OpenRelTime-Studio.svg`` —— 主图（渐变底板、按速率着色的年代树、校正环、
  时间轴刻度），≥ 65 px 时使用；
* ``OpenRelTime-Studio-symbolic.svg`` —— 简化变体（加粗三支树 + 校正环，去掉
  刻度与渐变），≤ 64 px 时使用：主图的时间轴与细分支在这个尺度会糊成一团。

``.png`` / ``.icns`` 只是派生物，由 ``resources/make_icon.py`` 从这里栅格化。
QtSvg 不可用时退回 ``QPainter`` 按同一套几何手工绘制。
"""

from __future__ import annotations

from pathlib import Path

from openreltime_studio.themes import icon_svg_path

__all__ = [
    "ICON_SIZES",
    "SYMBOLIC_MAX_PX",
    "app_icon",
    "icon_dir",
    "pixmap_from_svg",
    "svg_path_for_size",
    "svg_source",
    "symbolic_svg_path",
]

#: 窗口 / Dock / 任务栏需要的尺寸集合
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

#: 不超过这个边长就改用简化变体（64 px 下主图的时间轴已与分支粘连）
SYMBOLIC_MAX_PX = 64

_SYMBOLIC_FILENAME = "OpenRelTime-Studio-symbolic.svg"

_ACCENT = "#2f6fdb"
_MARK = "#f5c518"


def icon_dir() -> Path:
    """图标目录。"""
    return icon_svg_path().parent


def symbolic_svg_path() -> Path:
    """小尺寸简化变体的路径。"""
    return icon_dir() / _SYMBOLIC_FILENAME


def svg_path_for_size(size: int) -> Path:
    """按目标边长选择变体。"""
    return symbolic_svg_path() if size <= SYMBOLIC_MAX_PX else icon_svg_path()


def svg_source(size: int | None = None) -> bytes:
    """SVG 原始字节；给出 ``size`` 时按尺寸挑选对应变体。"""
    path = icon_svg_path() if size is None else svg_path_for_size(size)
    return path.read_bytes()


def pixmap_from_svg(size: int):
    """把对应变体渲染为 ``size``×``size`` 的 QPixmap；QtSvg 缺失时返回 None。"""
    try:
        from PySide6.QtCore import QByteArray, QRectF, Qt
        from PySide6.QtGui import QPainter, QPixmap
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:
        return None
    renderer = QSvgRenderer(QByteArray(svg_source(size)))
    if not renderer.isValid():
        return None
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm


def _painted_pixmap(size: int):
    """QtSvg 不可用时的兜底：按简化变体的几何手工绘制。"""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(_ACCENT))
    painter.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 58 * s, 58 * s)

    pen = QPen(
        QColor("#ffffff"), max(1.0, 22 * s), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
    )
    painter.setPen(pen)
    for x0, y0, x1, y1 in (
        (56, 128, 96, 128),
        (96, 68, 96, 188),
        (96, 68, 172, 68),
        (96, 188, 172, 188),
        (134, 128, 196, 128),
        (134, 128, 134, 188),
    ):
        painter.drawLine(x0 * s, y0 * s, x1 * s, y1 * s)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#ffffff"))
    for cx, cy in ((184, 68), (196, 128)):
        r = 17 * s
        painter.drawEllipse(QRectF(cx * s - r, cy * s - r, 2 * r, 2 * r))

    painter.setPen(QPen(QColor(_MARK), max(1.0, 12 * s)))
    painter.setBrush(Qt.NoBrush)
    r = 26 * s
    painter.drawEllipse(QRectF(134 * s - r, 188 * s - r, 2 * r, 2 * r))
    painter.end()
    return pm


def app_icon():
    """构建多尺寸 ``QIcon``（每个尺寸各取合适的变体）。"""
    from PySide6.QtGui import QIcon

    icon = QIcon()
    for size in ICON_SIZES:
        pm = pixmap_from_svg(size)
        if pm is None:
            pm = _painted_pixmap(size)
        icon.addPixmap(pm)
    return icon
