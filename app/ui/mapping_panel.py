"""映射列表 + 计量结果 + 操作按钮"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
                               QTableWidgetItem, QHeaderView, QPushButton,
                               QAbstractItemView, QGroupBox)

MODE_LABELS = {"entity": "点选", "layer": "图层", "block": "块"}


class MappingPanel(QWidget):
    deleteMappingRequested = Signal(int)
    recalcRequested = Signal()
    exportRequested = Signal()
    recolorRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mappings = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        self.current_label = QLabel("当前条目：未选择")
        self.current_label.setStyleSheet("font-weight:500;")
        root.addWidget(self.current_label)

        map_box = QGroupBox("映射列表")
        v = QVBoxLayout(map_box)
        self.map_table = QTableWidget()
        self.map_table.setColumnCount(4)
        self.map_table.setHorizontalHeaderLabels(["方式", "目标", "实体数", "时间"])
        self.map_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.map_table.verticalHeader().setVisible(False)
        self.map_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        v.addWidget(self.map_table)

        btn_row = QHBoxLayout()
        self.btn_delete = QPushButton("删除选中映射")
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_recalc = QPushButton("重算全部")
        self.btn_recalc.clicked.connect(self.recalcRequested.emit)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_recalc)
        v.addLayout(btn_row)
        root.addWidget(map_box, stretch=3)

        res_box = QGroupBox("计量结果")
        v2 = QVBoxLayout(res_box)
        self.result_label = QLabel("尚未计量")
        self.result_label.setWordWrap(True)
        v2.addWidget(self.result_label)
        self.btn_export = QPushButton("导出算量清单 (Excel)")
        self.btn_export.clicked.connect(self.exportRequested.emit)
        v2.addWidget(self.btn_export)
        root.addWidget(res_box, stretch=2)

    def refresh_enabled(self, has_project: bool):
        """P1-12：按钮与上下文对齐 — 无项目/无映射时禁用操作按钮。"""
        self.btn_delete.setEnabled(has_project and bool(self._mappings))
        self.btn_recalc.setEnabled(has_project)
        self.btn_export.setEnabled(has_project)

    def set_current(self, item_desc: str):
        self.current_label.setText(f"当前条目：{item_desc}")

    def load_mappings(self, mappings: list, entity_counts: dict):
        self._mappings = mappings
        self.map_table.blockSignals(True)
        self.map_table.setRowCount(0)
        for m in mappings:
            row = self.map_table.rowCount()
            self.map_table.insertRow(row)
            target = (m.layer_name or m.block_name or
                      (f"实体#{m.entity_id}" if m.entity_id else ""))
            self.map_table.setItem(row, 0, QTableWidgetItem(MODE_LABELS.get(m.mode, m.mode)))
            self.map_table.setItem(row, 1, QTableWidgetItem(target))
            self.map_table.setItem(row, 2, QTableWidgetItem(str(entity_counts.get(m.id, ""))))
            self.map_table.setItem(row, 3, QTableWidgetItem(m.created_at))
        self.map_table.blockSignals(False)

    def set_result(self, qty, count, detail_lines, factor):
        text = (f"计量数量：{qty:g}\n映射实体：{count} 个\n换算因子：{factor:g}\n"
                + "\n".join(detail_lines[:20]))
        if len(detail_lines) > 20:
            text += f"\n…共 {len(detail_lines)} 条明细"
        self.result_label.setText(text)

    def _on_delete(self):
        row = self.map_table.currentRow()
        if row >= 0 and row < len(self._mappings):
            self.deleteMappingRequested.emit(self._mappings[row].id)
