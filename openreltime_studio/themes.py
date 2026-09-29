"""亮/暗双主题：颜色令牌、全局样式表与图表配色。

设计要点：

* 全部颜色以 *令牌*（token）形式集中定义在 ``LIGHT`` / ``DARK`` 两套表里，
  样式表用 ``string.Template`` 的 ``$token`` 占位符引用令牌，因此两套主题
  共用同一份 QSS 文本，改样式不会只改到一边。
* ``set_theme()`` 切换主题时把新样式表一次性写入 ``QApplication``，并通知
  自绘控件（树画布等）重画，界面无需重启。
* ``mpl_rc_params()`` 把同一套令牌翻译成 matplotlib 配色，保证画布与窗口
  在暗色下不出现「白底黑字方块」。
* 主题偏好写入 ``QSettings("OpenRelTime", "Studio")``，默认亮色。
"""

from __future__ import annotations

import contextlib
import string
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DARK",
    "LIGHT",
    "THEMES",
    "THEME_LABELS",
    "DEFAULT_THEME",
    "THEME_SETTINGS_KEY",
    "apply_to_app",
    "configured_theme",
    "icon_svg_path",
    "on_theme_change",
    "persist_theme",
    "qt_palette",
    "set_theme",
    "stylesheet",
    "tokens",
    "watch",
    "theme",
]

THEMES = ("light", "dark")
DEFAULT_THEME = "light"
THEME_SETTINGS_KEY = "ui/theme"
THEME_LABELS = {"light": "Light", "dark": "Dark"}

ICON_SVG = "OpenRelTime-Studio.svg"


@dataclass(frozen=True)
class Tokens:
    """一套主题的全部颜色令牌。"""

    is_dark: bool
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_disabled_bg: str
    accent_disabled_fg: str
    text: str
    text_secondary: str
    text_muted: str
    border: str
    button_border: str
    surface: str
    surface_alt: str
    surface_sunken: str
    surface_hover: str
    surface_pressed: str
    field_border: str
    disabled_bg: str
    disabled_fg: str
    disabled_border: str
    header_bg: str
    grid_line: str
    alt_row: str
    tooltip_bg: str
    tooltip_fg: str
    menu_selected: str
    scroll_handle: str
    scroll_handle_hover: str
    selection_bg: str
    selection_fg: str
    canvas_face: str
    canvas_edge: str
    canvas_text: str
    mark_fill: str
    mark_edge: str
    tree_base: str
    rate_low: str
    rate_high: str
    grid_point: str
    grid_point_edge: str
    fitted_line: str
    ci_color: str
    ci_error: str


LIGHT = Tokens(
    is_dark=False,
    accent="#2f6fdb",
    accent_hover="#2a63c4",
    accent_pressed="#2458b0",
    accent_disabled_bg="#a9c3ee",
    accent_disabled_fg="#eef2f9",
    text="#1f2328",
    text_secondary="#5b6169",
    text_muted="#8a9099",
    border="#d9dce1",
    button_border="#c9ccd1",
    surface="#ffffff",
    surface_alt="#f5f6f8",
    surface_sunken="#eceef1",
    surface_hover="#eaf1fd",
    surface_pressed="#d8e5fb",
    field_border="#c9ccd1",
    disabled_bg="#f2f3f5",
    disabled_fg="#9aa0a6",
    disabled_border="#dfe1e5",
    header_bg="#f0f1f4",
    grid_line="#eceef1",
    alt_row="#f7f8fa",
    tooltip_bg="#2f3b4c",
    tooltip_fg="#ffffff",
    menu_selected="#e2e7ef",
    scroll_handle="#c9ccd1",
    scroll_handle_hover="#a8adb5",
    selection_bg="#d8e5fb",
    selection_fg="#1f2328",
    canvas_face="#ffffff",
    canvas_edge="#d9dce1",
    canvas_text="#1f2328",
    mark_fill="#f5c518",
    mark_edge="#333333",
    tree_base="#4575b4",
    rate_low="#a50026",
    rate_high="#313695",
    grid_point="#313695",
    grid_point_edge="#74add1",
    fitted_line="#a02c2c",
    ci_color="#313695",
    ci_error="#74add1",
)

DARK = Tokens(
    is_dark=True,
    accent="#4f8dee",
    accent_hover="#639cf2",
    accent_pressed="#3f7bd6",
    accent_disabled_bg="#2b3d5c",
    accent_disabled_fg="#6c7b93",
    text="#e6e9ee",
    text_secondary="#a8b1bd",
    text_muted="#7d8692",
    border="#3a4049",
    button_border="#454c56",
    surface="#1e2126",
    surface_alt="#171a1e",
    surface_sunken="#121417",
    surface_hover="#243044",
    surface_pressed="#2d3c57",
    field_border="#454c56",
    disabled_bg="#23262b",
    disabled_fg="#5f6771",
    disabled_border="#33383f",
    header_bg="#22262c",
    grid_line="#2a2f36",
    alt_row="#20242a",
    tooltip_bg="#e6e9ee",
    tooltip_fg="#1a1d21",
    menu_selected="#2d3c57",
    scroll_handle="#4a525d",
    scroll_handle_hover="#5f6771",
    selection_bg="#2d3c57",
    selection_fg="#f2f5fa",
    canvas_face="#1e2126",
    canvas_edge="#3a4049",
    canvas_text="#e6e9ee",
    mark_fill="#f5c518",
    mark_edge="#0f1114",
    tree_base="#74add1",
    rate_low="#f46d43",
    rate_high="#92c5de",
    grid_point="#92c5de",
    grid_point_edge="#4575b4",
    fitted_line="#fdae61",
    ci_color="#92c5de",
    ci_error="#4575b4",
)

