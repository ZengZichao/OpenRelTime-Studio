"""节点表部件 — 用 QTableWidget 显示 Result 的 DataFrame。"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from openreltime_studio import i18n


def _is_numeric(text: str) -> bool:
    """判断文本是否为数值（数值列右对齐，标签列左对齐）。"""
    try:
        float(text)
        return True
    except ValueError:
        return False


def _translated_columns() -> dict[str, str]:
    """引擎列名 → 当前语言的表头文案。

    未收录的列名（例如引擎新增的列）原样显示，单元格数据一律不翻译。
    """
    return {
        "NodeLabel": i18n.t("nodetable.col_node_label"),
        "NodeId": i18n.t("nodetable.col_node_id"),
        "Des1": i18n.t("nodetable.col_des1"),
        "Des2": i18n.t("nodetable.col_des2"),
        "Time": i18n.t("nodetable.col_time"),
        "Rate": i18n.t("nodetable.col_rate"),
        "RRFRate": i18n.t("nodetable.col_rrf_rate"),
        "ImpliedRate": i18n.t("nodetable.col_implied_rate"),
        "node_id": i18n.t("nodetable.col_ci_node_id"),
        "label": i18n.t("nodetable.col_ci_label"),
        "time": i18n.t("nodetable.col_ci_time"),
        "se": i18n.t("nodetable.col_ci_se"),
        "lower": i18n.t("nodetable.col_ci_lower"),
        "upper": i18n.t("nodetable.col_ci_upper"),
        "width": i18n.t("nodetable.col_ci_width"),
        "se_reliable": i18n.t("nodetable.col_ci_se_reliable"),
        "notes": i18n.t("nodetable.col_ci_notes"),
    }


class NodeTable(QTableWidget):
    """显示 Result.to_pandas() 结果的表格部件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns: list[str] = []
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSortingEnabled(False)  # 填充期间禁止排序，避免行序错乱
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._language_hook = i18n.on_language_change(self._retranslate)

    def _header_labels(self, columns: list[str]) -> list[str]:
        """列名按当前语言取表头；未知列名保持原样。"""
        labels = _translated_columns()
        return [labels.get(c, c) for c in columns]

    def _retranslate(self, _lang: str = ""):
        """语言切换后重放表头（列数不符说明表已清空或被重建，不重画）。"""
        if self._columns and self.columnCount() == len(self._columns):
            self.setHorizontalHeaderLabels(self._header_labels(self._columns))

    def fill_from_dataframe(self, df: Any):
        """从 pandas DataFrame 填充表格。"""
        self.setUpdatesEnabled(False)
        try:
            self.clear()
            self.setRowCount(df.shape[0])
            self.setColumnCount(df.shape[1])
            self._columns = [str(c) for c in df.columns]
            self.setHorizontalHeaderLabels(self._header_labels(self._columns))
            for i, (_, row) in enumerate(df.iterrows()):
                for j, val in enumerate(row):
                    if val is None or (isinstance(val, float) and np.isnan(val)):
                        text = ""
                    elif isinstance(val, float):
                        text = f"{val:.6g}"
                    else:
                        text = str(val)
                    item = QTableWidgetItem(text)
                    if text and _is_numeric(text):
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.setItem(i, j, item)
            self.resizeColumnsToContents()
        finally:
            self.setUpdatesEnabled(True)

    def fill_from_ci_table(self, table: Any):
        """从 CIResult.table（DataFrame）填充表格。"""
        self.fill_from_dataframe(table)

    def clear_table(self):
        """清空表格。"""
        self.clear()
        self.setRowCount(0)
        self.setColumnCount(0)
        self._columns = []
