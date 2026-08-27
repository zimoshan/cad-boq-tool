"""主要材料表对话框：项目级设备（块计数）+ 导线（图层长度）。

功能：
- 设备 tab：按块计数，可关联 BOQ 子项（block 映射）
- 导线 tab：图层长度（实际值，未换算），换算率可人工编辑 → 自动换算后长度
- 关联 BOQ 后回写实测数量列（write_back_quantities）
- 导出主要材料表 Excel（report.export_materials，含换算三列）
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QTabWidget,
                               QFileDialog, QMessageBox)

from .. import db, mapping as map_svc, report
from ..boq import write_back_quantities
from ..engineering import infer_spec_from_block

logger = logging.getLogger(__name__)

WARN_FG = "#b8860b"
WARN_BG = "#FEF3C7"

WIRE_TIP = ("导线长度按实际数值显示（未自动换算比例）。"
            "「换算率」列可双击编辑，输入后「换算后长度」自动更新；"
            "导出 Excel 时同样带 原始长度/换算率/换算后长度 三列。")

_COLS_D = ["名称（块名）", "规格/型号", "数量", "出现图纸", "关联 BOQ"]
_COLS_W = ["名称（图层）", "规格/型号", "原始长度", "换算率(可编辑)",
           "换算后长度", "实体数", "出现图纸", "关联 BOQ"]


class BoqPickerDialog(QDialog):
    """选择要关联的 BOQ 子项。"""

    def __init__(self, items: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关联到 BOQ 条目")
        self.resize(620, 460)
        self._items = items
        self.selected_id = None

        lay = QVBoxLayout(self)
        tbl = QTableWidget(0, 3)
        tbl.setHorizontalHeaderLabels(["编号", "描述", "单位"])
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.setRowCount(len(items))
        for r, it in enumerate(items):
            vals = [it.code, it.description, it.unit]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, it.id)
                tbl.setItem(r, c, item)
        tbl.doubleClicked.connect(lambda _i: self._accept(tbl))
        lay.addWidget(tbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("关联")
        btn_ok.setObjectName("primaryBtn")
        btn_ok.clicked.connect(lambda: self._pick(tbl))
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)
        self._tbl = tbl

    def _pick(self, tbl):
        rows = tbl.selectionModel().selectedRows()
        if rows:
            cell = tbl.item(rows[0].row(), 0)
            self.selected_id = cell.data(Qt.UserRole) if cell else None
            self.accept()


class MaterialsDialog(QDialog):
    """主要材料表（项目级统计 + BOQ 关联/回写 + 导出）。"""

    def __init__(self, project_id: int, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._rates: dict[str, float] = {}
        self.setWindowTitle("主要材料表（项目统计）")
        self.resize(1120, 660)
        self._build_ui()
        self.reload()

    # ---------------- UI ----------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        warn = QLabel("⚠ " + WIRE_TIP)
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color:{WARN_FG}; background:{WARN_BG}; padding:6px 10px; border-radius:3px;")
        lay.addWidget(warn)

        # 工具栏
        tb = QHBoxLayout()
        tb.setSpacing(6)
        btn_refresh = QPushButton("刷新统计")
        btn_refresh.clicked.connect(self.reload)
        btn_export = QPushButton("导出 Excel")
        btn_export.setObjectName("primaryBtn")
        btn_export.clicked.connect(self._on_export)
        btn_write = QPushButton("回写 BOQ 实测数量")
        btn_write.clicked.connect(self._on_writeback)
        tb.addWidget(btn_refresh)
        tb.addWidget(btn_export)
        tb.addWidget(btn_write)
        tb.addStretch(1)
        lay.addLayout(tb)

        # 两个 Tab：设备 / 导线
        self._tabs = QTabWidget()
        self._tab_dev = QTableWidget()
        self._tab_wire = QTableWidget()
        for t in (self._tab_dev, self._tab_wire):
            t.setSelectionBehavior(QAbstractItemView.SelectRows)
            t.setSelectionMode(QAbstractItemView.SingleSelection)
            t.setEditTriggers(QAbstractItemView.NoEditTriggers |
                              QAbstractItemView.DoubleClicked |
                              QAbstractItemView.EditKeyPressed)
            t.setAlternatingRowColors(True)
            t.verticalHeader().setVisible(False)
            t.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tab_dev.customContextMenuRequested.connect(
            lambda pos: self._on_menu(self._tab_dev, pos, "block"))
        self._tab_wire.customContextMenuRequested.connect(
            lambda pos: self._on_menu(self._tab_wire, pos, "layer"))
        self._tab_wire.itemChanged.connect(self._on_wire_rate_edit)
        self._tabs.addTab(self._tab_dev, "设备（块计数）")
        self._tabs.addTab(self._tab_wire, "导线（图层长度）")
        lay.addWidget(self._tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

    # ---------------- 数据 ----------------
    def reload(self):
        data = db.summarize_materials(self._project_id)
        self._devices = data["devices"]
        self._wires = data["wires"]
        self._rates = {w["layer_name"]: self._rates.get(w["layer_name"], 1.0)
                      for w in self._wires}
        self._boq = {it.id: it for it in db.get_boq_items(self._project_id)}
        self._linked = self._build_linked_map()
        self._legend = db.get_block_legend_map(self._project_id)
        self._render_devices()
        self._render_wires()

    def _build_linked_map(self):
        """{ (kind, key): boq_item_id } —— 跨图纸扫 mapping。"""
        out = {}
        for m in db.get_mappings(boq_item_id=None, sheet_id=None):
            if m.mode == "block" and m.block_name:
                out.setdefault(("block", m.block_name), m.boq_item_id)
            elif m.mode == "layer" and m.layer_name:
                out.setdefault(("layer", m.layer_name), m.boq_item_id)
        return out

    def _linked_label(self, kind: str, key: str) -> str:
        bid = self._linked.get((kind, key))
        if bid is None:
            return ""
        it = self._boq.get(bid)
        return it.code if it else str(bid)

    def _device_spec(self, block_name: str) -> str:
        legend = self._legend.get(block_name)
        if legend and legend.get("spec"):
            return str(legend["spec"])
        return infer_spec_from_block(block_name)

    def _layer_spec(self, layer: str) -> str:
        legend = self._legend.get(layer)
        return str(legend["spec"]) if legend and legend.get("spec") else ""

    # ---------------- 渲染 ----------------
    def _render_devices(self):
        t = self._tab_dev
        t.blockSignals(True)
        t.clear()
        t.setColumnCount(len(_COLS_D))
        t.setHorizontalHeaderLabels(_COLS_D)
        t.setRowCount(len(self._devices))
        for r, d in enumerate(self._devices):
            vals = [d["block_name"], self._device_spec(d["block_name"]),
                    str(d["qty"]), str(d["sheet_count"]),
                    self._linked_label("block", d["block_name"])]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, d["block_name"])
                t.setItem(r, c, item)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        t.blockSignals(False)

    def _render_wires(self):
        t = self._tab_wire
        t.blockSignals(True)
        t.clear()
        t.setColumnCount(len(_COLS_W))
        t.setHorizontalHeaderLabels(_COLS_W)
        t.setRowCount(len(self._wires))
        for r, w in enumerate(self._wires):
            rate = self._rates.get(w["layer_name"], 1.0)
            vals = [w["layer_name"], self._layer_spec(w["layer_name"]),
                    f"{w['length_raw']:g}", f"{rate:g}",
                    f"{w['length_raw'] * rate:.2f}",
                    str(w["entity_count"]), str(w["sheet_count"]),
                    self._linked_label("layer", w["layer_name"])]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, w["layer_name"])
                # 换算率列可编辑、橙字提示
                if c == 3:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    item.setForeground(QColor(WARN_FG))
                elif c == 4:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                t.setItem(r, c, item)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        t.blockSignals(False)

    def _on_wire_rate_edit(self, item):
        if item.column() != 3:
            return
        layer = item.data(Qt.UserRole) or ""
        try:
            rate = float(item.text().strip())
        except ValueError:
            self.reload()
            return
        self._rates[layer] = rate
        for r in range(self._tab_wire.rowCount()):
            it = self._tab_wire.item(r, 0)
            if it and it.data(Qt.UserRole) == layer:
                raw = next((w["length_raw"] for w in self._wires
                            if w["layer_name"] == layer), 0.0)
                conv_item = self._tab_wire.item(r, 4)
                if conv_item:
                    self._tab_wire.blockSignals(True)
                    conv_item.setText(f"{raw * rate:.2f}")
                    self._tab_wire.blockSignals(False)
                break

    # ---------------- 布尔操作：关联 / 导出 / 回写 ----------------
    def _on_menu(self, tbl, pos, kind):
        row = tbl.rowAt(pos.y())
        if row < 0:
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        act_link = menu.addAction("关联到 BOQ 条目…")
        act_unlink = menu.addAction("取消关联")
        act_export = menu.addAction("导出 Excel…")
        chosen = menu.exec(tbl.viewport().mapToGlobal(pos))
        if chosen == act_link:
            self._on_link(tbl, row, kind)
        elif chosen == act_unlink:
            self._on_unlink(tbl, row, kind)
        elif chosen == act_export:
            self._on_export()

    def _on_link(self, tbl, row, kind):
        cell = tbl.item(row, 0)
        if cell is None:
            return
        key = cell.text()
        if not self._boq:
            QMessageBox.information(self, "提示", "请先导入 BOQ 清单（更多 → 导入 BOQ）")
            return
        picker = BoqPickerDialog(list(self._boq.values()), self)
        if picker.exec() != QDialog.Accepted or picker.selected_id is None:
            return
        boq_id = picker.selected_id
        if kind == "block":
            res = map_svc.add_project_block_mapping(boq_id, self._project_id, key)
        else:
            res = map_svc.add_project_layer_mapping(boq_id, self._project_id, key)
        if res["added"] == 0:
            QMessageBox.warning(self, "关联失败", f"「{key}」在项目中无实体可映射")
            return
        logger.info("material linked: kind=%s key=%s boq=%s added=%d",
                    kind, key, boq_id, res["added"])
        write_back_quantities(self._project_id)
        self.reload()

    def _on_unlink(self, tbl, row, kind):
        cell = tbl.item(row, 0)
        if cell is None:
            return
        key = cell.text()
        bid = self._linked.get((kind, key))
        if bid is None:
            return
        removed = 0
        for m in db.get_mappings(boq_item_id=bid, sheet_id=None):
            if m.mode == kind and (m.block_name if kind == "block" else m.layer_name) == key:
                db.delete_mapping(m.id)
                removed += 1
        self.reload()
        logger.info("material unlinked: kind=%s key=%s removed=%d", kind, key, removed)

    def _on_writeback(self):
        res = write_back_quantities(self._project_id)
        QMessageBox.information(
            self, "回写完成",
            f"已将 {res['written']} 条 BOQ 子项的实测数量写入「实测数量」列。\n"
            "可在 BOQ 清单「计量结果」列查看；原数量列保留对照。")

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出主要材料表", "主要材料表.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        rates = {w["layer_name"]: self._rates.get(w["layer_name"], 1.0)
                 for w in self._wires}
        n = report.export_materials(
            self._project_id, path,
            get_spec_fn=self._spec_lookup, rates=rates)
        QMessageBox.information(self, "导出成功", f"已导出 {n} 条材料 →\n{path}")

    def _spec_lookup(self, kind, key):
        if kind == "block":
            return self._device_spec(key)
        return self._layer_spec(key)