_QSS_TEMPLATE = string.Template("""
QMainWindow, QDialog { background: $surface_alt; }
QWidget { color: $text; font-size: 12px; }

QGroupBox {
    font-weight: 600;
    border: 1px solid $border;
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px 6px 6px 6px;
    background: $surface;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: $text_secondary;
}

QPushButton {
    padding: 5px 14px;
    border: 1px solid $button_border;
    border-radius: 4px;
    background: $surface;
    color: $text;
}
QPushButton:hover {
    background: $surface_hover;
    border-color: $accent;
}
QPushButton:pressed { background: $surface_pressed; }
QPushButton:focus { border-color: $accent; }
QPushButton:disabled {
    color: $disabled_fg;
    background: $disabled_bg;
    border-color: $disabled_border;
}
QPushButton#accentButton {
    background: $accent;
    color: #ffffff;
    font-weight: 600;
    border-color: $accent;
}
QPushButton#accentButton:hover { background: $accent_hover; }
QPushButton#accentButton:pressed { background: $accent_pressed; }
QPushButton#accentButton:disabled {
    background: $accent_disabled_bg;
    color: $accent_disabled_fg;
    border-color: transparent;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    padding: 3px 6px;
    border: 1px solid $field_border;
    border-radius: 4px;
    background: $surface;
    selection-background-color: $accent;
    selection-color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: $accent;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled {
    background: $disabled_bg;
    color: $disabled_fg;
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: $surface;
    color: $text;
    selection-background-color: $surface_hover;
    selection-color: $text;
    border: 1px solid $border;
}

QCheckBox { spacing: 6px; }
QCheckBox:disabled { color: $disabled_fg; }
QRadioButton:disabled { color: $disabled_fg; }

QTabWidget::pane {
    border: 1px solid $border;
    border-radius: 0 0 4px 4px;
    background: $surface;
    top: -1px;
}
QTabBar::tab {
    padding: 5px 14px;
    border: 1px solid $border;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    background: $surface_sunken;
    color: $text_secondary;
    margin-right: 2px;
}
QTabBar::tab:selected { background: $surface; color: $text; }
QTabBar::tab:hover:!selected { background: $surface_alt; }

QTableWidget {
    gridline-color: $grid_line;
    alternate-background-color: $alt_row;
    background: $surface;
    border: 1px solid $border;
    selection-background-color: $selection_bg;
    selection-color: $selection_fg;
}
QTableWidget::item { padding: 2px 6px; }
QHeaderView::section {
    background: $header_bg;
    color: $text_secondary;
    border: none;
    border-right: 1px solid $border;
    border-bottom: 1px solid $border;
    padding: 3px 6px;
    font-weight: 600;
}
QTableCornerButton::section { background: $header_bg; border: none; }

QTextEdit {
    font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 11px;
    background: $surface;
    border: 1px solid $border;
    border-radius: 4px;
    color: $text;
}

QStatusBar {
    background: $surface_sunken;
    border-top: 1px solid $border;
    color: $text_secondary;
}
QMenuBar { background: $surface_alt; color: $text; }
QMenuBar::item:selected { background: $menu_selected; border-radius: 4px; }
QMenu { background: $surface; border: 1px solid $border; }
QMenu::item:selected { background: $surface_hover; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }

QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 5px; }
QSplitter::handle:hover { background: $surface_pressed; border-radius: 2px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical {
    background: $scroll_handle;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: $scroll_handle_hover; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: $scroll_handle;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: $scroll_handle_hover; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip {
    background: $tooltip_bg;
    color: $tooltip_fg;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}

QLabel#panelTitle { font-weight: 600; color: $text_secondary; padding: 2px; }
QLabel#hintLabel { color: $text_muted; font-size: 11px; }
""")


_current = LIGHT

_theme = DEFAULT_THEME
_listeners: list[Callable[[str], None]] = []
_widgets: list[weakref.ReferenceType] = []


def tokens() -> Tokens:
    """当前主题的颜色令牌。"""
    return _current


def theme() -> str:
    """当前主题代码（``light`` / ``dark``）。"""
    return _theme


