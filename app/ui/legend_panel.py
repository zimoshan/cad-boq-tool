"""图例标定面板：列出项目全部已识别块，人工标定设备语义。

- 每个块一行：块名 / 类别 / 设备类型 / 规格 / 单位 / 规则 / 状态 / 来源
- 类别·单位·规则 用下拉选择；设备类型·规格 内联编辑，改完自动落库
- 工具栏：图纸筛选 / 保存 / 确认全部 / 仅看未标定 / 隐藏建筑块 / 底图减法 / 导入 / 导出 / 刷新
- 行右键「在图纸中定位」→ locateRequested(block_name)
- legendChanged()：任一条目变更后发出，供主窗口刷新算量口径

数据来自 app/db.block_legend（按 project 唯一），逻辑来自 app/takeoff/block_legend。
"""
from __future__ import annotations

import json
import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QTableWidgetItem, QHeaderView, QPushButton,
                               QAbstractItemView, QLabel, QMenu, QFileDialog,
                               QStyledItemDelegate, QComboBox)
from .. import db
from ..takeoff import block_legend as bl
from . import theme as T

COL_BLOCK = 0
COL_CAT = 1
COL_TYPE = 2
COL_SPEC = 3
COL_UNIT = 4
COL_RULE = 5
COL_STATUS = 6
COL_SOURCE = 7
HEADERS = ["块名", "类别", "设备类型", "规格", "单位", "规则", "状态", "来源"]

RULE_LABEL = {"count": "count(计数)", "length": "length(长度)", "manual": "manual(人工)"}


class _ComboDelegate(QStyledItemDelegate):
    """下拉选择委托（类别 / 单位 / 规则）"""
    def __init__(self, options, parent=None):
        super().__init__(parent)
        self._options = options

    def createEditor(self, parent, option, index):
        cb = QComboBox(parent)
        cb.addItems(self._options)
        cb.setEditable(False)
        return cb

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)


class _WrapDelegate(QStyledItemDelegate):
    """文字换行委托：长文本自动换行完整显示（不再截断省略号）"""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.textElideMode = Qt.ElideNone
        option.wordWrap = True


