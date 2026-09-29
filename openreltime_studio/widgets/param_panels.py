"""参数面板部件 — 收集分析参数的表单控件。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from openreltime_studio import i18n


class RRFParamsWidget(QGroupBox):
    """RRF 分析参数面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        i18n.bind(self, "setTitle", "params.rrf_title")
        form = QFormLayout(self)

        self.mean_combo = QComboBox()
        self.mean_combo.addItems(["geometric", "arithmetic"])
        mean_label = QLabel()
        i18n.bind_text(mean_label, "params.rrf_mean_label")
        form.addRow(mean_label, self.mean_combo)

        self.norm_check = QCheckBox()
        i18n.bind_text(self.norm_check, "params.rrf_normalize_check")
        form.addRow(self.norm_check)

        self.no_guard_check = QCheckBox()
        i18n.bind_text(self.no_guard_check, "params.rrf_no_guard_check")
        i18n.bind_tooltip(self.no_guard_check, "params.rrf_no_guard_tip")
        form.addRow(self.no_guard_check)

    @property
    def mean(self) -> str:
        return self.mean_combo.currentText()

    @property
    def normalize(self) -> bool:
        return self.norm_check.isChecked()

    @property
    def rate_ratio_threshold(self) -> Optional[float]:
        """None 表示关闭守卫；否则为 R3F 默认阈值 20。"""
        return None if self.no_guard_check.isChecked() else 20.0


class CalibrateParamsWidget(QGroupBox):
    """校正参数面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        i18n.bind(self, "setTitle", "params.calibrate_title")
        form = QFormLayout(self)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["bounds", "effective"])
        self.method_combo.currentTextChanged.connect(self._on_method_change)
        method_label = QLabel()
        i18n.bind_text(method_label, "params.calibrate_method_label")
        form.addRow(method_label, self.method_combo)

        self.n_effective_spin = QSpinBox()
        self.n_effective_spin.setRange(2, 100000)
        self.n_effective_spin.setValue(10000)
        n_effective_label = QLabel()
        i18n.bind_text(n_effective_label, "params.calibrate_n_effective_label")
        form.addRow(n_effective_label, self.n_effective_spin)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(42)
        self.seed_check = QCheckBox()
        i18n.bind_text(self.seed_check, "params.seed_fixed_check")
        self.seed_check.toggled.connect(self.seed_spin.setEnabled)
        self.seed_spin.setEnabled(False)

        seed_row = QHBoxLayout()
        seed_row.addWidget(self.seed_check)
        seed_row.addWidget(self.seed_spin)
        seed_label = QLabel()
        i18n.bind_text(seed_label, "params.seed_label")
        form.addRow(seed_label, seed_row)

        self._on_method_change("bounds")

    def _on_method_change(self, method: str):
        self.n_effective_spin.setEnabled(method == "effective")
        self.seed_spin.setEnabled(method == "effective" and self.seed_check.isChecked())
        self.seed_check.setEnabled(method == "effective")

    @property
    def method(self) -> str:
        return self.method_combo.currentText()

    @property
    def n_effective(self) -> int:
        return self.n_effective_spin.value()

    @property
    def seed(self) -> Optional[int]:
        if self.method == "effective" and self.seed_check.isChecked():
            return self.seed_spin.value()
        return None


class CIParamsWidget(QGroupBox):
    """置信区间参数面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        i18n.bind(self, "setTitle", "params.ci_title")
        form = QFormLayout(self)

        self.level_combo = QComboBox()
        self.level_combo.addItems(["0.95", "0.90", "0.99"])
        level_label = QLabel()
        i18n.bind_text(level_label, "params.ci_level_label")
        form.addRow(level_label, self.level_combo)

        self.n_sites_spin = QSpinBox()
        # Lower limit of 1: once the box is ticked, 0 is not an option.  0 sites
        # would silently drop the run back to the rate-heterogeneity-only
        # variance while looking like a real site count.
        self.n_sites_spin.setRange(1, 10**9)
        self.n_sites_spin.setValue(1000)
        self.n_sites_check = QCheckBox()
        i18n.bind_text(self.n_sites_check, "params.ci_n_sites_check")
        self.n_sites_check.toggled.connect(self._on_nsites_toggle)
        form.addRow(self.n_sites_check)
        n_sites_label = QLabel()
        i18n.bind_text(n_sites_label, "params.ci_n_sites_value_label")
        form.addRow(n_sites_label, self.n_sites_spin)
        self.n_sites_spin.setEnabled(False)

        # 未指定位点数时 vS(b)=0，区间只剩速率异质性分量：必须说出来
        self.fallback_note = QLabel()
        i18n.bind_text(self.fallback_note, "params.ci_fallback_note")
        self.fallback_note.setWordWrap(True)
        self.fallback_note.setObjectName("hintLabel")
        self.fallback_note.setVisible(False)
        form.addRow(self.fallback_note)

        self.branch_var_edit = QLineEdit()
        i18n.bind_placeholder(self.branch_var_edit, "params.ci_branch_var_placeholder")
        self.btn_branch_var = QPushButton()
        i18n.bind_text(self.btn_branch_var, "params.browse_button")
        self.btn_branch_var.clicked.connect(self._choose_branch_var)
        bvar_row = QHBoxLayout()
        bvar_row.addWidget(self.branch_var_edit, 1)
        bvar_row.addWidget(self.btn_branch_var)
        branch_var_label = QLabel()
        i18n.bind_text(branch_var_label, "params.ci_branch_var_label")
        form.addRow(branch_var_label, bvar_row)

        self._on_nsites_toggle(False)

    def _on_nsites_toggle(self, checked: bool):
        self.n_sites_spin.setEnabled(checked)
        self.fallback_note.setVisible(not checked)

    def _choose_branch_var(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            i18n.t("params.ci_branch_var_dialog_title"),
            "",
            i18n.t("params.tsv_filter"),
        )
        if path:
            self.branch_var_edit.setText(str(Path(path).resolve()))

    @property
    def level(self) -> float:
        return float(self.level_combo.currentText())

    @property
    def n_sites(self) -> Optional[int]:
        """位点数（Poisson 近似 vS(b)=b/L 里的 L）；未勾选时为 None。

        取值必为正（spin 下界 1），因此 None 只可能是“用户没有勾选”，
        面板同时用 ``fallback_note`` 明示这一选择的后果。
        """
        if self.n_sites_check.isChecked():
            return self.n_sites_spin.value()
        return None

    @property
    def branch_var_path(self) -> Optional[str]:
        text = self.branch_var_edit.text().strip()
        return text or None


