"""UI 布局与交互修复的回归测试。

覆盖四条界面契约（对应 v0.1.2 修复）：

1. 左侧分析标签页的竖向高度跟随**当前页**：矮的页（RRF/CI/CorrTest/ddBD）
   不得被最高的页（校正）撑出「参数组与导出组之间」的大片空白；
2. 右侧节点表列宽归用户管：Interactive 模式、初始按内容适配、同列集
   重填不覆盖手动列宽；
3. 树画布点选节点后必须在树上留下可见的选中环，且样式区别于校正点标记，
   校正列表变动后撤环；
4. 打包位图（icon.png / icon.icns 的来源）按 macOS 图标网格留边，
   Dock 图标不得明显大于系统其他应用。

收集粒度：真跑 UI 的用例需要引擎 ``openreltime``（经 main_window 的导入链）
与 Qt，模块级先拦引擎、用例级再标 ``requires_qt``，与
``test_tree_orientation.py`` 的门控策略一致。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from openreltime_studio.tests import _availability as availability  # noqa: E402

pytestmark = pytest.mark.requires_engine

availability.require_engine()

from openreltime_studio.adapters import (  # noqa: E402
    openreltime_adapter as adapter,
)

STUDIO = ROOT / "openreltime_studio"

SMALL_NEWHICK = (
    "(((taxonA:0.10,taxonB:0.12)AB:0.03,(taxonC:0.20,taxonD:0.22)CD:0.05)"
    "ABCD:0.03,(taxonE:0.30,taxonF:0.33)EF:0.07)root;"
)


def _source(rel: str) -> str:
    return (STUDIO / rel).read_text(encoding="utf-8")


def _function_source(rel: str, name: str) -> str:
    source = _source(rel)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(f"function {name} not found in {rel}")


# ── 1. 分析标签页高度跟随当前页 ──────────────────────────────────────────


class TestTabsFollowCurrentPage:
    def test_main_window_uses_the_current_height_tab_widget(self):
        """静态：主窗口的分析标签页必须是高度自适应容器。"""
        source = _source("windows/main_window.py")
        assert "class CurrentHeightTabWidget(QTabWidget)" in source
        assert "self.analysis_tabs = CurrentHeightTabWidget()" in source

    @pytest.mark.requires_qt  # 需要 PySide6 才能量测布局
    def test_short_page_is_no_longer_stretched_to_the_tallest_page(self, qapp):
        """真跑：矮页的高度 ≈ 自己的内容；切到高页时容器随内容长高。"""
        from PySide6.QtWidgets import (
            QFormLayout,
            QGroupBox,
            QLabel,
            QTabWidget,
            QTableWidget,
            QVBoxLayout,
            QWidget,
        )

        from openreltime_studio.windows.main_window import CurrentHeightTabWidget

        def page(rows: int, *, tall: bool = False) -> QWidget:
            w = QWidget()
            layout = QVBoxLayout(w)
            group = QGroupBox("params")
            form = QFormLayout(group)
            for i in range(rows):
                form.addRow(QLabel(f"label{i}"), QLabel("value"))
            layout.addWidget(group)
            if tall:
                table = QTableWidget(8, 4)
                table.setMinimumHeight(240)
                layout.addWidget(table)
            layout.addStretch(1)
            return w

        tabs = CurrentHeightTabWidget()
        short = page(2)
        tall = page(2, tall=True)
        tabs.addTab(short, "short")
        tabs.addTab(tall, "tall")

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.addWidget(tabs)
        outer.addStretch(1)
        container.resize(400, 900)
        container.show()
        qapp.processEvents()

        assert isinstance(tabs, QTabWidget)
        height_short = tabs.height()
        # 矮页不得被高页撑高：容器有大量剩余空间（含末尾 stretch）时，
        # 标签页高度必须贴近矮页自己的 sizeHint
        assert height_short <= short.sizeHint().height() + tabs.tabBar().height() + 8
        assert height_short < tall.sizeHint().height()

        tabs.setCurrentIndex(1)
        qapp.processEvents()
        height_tall = tabs.height()
        assert height_tall >= tall.sizeHint().height() - 8

        tabs.setCurrentIndex(0)
        qapp.processEvents()
        assert tabs.height() <= height_short + 8

    @pytest.mark.requires_qt  # 需要构造整个主窗口
    def test_every_tab_keeps_export_group_adjacent_after_visiting_calibration(
        self, qapp
    ):
        """真跑（主窗口）：访过高页再切回矮页，「导出」组必须仍然紧贴页尾。

        旧缺陷正是这条序列暴露的：QTabWidget 的 heightForWidth 会把最高页
        （校正）的 hfw 透传给外层布局，先访校正页再切 CI 时容器停在 748px。
        """
        from PySide6.QtWidgets import QGroupBox

        from openreltime_studio.windows.main_window import MainWindow

        window = MainWindow()
        try:
            window.resize(1280, 800)
            window.show()
            qapp.processEvents()
            tabs = window.analysis_tabs

            def flush() -> None:
                """跑完延迟布局事件，否则切换页后的高度还没生效。"""
                from PySide6.QtCore import QCoreApplication

                qapp.processEvents()
                QCoreApplication.sendPostedEvents(None, 0)
                qapp.processEvents()

            # 先访问最高的校正页，让缺陷在旧实现下必然触发
            tabs.setCurrentIndex(1)
            flush()
            calibration_height = tabs.height()

            for idx, name in enumerate(("RRF", "Calibration", "CI", "CorrTest", "ddBD")):
                tabs.setCurrentIndex(idx)
                flush()
                assert tabs.hasHeightForWidth() == tabs.currentWidget().hasHeightForWidth()
                tabs_bottom = tabs.y() + tabs.height()
                export = next(
                    child
                    for child in window.findChildren(QGroupBox)
                    if child.parentWidget() is tabs.parentWidget() and child.y() >= tabs_bottom
                )
                gap = export.y() - tabs_bottom
                assert gap <= 24, f"tab {name}: gap(tabs→export) = {gap}px"
                if idx != 1:
                    assert tabs.height() < calibration_height, (
                        f"tab {name} stretched to the calibration page height"
                    )
        finally:
            window.close()
            window.deleteLater()


# ── 2. 节点表列宽可拖拽 ─────────────────────────────────────────────────


class TestNodeTableInteractiveColumns:
    def test_header_no_longer_uses_resize_to_contents(self):
        """静态：ResizeToContents 会收回列宽控制权，表头拖不动。"""
        source = _source("widgets/node_table.py")
        assert "ResizeToContents" not in source

    @pytest.mark.requires_qt  # 需要 PySide6 才能操作 QHeaderView
    def test_columns_start_interactive_and_draggable(self, qapp):
        import pandas as pd
        from PySide6.QtWidgets import QHeaderView

        from openreltime_studio.widgets.node_table import NodeTable

        table = NodeTable()
        header = table.horizontalHeader()
        # 空表头（0 列）下 sectionResizeMode 走越界回退值，须建列后再断言
        table.setColumnCount(3)
        assert header.sectionResizeMode(0) == QHeaderView.Interactive

        df = pd.DataFrame({"NodeLabel": ["A", "LongerName"], "Time": [1.0, 2.0]})
        table.fill_from_dataframe(df)
        # 初始列宽仍按内容适配（与旧行为一致）
        assert table.columnWidth(0) >= table.fontMetrics().horizontalAdvance(
            "LongerName"
        )

        header.resizeSection(0, 233)  # 模拟用户拖拽列边界
        table.fill_from_dataframe(df)  # 同列集重填：不得收回手动列宽
        assert table.columnWidth(0) == 233

        df2 = pd.DataFrame({"node_id": [1, 2], "se": [0.1, 0.2]})
        table.fill_from_dataframe(df2)  # 列结构变化后重新按内容适配
        assert table.columnWidth(0) != 233


# ── 3. 树画布点选节点的高亮环 ───────────────────────────────────────────


def _selection_rings(canvas) -> list:
    """画布上的空心选中环（markersize ≥ 12 且无填充）。"""
    return [
        line
        for line in canvas.ax.lines
        if line.get_marker() == "o"
        and line.get_markersize() >= 12
        and line.get_markerfacecolor() in ("none", None)
    ]


class TestCanvasNodeSelection:
    @pytest.fixture
    def small_result(self, tmp_path):
        tree_path = tmp_path / "small.nwk"
        tree_path.write_text(SMALL_NEWHICK + "\n", encoding="utf-8")
        tree = adapter.read_tree(tree_path)
        return adapter.run_rrf_rates_times(tree)

    @pytest.fixture
    def canvas(self, qapp, small_result):
        from openreltime_studio.widgets.tree_canvas import TreeCanvas

        canvas = TreeCanvas()
        canvas.plot_timetree(small_result, use_rates=True)
        yield canvas
        canvas.deleteLater()

    @pytest.mark.requires_qt  # 需要 PySide6 + matplotlib Qt 画布
    def test_selected_node_is_drawn_as_a_hollow_ring(self, canvas, small_result):
        """点选后树上必须留下可见且区别于校正点的标记。"""
        internal = [n.node_id for n in small_result.tree.walk() if not n.is_tip()]
        node_id = internal[0]

        assert _selection_rings(canvas) == []
        canvas.set_selected_node(node_id)
        assert canvas.selected_node == node_id
        rings = _selection_rings(canvas)
        assert len(rings) == 1

        # 同一节点加为校正点后：实心标记与选中环并存，样式可区分
        canvas.mark_calibration_node(node_id)
        rings = _selection_rings(canvas)
        assert len(rings) == 1
        solids = [
            line
            for line in canvas.ax.lines
            if line.get_marker() == "o"
            and line.get_markersize() < 12
            and line.get_markerfacecolor() not in ("none", None)
        ]
        assert solids

    @pytest.mark.requires_qt  # 需要 PySide6 + matplotlib Qt 画布
    def test_ring_survives_tree_replot_and_clears_on_request(self, canvas, small_result):
        """主题/语言切换会整树重绘：选中环必须像校正点一样被保留。"""
        internal = [n.node_id for n in small_result.tree.walk() if not n.is_tip()]
        node_id = internal[0]
        canvas.set_selected_node(node_id)

        canvas.plot_timetree(small_result, use_rates=True)
        assert len(_selection_rings(canvas)) == 1

        canvas.clear_selected_node()
        assert canvas.selected_node is None
        assert _selection_rings(canvas) == []

    def test_main_window_wires_click_to_ring_and_calibration_list_to_clear(self):
        """静态：点击回调设置选中环，校正列表变动后撤环。"""
        clicked = _function_source("windows/main_window.py", "_on_node_clicked")
        assert "set_selected_node" in clicked
        changed = _function_source(
            "windows/main_window.py", "_on_calibrations_changed"
        )
        assert "clear_selected_node" in changed

    @pytest.mark.requires_qt  # 需要构造整个主窗口
    def test_click_flow_end_to_end(self, qapp, tmp_path):
        """真跑：canvas 点击信号 → 选中环 + 编辑器目标节点；添加校正后撤环。"""
        from openreltime_studio.windows.main_window import MainWindow

        tree_path = tmp_path / "small.nwk"
        tree_path.write_text(SMALL_NEWHICK + "\n", encoding="utf-8")
        window = MainWindow()
        try:
            result = adapter.run_rrf_rates_times(adapter.read_tree(tree_path))
            window.canvas.plot_timetree(result)
            internal = [n.node_id for n in result.tree.walk() if not n.is_tip()]
            # 直接驱动画布点击的信号源；命中判定由 _nearest_node_px 单独负责
            window.canvas.node_clicked.emit(internal[0])
            assert window.canvas.selected_node == internal[0]
            assert window.calibration_editor._pending_node_id == internal[0]

            # 添加校正 → calibrations_changed → 撤环。
            # 勾一个下界，避免无约束校正在 _on_add_calibration 里弹模态警告框
            editor = window.calibration_editor
            editor.min_check.setChecked(True)
            editor._on_add_calibration()
            assert editor.calibrations
            assert window.canvas.selected_node is None
        finally:
            window.deleteLater()


# ── 4. 打包位图按 macOS 图标网格留边 ────────────────────────────────────


class TestBundleIconMargins:
    def test_make_icon_uses_the_macos_fill(self):
        """静态：打包脚本必须用缩进比例渲染 icon.png / icon.icns。"""
        source = _source("resources/make_icon.py")
        assert "fill_ratio=MACOS_ICON_FILL" in source
        appicon = _source("appicon.py")
        assert "MACOS_ICON_FILL" in appicon

    @pytest.mark.requires_qt  # 需要 PySide6.QtSvg 渲染
    def test_padded_pixmap_keeps_macos_margins(self, qapp):
        """真跑：画布四角透明，主体占比落在 macOS 图标网格附近。"""
        from openreltime_studio.appicon import MACOS_ICON_FILL, pixmap_from_svg

        size = 256
        pm = pixmap_from_svg(size, fill_ratio=MACOS_ICON_FILL)
        assert pm is not None
        img = pm.toImage()
        for x, y in ((1, 1), (size - 2, 1), (1, size - 2), (size - 2, size - 2)):
            assert img.pixelColor(x, y).alpha() == 0, f"corner ({x},{y}) not transparent"

        # 沿中行扫主体宽度：HIG ≈ 80.5%；fill=0.88 × SVG 自身边距 ≈ 0.797
        row = size // 2
        opaque = [x for x in range(size) if img.pixelColor(x, row).alpha() > 0]
        assert opaque
        body = (max(opaque) - min(opaque) + 1) / size
        assert 0.75 <= body <= 0.83, f"icon body ratio {body:.3f} off the macOS grid"
