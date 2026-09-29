"""语言、主题与图标的功能性测试。

与 ``test_i18n_catalogs.py`` 的静态检查互补：这里真的构造主窗口，切语言、
切主题，验证界面文本与配色**当场**改变（不重启进程），并确认图标确实来自
包内 SVG。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from openreltime_studio import i18n, themes

QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication


@pytest.fixture
def app(qapp):
    """会话级 QApplication 已在 conftest 建好，这里只保证样式表已应用。"""
    themes.set_theme(themes.DEFAULT_THEME, persist=False)
    qapp.setStyleSheet(themes.stylesheet())
    return qapp


@pytest.fixture
def main_window(app):
    from openreltime_studio.windows.main_window import MainWindow

    i18n.set_language("en", persist=False)
    win = MainWindow()
    yield win
    win.close()


def titles(win):
    from PySide6.QtWidgets import QGroupBox

    return {g.title() for g in win.findChildren(QGroupBox)}


def test_default_language_and_theme_are_english_light() -> None:
    assert i18n.DEFAULT_LANGUAGE == "en"
    assert themes.DEFAULT_THEME == "light"
    assert set(i18n.LANGUAGES) == {"en", "zh"}
    assert set(themes.THEMES) == {"light", "dark"}


def test_group_box_titles_switch_without_restart(main_window) -> None:
    en = titles(main_window)
    i18n.set_language("zh", persist=False)
    zh = titles(main_window)
    assert en and zh
    assert en != zh, "分组框标题没有随语言改变"
    assert any("导入" in text for text in zh)
    assert any("Import" in text for text in en)
    i18n.set_language("en", persist=False)


def test_tab_labels_and_status_bar_follow_language(main_window) -> None:
    tabs = [
        main_window.analysis_tabs.tabText(i) for i in range(main_window.analysis_tabs.count())
    ]
    assert tabs[1] == "Calibration"
    main_window._show_status("status.ready")
    english_status = main_window.statusBar().currentMessage()

    i18n.set_language("zh", persist=False)
    assert main_window.analysis_tabs.tabText(1) == "校正"
    assert main_window.statusBar().currentMessage() != english_status
    assert "就绪" in main_window.statusBar().currentMessage()
    i18n.set_language("en", persist=False)


def test_view_menu_exposes_language_and_theme_choices(main_window) -> None:
    from PySide6.QtGui import QAction

    texts = [act.text() for act in main_window.findChildren(QAction)]
    assert "English" in texts and "简体中文" in texts
    assert "Light" in texts and "Dark" in texts


def test_triggering_language_action_changes_catalog(main_window) -> None:
    from PySide6.QtGui import QAction

    zh_action = next(a for a in main_window.findChildren(QAction) if a.text() == "简体中文")
    zh_action.trigger()
    assert i18n.language() == "zh"
    assert any("导出" in text for text in titles(main_window))
    assert zh_action.isChecked()
    en_action = next(a for a in main_window.findChildren(QAction) if a.text() == "English")
    en_action.trigger()
    assert i18n.language() == "en"
    assert en_action.isChecked() and not zh_action.isChecked()


def test_theme_switch_replaces_stylesheet_and_tokens(app) -> None:
    light_qss = themes.stylesheet()
    light = themes.tokens()
    themes.set_theme("dark", persist=False)
    dark = themes.tokens()
    dark_qss = themes.stylesheet()

    assert light.surface != dark.surface
    assert dark.is_dark and not light.is_dark
    assert app.styleSheet() == dark_qss != light_qss
    assert dark.surface in app.styleSheet()
    themes.set_theme("light", persist=False)
    assert app.styleSheet() == light_qss


def test_matplotlib_params_follow_theme(app) -> None:
    themes.set_theme("light", persist=False, notify=False)
    light_face = themes.mpl_rc_params()["figure.facecolor"]
    themes.set_theme("dark", persist=False, notify=False)
    dark_face = themes.mpl_rc_params()["figure.facecolor"]
    assert light_face != dark_face
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", str(dark_face))
    themes.set_theme("light", persist=False, notify=False)


def test_window_constructs_in_all_four_combinations(app) -> None:
    from openreltime_studio.windows.main_window import MainWindow

    for language in i18n.LANGUAGES:
        for theme in themes.THEMES:
            i18n.set_language(language, persist=False, notify=False)
            themes.set_theme(theme, persist=False)
            win = MainWindow()
            win.show()
            app.processEvents()
            assert win.isVisible()
            assert win.statusBar().currentMessage()
            win.close()


def test_preferences_round_trip_through_settings(app) -> None:
    from PySide6.QtCore import QSettings

    i18n.set_language("zh", persist=True)
    themes.set_theme("dark", persist=True)
    settings = QSettings("OpenRelTime", "Studio")
    assert settings.value(i18n.LANGUAGE_SETTINGS_KEY) == "zh"
    assert settings.value(themes.THEME_SETTINGS_KEY) == "dark"
    assert i18n.configured_language() == "zh"
    assert themes.configured_theme() == "dark"

    settings.remove(i18n.LANGUAGE_SETTINGS_KEY)
    settings.remove(themes.THEME_SETTINGS_KEY)
    assert i18n.configured_language() == i18n.DEFAULT_LANGUAGE
    assert themes.configured_theme() == themes.DEFAULT_THEME


def test_svg_icon_is_valid_vector_source() -> None:
    from openreltime_studio.appicon import svg_source

    root = ET.fromstring(svg_source().decode("utf-8"))
    assert root.tag == "{http://www.w3.org/2000/svg}svg" or root.tag == "svg"
    text = svg_source().decode("utf-8")
    assert "<rect" in text and "<path" in text and "<circle" in text
    assert themes.icon_svg_path().is_file()


def test_app_icon_is_built_from_svg_with_multiple_sizes(app) -> None:
    from openreltime_studio.appicon import ICON_SIZES, app_icon

    icon = app_icon()
    assert not icon.isNull()
    sizes = set(icon.availableSizes())
    assert len(sizes) >= 3
    assert max(size.width() for size in sizes) >= 128
    assert len(ICON_SIZES) >= 5


def test_view_menu_offers_four_root_positions(main_window) -> None:
    from PySide6.QtGui import QAction

    texts = [act.text() for act in main_window.findChildren(QAction)]
    for expected in ("Root on left", "Root on right", "Root on top", "Root on bottom"):
        assert expected in texts
    assert main_window.canvas.orientation == "left"  # 默认根在左
    assert [a for a in main_window.findChildren(QAction) if a.text() == "Root on left"][0].isChecked()


def test_choosing_root_position_redraws_canvas(main_window, tmp_path) -> None:
    """切换朝向必须立刻重画当前视图：先加载一棵树再点菜单。"""
    from PySide6.QtGui import QAction

    from openreltime_studio.adapters import openreltime_adapter as adapter

    tree_path = tmp_path / "tiny.nwk"
    tree_path.write_text(
        "(((a:0.10,b:0.12)ab:0.03,(c:0.20,d:0.22)cd:0.05)abcd:0.03,"
        "(e:0.30,f:0.33)ef:0.07)root;\n",
        encoding="utf-8",
    )
    tree = adapter.read_tree(tree_path)
    result = adapter.run_rrf_rates_times(tree)
    main_window.canvas.plot_timetree(result, use_rates=True)
    assert main_window.canvas.ax.get_xlabel() == i18n.t("canvas.axis_relative")

    bottom = next(a for a in main_window.findChildren(QAction) if a.text() == "Root on bottom")
    bottom.trigger()
    assert main_window.canvas.orientation == "bottom"
    assert bottom.isChecked()
    ax = main_window.canvas.ax
    assert ax.get_ylabel() == i18n.t("canvas.axis_relative")
    assert ax.get_ylim()[0] > ax.get_ylim()[1]  # 根在下方 → 时间轴反向

    left = next(a for a in main_window.findChildren(QAction) if a.text() == "Root on left")
    left.trigger()
    assert main_window.canvas.orientation == "left"
    assert main_window.canvas.ax.get_xlabel() == i18n.t("canvas.axis_relative")


def test_root_position_label_follows_language(main_window) -> None:
    from PySide6.QtGui import QAction

    i18n.set_language("zh", persist=False)
    texts = [act.text() for act in main_window.findChildren(QAction)]
    assert "根在左" in texts and "根在下" in texts
    i18n.set_language("en", persist=False)


def test_missing_key_falls_back_to_key_name() -> None:
    assert i18n.t("panel.definitely_missing_key") == "panel.definitely_missing_key"
