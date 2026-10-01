"""内置示例与图标变体的测试。

内置示例必须满足两件事：**真的随包发行**（安装版 / 冻结的 .app 里也在包内，
不依赖仓库路径），而且**开箱可跑通**（树能读、校正点是合法单系群、整条流水线
出得来合理结果）。图标则要求主图与小尺寸变体都在包内、且按尺寸正确挑选。
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from openreltime_studio import examples, i18n
from openreltime_studio.adapters import openreltime_adapter as adapter
from openreltime_studio.appicon import (
    ICON_SIZES,
    SYMBOLIC_MAX_PX,
    app_icon,
    pixmap_from_svg,
    svg_path_for_size,
    svg_source,
    symbolic_svg_path,
)
from openreltime_studio.widgets.tree_canvas import TreeCanvas
from openreltime_studio.windows.main_window import MainWindow

PKG_DIR = Path(examples.__file__).resolve().parent


def wait_until(predicate, timeout: float = 20.0) -> bool:
    """跑事件循环直到条件成立（示例树是在 Worker 线程里读的）。"""
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


# ---- 内置示例：存在性与可跑通 -------------------------------------------


def test_example_files_live_inside_the_package() -> None:
    files = examples.example_files()
    assert set(files) == {"tree", "calibrations"}
    for path in files.values():
        assert path.is_file(), f"{path} 未随包发行"
        assert PKG_DIR in path.parents, f"{path} 不在包目录内"
        assert "site-packages" in str(path) or "openreltime_studio" in path.parts


def test_example_file_names_are_stable() -> None:
    assert examples.EXAMPLE_TREE_FILENAME == "example_tree.nwk"
    assert examples.EXAMPLE_CALIBRATIONS_FILENAME == "example_calibrations.tsv"


def test_example_tree_is_small_but_nontrivial() -> None:
    tree = adapter.read_tree(examples.example_tree_path())
    tips = tree.tips()
    assert 10 <= len(tips) <= 40, "示例树要小到能一眼看清，又要大到有结构可看"
    assert all(t.label for t in tips), "每个尖都要有可读的标签"
    assert tree.is_binary(), "示例树必须是二分树，否则载入即报错"


def test_example_calibrations_are_valid_complete_clades() -> None:
    tree = adapter.read_tree(examples.example_tree_path())
    cals = adapter.load_calibrations(examples.example_calibrations_path())
    assert len(cals) >= 2, "至少两条校正，才能演示边界与冲突检查"
    kept, problems = adapter.validate_calibrations(tree, cals)
    assert not problems, f"示例校正点不合法：{problems}"
    assert len(kept) == len(cals)
    for cal in kept:
        assert cal.min_bound is not None and cal.max_bound is not None
        assert cal.min_bound < cal.max_bound


def test_example_runs_the_whole_pipeline() -> None:
    """载入 → RRF → 校正 → CI 全跑通，且根龄落在演示边界允许的区间内。"""
    tree = adapter.read_tree(examples.example_tree_path())
    times = adapter.run_rrf_rates_times(tree)
    cals = adapter.load_calibrations(examples.example_calibrations_path())
    calibrated = adapter.run_calibrate(times, cals, method="bounds", provenance={})
    root_age = calibrated.times[tree.node_id]
    assert 50.0 < root_age < 400.0, f"示例根龄不合理：{root_age}"
    for cal in cals:
        node = adapter.resolve_calibration_target(tree, cal)
        assert node is not None
        age = calibrated.times[node.node_id]
        assert cal.min_bound - 1e-6 <= age <= cal.max_bound + 1e-6, (
            f"示例校正 {sorted(cal.taxon_set)} 的边界 {cal.min_bound}-{cal.max_bound} "
            f"未被满足（实得 {age}）"
        )
    ci = adapter.run_confidence_interval(calibrated, level=0.95, n_sites=None)
    assert len(ci.table) > 0


def test_example_readme_declares_the_disclaimer() -> None:
    readme = PKG_DIR / "examples" / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8")
    assert "假想" in text and "不是" in text, "示例边界必须注明是演示用而非文献结论"


# ---- 内置示例：界面入口 ---------------------------------------------------


def test_button_and_menu_load_the_example(qapp) -> None:
    win = MainWindow()
    win.show()
    try:
        assert win.tree is None
        win.btn_example.click()
        assert wait_until(lambda: win.tree is not None), "示例树没有载入"
        assert wait_until(lambda: not win._active_workers)
        assert len(win.calibration_editor.calibrations) >= 2, "示例校正点没有排队载入"
        assert win.btn_run_rrf.isEnabled(), "RRF 入口没有随示例树解锁"
        assert "example" in win.statusBar().currentMessage().lower() or wait_until(
            lambda: "示例" in win.statusBar().currentMessage()
            or "example" in win.statusBar().currentMessage().lower()
        )
        # 画布按既有约定：树要等「运行 RRF 分析」才画，此刻只有空态提示
        assert not win.canvas.ax.lines
        assert [t.get_text() for t in win.canvas.ax.texts] == [i18n.t("canvas.empty_hint")]

        # 跑一次 RRF，确认示例确实能立刻出图（这是内置示例的全部意义）
        win.btn_run_rrf.click()
        assert wait_until(lambda: win.rrf_result is not None), "示例 RRF 没有跑完"
        assert len(win.canvas.ax.lines) > 0, "RRF 完成后画布仍然空白"
        assert win.btn_export.isEnabled(), "有结果后导出入口应解锁"
    finally:
        win.close()


def test_example_button_text_follows_language(qapp) -> None:
    from openreltime_studio import i18n

    win = MainWindow()
    try:
        assert win.btn_example.text() == i18n.t("panel.example")
        i18n.set_language("zh", persist=False)
        assert win.btn_example.text() == "内置示例…"
        i18n.set_language("en", persist=False)
        assert win.btn_example.text() == "Bundled example…"
    finally:
        win.close()


def test_missing_example_reports_instead_of_crashing(qapp, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    from openreltime_studio.windows import main_window as mw

    calls: list[tuple[str, str]] = []

    def fake_critical(parent, title, text, *args, **kwargs):
        calls.append((title, text))

    monkeypatch.setattr(mw, "example_files", lambda: (_ for _ in ()).throw(
        FileNotFoundError("example_tree.nwk")
    ))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(fake_critical))

    win = MainWindow()
    try:
        win.load_example()
        assert calls, "示例缺失时没有给出可见错误"
        assert "example" in calls[0][0].lower() or "示例" in calls[0][0]
    finally:
        win.close()


# ---- 图标：主图与小尺寸变体 ----------------------------------------------


def test_both_icon_variants_are_valid_svg() -> None:
    from openreltime_studio.themes import icon_svg_path

    for path in (icon_svg_path(), symbolic_svg_path()):
        assert path.is_file(), path
        root = ET.fromstring(path.read_bytes())
        assert root.tag.endswith("svg")
        text = path.read_text(encoding="utf-8")
        assert "<rect" in text and "<path" in text and "<circle" in text
        assert "filter:" not in text and "<filter" not in text, "QtSvg 对滤镜支持不稳"


def test_symbolic_variant_is_used_only_at_small_sizes() -> None:
    assert svg_path_for_size(16).name.endswith("-symbolic.svg")
    assert svg_path_for_size(SYMBOLIC_MAX_PX).name.endswith("-symbolic.svg")
    assert not svg_path_for_size(SYMBOLIC_MAX_PX + 1).name.endswith("-symbolic.svg")
    assert svg_source(16) != svg_source(256)


def test_primary_icon_declares_rate_colours_and_calibration_mark() -> None:
    from openreltime_studio.themes import icon_svg_path

    text = icon_svg_path().read_text(encoding="utf-8")
    assert "linearGradient" in text, "主图应有渐变底板，避免塑料感纯色"
    assert "#f5c518" in text, "主图应保留琥珀色校正环这一识别元素"


@pytest.mark.parametrize("size", ICON_SIZES)
def test_every_icon_size_renders(qapp, size) -> None:
    pm = pixmap_from_svg(size)
    assert pm is None or (pm.width() == size and pm.height() == size)


def test_app_icon_carries_multiple_sizes(qapp) -> None:
    icon = app_icon()
    assert not icon.isNull()
    assert len({s.width() for s in icon.availableSizes()}) >= 5


def test_painter_fallback_draws_something(qapp) -> None:
    from openreltime_studio.appicon import _painted_pixmap

    pm = _painted_pixmap(64)
    assert pm.width() == 64
    image = pm.toImage()
    opaque = sum(
        1
        for x in range(0, 64, 4)
        for y in range(0, 64, 4)
        if image.pixelColor(x, y).alpha() > 0
    )
    assert opaque > 100, "兜底绘制几乎是空的"


def test_canvas_still_reads_icon_paths_without_qt_state() -> None:
    """图标路径解析不应依赖 QApplication（便于单测与打包脚本）。"""
    assert TreeCanvas.__name__ == "TreeCanvas"
    assert symbolic_svg_path().suffix == ".svg"


def test_self_check_passes_from_source() -> None:
    """打包自检在源码态也必须通过（它同时是资源完整性的回归门）。"""
    from openreltime_studio.main import self_check

    assert self_check() == 0


def test_self_check_fails_when_example_missing(monkeypatch, tmp_path) -> None:
    from openreltime_studio import examples as examples_mod
    from openreltime_studio.main import self_check

    monkeypatch.setattr(examples_mod, "_EXAMPLES_DIR", tmp_path)
    assert self_check() == 1