class CorrTestParamsWidget(QGroupBox):
    """CorrTest 参数面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        i18n.bind(self, "setTitle", "params.corrtest_title")
        form = QFormLayout(self)

        self.sister_resample_spin = QSpinBox()
        self.sister_resample_spin.setRange(0, 10000)
        self.sister_resample_spin.setValue(0)
        sister_label = QLabel()
        i18n.bind_text(sister_label, "params.corrtest_sister_resample_label")
        form.addRow(sister_label, self.sister_resample_spin)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(42)
        self.seed_check = QCheckBox()
        i18n.bind_text(self.seed_check, "params.seed_fixed_check")
        self.seed_check.toggled.connect(self.seed_spin.setEnabled)
        self.seed_spin.setEnabled(False)

        seed_row = QHBoxLayout()
        seed_row.addWidget(self.seed_check)
        seed_row.addWidget(self.seed_spin)
        seed_label = QLabel()
        i18n.bind_text(seed_label, "params.seed_label")
        form.addRow(seed_label, seed_row)

        self.anchor_check = QCheckBox()
        i18n.bind_text(self.anchor_check, "params.anchor_check")
        form.addRow(self.anchor_check)

        self.anchor_node_spin = QSpinBox()
        self.anchor_node_spin.setRange(1, 10**6)
        self.anchor_node_spin.setValue(1)
        self.anchor_node_spin.setEnabled(False)
        self.anchor_check.toggled.connect(self.anchor_node_spin.setEnabled)
        anchor_node_label = QLabel()
        i18n.bind_text(anchor_node_label, "params.anchor_node_label")
        form.addRow(anchor_node_label, self.anchor_node_spin)

        self.anchor_time_spin = QDoubleSpinBox()
        self.anchor_time_spin.setRange(0.0, 1e6)
        self.anchor_time_spin.setDecimals(6)
        self.anchor_time_spin.setValue(1.0)
        self.anchor_time_spin.setEnabled(False)
        self.anchor_check.toggled.connect(self.anchor_time_spin.setEnabled)
        anchor_time_label = QLabel()
        i18n.bind_text(anchor_time_label, "params.anchor_time_label")
        form.addRow(anchor_time_label, self.anchor_time_spin)

    @property
    def sister_resample(self) -> int:
        return self.sister_resample_spin.value()

    @property
    def seed(self) -> Optional[int]:
        if self.seed_check.isChecked():
            return self.seed_spin.value()
        return None

    @property
    def anchor_node(self) -> Optional[int]:
        if self.anchor_check.isChecked():
            return self.anchor_node_spin.value()
        return None

    @property
    def anchor_time(self) -> float:
        return self.anchor_time_spin.value()


class DDBDParamsWidget(QGroupBox):
    """ddBD 参数面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        i18n.bind(self, "setTitle", "params.ddbd_title")
        form = QFormLayout(self)

        self.measure_combo = QComboBox()
        self.measure_combo.addItems(["SSE", "KL"])
        measure_label = QLabel()
        i18n.bind_text(measure_label, "params.ddbd_measure_label")
        form.addRow(measure_label, self.measure_combo)

        self.anchor_check = QCheckBox()
        i18n.bind_text(self.anchor_check, "params.anchor_check")
        form.addRow(self.anchor_check)

        self.anchor_node_spin = QSpinBox()
        self.anchor_node_spin.setRange(1, 10**6)
        self.anchor_node_spin.setValue(1)
        self.anchor_node_spin.setEnabled(False)
        self.anchor_check.toggled.connect(self.anchor_node_spin.setEnabled)
        anchor_node_label = QLabel()
        i18n.bind_text(anchor_node_label, "params.anchor_node_label")
        form.addRow(anchor_node_label, self.anchor_node_spin)

        self.anchor_time_spin = QDoubleSpinBox()
        self.anchor_time_spin.setRange(0.0, 1e6)
        self.anchor_time_spin.setDecimals(6)
        self.anchor_time_spin.setValue(1.0)
        self.anchor_time_spin.setEnabled(False)
        self.anchor_check.toggled.connect(self.anchor_time_spin.setEnabled)
        anchor_time_label = QLabel()
        i18n.bind_text(anchor_time_label, "params.anchor_time_label")
        form.addRow(anchor_time_label, self.anchor_time_spin)

        self.sampling_check = QCheckBox()
        i18n.bind_text(self.sampling_check, "params.ddbd_sampling_check")
        form.addRow(self.sampling_check)

        self.sampling_spin = QDoubleSpinBox()
        self.sampling_spin.setRange(0.0, 1.0)
        self.sampling_spin.setDecimals(6)
        self.sampling_spin.setValue(0.5)
        self.sampling_spin.setEnabled(False)
        self.sampling_check.toggled.connect(self.sampling_spin.setEnabled)
        sampling_label = QLabel()
        i18n.bind_text(sampling_label, "params.ddbd_sampling_frac_label")
        form.addRow(sampling_label, self.sampling_spin)

    @property
    def measure(self) -> str:
        return self.measure_combo.currentText()

    @property
    def anchor_node(self) -> Optional[int]:
        if self.anchor_check.isChecked():
            return self.anchor_node_spin.value()
        return None

    @property
    def anchor_time(self) -> float:
        return self.anchor_time_spin.value()

    @property
    def sampling_frac(self) -> Optional[float]:
        if self.sampling_check.isChecked():
            return self.sampling_spin.value()
        return None
