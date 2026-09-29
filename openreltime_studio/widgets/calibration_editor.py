"""校正点编辑器 — 在树上点选节点后设置 min/max/密度。

交互流程：
1. 用户在树画布上点击内部节点 → 触发 node_clicked 信号；
2. 本部件填入待编辑节点，用户填写 min/max 与密度类型；
3. 确认后构造 Calibration 对象并通知主窗口。
"""

from __future__ import annotations

from typing import ClassVar, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from openreltime_studio import i18n
from openreltime_studio.adapters import openreltime_adapter as adapter

#: Smallest bound a spin box may hold (Mya).  It must stay strictly positive:
#: a ticked "max" that the user never edits would otherwise hand 0.0 to the
#: solver as an upper bound and scale the entire tree to zero.  A lower bound
#: of 0 carries no constraint, so "no lower bound" is expressed by leaving the
#: checkbox off rather than by a value the spin box can reach.
_MIN_BOUND = 1e-6

#: 提示标签的状态：空闲 / 已选中目标节点 / 刚添加 / 刚替换
_HINT_IDLE = "idle"
_HINT_SELECTED = "selected"
_HINT_ADDED = "added"
_HINT_REPLACED = "replaced"


class CalibrationEditor(QGroupBox):
    """校正点编辑器：添加、编辑、删除校正点。

    信号：
        calibrations_changed(list) — 校正点列表变动时发出（list[Calibration]）。
    """

    calibrations_changed = Signal(list)

    DENSITY_TYPES: ClassVar[list[str]] = [
        "(none)", "uniform", "exponential", "normal", "lognormal",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._calibrations: list = []
        self._pending_node_id: Optional[int] = None
        self._row_buttons: list[QPushButton] = []  # 每行复用的删除按钮
        self._hint_state: tuple[str, Optional[int]] = (_HINT_IDLE, None)
        self._build_ui()
        # QGroupBox 没有 setText，标题要走 setTitle 绑定
        i18n.bind(self, "setTitle", "calibration.title")
        self._language_hook = i18n.on_language_change(self._retranslate)
        self._retranslate()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 状态提示（文本随交互变化，由 _apply_hint 计算）
        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setObjectName("hintLabel")
        layout.addWidget(self.hint_label)

        # 校正点表格
        self.table = QTableWidget(0, 5)
        self._apply_header_labels()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        # 「操作」列只放按钮：cell widget 不参与 ResizeToContents 计算，需定宽
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 68)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMinimumHeight(96)
        layout.addWidget(self.table)

        # 添加校正点的内联编辑区
        edit_group = QGroupBox()
        i18n.bind(edit_group, "setTitle", "calibration.edit_group")
        edit_layout = QFormLayout(edit_group)

        self.node_id_label = QLabel()
        target_caption = QLabel()
        i18n.bind_text(target_caption, "calibration.target_node")
        edit_layout.addRow(target_caption, self.node_id_label)

        # "No bound" is expressed by the checkbox, never by the number in the
        # spin box: a 0 lower bound would carry no constraint anyway, so an
        # unchecked box means "unset".  Keeping the spin range strictly positive
        # then prevents a ticked box from passing 0.0 straight to the solver,
        # which as an upper bound would scale every age in the tree to zero.
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(_MIN_BOUND, 1e9)
        self.min_spin.setDecimals(6)
        self.min_spin.setValue(_MIN_BOUND)
        self.min_spin.setEnabled(False)
        i18n.bind_tooltip(self.min_spin, "calibration.min_bound_tooltip")
        self.min_check = QCheckBox()
        i18n.bind_text(self.min_check, "calibration.set_min_bound")
        self.min_check.toggled.connect(self.min_spin.setEnabled)
        edit_layout.addRow(self.min_check, self.min_spin)

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(_MIN_BOUND, 1e9)
        self.max_spin.setDecimals(6)
        self.max_spin.setValue(_MIN_BOUND)
        self.max_spin.setEnabled(False)
        i18n.bind_tooltip(self.max_spin, "calibration.max_bound_tooltip")
        self.max_check = QCheckBox()
        i18n.bind_text(self.max_check, "calibration.set_max_bound")
        self.max_check.toggled.connect(self.max_spin.setEnabled)
        edit_layout.addRow(self.max_check, self.max_spin)

        self.density_combo = QComboBox()
        self.density_combo.addItems(self.DENSITY_TYPES)
        density_caption = QLabel()
        i18n.bind_text(density_caption, "calibration.density_type")
        edit_layout.addRow(density_caption, self.density_combo)

        # 密度参数输入：与 CLI 相同的 key=value;... 语法，留空用引擎默认
        self.density_params_edit = QLineEdit()
        i18n.bind_placeholder(
            self.density_params_edit, "calibration.density_params_placeholder"
        )
        i18n.bind_tooltip(
            self.density_params_edit, "calibration.density_params_tooltip"
        )
        params_caption = QLabel()
        i18n.bind_text(params_caption, "calibration.density_params")
        edit_layout.addRow(params_caption, self.density_params_edit)

        # 添加按钮
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton()
        i18n.bind_text(self.btn_add, "calibration.btn_add")
        self.btn_add.clicked.connect(self._on_add_calibration)
        self.btn_add.setEnabled(False)
        self.btn_add.setDefault(True)
        self.btn_clear = QPushButton()
        i18n.bind_text(self.btn_clear, "calibration.btn_clear")
        self.btn_clear.clicked.connect(self._on_clear_all)
        btn_row.addWidget(self.btn_add, 1)
        btn_row.addWidget(self.btn_clear)
        edit_layout.addRow(btn_row)

        layout.addWidget(edit_group)

    def _retranslate(self, _lang: str = ""):
        """语言切换时重算全部动态文本（表头、提示、目标节点与单元格）。"""
        self._apply_header_labels()
        self._apply_pending_node()
        self._apply_hint()
        self._refresh_table()

    def _apply_header_labels(self):
        """表头文案（列宽与缩放模式不随语言变化）。"""
        self.table.setHorizontalHeaderLabels(
            [
                i18n.t("calibration.col_node_id"),
                i18n.t("calibration.col_min"),
                i18n.t("calibration.col_max"),
                i18n.t("calibration.col_density"),
                i18n.t("calibration.col_action"),
            ]
        )

    def _apply_pending_node(self):
        """目标节点标签：未选中时给占位提示，选中后显示 node_id。"""
        if self._pending_node_id is None:
            self.node_id_label.setText(i18n.t("calibration.no_target_node"))
        else:
            self.node_id_label.setText(
                i18n.t("calibration.node_label", node_id=self._pending_node_id)
            )

    def _set_hint(self, state: str, node_id: Optional[int] = None):
        self._hint_state = (state, node_id)
        self._apply_hint()

    def _apply_hint(self):
        """按当前提示状态取当前语言的文案。"""
        state, node_id = self._hint_state
        if state == _HINT_SELECTED:
            self.hint_label.setText(
                i18n.t("calibration.hint_selected", node_id=node_id)
            )
        elif state == _HINT_ADDED:
            self.hint_label.setText(
                i18n.t("calibration.hint_added", node_id=node_id)
            )
        elif state == _HINT_REPLACED:
            self.hint_label.setText(
                i18n.t("calibration.hint_replaced", node_id=node_id)
            )
        else:
            self.hint_label.setText(i18n.t("calibration.hint_pick_node"))

    def set_pending_node(self, node_id: int):
        """设置当前选中的节点（由树画布点击触发）。"""
        self._pending_node_id = node_id
        self._apply_pending_node()
        self.btn_add.setEnabled(True)
        self._set_hint(_HINT_SELECTED, node_id)

    def _on_add_calibration(self):
        """添加一个校正点（同一节点重复添加时替换旧校正点）。"""
        if self._pending_node_id is None:
            return

        min_val = self.min_spin.value() if self.min_check.isChecked() else None
        max_val = self.max_spin.value() if self.max_check.isChecked() else None
        density = self.density_combo.currentText()
        density = None if density == "(none)" else density

        problem = adapter.bound_error(min_val, max_val, density)
        if problem is not None:
            QMessageBox.warning(
                self,
                i18n.t("calibration.invalid_title"),
                i18n.t("calibration.invalid_body", problem=problem),
            )
            return

        # 密度参数：与 CLI 相同的 key=value;... 语法；留空时交给引擎默认值
        density_params: dict[str, float] = {}
        raw_params = self.density_params_edit.text().strip()
        if density is not None and raw_params:
            try:
                for chunk in raw_params.split(";"):
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    if "=" not in chunk:
                        raise ValueError(
                            i18n.t("calibration.missing_equals", chunk=repr(chunk))
                        )
                    key, _, value = chunk.partition("=")
                    density_params[key.strip()] = float(value.strip())
            except ValueError as exc:
                QMessageBox.warning(
                    self,
                    i18n.t("calibration.bad_params_title"),
                    i18n.t("calibration.bad_params_body", error=exc),
                )
                return

        replaced = any(
            c.node_id == self._pending_node_id for c in self._calibrations
        )
        cal = adapter.make_calibration(
            node_id=self._pending_node_id,
            min_bound=min_val,
            max_bound=max_val,
            density=density,
            density_params=density_params or None,
        )
        # 同一节点只保留一条校正，避免重复条目导致校正歧义
        self._calibrations = [
            c for c in self._calibrations
            if c.node_id != self._pending_node_id
        ]
        self._calibrations.append(cal)
        self._refresh_table()
        self.calibrations_changed.emit(list(self._calibrations))

        added_node_id = self._pending_node_id
        self._set_hint(
            _HINT_REPLACED if replaced else _HINT_ADDED, added_node_id
        )

        # 重置编辑区
        self.min_check.setChecked(False)
        self.max_check.setChecked(False)
        self.min_spin.setValue(_MIN_BOUND)
        self.max_spin.setValue(_MIN_BOUND)
        self.density_params_edit.clear()
        self.density_combo.setCurrentIndex(0)
        self._pending_node_id = None
        self._apply_pending_node()
        self.btn_add.setEnabled(False)

    def _on_clear_all(self):
        """清空所有校正点（需确认）。"""
        if not self._calibrations:
            return
        ret = QMessageBox.question(
            self,
            i18n.t("calibration.clear_title"),
            i18n.t("calibration.clear_confirm", count=len(self._calibrations)),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        self.clear()

    def remove_calibration(self, index: int):
        """删除指定索引的校正点。"""
        if 0 <= index < len(self._calibrations):
            del self._calibrations[index]
            self._refresh_table()
            self.calibrations_changed.emit(list(self._calibrations))

    def _refresh_table(self):
        """刷新校正点表格。

        删除按钮由 ``_row_buttons`` 独立管理并按行复用（只重绑回调、
        不重建控件）：重建控件会经 ``deleteLater`` 延迟销毁，下一轮
        事件循环前会出现位置错误的孤儿按钮。
        """
        n = len(self._calibrations)
        self.table.setRowCount(n)
        # 行收缩：释放多余按钮（对应行已被表格移除）
        while len(self._row_buttons) > n:
            btn = self._row_buttons.pop()
            btn.hide()
            btn.deleteLater()
        for i, cal in enumerate(self._calibrations):
            target_item = QTableWidgetItem(
                str(cal.node_id)
                if cal.node_id is not None
                else "|".join(sorted(cal.taxon_set or ()))
            )
            if cal.node_id is None:
                target_item.setToolTip(
                    i18n.t("calibration.taxon_target_tooltip")
                )
            self.table.setItem(i, 0, target_item)
            self.table.setItem(
                i, 1, QTableWidgetItem(adapter.format_bound(cal.min_bound))
            )
            self.table.setItem(
                i, 2, QTableWidgetItem(adapter.format_bound(cal.max_bound))
            )
            self.table.setItem(
                i, 3,
                QTableWidgetItem(cal.density or "-"),
            )
            if i >= len(self._row_buttons):
                btn = QPushButton()
                i18n.bind_text(btn, "calibration.delete")
                btn.clicked.connect(self._on_delete_clicked)
                self._row_buttons.append(btn)
                self.table.setCellWidget(i, 4, btn)
            else:
                btn = self._row_buttons[i]
            btn.setProperty("row", i)
            btn.setToolTip(
                i18n.t("calibration.delete_tooltip", target=target_item.text())
            )

    def _on_delete_clicked(self):
        """删除按钮回调：行号存于按钮的 row 属性，每次刷新时更新。"""
        btn = self.sender()
        if btn is None:
            return
        idx = btn.property("row")
        if idx is not None:
            self.remove_calibration(int(idx))

    @property
    def calibrations(self) -> list:
        """返回当前校正点列表的副本。"""
        return list(self._calibrations)

    def load_from_file(self, path: str) -> int:
        """从 TSV 文件加载校正点；解析失败时抛出异常。返回加载条数。"""
        calibrations = adapter.load_calibrations(path)
        self.replace_calibrations(calibrations)
        return len(self._calibrations)

    def replace_calibrations(self, calibrations: list) -> None:
        """整体替换校正点列表（供主窗口做树内校验后回写）。"""
        self._calibrations = list(calibrations)
        self._refresh_table()
        self.calibrations_changed.emit(list(self._calibrations))

    def clear(self):
        """清空校正点（无确认弹窗）。"""
        self._calibrations.clear()
        self._refresh_table()
        self.calibrations_changed.emit([])