class LegendPanel(QWidget):
    locateRequested = Signal(str)       # 在画布定位某块
    statusMessage = Signal(str)
    legendChanged = Signal()            # 标定变更（刷新算量口径）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_id: Optional[int] = None
        self._sheet_id: Optional[int] = None     # None=全部图纸；否则只显示该图纸的块
        self._rows: list = []           # 全部块行（dict）
        self._loading = False
        self._only_unconfirmed = False
        self._hide_building = True      # 默认隐藏建筑块（门窗墙柱洁具等）
        self._base_layers: set = set()  # 底图图层集（set[str]）
        self._base_subtraction = True   # 底图减法默认开（有底图时生效）
        self._base_hidden_blocks: set = set()   # 底图减法判定为建筑块的块名集
        self._build_ui()

    def refresh_enabled(self, has_project: bool):
        """P1-12：按钮与上下文对齐 — 无项目时禁用图例标定操作按钮。"""
        for b in (self.btn_confirm_all, self.btn_save, self.btn_refresh,
                  self.btn_import, self.btn_export):
            b.setEnabled(has_project)

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # 工具栏
        bar = QHBoxLayout()
        # 图纸过滤：全部图纸 / 单张图纸（跟随左侧图纸列表联动，也可手动切回）
        self.cmb_sheet = QComboBox()
        self.cmb_sheet.setMinimumWidth(420)   # 任务5：拉长筛选框，文件名基本完整显示
        self.cmb_sheet.setToolTip("按图纸过滤：显示该图纸实际出现的设备块；「全部图纸」为项目聚合视图")
        self.cmb_sheet.currentIndexChanged.connect(self._on_sheet_combo_changed)
        self.btn_confirm_all = QPushButton("确认全部")
        self.btn_confirm_all.clicked.connect(self._on_confirm_all)
        self.btn_save = QPushButton("保存")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(lambda: self.load_project(self._project_id, self._sheet_id))
        self.btn_import = QPushButton("导入")
        self.btn_import.clicked.connect(self._on_import)
        self.btn_export = QPushButton("导出")
        self.btn_export.clicked.connect(self._on_export)
        self.chk_unconfirmed = QPushButton("仅看未标定")
        self.chk_unconfirmed.setCheckable(True)
        self.chk_unconfirmed.toggled.connect(self._on_filter_toggle)
        self.chk_hide_building = QPushButton("隐藏建筑块")
        self.chk_hide_building.setCheckable(True)
        self.chk_hide_building.setChecked(self._hide_building)
        self.chk_hide_building.setToolTip(
            "隐藏门/窗/墙/柱/洁具/家具/轴线等建筑块，只看设备/线缆/待分类块。\n"
            "类别未知（未标定）的块不受该开关影响")
        self.chk_hide_building.toggled.connect(self._on_hide_building_toggle)
        self.chk_base_sub = QPushButton("底图减法")
        self.chk_base_sub.setCheckable(True)
        self.chk_base_sub.setChecked(self._base_subtraction)
        self.chk_base_sub.setToolTip(
            "有建筑底图时自动隐藏与底图同名图层上的块（确定性过滤，零 LLM 成本）。\n"
            "切换底图后自动生效；无底图时无效。")
        self.chk_base_sub.toggled.connect(self._on_base_sub_toggle)
        self.chk_base_sub.setVisible(False)   # 无底图时不显示
        bar.addWidget(self.cmb_sheet)
        for b in (self.btn_confirm_all, self.btn_save,
                  self.btn_refresh, self.btn_import, self.btn_export,
                  self.chk_unconfirmed, self.chk_hide_building, self.chk_base_sub):
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        # 列宽策略（任务4）：短列贴合内容且用户可拖动；长文本列均分剩余空间。
        # 全表 wordWrap：长文本按列宽自动换行，行高随内容自适应。
        self.table.setWordWrap(True)
        self._stretch_cols = {COL_TYPE, COL_SPEC, COL_SOURCE}
        hdr = self.table.horizontalHeader()
        for col in range(len(HEADERS)):
            hdr.setSectionResizeMode(
                col, QHeaderView.Stretch if col in self._stretch_cols
                else QHeaderView.Interactive)
        # 拖动列宽后行高联动重算（换行行数变化 → 防抖 150ms 重算，避免拖动中每帧全表重排）
        self._row_height_timer = QTimer(self)
        self._row_height_timer.setSingleShot(True)
        self._row_height_timer.setInterval(150)
        self._row_height_timer.timeout.connect(self.table.resizeRowsToContents)
        hdr.sectionResized.connect(self._on_section_resized)
        self._fit_key = None   # 列宽自适应记忆：(project_id, sheet_id) 变化才重新 fit
        self._wrap_delegate = _WrapDelegate(self.table)
        self.table.setItemDelegate(self._wrap_delegate)
        # 注意：QTableWidget.setItemDelegateForColumn 不接管 delegate 所有权，
        # 临时对象会被 Python GC 回收 → C++ 悬垂指针 → 滚动/重绘时段错误闪退。
        # 必须保存引用并显式传 parent。
        self._cat_delegate = _ComboDelegate(bl.CATEGORIES, self.table)
        self._unit_delegate = _ComboDelegate(bl.UNITS, self.table)
        self._rule_delegate = _ComboDelegate(
            [RULE_LABEL[k] for k in bl.COUNT_RULES], self.table)
        self.table.setItemDelegateForColumn(COL_CAT, self._cat_delegate)
        self.table.setItemDelegateForColumn(COL_UNIT, self._unit_delegate)
        self.table.setItemDelegateForColumn(COL_RULE, self._rule_delegate)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self.table, 1)

        # 状态条
        self.status_label = QLabel("未选择项目")
        self.status_label.setStyleSheet(f"color:{T.TEXT_HINT};font-size:{T.FONT_SIZE_CAPTION}px;")
        root.addWidget(self.status_label)

    # ---------- 数据加载 ----------
    def load_project(self, project_id: Optional[int], sheet_id: Optional[int] = None,
                     _reload_combo: bool = True):
        """加载图例。sheet_id=None 显示项目全部块；否则只显示该图纸实际出现的块。"""
        self._project_id = project_id
        self._rows = []
        if project_id is None:
            self._sheet_id = None
            if _reload_combo:
                self._reload_sheet_combo()
            self._render()
            self.status_label.setText("未选择项目")
            return
        if _reload_combo:
            self._reload_sheet_combo()
        # 校验 sheet_id 仍属于该项目（删除图纸后兜底回落全部）
        if sheet_id is not None:
            sheets = db.get_sheets(project_id)
            if not any(s.id == sheet_id for s in sheets):
                sheet_id = None
        self._sheet_id = sheet_id
        legend = db.get_block_legend_map(project_id)
        if sheet_id is not None:
            # 单图纸核对视图：只显示该图纸实际出现的块，附标定信息
            blocks = db.collect_blocks(project_id, sheet_id)
            for bname, count, _sh in blocks:
                if bname in legend:
                    row = dict(legend[bname])
                else:
                    row = {
                        "project_id": project_id, "block_name": bname,
                        "category": "", "device_type": "", "spec": "",
                        "unit": "个", "count_rule": "count",
                        "confirmed": 0, "source": "", "note": "",
                    }
                row["_count"] = count
                self._rows.append(row)
        else:
            # 项目聚合视图：该项目下全部已识别块
            blocks = db.collect_blocks(project_id)
            for bname, count, _sh in blocks:
                if bname in legend:
                    row = dict(legend[bname])
                else:
                    row = {
                        "project_id": project_id, "block_name": bname,
                        "category": "", "device_type": "", "spec": "",
                        "unit": "个", "count_rule": "count",
                        "confirmed": 0, "source": "", "note": "",
                    }
                row["_count"] = count  # 引用次数（展示用，不入表）
                self._rows.append(row)
            # 已标定但当前图纸未出现的（少见，仍列出）
            for bname, row in legend.items():
                if not any(r["block_name"] == bname for r in self._rows):
                    r = dict(row); r["_count"] = 0
                    self._rows.append(r)
        self._compute_base_hidden_blocks()
        self._render()
        self._update_status()

    def set_base_layers(self, base_layers: set):
        """主窗口调用：传入底图图层集，自动计算隐藏块并刷新。"""
        self._base_layers = base_layers or set()
        self.chk_base_sub.setVisible(bool(self._base_layers))
        if self._project_id is not None:
            self._compute_base_hidden_blocks()
            self._render()
            self._update_status()

    def _compute_base_hidden_blocks(self):
        """计算底图减法判定为建筑块的块名集合。

        规则：一个块的所有 INSERT 图层都在 base_layers 中 → 建筑块 → 隐藏。
        （块只要有一个 INSERT 在非底图图层上 → 设备块 → 保留）
        """
        if not self._base_layers or self._project_id is None:
            self._base_hidden_blocks = set()
            return
        base_lower = {l.lower() for l in self._base_layers}
        hidden = set()
        if self._sheet_id is not None:
            # 单图纸视图：查该图纸的块-INSERT 图层映射
            b2l = db.get_block_insert_layers(self._sheet_id)
            for bn, layers in b2l.items():
                if layers and all(l.lower() in base_lower for l in layers):
                    hidden.add(bn)
        else:
            # 全部图纸视图：聚合所有 MEP 图纸（排除底图自身）
            base = db.get_base_sheet(self._project_id)
            for s in db.get_sheets(self._project_id):
                if base and s.id == base.id:
                    continue
                b2l = db.get_block_insert_layers(s.id)
                for bn, layers in b2l.items():
                    if bn in hidden:
                        continue
                    if layers and all(l.lower() in base_lower for l in layers):
                        hidden.add(bn)
        self._base_hidden_blocks = hidden

    def _on_base_sub_toggle(self, checked: bool):
        self._base_subtraction = checked
        self._render()
        self._update_status()

    def _reload_sheet_combo(self):
        """重建图纸下拉选项（首项「全部图纸」），保持当前选中值。"""
        cur = self.cmb_sheet.currentData()
        self.cmb_sheet.blockSignals(True)
        self.cmb_sheet.clear()
        self.cmb_sheet.addItem("全部图纸", None)
        if self._project_id is not None:
            for s in db.get_sheets(self._project_id):
                self.cmb_sheet.addItem(s.filename, s.id)
        # 恢复选中（当前图纸已删除则回落全部图纸）
        idx = self.cmb_sheet.findData(cur)
        self.cmb_sheet.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_sheet.blockSignals(False)

    def set_sheet_filter(self, sheet_id: Optional[int]):
        """主窗口联动入口：按图纸过滤图例（sheet_id=None 切回全部图纸）。

        同步下拉选中项（blockSignals 防递归），再触发加载。
        """
        idx = self.cmb_sheet.findData(sheet_id)
        if idx >= 0 and idx != self.cmb_sheet.currentIndex():
            self.cmb_sheet.blockSignals(True)
            self.cmb_sheet.setCurrentIndex(idx)
            self.cmb_sheet.blockSignals(False)
        self._sheet_id = sheet_id
        self.load_project(self._project_id, sheet_id)

    def _on_sheet_combo_changed(self, _idx):
        if self._project_id is None:
            return
        self.set_sheet_filter(self.cmb_sheet.currentData())

    @property
    def current_sheet_id(self) -> Optional[int]:
        return self._sheet_id

    def _visible_rows(self) -> list:
        rows = self._rows
        if self._base_subtraction and self._base_hidden_blocks:
            rows = [r for r in rows if r["block_name"] not in self._base_hidden_blocks]
        if self._hide_building:
            rows = [r for r in rows if (r.get("category") or "").strip() != "建筑"]
        if self._only_unconfirmed:
            rows = [r for r in rows if not r.get("confirmed")]
        return rows

    def _on_hide_building_toggle(self, checked: bool):
        self._hide_building = checked
        self._render()
        self._update_status()

    def _hidden_building_count(self) -> int:
        return sum(1 for r in self._rows
                   if (r.get("category") or "").strip() == "建筑")

    def _render(self):
        self._loading = True
        rows = self._visible_rows()
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            count_disp = f" {r.get('_count', 0)}" if r.get("_count") else ""
            self._set(i, COL_BLOCK, r["block_name"] + count_disp, editable=False)
            self._set(i, COL_CAT, r.get("category") or "", editable=True)
            self._set(i, COL_TYPE, r.get("device_type") or "", editable=True)
            self._set(i, COL_SPEC, r.get("spec") or "", editable=True)
            self._set(i, COL_UNIT, r.get("unit") or "个", editable=True)
            self._set(i, COL_RULE, RULE_LABEL.get(r.get("count_rule", "count"), ""), editable=True)
            confirmed = bool(r.get("confirmed"))
            status = "✓ 已确认" if confirmed else "待复核"
            self._set(i, COL_STATUS, status, editable=False,
                      color=(T.SUCCESS_BG if confirmed else T.WARNING_TEXT))
            src = r.get("source") or "—"
            self._set(i, COL_SOURCE, src, editable=False)
        self.table.resizeRowsToContents()   # 换行后行高自适应
        self._loading = False
        self._fit_columns()

    def _on_section_resized(self, *args):
        """列宽变化（含拖动）→ 防抖重算行高（换行行数随列宽变化）。"""
        self._row_height_timer.start()

    def _fit_columns(self):
        """按内容自适应初始列宽（任务4）。

        - 短列（块名/类别/单位/规则/状态）：贴合内容宽度，设上下限，用户可拖动
        - 长文本列（设备类型/规格/来源）：Stretch 模式自动均分剩余空间，长文本换行
        - 同一数据源只 fit 一次：保留用户手动拖动的列宽；切换项目/图纸后重新 fit
        """
        key = (self._project_id, self._sheet_id)
        if key == self._fit_key:
            return
        self._fit_key = key
        hdr = self.table.horizontalHeader()
        self.table.resizeColumnsToContents()   # 先全列按内容（含表头文字）
        for col in range(self.table.columnCount()):
            if col in self._stretch_cols:
                continue                        # 长文本列交给 Stretch，不手动定宽
            w = hdr.sectionSize(col)
            w = max(56, min(w, 260))            # 过窄无法点击，过宽（超长块名）换行
            hdr.resizeSection(col, w)

    def _set(self, row, col, text, editable=True, color=None):
        item = QTableWidgetItem(str(text))
        item.setToolTip(str(text))          # 悬停显示完整文本（防截断）
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if color:
            item.setForeground(QColor(color))
        self.table.setItem(row, col, item)

    # ---------- 编辑落库 ----------
    def _on_cell_changed(self, row, col):
        if self._loading:
            return
        rows = self._visible_rows()
        if row >= len(rows):
            return
        r = rows[row]
        new_val = self.table.item(row, col).text().strip()
        field = {COL_CAT: "category", COL_TYPE: "device_type", COL_SPEC: "spec",
                 COL_UNIT: "unit", COL_RULE: "count_rule"}.get(col)
        if field is None:
            return
        if field == "count_rule":
            # 反查规则 key
            inv = {v: k for k, v in RULE_LABEL.items()}
            new_val = inv.get(new_val, new_val)
        r[field] = new_val
        # 人工编辑即视为 manual 来源（除非原本是已确认 llm，保留来源）
        if not r.get("confirmed") and field in ("category", "device_type", "spec", "unit", "count_rule"):
            if r.get("source") in ("", None):
                r["source"] = "manual"
        self._persist_row(r)
        self._update_status()

    def _persist_row(self, r):
        if self._project_id is None:
            return
        db.save_block_legend({
            "project_id": self._project_id,
            "block_name": r["block_name"],
            "category": r.get("category", ""),
            "device_type": r.get("device_type", ""),
            "spec": r.get("spec", ""),
            "unit": r.get("unit", "个"),
            "count_rule": r.get("count_rule", "count"),
            "confirmed": int(bool(r.get("confirmed"))),
            "source": r.get("source") or "manual",
            "note": r.get("note", ""),
        })
        self.legendChanged.emit()

    # ---------- 工具栏动作 ----------
    def _on_save(self):
        for r in self._rows:
            # 仅保存有内容的（避免把空行也落库）
            if r.get("device_type") or r.get("category") or r.get("spec"):
                self._persist_row(r)
        self.statusMessage.emit("图例已保存")
        self._update_status()

    def _on_confirm_all(self):
        if self._project_id is None:
            return
        for r in self._rows:
            r["confirmed"] = 1
            if not r.get("source"):
                r["source"] = "manual"
            self._persist_row(r)
        self._render()
        self.statusMessage.emit("已确认全部标定")
        self._update_status()

    def _on_filter_toggle(self, checked: bool):
        self._only_unconfirmed = checked
        self._render()

    def _on_import(self):
        if self._project_id is None:
            self.statusMessage.emit("请先选择项目")
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入图例", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.statusMessage.emit(f"导入失败: {e}")
            return
        rows = data if isinstance(data, list) else data.get("legend", [])
        for r in rows:
            bname = r.get("block_name")
            if not bname:
                continue
            db.save_block_legend({
                "project_id": self._project_id,
                "block_name": bname,
                "category": r.get("category", ""),
                "device_type": r.get("device_type", ""),
                "spec": r.get("spec", ""),
                "unit": r.get("unit", "个"),
                "count_rule": r.get("count_rule", "count"),
                "confirmed": 1 if r.get("device_type") or r.get("category") else 0,
                "source": "manual",
                "note": r.get("note", ""),
            })
        self.load_project(self._project_id)
        self.statusMessage.emit(f"已导入 {len(rows)} 条图例")

    def _on_export(self):
        if self._project_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出图例", "legend.json", "JSON (*.json)")
        if not path:
            return
        out = [{
            "block_name": r["block_name"], "category": r.get("category", ""),
            "device_type": r.get("device_type", ""), "spec": r.get("spec", ""),
            "unit": r.get("unit", "个"), "count_rule": r.get("count_rule", "count"),
            "confirmed": int(bool(r.get("confirmed"))), "source": r.get("source", ""),
        } for r in self._rows]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        self.statusMessage.emit(f"已导出 {len(out)} 条图例 → {os.path.basename(path)}")

    # ---------- 行右键：定位 / 手动纠正建筑分类 ----------
    def _on_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        rows = self._visible_rows()
        if row >= len(rows):
            return
        bname = rows[row]["block_name"]
        is_building = (rows[row].get("category") or "").strip() == "建筑"
        menu = QMenu(self)
        acts = {"locate": menu.addAction("在图纸中定位")}
        if is_building:
            acts["device"] = menu.addAction("标记为设备块（取消隐藏）")
        else:
            acts["building"] = menu.addAction("标记为建筑块（隐藏）")
        act = menu.exec(self.table.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act == acts["locate"]:
            self.locateRequested.emit(bname)
        elif "device" in acts and act == acts["device"]:
            self._set_row_category(bname, "设备")
        elif "building" in acts and act == acts["building"]:
            self._set_row_category(bname, "建筑")

    def _set_row_category(self, bname: str, category: str):
        """右键手动纠正分类（LLM 判错时一键改回；人工纠正后续快筛不覆盖）"""
        for r in self._rows:
            if r["block_name"] == bname:
                r["category"] = category
                r["source"] = "manual"
                self._persist_row(r)
                break
        self._render()
        self._update_status()
        self.statusMessage.emit(f"块 [{bname}] 已标记为「{category}」")

    def _update_status(self):
        total = len(self._rows)
        confirmed = sum(1 for r in self._rows if r.get("confirmed"))
        uncalibrated = sum(1 for r in self._rows
                           if not (r.get("device_type") or r.get("category")))
        if self._sheet_id is not None and self._project_id is not None:
            name = self.cmb_sheet.currentText()
            scope = f"图纸「{name}」"
        else:
            scope = "全部图纸"
        hidden = self._hidden_building_count()
        hidden_part = f" · 已隐藏建筑块 {hidden}" if (self._hide_building and hidden) else ""
        base_part = ""
        if self._base_subtraction and self._base_hidden_blocks:
            base_part = f" · 底图减法已过滤 {len(self._base_hidden_blocks)} 块"
        self.status_label.setText(
            f"{scope} · 共 {total} 块 · 已确认 {confirmed} · 待复核 {total - confirmed} · "
            f"未标定(无设备类型) {uncalibrated}{hidden_part}{base_part}")
