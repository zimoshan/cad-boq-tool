"""BOQ 条目表格"""
from __future__ import annotations

import logging
import time
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

from . import theme as T

logger = logging.getLogger(__name__)

RULE_LABELS = {"length": "长度", "area": "面积", "count": "数量"}
RULE_VALUES = {v: k for k, v in RULE_LABELS.items()}

COLS = ["编号", "描述", "单位", "原数量", "计量规则", "比例", "映射数", "计量结果"]


class BoqTable(QTableWidget):
    itemSelected = Signal(int)          # boq_item_id
    ruleChanged = Signal(int, str)      # item_id, rule_type
    scaleChanged = Signal(int, float)   # item_id, scale_factor

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""  # P1-10 搜索过滤词
        self.setColumnCount(len(COLS))
        self.setHorizontalHeaderLabels(COLS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        header = self.horizontalHeader()
        # 描述列拥有最大伸缩权；其余列固定宽度，防止被挤压
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4, 5, 6, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
            header.setMinimumSectionSize(50)
        header.setMaximumSectionSize(220)
        self.verticalHeader().setVisible(False)
        self._items = {}  # row -> BoqItem
        self.itemSelectionChanged.connect(self._emit_selection)
        self.itemChanged.connect(self._on_item_changed)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)  # Phase 3: 双击提交

    def load(self, items: list):
        started = time.perf_counter()
        self.blockSignals(True)
        self.clearContents()
        self.setRowCount(0)
        self._items.clear()
        for it in items:
            row = self.rowCount()
            self.insertRow(row)
            self._items[row] = it
            self._set_item(row, 0, it.code)
            self._set_item(row, 1, it.description)
            self._set_item(row, 2, it.unit)
            self._set_item(row, 3, str(it.original_qty) if it.original_qty else "")
            self._set_combo(row, 4, RULE_LABELS.get(it.rule_type, "长度"))
            self._set_item(row, 5, str(it.scale_factor))
            self._set_item(row, 6, "0", gray=True)
            self._set_item(row, 7, "", gray=True)
        self.blockSignals(False)
        self.resizeRowsToContents()
        # 重载后若有搜索词，重新应用过滤（P1-10）
        if self._filter_text:
            self.set_filter(self._filter_text)
        logger.info("boq_table load: items=%d elapsed_ms=%.1f", len(items), (time.perf_counter() - started) * 1000)

    # ================= 搜索过滤 + 高亮（P1-10） =================
    def set_filter(self, text: str):
        """按 编号/描述/单位 过滤行；匹配行高亮底色。

        Args:
            text: 搜索词（空 = 显示全部并清除高亮）
        """
        text = (text or "").strip()
        self._filter_text = text
        low = text.lower()
        highlight = QColor(T.SELECTION)  # 浅蓝选中底，标识命中行
        for row, it in list(self._items.items()):
            hit = (not low) or (
                low in str(it.code).lower()
                or low in str(it.description).lower()
                or low in str(it.unit).lower()
            )
            self.setRowHidden(row, not hit)
            for c in range(self.columnCount()):
                cell = self.item(row, c)
                if cell:
                    # 命中行浅蓝底，未命中/清空时用空 QBrush 还原（QTableWidgetItem 不接受 None）
                    cell.setBackground(highlight if (hit and text) else QBrush())

    def clear_filter(self):
        """清空搜索词并恢复全部行。"""
        self.set_filter("")

    def _set_item(self, row, col, text, gray=False):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if gray:
            item.setForeground(Qt.gray)
        self.setItem(row, col, item)

    def _set_combo(self, row, col, label):
        from PySide6.QtWidgets import QComboBox
        combo = QComboBox()
        combo.addItems(list(RULE_LABELS.values()))
        combo.setCurrentText(label)
        combo.currentTextChanged.connect(
            lambda t, r=row: self._on_rule_changed(r, t))
        self.setCellWidget(row, col, combo)

    def _on_rule_changed(self, row, label):
        it = self._items.get(row)
        if it:
            it.rule_type = RULE_VALUES.get(label, "length")
            self.ruleChanged.emit(it.id, it.rule_type)

    def _on_item_changed(self, item):
        row = item.row()
        col = item.column()
        it = self._items.get(row)
        if not it:
            return
        if col == 5:  # 比例
            try:
                v = float(item.text())
                it.scale_factor = v
                self.scaleChanged.emit(it.id, v)
            except ValueError:
                pass
        elif col == 2:  # 单位
            it.unit = item.text()

    def _emit_selection(self):
        rows = self.selectionModel().selectedRows()
        if rows:
            it = self._items.get(rows[0].row())
            if it:
                self.itemSelected.emit(it.id)

    def update_result(self, item_id: int, mapped_count: int, qty: float):
        for row, it in self._items.items():
            if it.id == item_id:
                self.blockSignals(True)
                cell = self.item(row, 6)
                if cell:
                    # 状态表达：图标 + 文字 + 颜色（不单纯依赖颜色，符合 WCAG）
                    if mapped_count > 0:
                        cell.setText(f"✓ {mapped_count}")
                        cell.setForeground(QColor(T.ACCENT))
                        cell.setToolTip(f"已映射 {mapped_count} 个实体")
                    else:
                        cell.setText("— 0")
                        cell.setForeground(QColor(T.TEXT_DISABLED))
                        cell.setToolTip("未映射实体")
                cell2 = self.item(row, 7)
                if cell2:
                    if qty:
                        cell2.setText(f"✓ {qty:.4g}")
                        cell2.setForeground(QColor(T.SUCCESS))
                        cell2.setToolTip(f"计量结果：{qty:g}")
                    else:
                        cell2.setText("—")
                        cell2.setForeground(QColor(T.TEXT_DISABLED))
                        cell2.setToolTip("未计量")
                self.blockSignals(False)
                return

    def current_item_id(self) -> int | None:
        rows = self.selectionModel().selectedRows()
        if rows:
            it = self._items.get(rows[0].row())
            return it.id if it else None
        return None

    def all_items(self) -> list:
        return list(self._items.values())

    # ---------- Phase 3: 跨高亮 + 提交 ----------
    def highlight_item(self, item_id: int, flash: bool = True, select: bool = True):
        """滚动到 item_id 对应行 + 闪烁背景 + 可选选中"""
        for row, it in self._items.items():
            if it.id == item_id:
                if select:
                    self.selectRow(row)
                cell = self.item(row, 0)
                if cell:
                    self.scrollToItem(cell, QAbstractItemView.PositionAtCenter)
                if flash:
                    self._flash_row(row)
                return

    def _on_cell_double_clicked(self, row, col):
        """Phase 3: 双击 BOQ 行触发提交（如果主窗口有待选）"""
        it = self._items.get(row)
        if it:
            # 通过 currentChanged 选中行；主窗口监听 selection 后会从 canvas 提
            # 实际上 main_window 通过 _on_boq_row_activated 信号接收更直接
            self.selectRow(row)
            self.itemSelected.emit(it.id)

    def _flash_row(self, row: int, times: int = 2, interval_ms: int = 220):
        """行背景闪烁若干次（用 QTimer 异步）"""
        colors = [QColor(T.FLASH_COLORS[0]), QColor(T.FLASH_COLORS[1])]
        state = {"i": 0}

        def step():
            if state["i"] >= times * 2:
                # 恢复：刷一遍默认背景
                for c in range(self.columnCount()):
                    cell = self.item(row, c)
                    if cell:
                        cell.setData(Qt.BackgroundRole, None)
                return
            color = colors[state["i"] % 2]
            for c in range(self.columnCount()):
                cell = self.item(row, c)
                if cell:
                    cell.setBackground(color)
            state["i"] += 1
            QTimer.singleShot(interval_ms, step)

        step()
