"""AI 算量结果对话框（22C-2 / 22C-3）。

UI 26 号设计方案 2.4 节：
- 表格显示 LLM 输出的 BOQ 条目
- 列：编号/描述/单位/数量/置信度/来源/楼层
- 颜色编码：绿(>=0.7)/橙(0.5-0.7)/红(<0.5)
- 冲突单独成行
- 操作：全部接受/接受选中/导出 Excel/重新分析
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QCheckBox, QLineEdit
)

from . import theme as T


COLUMNS = ["", "编号", "描述", "单位", "数量", "置信度", "来源", "楼层"]


def confidence_color(conf: float) -> QColor:
    """置信度 → 背景色（引用 theme 常量）"""
    if conf >= 0.7:
        return QColor(T.CONFIDENCE_HIGH)
    elif conf >= 0.5:
        return QColor(T.CONFIDENCE_MID)
    return QColor(T.CONFIDENCE_LOW)


def confidence_icon(conf: float) -> str:
    if conf >= 0.7:
        return "✓"
    elif conf >= 0.5:
        return "⚠"
    return "✗"


class AiResultsDialog(QDialog):
    """AI 算量结果展示 + 接受/拒绝/导出"""

    accepted = Signal(list)        # 接受的 TakeoffItem 列表
    rejected = Signal(list)        # 拒绝的 TakeoffItem 列表

    def __init__(self, items: list, project_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"🤖 AI 算量结果 — {project_name}" if project_name else "🤖 AI 算量结果")
        self._items = items
        self._build_ui()
        self._populate(items)
        # 屏幕适配
        from .ui_utils import fit_dialog_to_screen
        fit_dialog_to_screen(self, (1100, 600), "review")

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)

        # 顶部：筛选
        h_filter = QHBoxLayout()
        h_filter.addWidget(QLabel("筛选:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索编号/描述/图层")
        self.search_box.textChanged.connect(self._apply_filter)
        h_filter.addWidget(self.search_box, 1)

        self.cb_high = QCheckBox("高置信")
        self.cb_high.setChecked(True)
        self.cb_mid = QCheckBox("中置信")
        self.cb_mid.setChecked(True)
        self.cb_low = QCheckBox("低置信")
        self.cb_low.setChecked(True)
        self.cb_conflict = QCheckBox("冲突")
        self.cb_conflict.setChecked(True)
        for cb in [self.cb_high, self.cb_mid, self.cb_low, self.cb_conflict]:
            cb.toggled.connect(self._apply_filter)
            h_filter.addWidget(cb)
        v.addLayout(h_filter)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        v.addWidget(self.table, 1)

        # 状态栏
        self.status_label = QLabel("")
        v.addWidget(self.status_label)

        # 底部：操作按钮（层级：全部接受=primary, 接受选中=secondary, 拒绝=danger）
        h_btn = QHBoxLayout()
        h_btn.addStretch(1)
        self.btn_accept_all = QPushButton("全部接受")
        self.btn_accept_all.setObjectName("primaryBtn")
        self.btn_accept_all.clicked.connect(self._accept_all)
        h_btn.addWidget(self.btn_accept_all)

        self.btn_accept_sel = QPushButton("接受选中")
        self.btn_accept_sel.clicked.connect(self._accept_selected)
        h_btn.addWidget(self.btn_accept_sel)

        self.btn_reject = QPushButton("拒绝选中")
        self.btn_reject.setObjectName("dangerBtn")
        self.btn_reject.clicked.connect(self._reject_selected)
        h_btn.addWidget(self.btn_reject)

        self.btn_export = QPushButton("导出 Excel")
        self.btn_export.clicked.connect(self._export_excel)
        h_btn.addWidget(self.btn_export)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.reject)
        h_btn.addWidget(self.btn_close)

        v.addLayout(h_btn)

    def _populate(self, items: list):
        self.table.setRowCount(len(items))
        for r, it in enumerate(items):
            conf = it.confidence
            is_conflict = it.raw.get("_conflict", False)
            color = QColor(T.CONFLICT_BG) if is_conflict else confidence_color(conf)

            # 复选框
            chk = QCheckBox()
            chk.setChecked(True)
            self.table.setCellWidget(r, 0, chk)

            # 其他列
            values = [
                it.code,
                it.description,
                it.unit,
                f"{it.quantity:.2f}",
                f"{confidence_icon(conf)} {conf:.0%}",
                it.source_layer or it.source_block or "-",
                ", ".join(it.raw.get("floors", [])) or "-",
            ]
            for c, v_text in enumerate(values, 1):
                cell = QTableWidgetItem(v_text)
                cell.setBackground(QBrush(color))
                # 冲突时整行加粗红字
                if is_conflict:
                    font = cell.font()
                    font.setBold(True)
                    cell.setFont(font)
                    cell.setForeground(QBrush(QColor(T.ERROR)))
                # 工具提示
                tip = f"描述: {it.description}\n置信度: {conf:.0%}\n理由: {it.reasoning[:100]}"
                if is_conflict:
                    tip += f"\n⚠ 冲突: 与均值差 {it.raw.get('_conflict_diff',0):.1f}%"
                cell.setToolTip(tip)
                self.table.setItem(r, c, cell)

        self._update_status()
        self._auto_resize()

    def _auto_resize(self):
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 100)
        self.table.setColumnWidth(6, 100)
        # 描述列 stretch
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

    def _update_status(self):
        total = len(self._items)
        high = sum(1 for i in self._items if i.confidence >= 0.7)
        mid = sum(1 for i in self._items if 0.5 <= i.confidence < 0.7)
        low = sum(1 for i in self._items if i.confidence < 0.5)
        conflict = sum(1 for i in self._items if i.raw.get("_conflict"))
        self.status_label.setText(
            f"共 {total} 条：高置信 {high} | 中 {mid} | 低 {low} | 冲突 {conflict}"
        )

    def _apply_filter(self):
        """根据筛选条件 + 搜索词过滤行"""
        keyword = self.search_box.text().lower()
        show_high = self.cb_high.isChecked()
        show_mid = self.cb_mid.isChecked()
        show_low = self.cb_low.isChecked()
        show_conflict = self.cb_conflict.isChecked()

        for r, it in enumerate(self._items):
            conf = it.confidence
            is_conflict = it.raw.get("_conflict", False)

            # 类别
            if is_conflict and not show_conflict:
                hide = True
            elif conf >= 0.7 and not show_high:
                hide = True
            elif 0.5 <= conf < 0.7 and not show_mid:
                hide = True
            elif conf < 0.5 and not show_low:
                hide = True
            else:
                hide = False

            # 关键词
            if not hide and keyword:
                text = f"{it.code} {it.description} {it.source_layer} {it.source_block}".lower()
                hide = keyword not in text

            self.table.setRowHidden(r, hide)

    def _get_selected_items(self, checked_only: bool = False) -> list:
        """获取选中行/勾选行对应的 TakeoffItem"""
        if checked_only:
            out = []
            for r in range(self.table.rowCount()):
                chk = self.table.cellWidget(r, 0)
                if chk and chk.isChecked():
                    out.append(self._items[r])
            return out
        else:
            rows = {i.row() for i in self.table.selectedIndexes()}
            return [self._items[r] for r in sorted(rows) if r < len(self._items)]

    def _accept_all(self):
        items = self._get_selected_items(checked_only=True)
        if not items:
            QMessageBox.information(self, "提示", "没有勾选的条目")
            return
        self.accepted.emit(items)
        QMessageBox.information(self, "成功", f"已接受 {len(items)} 条")
        self.accept()

    def _accept_selected(self):
        items = self._get_selected_items(checked_only=False)
        if not items:
            QMessageBox.information(self, "提示", "请先选中要接受的行（Ctrl+点击多选）")
            return
        self.accepted.emit(items)
        QMessageBox.information(self, "成功", f"已接受 {len(items)} 条")
        self.accept()

    def _reject_selected(self):
        items = self._get_selected_items(checked_only=True)
        if not items:
            QMessageBox.information(self, "提示", "没有勾选的条目")
            return
        self.rejected.emit(items)

    def _export_excel(self):
        items = self._get_selected_items(checked_only=True)
        if not items:
            items = self._items
        if not items:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel", "ai_takeoff_result.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            from app.report import export_items_to_excel
            export_items_to_excel(items, path)
            QMessageBox.information(self, "成功", f"已导出 {len(items)} 条 →\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"导出失败: {e}")