def configured_theme() -> str:
    """启动时应使用的主题：已保存的偏好优先，否则默认亮色。"""
    stored = _read_setting(THEME_SETTINGS_KEY)
    if isinstance(stored, str) and stored in THEMES:
        return stored
    return DEFAULT_THEME


def persist_theme(name: str) -> None:
    """把主题偏好写回 ``QSettings``。"""
    _write_setting(THEME_SETTINGS_KEY, name)


def set_theme(name: str, *, persist: bool = True, notify: bool = True) -> str:
    """切换主题：更新令牌、刷新样式表、通知自绘控件重画。"""
    global _current, _theme
    if name not in THEMES:
        raise ValueError(f"unsupported theme: {name!r}")
    _theme = name
    _current = DARK if name == "dark" else LIGHT
    if persist:
        persist_theme(name)
    _refresh_application_style()
    if notify:
        alive = []
        for ref in _widgets:
            widget = ref()
            if widget is None:
                continue
            alive.append(ref)
            hook = getattr(widget, "retheme", None)
            if callable(hook):
                hook()
        _widgets[:] = alive
        for callback in list(_listeners):
            callback(name)
    return _theme


def on_theme_change(callback: Callable[[str], None]) -> Callable[[], None]:
    """注册主题变化回调，返回注销函数。"""
    _listeners.append(callback)

    def unregister() -> None:
        with contextlib.suppress(ValueError):  # pragma: no cover - 重复注销
            _listeners.remove(callback)

    return unregister


def watch(widget) -> None:
    """登记需要随主题重画的自绘控件（弱引用）。"""
    _widgets.append(weakref.ref(widget))


def apply_to_app(app) -> str:
    """把当前主题（调色板 + 样式表）应用到 ``QApplication``。

    换主题时必须先改调色板、再清空并重设样式表：Qt 会在样式表生效时按当时
    的调色板为每个控件解析一次配色，只换其中一个会让另一套主题的底色残留
    （表现为暗色下仍有亮色面板）。
    """
    palette = qt_palette()
    if palette is not None:
        app.setPalette(palette)
    app.setStyleSheet("")
    app.setStyleSheet(stylesheet())
    return _theme


def stylesheet() -> str:
    """当前主题的样式表文本。"""
    return _QSS_TEMPLATE.substitute(vars(_current))


def mpl_rc_params(palette_tokens: Tokens | None = None) -> dict[str, object]:
    """当前主题对应的 matplotlib rcParams 片段。"""
    tk = palette_tokens or _current
    return {
        "figure.facecolor": tk.canvas_face,
        "axes.facecolor": tk.canvas_face,
        "savefig.facecolor": tk.canvas_face,
        "axes.edgecolor": tk.canvas_edge,
        "axes.labelcolor": tk.canvas_text,
        "text.color": tk.canvas_text,
        "xtick.color": tk.canvas_text,
        "ytick.color": tk.canvas_text,
        "grid.color": tk.canvas_edge,
        "axes.titlecolor": tk.canvas_text,
        "legend.framebackground": tk.surface,
        "legend.framealpha": 0.9,
    }


def icon_svg_path() -> Path:
    """应用图标 SVG 文件路径。"""
    return Path(__file__).resolve().parent / "resources" / "icons" / ICON_SVG


def qt_palette(palette_tokens: Tokens | None = None):
    """当前主题对应的 ``QPalette``。

    样式表只能覆盖它认识的控件；视口、滚动区域、条目视图的空白区等走的是
    调色板，暗色下若不改调色板会残留亮色底。
    """
    try:
        from PySide6.QtGui import QColor, QPalette
    except ImportError:  # pragma: no cover - 无 Qt 环境
        return None
    tk = palette_tokens or _current
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(tk.surface_alt))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(tk.text))
    pal.setColor(QPalette.ColorRole.Base, QColor(tk.surface))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(tk.alt_row))
    pal.setColor(QPalette.ColorRole.Text, QColor(tk.text))
    pal.setColor(QPalette.ColorRole.Button, QColor(tk.surface_alt))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(tk.text))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(tk.tooltip_bg))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(tk.tooltip_fg))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(tk.text_muted))
    pal.setColor(QPalette.ColorRole.Link, QColor(tk.accent))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(tk.accent))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    disabled = QPalette.ColorGroup.Disabled
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(disabled, role, QColor(tk.disabled_fg))
    pal.setColor(disabled, QPalette.ColorRole.Base, QColor(tk.disabled_bg))
    return pal


def _refresh_application_style() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - 无 Qt 环境
        return
    app = QApplication.instance()
    if app is not None:
        apply_to_app(app)


def _read_setting(key: str):
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - 无 Qt 时退回默认值
        return None
    if QApplication.instance() is None:
        return None
    return QSettings("OpenRelTime", "Studio").value(key)


def _write_setting(key: str, value: str) -> None:
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - 无 Qt 时忽略持久化
        return
    if QApplication.instance() is None:
        return
    settings = QSettings("OpenRelTime", "Studio")
    settings.setValue(key, value)
    settings.sync()
