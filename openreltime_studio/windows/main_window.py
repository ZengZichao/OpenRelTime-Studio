"""OpenRelTime Studio 主窗口。

布局：左向导/参数 → 中主画布 → 右结果表 → 底状态栏。

支持的分析模块（M2 全分析模块页）：
- RRF Rates+Times（M0 基础）
- Calibrate（M1 交互式校正）
- Confidence Interval
- CorrTest
- ddBD

所有计算经 QThread Worker 异步执行，界面不卡死；运行期间统一由
``_refresh_actions`` 禁用入口、显示等待光标，结束后按当前状态恢复。
所有 ``import openreltime`` 经由适配层 ``adapters``。

界面文案全部取自 ``i18n`` 目录（中英文即时切换、偏好持久化），颜色全部取自
``themes`` 令牌（亮/暗即时切换）；两者都在「视图」菜单里切换。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from openreltime import (
    CalibratedResult,
    CIResult,
    CorrTestResult,
    DDBDResult,
    PhyloNode,
    TimeResult,
)
from openreltime_studio import i18n, themes
from openreltime_studio.examples import example_files
from openreltime_studio.adapters import openreltime_adapter as adapter
from openreltime_studio.main import LOG_COLLECTOR
from openreltime_studio.widgets.calibration_editor import CalibrationEditor
from openreltime_studio.widgets.node_table import NodeTable
from openreltime_studio.widgets.param_panels import (
    CalibrateParamsWidget,
    CIParamsWidget,
    CorrTestParamsWidget,
    DDBDParamsWidget,
    RRFParamsWidget,
)
from openreltime_studio.widgets.tree_canvas import TreeCanvas
from openreltime_studio.workers.analysis_workers import (
    CANCELLED_FLAG,
    CalibrateWorker,
    CIWorker,
    CorrTestWorker,
    DDBDWorker,
    RRFWorker,
    TimesOnlyWorker,
    TreeReadWorker,
)

logger = logging.getLogger("openreltime")

#: 标签页顺序 → 文案键（切换语言时按此重设 tab 文本）
_TAB_KEYS = (
    "menu.tab_rrf",
    "menu.tab_calibrate",
    "menu.tab_ci",
    "menu.tab_corrtest",
    "menu.tab_ddbd",
)


class MainWindow(QMainWindow):
    """OpenRelTime Studio 主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenRelTime Studio")
        self.resize(1280, 800)

        # 状态
        self.tree: Optional[PhyloNode] = None
        self.tree_path: Optional[str] = None
        self.rrf_result: Optional[TimeResult] = None
        self.calibrated_result: Optional[CalibratedResult] = None
        self.ci_result: Optional[CIResult] = None
        self.corrtest_result: Optional[CorrTestResult] = None
        self.ddbd_result: Optional[DDBDResult] = None

        # 运行中的 Worker 登记表：持引用防 GC，并作为“忙碌”状态的唯一来源
        self._active_workers: set = set()
        self._cursor_busy: bool = False

        # 等效 CLI：按分析阶段登记，导出时按流水线顺序拼成可重放脚本
        self._cli_commands: dict[str, str] = {}
        # File the calibration list was loaded from; set only while the list
        # still matches that file, because it is reported as
        # ``calibrations_file`` in the run report and the CLI replays against it.
        self._calibrations_source: Optional[str] = None
        self._loading_cals: bool = False
        # Current calibration worker: lets a cancelled run's result be discarded.
        self._cal_worker: Optional[CalibrateWorker] = None
        self._cal_progress: Optional[QProgressDialog] = None
        # Once the user picks a format by hand, extension detection must stop
        # overwriting the combo; otherwise a NEXUS file whose suffix is not
        # .nexus/.nex could never be read.
        self._fmt_manual: bool = False

        # 动态文案记住「键 + 参数」，切换语言时可原样重放
        self._status: Optional[tuple[str, dict, int]] = None
        self._summary: Optional[tuple[str, dict]] = None
        #: 载入内置示例树后，等树读完了再补上示例校正点
        self._example_pending: bool = False

        # 设置
        self.settings = QSettings("OpenRelTime", "Studio")

        self._build_ui()
        self._build_menu()
        # 校正点列表变动 → 画布标记同步（增删均即时反映）
        self.calibration_editor.calibrations_changed.connect(
            self._on_calibrations_changed
        )
        self._restore_state()
        self._refresh_actions()
        i18n.on_language_change(self._on_language_change)

    # ---- UI 构建 -------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        # ── 左侧：向导与参数 ─────────────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_content = QWidget()
        left_content.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 4, 8)
        left_layout.setSpacing(8)

        # 文件导入区
        file_group = QGroupBox()
        i18n.bind(file_group, "setTitle", "panel.import_group")
        file_layout = QFormLayout(file_group)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        i18n.bind_placeholder(self.path_edit, "panel.tree_unselected")
        self.btn_open = QPushButton()
        i18n.bind_text(self.btn_open, "panel.choose_tree")
        i18n.bind_tooltip(self.btn_open, "panel.choose_tree_tip")
        self.btn_open.clicked.connect(self.choose_file)
        self.btn_example = QPushButton()
        i18n.bind_text(self.btn_example, "panel.example")
        i18n.bind_tooltip(self.btn_example, "panel.example_tip")
        self.btn_example.clicked.connect(self.load_example)
        file_row = QHBoxLayout()
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(self.btn_open)
        self._add_row(file_layout, "panel.tree_file", file_row)
        # 示例按钮独占一行：与「选择树文件」并排会把路径框挤到看不见文件名
        file_layout.addRow(self.btn_example)

        self.og_edit = QLineEdit()
        i18n.bind_placeholder(self.og_edit, "panel.outgroup_placeholder")
        self._add_row(file_layout, "panel.outgroup", self.og_edit)

        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["newick", "nexus"])
        i18n.bind_tooltip(self.fmt_combo, "panel.format_tip")
        self.fmt_combo.currentTextChanged.connect(self._on_format_changed)
        self._add_row(file_layout, "panel.format", self.fmt_combo)

        self.resolve_combo = QComboBox()
        self.resolve_combo.addItems(["error", "random"])
        i18n.bind_tooltip(self.resolve_combo, "panel.polytomy_tip")
        self._add_row(file_layout, "panel.polytomy", self.resolve_combo)

        self.outgroup_check_combo = QComboBox()
        self.outgroup_check_combo.addItems(["error", "warn"])
        i18n.bind_tooltip(self.outgroup_check_combo, "panel.outgroup_check_tip")
        self._add_row(file_layout, "panel.outgroup_check", self.outgroup_check_combo)

        left_layout.addWidget(file_group)

        # 分析类型标签页
        self.analysis_tabs = QTabWidget()
        self.analysis_tabs.setDocumentMode(True)

        # Tab 1: RRF
        rrf_tab = QWidget()
        rrf_layout = QVBoxLayout(rrf_tab)
        self.rrf_params = RRFParamsWidget()
        rrf_layout.addWidget(self.rrf_params)
        self.btn_run_rrf = self._make_run_button("panel.run_rrf", self.run_rrf)
        rrf_layout.addWidget(self.btn_run_rrf)
        rrf_layout.addStretch(1)

        # Tab 2: Calibrate
        cal_tab = QWidget()
        cal_layout = QVBoxLayout(cal_tab)
        self.calibrate_params = CalibrateParamsWidget()
        cal_layout.addWidget(self.calibrate_params)
        self.calibration_editor = CalibrationEditor()
        cal_layout.addWidget(self.calibration_editor)
        self.btn_load_cals = QPushButton()
        i18n.bind_text(self.btn_load_cals, "panel.load_cals")
        self.btn_load_cals.clicked.connect(self.load_calibrations_file)
        cal_layout.addWidget(self.btn_load_cals)
        self.btn_run_calibrate = self._make_run_button(
            "panel.run_calibrate", self.run_calibrate
        )
        i18n.bind_tooltip(self.btn_run_calibrate, "panel.run_calibrate_tip")
        cal_layout.addWidget(self.btn_run_calibrate)
        cal_layout.addStretch(1)
        self._cal_tab = cal_tab

        # Tab 3: CI
        ci_tab = QWidget()
        ci_layout = QVBoxLayout(ci_tab)
        self.ci_params = CIParamsWidget()
        ci_layout.addWidget(self.ci_params)
        self.btn_run_ci = self._make_run_button("panel.run_ci", self.run_ci)
        i18n.bind_tooltip(self.btn_run_ci, "panel.run_ci_tip")
        ci_layout.addWidget(self.btn_run_ci)
        ci_layout.addStretch(1)

        # Tab 4: CorrTest
        ct_tab = QWidget()
        ct_layout = QVBoxLayout(ct_tab)
        self.corrtest_params = CorrTestParamsWidget()
        ct_layout.addWidget(self.corrtest_params)
        self.btn_run_corrtest = self._make_run_button(
            "panel.run_corrtest", self.run_corrtest
        )
        ct_layout.addWidget(self.btn_run_corrtest)
        ct_layout.addStretch(1)

        # Tab 5: ddBD
        bd_tab = QWidget()
        bd_layout = QVBoxLayout(bd_tab)
        self.ddbd_params = DDBDParamsWidget()
        bd_layout.addWidget(self.ddbd_params)
        self.btn_run_ddbd = self._make_run_button("panel.run_ddbd", self.run_ddbd)
        bd_layout.addWidget(self.btn_run_ddbd)
        bd_layout.addStretch(1)

        for widget, key in zip(
            (rrf_tab, cal_tab, ci_tab, ct_tab, bd_tab), _TAB_KEYS, strict=True
        ):
            self.analysis_tabs.addTab(widget, i18n.t(key))

        left_layout.addWidget(self.analysis_tabs)

        # 导出
        export_group = QGroupBox()
        i18n.bind(export_group, "setTitle", "panel.export_group")
        export_layout = QVBoxLayout(export_group)
        self.btn_export = QPushButton()
        i18n.bind_text(self.btn_export, "panel.export")
        i18n.bind_tooltip(self.btn_export, "panel.export_tip")
        self.btn_export.clicked.connect(self.export_results)
        export_layout.addWidget(self.btn_export)
        left_layout.addWidget(export_group)

        # 引擎警告徽标（openreltime 日志经 main.LOG_COLLECTOR 汇集）
        self.btn_warnings = QPushButton()
        i18n.bind_tooltip(self.btn_warnings, "panel.warnings_tip")
        self.btn_warnings.clicked.connect(self.show_engine_warnings)
        self.btn_warnings.setVisible(False)
        left_layout.addWidget(self.btn_warnings)

        # 等效 CLI
        cli_group = QGroupBox()
        i18n.bind(cli_group, "setTitle", "panel.cli_group")
        cli_layout = QVBoxLayout(cli_group)
        self.cli_text = QTextEdit()
        self.cli_text.setReadOnly(True)
        self.cli_text.setMaximumHeight(100)
        cli_layout.addWidget(self.cli_text)
        self.btn_copy_cli = QPushButton()
        i18n.bind_text(self.btn_copy_cli, "panel.copy_cli")
        i18n.bind_tooltip(self.btn_copy_cli, "panel.copy_cli_tip")
        self.btn_copy_cli.clicked.connect(self.copy_cli)
        cli_layout.addWidget(self.btn_copy_cli)
        left_layout.addWidget(cli_group)

        left_layout.addStretch(1)
        left_scroll.setWidget(left_content)
        splitter.addWidget(left_scroll)

        # ── 中央：主画布 ───────────────────────────────────────────────
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(4, 0, 4, 8)
        self.canvas = TreeCanvas(width=8, height=6)
        self.canvas.setMinimumWidth(320)
        center_layout.addWidget(self.canvas, 1)
        splitter.addWidget(center)

        # ── 右侧：结果表 ──────────────────────────────────────────────
        right = QWidget()
        right.setMinimumWidth(240)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 8)
        right_label = QLabel()
        right_label.setObjectName("panelTitle")
        i18n.bind_text(right_label, "panel.node_table")
        right_layout.addWidget(right_label)
        self.table_summary = QLabel("")
        self.table_summary.setObjectName("hintLabel")
        self.table_summary.setWordWrap(True)
        right_layout.addWidget(self.table_summary)
        self.node_table = NodeTable()
        right_layout.addWidget(self.node_table, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([360, 560, 360])
        root.addWidget(splitter)

        # 状态栏
        self._show_status("status.ready")
        self._render_cli()

        # 连接画布信号
        self.canvas.node_clicked.connect(self._on_node_clicked)
        self.canvas.node_hovered.connect(self._on_node_hovered)

    def _add_row(self, layout: QFormLayout, key: str, field) -> None:
        """加一行表单标签（标签文本随语言切换刷新）。"""
        label = QLabel()
        i18n.bind_text(label, key)
        layout.addRow(label, field)

    def _make_run_button(self, key: str, slot: Callable) -> QPushButton:
        """统一的「运行」按钮：强调色样式 + 初始禁用。"""
        btn = QPushButton()
        btn.setObjectName("accentButton")
        i18n.bind_text(btn, key)
        btn.clicked.connect(slot)
        btn.setEnabled(False)
        return btn

    def _build_menu(self):
        menubar = self.menuBar()

        fmenu = menubar.addMenu(i18n.t("menu.file"))
        i18n.bind_text(fmenu.menuAction(), "menu.file")
        self.open_action = QAction(self)
        i18n.bind_text(self.open_action, "menu.open")
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.choose_file)
        fmenu.addAction(self.open_action)

        self.example_action = QAction(self)
        i18n.bind_text(self.example_action, "menu.example")
        self.example_action.setShortcut("Ctrl+I")
        self.example_action.triggered.connect(self.load_example)
        fmenu.addAction(self.example_action)

        export_act = QAction(self)
        i18n.bind_text(export_act, "menu.export")
        export_act.setShortcut("Ctrl+E")
        export_act.triggered.connect(self.export_results)
        fmenu.addAction(export_act)

        fmenu.addSeparator()
        exit_act = QAction(self)
        i18n.bind_text(exit_act, "menu.quit")
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        fmenu.addAction(exit_act)

        vmenu = menubar.addMenu(i18n.t("menu.view"))
        i18n.bind_text(vmenu.menuAction(), "menu.view")
        self.show_rates_act = QAction(self, checkable=True)
        i18n.bind_text(self.show_rates_act, "menu.show_rates")
        self.show_rates_act.setChecked(True)
        self.show_rates_act.triggered.connect(self._toggle_rates)
        vmenu.addAction(self.show_rates_act)

        vmenu.addSeparator()
        self._build_language_menu(vmenu)
        self._build_theme_menu(vmenu)
        self._build_orientation_menu(vmenu)

        hmenu = menubar.addMenu(i18n.t("menu.help"))
        i18n.bind_text(hmenu.menuAction(), "menu.help")
        about_act = QAction(self)
        i18n.bind_text(about_act, "menu.about")
        about_act.triggered.connect(self.show_about)
        hmenu.addAction(about_act)

    def _build_language_menu(self, parent_menu):
        """语言子菜单：各语言用自身文字显示，故不进目录。"""
        submenu = parent_menu.addMenu(i18n.t("menu.language"))
        self._language_actions: dict[str, QAction] = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for code in i18n.available_languages():
            act = QAction(i18n.LANGUAGE_LABELS[code], self, checkable=True)
            act.setChecked(i18n.language() == code)
            act.triggered.connect(lambda _checked=False, c=code: i18n.set_language(c))
            group.addAction(act)
            submenu.addAction(act)
            self._language_actions[code] = act
        self._language_menu = submenu

    def _build_theme_menu(self, parent_menu):
        """亮/暗主题子菜单。"""
        submenu = parent_menu.addMenu(i18n.t("menu.theme"))
        self._theme_actions: dict[str, QAction] = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for code, key in (("light", "menu.theme_light"), ("dark", "menu.theme_dark")):
            act = QAction(self, checkable=True)
            i18n.bind_text(act, key)
            act.setChecked(themes.theme() == code)
            act.triggered.connect(lambda _checked=False, c=code: themes.set_theme(c))
            group.addAction(act)
            submenu.addAction(act)
            self._theme_actions[code] = act
        self._theme_menu = submenu

    #: 根节点朝向 → 文案键
    _ORIENTATION_KEYS = {
        "left": "menu.root_left",
        "right": "menu.root_right",
        "top": "menu.root_top",
        "bottom": "menu.root_bottom",
    }

    def _build_orientation_menu(self, parent_menu):
        """根节点方向子菜单：左 / 右 / 上 / 下。"""
        submenu = parent_menu.addMenu(i18n.t("menu.root_position"))
        self._orientation_actions: dict[str, QAction] = {}
        group = QActionGroup(self)
        group.setExclusive(True)
        for code, key in self._ORIENTATION_KEYS.items():
            act = QAction(self, checkable=True)
            i18n.bind_text(act, key)
            act.setChecked(self.canvas.orientation == code)
            act.triggered.connect(
                lambda _checked=False, c=code: self.canvas.set_orientation(c)
            )
            group.addAction(act)
            submenu.addAction(act)
            self._orientation_actions[code] = act
        self._orientation_menu = submenu

    def _on_language_change(self, _code: str) -> None:
        """切换语言后刷新 bind_* 覆盖不到的动态文本。"""
        for idx, key in enumerate(_TAB_KEYS):
            self.analysis_tabs.setTabText(idx, i18n.t(key))
        self._language_menu.setTitle(i18n.t("menu.language"))
        self._theme_menu.setTitle(i18n.t("menu.theme"))
        self._orientation_menu.setTitle(i18n.t("menu.root_position"))
        for code, act in self._language_actions.items():
            act.setChecked(i18n.language() == code)
        for code, act in self._theme_actions.items():
            act.setChecked(themes.theme() == code)
        for code, act in self._orientation_actions.items():
            act.setChecked(self.canvas.orientation == code)
        self._render_cli()
        self._update_warning_badge()
        if self._status is not None:
            key, params, timeout = self._status
            self.statusBar().showMessage(i18n.t(key, **params), timeout)
        if self._summary is not None:
            key, params = self._summary
            self.table_summary.setText(i18n.t(key, **params))
        if self._cal_progress is not None:
            self._cal_progress.setCancelButtonText(i18n.t("dialog.cancel"))

    # ---- 动态文案 ------------------------------------------------------

    def _show_status(self, key: str, timeout: int = 0, **params: object) -> None:
        """状态栏消息：记住键与参数，语言切换时原样重放。"""
        self._status = (key, params, timeout)
        self.statusBar().showMessage(i18n.t(key, **params), timeout)

    def _set_table_summary(self, key: str, **params: object) -> None:
        """更新节点表上方的摘要行（CorrTest/ddBD 等无表结果也在此呈现）。"""
        self._summary = (key, params)
        self.table_summary.setText(i18n.t(key, **params))

    # ---- 响应式状态 ------------------------------------------------------

    def _start_worker(self, worker, on_done: Callable):
        """登记并启动后台 Worker；结束时由内建 finished 信号统一恢复界面。"""
        self._active_workers.add(worker)
        worker.done.connect(on_done)
        # QThread 内建 finished：线程真正结束后触发（自定义信号已改名 done）
        worker.finished.connect(self._on_worker_finished)
        self._refresh_actions()
        worker.start()

    def _on_worker_finished(self):
        worker = self.sender()
        if worker is not None:
            self._active_workers.discard(worker)
            worker.deleteLater()
        self._refresh_actions()
        self._update_warning_badge()

    def _refresh_actions(self):
        """根据当前状态统一刷新所有入口的可用性（单一状态源）。"""
        busy = bool(self._active_workers)
        has_tree = self.tree is not None
        has_rrf = self.rrf_result is not None
        has_cal = self.calibrated_result is not None
        has_any_result = any(
            r is not None
            for r in (self.rrf_result, self.calibrated_result, self.ci_result,
                      self.corrtest_result, self.ddbd_result)
        )

        # 忙碌时显示等待光标
        if busy and not self._cursor_busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self._cursor_busy = True
        elif not busy and self._cursor_busy:
            QApplication.restoreOverrideCursor()
            self._cursor_busy = False

        self.open_action.setEnabled(not busy)
        self.btn_open.setEnabled(not busy)
        self.btn_example.setEnabled(not busy)
        self.btn_load_cals.setEnabled(not busy)

        self.btn_run_rrf.setEnabled(has_tree and not busy)
        self.btn_run_calibrate.setEnabled(has_rrf and not busy)
        self.btn_run_ci.setEnabled(has_cal and not busy)
        self.btn_run_corrtest.setEnabled(has_tree and not busy)
        self.btn_run_ddbd.setEnabled(has_tree and not busy)

        self.btn_export.setEnabled(has_any_result and not busy)

    def _invalidate_results(self):
        """丢弃全部分析结果并清空结果视图（加载新树时调用）。

        校正点必须一并失效：其 node_id 绑定的是旧树拓扑，套到新树会
        静默命中完全不同的支系。
        """
        self.rrf_result = None
        self.calibrated_result = None
        self.ci_result = None
        self.corrtest_result = None
        self.ddbd_result = None
        self.calibration_editor.clear()
        self.canvas.reset()
        self.node_table.clear_table()
        self._summary = None
        self.table_summary.setText("")
        self._cli_commands.clear()
        self._calibrations_source = None
        self._render_cli()

    def _on_calibrations_changed(self, calibrations: list):
        """Keep the canvas marks in sync with the calibration list, removals included.

        A ``taxon_set`` calibration carries no node_id, so its mark is placed
        on the node it resolves to in the current tree.  Such a calibration is
        valid input and must survive loading, otherwise its mark could never
        appear.
        """
        if not self._loading_cals:
            # 列表被手动改动后与来源文件不再一致，不得再声明该文件为来源
            self._calibrations_source = None
        ids = []
        if self.tree is not None:
            for cal in calibrations:
                node = adapter.resolve_calibration_target(self.tree, cal)
                if node is not None:
                    ids.append(node.node_id)
        self.canvas.set_calibration_marks(ids)

    def _update_warning_badge(self) -> None:
        """按引擎警告数量刷新徽标可见性与文案。"""
        n = LOG_COLLECTOR.count()
        self.btn_warnings.setText(i18n.t("panel.warnings_badge", count=n))
        self.btn_warnings.setVisible(n > 0)

    def show_engine_warnings(self) -> None:
        """弹窗展示 openreltime 引擎的警告日志。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(i18n.t("dialog.warnings_title"))
        layout = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(
            "\n".join(LOG_COLLECTOR.records) or i18n.t("dialog.warnings_empty")
        )
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.resize(640, 360)
        dlg.exec()

    # ---- 文件导入 ------------------------------------------------------

    @property
    def input_fmt(self) -> str:
        """当前生效的树文件格式（用户可在下拉框手改）。"""
        return self.fmt_combo.currentText()

    @property
    def resolve_polytomy(self) -> str:
        return self.resolve_combo.currentText()

    @property
    def outgroup_check(self) -> str:
        return self.outgroup_check_combo.currentText()

    def choose_file(self):
        if self._active_workers:
            return
        last_dir = self.settings.value("last_tree_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.t("dialog.tree_chooser"),
            last_dir,
            f"{i18n.t('dialog.tree_filter')};;{i18n.t('dialog.all_files_filter')}",
        )
        if not path:
            return
        self.path_edit.setText(path)
        self.settings.setValue("last_tree_dir", str(Path(path).parent))

        # Extension detection only supplies a default: once the user has chosen
        # a format by hand it must not be overwritten, because a NEXUS file
        # saved under something other than a .nexus/.nex suffix would otherwise
        # never be readable.
        detected = adapter.detect_format(path)
        if not self._fmt_manual and self.fmt_combo.findText(detected) >= 0:
            self.fmt_combo.blockSignals(True)
            self.fmt_combo.setCurrentText(detected)
            self.fmt_combo.blockSignals(False)
        self._read_tree_file(path)

    def load_example(self) -> None:
        """载入随包发行的示例树（并排队载入配套示例校正点）。"""
        if self._active_workers:
            return
        try:
            tree_path = example_files()["tree"]
        except FileNotFoundError as exc:
            QMessageBox.critical(
                self,
                i18n.t("dialog.example_missing_title"),
                i18n.t("dialog.example_missing_body", error=exc),
            )
            return
        self.path_edit.setText(str(tree_path))
        self._example_pending = True
        self._read_tree_file(str(tree_path))

    def _load_example_calibrations(self) -> None:
        """示例树读完后补上演示校正点：与手动「从 TSV 加载」走同一条路径。"""
        from openreltime_studio.adapters import openreltime_adapter as _adapter

        try:
            cal_path = example_files()["calibrations"]
            self.calibration_editor.load_from_file(cal_path)
        except Exception as exc:  # noqa: BLE001 - 示例只是锦上添花，不得打断载入
            logger.warning(i18n.t("status.example_cals_failed"), exc_info=exc)
            self._show_status("status.example_cals_failed")
            return
        valid, _problems = _adapter.validate_calibrations(
            self.tree, self.calibration_editor.calibrations
        )
        self.calibration_editor.replace_calibrations(valid)
        self._show_status(
            "status.example_ready",
            tips=len(self.tree.tips()),
            cals=len(self.calibration_editor.calibrations),
        )

    def _on_format_changed(self, _fmt: str) -> None:
        """用户手改格式：已选中文件时按新格式重读，让下拉框真正生效。"""
        self._fmt_manual = True
        if self.tree_path and not self._active_workers:
            self._read_tree_file(self.tree_path)

    def _read_tree_file(self, path: str) -> None:
        """按当前 fmt / outgroup / 多岔 / 外群校验设置读取树文件。"""
        self.tree_path = path
        self._show_status("status.reading_tree")
        self._start_worker(
            TreeReadWorker(
                path,
                outgroup=self._parse_outgroup(),
                fmt=self.input_fmt,
                resolve_polytomy=self.resolve_polytomy,
                outgroup_check=self.outgroup_check,
            ),
            self._on_tree_loaded,
        )

    def _on_tree_loaded(self, tree: Optional[PhyloNode], err: str):
        if err:
            QMessageBox.critical(self, i18n.t("dialog.read_failed_title"), err)
            self._show_status("status.read_failed")
            return

        self.tree = tree
        # 新树使既有结果与视图全部失效，避免旧结果误配新树
        self._invalidate_results()
        # 手动格式覆盖只对当前这一次读取生效：换树后重新按扩展名检测
        self._fmt_manual = False

        info = adapter.tree_summary(tree)
        self._show_status(
            "status.tree_loaded",
            name=Path(self.tree_path).name,
            tips=info["n_tips"],
            internal=info["n_internal"],
            tree_kind=i18n.t(
                "status.tree_binary" if info["is_binary"] else "status.tree_nonbinary"
            ),
        )
        if self._example_pending:
            self._example_pending = False
            self._load_example_calibrations()

    def _parse_outgroup(self) -> Optional[list[str]]:
        text = self.og_edit.text().strip()
        if not text:
            return None
        return [t.strip() for t in text.split(",") if t.strip()]

    # ---- RRF 分析 ------------------------------------------------------

    def run_rrf(self):
        if self.tree is None or self._active_workers:
            return
        self._show_status("status.rrf_running")

        self._start_worker(
            RRFWorker(
                self.tree,
                mean=self.rrf_params.mean,
                normalize=self.rrf_params.normalize,
                rate_ratio_threshold=self.rrf_params.rate_ratio_threshold,
            ),
            self._on_rrf_finished,
        )

    def _on_rrf_finished(self, result: Optional[TimeResult], err: str):
        if err:
            QMessageBox.critical(self, i18n.t("dialog.rrf_failed_title"), err)
            self._show_status("status.rrf_failed")
            return

        self.rrf_result = result
        # 重跑 RRF 后所有依赖该结果的旧分析全部失效
        self.calibrated_result = None
        self.ci_result = None
        self.corrtest_result = None
        self.ddbd_result = None

        # 绘制时间树
        self.canvas.plot_timetree(result, use_rates=self.show_rates_act.isChecked())

        # 填充表格
        df = adapter.result_to_dataframe(result, with_rate=True)
        self.node_table.fill_from_dataframe(df)

        info = adapter.result_summary(result)
        self._show_status(
            "status.rrf_done",
            nodes=info.get("n_nodes", 0),
            mean=info.get("mean", "geometric"),
            normalize=info.get("normalize", False),
        )
        self._update_cli_rrf()

    # ---- 校正 ----------------------------------------------------------

    def load_calibrations_file(self):
        last_dir = self.settings.value("last_cal_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.t("dialog.cal_chooser"),
            last_dir,
            f"{i18n.t('dialog.cal_filter')};;{i18n.t('dialog.all_files_filter')}",
        )
        if not path:
            return
        try:
            n = self.calibration_editor.load_from_file(path)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                i18n.t("dialog.log_cals_load_failed", error=exc), exc_info=exc
            )
            QMessageBox.critical(
                self,
                i18n.t("dialog.load_cals_failed_title"),
                f"{type(exc).__name__}: {exc}",
            )
            self._show_status("status.cals_load_failed")
            return

        # Validate each target against the current tree at load time rather
        # than only when an analysis runs.  A calibration that names a
        # taxon_set without a node_id is valid input -- the engine resolves it
        # to that clade's MRCA -- so it must be kept, not dropped as malformed.
        self._loading_cals = True
        problems: list[str] = []
        try:
            if self.tree is not None:
                valid, problems = adapter.validate_calibrations(
                    self.tree, self.calibration_editor.calibrations
                )
                if problems:
                    self.calibration_editor.replace_calibrations(valid)
                    QMessageBox.warning(
                        self,
                        i18n.t("dialog.cal_validation_title"),
                        i18n.t(
                            "dialog.cal_validation_body", items="\n".join(problems)
                        ),
                    )
                    n = len(valid)
        finally:
            self._loading_cals = False
        # Remember where the list came from: run_calibrate writes this as
        # ``calibrations_file`` in the report, which is what lets the exported
        # ``_report.json`` be replayed directly by ``openreltime ci``.
        self._calibrations_source = str(Path(path).resolve()) if not problems else None
        self.settings.setValue("last_cal_dir", str(Path(path).parent))
        self._show_status(
            "status.cals_loaded", timeout=4000, name=Path(path).name, count=n
        )

    def run_calibrate(self):
        if self.rrf_result is None or self._active_workers:
            return

        cals = self.calibration_editor.calibrations
        if not cals:
            QMessageBox.warning(
                self, i18n.t("dialog.notice_title"), i18n.t("dialog.need_calibrations")
            )
            return

        # Re-check the bounds before running: a ticked "max" left at its default
        # would hand 0.0 to the solver, scaling every age in the tree to zero
        # without raising an error, and a density-only calibration paired with
        # the bounds method leaves the engine solving the time factor as inf.
        messages = []
        for cal in cals:
            problem = adapter.bound_error(
                cal.min_bound, cal.max_bound, cal.density,
                method=self.calibrate_params.method,
            )
            if problem is not None:
                messages.append(f"{adapter.describe_calibration_target(cal)}: {problem}")
        if messages:
            QMessageBox.critical(
                self,
                i18n.t("dialog.invalid_cals_title"),
                i18n.t("dialog.invalid_cals_body", items="\n".join(messages)),
            )
            self._show_status("status.cals_invalid")
            return

        self._show_status("status.cal_running")

        worker = CalibrateWorker(
            self.rrf_result,
            cals,
            method=self.calibrate_params.method,
            n_effective=self.calibrate_params.n_effective,
            seed=self.calibrate_params.seed,
            provenance=self._calibrate_provenance(),
        )
        self._cal_worker = worker
        # The effective method may run tens of thousands of repetitions, so it
        # reports per-repetition progress and can be interrupted mid-run.  The
        # bounds method is a single solve that cannot be stopped, so cancelling
        # it can only guarantee that its eventual result is thrown away.
        cancellable = self.calibrate_params.method == "effective"
        text = i18n.t(
            "dialog.cal_progress_effective"
            if cancellable
            else "dialog.cal_progress_bounds"
        )
        self._cal_progress = QProgressDialog(text, i18n.t("dialog.cancel"), 0, 0, self)
        self._cal_progress.setWindowModality(Qt.WindowModal)
        self._cal_progress.setMinimumDuration(300)
        self._cal_progress.canceled.connect(worker.cancel)
        worker.progress.connect(self._on_calibrate_progress)
        self._start_worker(worker, self._on_calibrate_finished)

    def _calibrate_provenance(self) -> dict:
        """Input settings recorded in the report so ``openreltime ci`` can replay them.

        ``tree_file`` has to be among them: without it the CLI's ci subcommand
        fails outright with "cannot locate the original tree".
        """
        prov: dict = {
            "input_fmt": self.input_fmt,
            "resolve_polytomy": self.resolve_polytomy,
            "outgroup_check": self.outgroup_check,
        }
        if self.tree_path:
            prov["tree_file"] = str(Path(self.tree_path).resolve())
        og = self._parse_outgroup()
        if og:
            prov["outgroup"] = og
        if self._calibrations_source:
            prov["calibrations_file"] = self._calibrations_source
        return prov

    def _on_calibrate_progress(self, done: int, total: int) -> None:
        if self._cal_progress is not None:
            self._cal_progress.setLabelText(
                i18n.t("dialog.cal_progress_count", done=done, total=total)
            )

    def _close_cal_progress(self) -> None:
        if self._cal_progress is not None:
            self._cal_progress.reset()
            self._cal_progress = None

    def _on_calibrate_finished(
        self, result: Optional[CalibratedResult], err: str
    ):
        worker, self._cal_worker = self._cal_worker, None
        self._close_cal_progress()
        cancelled = err == CANCELLED_FLAG or bool(
            worker is not None and worker.cancel_requested
        )
        if cancelled:
            # The user cancelled, so the result must not be applied even when
            # the bounds method ran to completion in the meantime.
            self._show_status("status.cal_cancelled", timeout=4000)
            return
        if err:
            QMessageBox.critical(self, i18n.t("dialog.cal_failed_title"), err)
            self._show_status("status.cal_failed")
            return

        self.calibrated_result = result
        self.ci_result = None

        # 重绘绝对时间树
        self.canvas.plot_timetree(result, use_rates=self.show_rates_act.isChecked())

        # 标记校正节点（报告里的 node_id 已按 taxon_set 解析）
        self.canvas.set_calibration_marks(
            [cal.node_id for cal in result.calibrations]
        )

        # 更新表格
        df = adapter.result_to_dataframe(result, with_rate=True)
        self.node_table.fill_from_dataframe(df)

        info = adapter.result_summary(result)
        params = {
            "method": info.get("method", "bounds"),
            "factor": f"{info.get('time_factor', 0):.6g}",
            "count": info.get("n_calibrations", 0),
            "warnings": self._warning_suffix(info.get("warnings")),
        }
        self._set_table_summary("status.cal_done", **params)
        self._show_status("status.cal_done", **params)
        self._update_cli_calibrate()

    def _warning_suffix(self, warnings) -> str:
        if not warnings:
            return ""
        return i18n.t("status.warning_suffix", count=len(warnings))

    # ---- 置信区间 ------------------------------------------------------

    def run_ci(self):
        if self.calibrated_result is None or self._active_workers:
            return

        branch_var = None
        if self.ci_params.branch_var_path:
            try:
                branch_var = adapter.load_branch_variances(
                    self.ci_params.branch_var_path
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    i18n.t("dialog.log_branchvar_failed", error=exc),
                    exc_info=exc,
                )
                QMessageBox.critical(
                    self,
                    i18n.t("dialog.branchvar_failed_title"),
                    f"{type(exc).__name__}: {exc}",
                )
                self._show_status("status.branchvar_failed")
                return

        self._show_status("status.ci_running")

        self._start_worker(
            CIWorker(
                self.calibrated_result,
                level=self.ci_params.level,
                n_sites=self.ci_params.n_sites,
                branch_var=branch_var,
            ),
            self._on_ci_finished,
        )

    def _on_ci_finished(self, result: Optional[CIResult], err: str):
        if err:
            QMessageBox.critical(self, i18n.t("dialog.ci_failed_title"), err)
            self._show_status("status.ci_failed")
            return

        self.ci_result = result

        # 绘制 CI 误差棒图
        self.canvas.plot_ci(result)

        # 更新表格
        self.node_table.fill_from_ci_table(result.table)

        info = adapter.result_summary(result)
        params = {
            "level": info.get("level", 0.95),
            "nodes": info.get("n_nodes", 0),
            "v_s_source": info.get("v_s_source", "unknown"),
        }
        self._set_table_summary("status.ci_done", **params)
        self._show_status("status.ci_done", **params)
        self._update_cli_ci()

    # ---- CorrTest ------------------------------------------------------

    def run_corrtest(self):
        if self.tree is None or self._active_workers:
            return
        self._show_status("status.corrtest_running")

        self._start_worker(
            CorrTestWorker(
                self.tree,
                sister_resample=self.corrtest_params.sister_resample,
                seed=self.corrtest_params.seed,
                anchor_node=self.corrtest_params.anchor_node,
                anchor_time=self.corrtest_params.anchor_time,
            ),
            self._on_corrtest_finished,
        )

    def _on_corrtest_finished(self, result: Optional[CorrTestResult], err: str):
        if err:
            QMessageBox.critical(self, i18n.t("dialog.corrtest_failed_title"), err)
            self._show_status("status.corrtest_failed")
            return

        self.corrtest_result = result
        info = adapter.result_summary(result)
        params = {
            "score": f"{info.get('score', 0):.4g}",
            "p_band": info.get("p_band", "?"),
        }
        self._set_table_summary("status.corrtest_summary", **params)
        self._show_status("status.corrtest_done", **params)
        self._update_cli_corrtest()

        # 弹出结果摘要
        QMessageBox.information(
            self,
            i18n.t("dialog.corrtest_result_title"),
            i18n.t(
                "dialog.corrtest_result_body",
                score=f"{result.score:.5g}",
                p_band=result.p_band,
                rho_s=f"{result.rho_s:.4g}",
                rho_ad=f"{result.rho_ad:.4g}",
                rho_ad_1=f"{result.rho_ad_1_decay:.4g}",
                rho_ad_2=f"{result.rho_ad_2_decay:.4g}",
            ),
        )

    # ---- ddBD ----------------------------------------------------------

    def run_ddbd(self):
        if self.tree is None or self._active_workers:
            return
        self._show_status("status.ddbd_running")

        self._start_worker(
            DDBDWorker(
                self.tree,
                sampling_frac=self.ddbd_params.sampling_frac,
                anchor_node=self.ddbd_params.anchor_node,
                anchor_time=self.ddbd_params.anchor_time,
                measure=self.ddbd_params.measure,
            ),
            self._on_ddbd_finished,
        )

    def _on_ddbd_finished(self, result: Optional[DDBDResult], err: str):
        if err:
            QMessageBox.critical(self, i18n.t("dialog.ddbd_failed_title"), err)
            self._show_status("status.ddbd_failed")
            return

        self.ddbd_result = result

        if self.rrf_result is None:
            # 未跑过 RRF 时树上还没有相对时间：经 Worker 异步补算，避免阻塞界面
            self._show_status("status.ddbd_backfill")
            self._start_worker(
                TimesOnlyWorker(self.tree),
                lambda times, err2, ddbd=result: self._show_ddbd_result(
                    ddbd, times, err2
                ),
            )
        else:
            self._show_ddbd_result(result)

    def _show_ddbd_result(
        self,
        result: DDBDResult,
        times: Optional[TimeResult] = None,
        err: str = "",
    ):
        times = times if times is not None else self.rrf_result
        if err:
            QMessageBox.warning(self, "ddBD", i18n.t("dialog.ddbd_no_times"))
        elif times is not None:
            self.canvas.plot_ddbd(result, times)

        info = adapter.result_summary(result)
        params = {
            "birth": f"{info.get('birth_rate', 0):.4g}",
            "death": f"{info.get('death_rate', 0):.4g}",
            "rho": f"{info.get('sampling_frac', 0):.4g}",
        }
        self._set_table_summary("status.ddbd_summary", **params)
        self._show_status("status.ddbd_done", **params)
        self._update_cli_ddbd()

        QMessageBox.information(
            self,
            i18n.t("dialog.ddbd_result_title"),
            i18n.t(
                "dialog.ddbd_result_body",
                birth=f"{result.birth_rate:.6g}",
                death=f"{result.death_rate:.6g}",
                rho=f"{result.sampling_frac:.6g}",
                scale=f"{result.scale_factor:.6g}",
            ),
        )

    # ---- 画布交互 ------------------------------------------------------

    def _on_node_clicked(self, node_id: int):
        """树画布节点点击：在校正编辑器中设置待编辑节点。"""
        self.analysis_tabs.setCurrentWidget(self._cal_tab)
        self.calibration_editor.set_pending_node(node_id)

    def _on_node_hovered(self, info: str):
        """树画布节点悬停：在状态栏显示信息（计算期间不覆盖进度消息）。"""
        if info and not self._active_workers:
            self.statusBar().showMessage(info)

    def _toggle_rates(self):
        """切换速率着色显示。"""
        if self.calibrated_result is not None:
            self.canvas.plot_timetree(
                self.calibrated_result, use_rates=self.show_rates_act.isChecked()
            )
            self.node_table.fill_from_dataframe(
                adapter.result_to_dataframe(self.calibrated_result, with_rate=True)
            )
        elif self.rrf_result is not None:
            self.canvas.plot_timetree(
                self.rrf_result, use_rates=self.show_rates_act.isChecked()
            )
            self.node_table.fill_from_dataframe(
                adapter.result_to_dataframe(self.rrf_result, with_rate=True)
            )

    # ---- 导出 ----------------------------------------------------------

    def export_results(self):
        """导出当前结果。"""
        result = self._get_current_result()
        if result is None:
            QMessageBox.warning(
                self, i18n.t("dialog.notice_title"), i18n.t("dialog.nothing_to_export")
            )
            return

        last_dir = self.settings.value("last_export_dir", "")
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.ShowDirsOnly, True)
        dlg.setDirectory(last_dir)
        if not dlg.exec():
            return

        out_dir = Path(dlg.selectedFiles()[0])
        self.settings.setValue("last_export_dir", str(out_dir))
        prefix = out_dir / adapter.OUTPUT_PREFIX

        try:
            written = adapter.export_result(result, prefix, nexus=True)
        except Exception as exc:  # noqa: BLE001
            logger.error(i18n.t("dialog.log_export_failed", error=exc), exc_info=exc)
            QMessageBox.critical(
                self,
                i18n.t("dialog.export_failed_title"),
                f"{type(exc).__name__}: {exc}",
            )
            return

        # 导出交互式添加的校正点，保证 run_reltime.sh 里的 -c 可复现。
        # 只要脚本包含 calibrate/ci 步骤就必须有这个文件，与当前导出的
        # 结果类型无关（导 CI 结果时 result 不是 CalibratedResult）
        cals = self.calibration_editor.calibrations
        commands = self._cli_pipeline()
        needs_cal_file = any(
            "openreltime calibrate" in c or "openreltime ci " in c
            for c in commands
        )
        if cals and needs_cal_file:
            cal_path = out_dir / adapter.CALIBRATIONS_FILENAME
            cal_path.write_text(adapter.calibrations_to_tsv(cals))
            written.append(cal_path)

        # 同时导出图像（失败不阻断数据导出，但要给出可见提示）；
        # 文件名跟随画布当前内容，不再恒为 timetree.png
        notes: list[str] = []
        try:
            names = {0: "timetree", 1: "timetree", 2: "ci", 3: "corrtest", 4: "ddbd"}
            img_name = names.get(self.analysis_tabs.currentIndex(), "timetree")
            img_path = out_dir / f"{img_name}.png"
            self.canvas.save_figure(str(img_path))
            written.append(img_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(i18n.t("dialog.log_image_export_failed", error=exc))
            notes.append(i18n.t("export.note_image_failed", error=exc))

        # Write the equivalent CLI script in pipeline order, containing every
        # stage that was actually run: a lone ci command is not replayable,
        # because it consumes the report the calibrate step produces.
        if commands:
            script_path = out_dir / "run_reltime.sh"
            script_path.write_text(adapter.build_cli_script(commands))
            script_path.chmod(0o755)
            written.append(script_path)
        else:
            notes.append(i18n.t("export.note_no_cli"))
        if cals and not needs_cal_file:
            notes.append(
                i18n.t("export.note_cals_ui_only", file=adapter.CALIBRATIONS_FILENAME)
            )

        QMessageBox.information(
            self,
            i18n.t("dialog.export_done_title"),
            i18n.t(
                "dialog.export_done_body",
                files="\n".join(str(p) for p in written),
                notes=i18n.t("dialog.export_notes", notes="\n".join(notes))
                if notes
                else "",
            ),
        )
        self._show_status("status.exported", timeout=4000, directory=out_dir)

    def _get_current_result(self):
        """获取当前标签页对应的结果对象。"""
        idx = self.analysis_tabs.currentIndex()
        if idx == 0 and self.rrf_result is not None:
            return self.rrf_result
        if idx == 1 and self.calibrated_result is not None:
            return self.calibrated_result
        if idx == 2 and self.ci_result is not None:
            return self.ci_result
        if idx == 3 and self.corrtest_result is not None:
            return self.corrtest_result
        if idx == 4 and self.ddbd_result is not None:
            return self.ddbd_result
        # fallback: 任意非空结果
        for r in [self.rrf_result, self.calibrated_result, self.ci_result,
                  self.corrtest_result, self.ddbd_result]:
            if r is not None:
                return r
        return None

    # ---- 等效 CLI ──────────────────────────────────────────────────────

    def _tree_path_for_cli(self) -> str:
        """脚本里的 ``-i``：始终写绝对路径，换目录重放也能找到树。"""
        if not self.tree_path:
            return "tree.nwk"
        return str(Path(self.tree_path).resolve())

    def _record_cli(self, stage: str, command: str) -> None:
        """登记某阶段的等效命令并刷新面板显示。"""
        self._cli_commands[stage] = command
        self._render_cli()

    def _cli_pipeline(self) -> list[str]:
        """按流水线顺序返回已运行阶段的命令。"""
        return adapter.cli_pipeline(self._cli_commands)

    def _render_cli(self) -> None:
        commands = self._cli_pipeline()
        self.cli_text.setPlainText(
            "\n".join(commands) if commands else i18n.t("panel.cli_placeholder")
        )

    def _input_flags(self) -> dict:
        """Tree-reading settings, which every equivalent CLI command must carry."""
        return {
            "input_fmt": self.input_fmt,
            "resolve_polytomy": self.resolve_polytomy,
            "outgroup_check": self.outgroup_check,
        }

    def _update_cli_rrf(self):
        og = self.og_edit.text().strip()
        # 重跑 RRF 会让下游结果全部失效，等效脚本也必须从头重建
        self._cli_commands.clear()
        self._record_cli(
            "rates-times",
            adapter.build_cli_rates_times(
                self._tree_path_for_cli(),
                og or None,
                self.rrf_params.mean,
                self.rrf_params.normalize,
                adapter.OUTPUT_PREFIX,
                **self._input_flags(),
            ),
        )

    def _update_cli_calibrate(self):
        og = self.og_edit.text().strip()
        # calibrate 重跑会让既有 CI 结果及其命令过期
        self._cli_commands.pop("ci", None)
        self._record_cli(
            "calibrate",
            adapter.build_cli_calibrate(
                self._tree_path_for_cli(),
                adapter.CALIBRATIONS_FILENAME,
                og or None,
                self.calibrate_params.method,
                self.calibrate_params.n_effective,
                self.calibrate_params.seed,
                adapter.OUTPUT_PREFIX,
                **self._input_flags(),
            ),
        )

    def _update_cli_ci(self):
        branch_var = self.ci_params.branch_var_path or None
        self._record_cli(
            "ci",
            adapter.build_cli_ci(
                adapter.OUTPUT_PREFIX,
                self.ci_params.level,
                self.ci_params.n_sites,
                adapter.OUTPUT_PREFIX,
                branch_var=branch_var,
            ),
        )

    def _update_cli_corrtest(self):
        og = self.og_edit.text().strip()
        self._record_cli(
            "corrtest",
            adapter.build_cli_corrtest(
                self._tree_path_for_cli(),
                og or None,
                self.corrtest_params.sister_resample,
                self.corrtest_params.seed,
                self.corrtest_params.anchor_node,
                self.corrtest_params.anchor_time,
                adapter.OUTPUT_PREFIX,
                **self._input_flags(),
            ),
        )

    def _update_cli_ddbd(self):
        og = self.og_edit.text().strip()
        self._record_cli(
            "ddbd",
            adapter.build_cli_ddbd(
                self._tree_path_for_cli(),
                og or None,
                self.ddbd_params.anchor_node,
                self.ddbd_params.anchor_time,
                self.ddbd_params.measure,
                adapter.OUTPUT_PREFIX,
                sampling_frac=self.ddbd_params.sampling_frac,
                **self._input_flags(),
            ),
        )

    def copy_cli(self):
        text = self.cli_text.toPlainText()
        if text and not text.startswith("#"):
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self._show_status("status.cli_copied", timeout=3000)

    # ---- 其他 ----------------------------------------------------------

    def show_about(self):
        import openreltime

        from openreltime_studio import __version__ as studio_version

        QMessageBox.about(
            self,
            i18n.t("about.title"),
            i18n.t(
                "about.body",
                version=studio_version,
                engine=openreltime.__version__,
            ),
        )

    def _restore_state(self):
        """恢复上次窗口状态。"""
        geom = self.settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = self.settings.value("window_state")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        """保存窗口状态；后台计算未结束时先确认，避免线程被强杀。"""
        if self._active_workers:
            ret = QMessageBox.question(
                self,
                i18n.t("dialog.quit_busy_title"),
                i18n.t("dialog.quit_busy_body"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        # 等待仍在运行的线程收尾，避免退出时销毁活动线程导致崩溃；
        # 超时后 terminate 是最后手段（Worker 内为阻塞科学计算，无法响应
        # requestInterruption/quit，只能由用户确认后强杀）
        for worker in list(self._active_workers):
            worker.wait(5000)
        for worker in list(self._active_workers):
            if worker.isRunning():
                worker.terminate()
                worker.wait(1000)
        super().closeEvent(event)
