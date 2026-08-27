"""项目设置对话框：图层筛选规则 / 设备筛选规则 / 图纸BOQ来源 / 项目基础信息。

V2 任务二十八：所有规则按项目保存到 project_config 表，方便回溯调用。
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QTabWidget, QWidget, QListWidget, QListWidgetItem,
                                QPushButton, QLineEdit, QMessageBox, QGroupBox,
                                QTextEdit, QFormLayout, QTableWidget,
                                QTableWidgetItem, QHeaderView, QAbstractItemView,
                                QFileDialog, QSplitter, QScrollArea)

from .. import db
from ..engineering.classifier import _is_building_bg_layer
from . import theme as T


# 4 个桶
BUCKETS = [
    ("设备 (equipment)", "equipment",
     "INSERT 块、灯具/插座/开关/消防探头/广播喇叭/配电柜/AP/门禁/电视"),
    ("导线 (linear)", "linear",
     "桥架/线槽/管道（cable tray / conduit / kablo kanalı）"),
    ("面积 (area)", "area",
     "HATCH 风管/水管/防火分区（DUCT/AHU/PIPE/风管/管道）"),
    ("跳过 (skip)", "skip",
     "建筑底图（墙/柱/门窗/装饰/家具）— 无需进入算量"),
]


class LayerRulesTab(QWidget):
    """Tab 1：图层筛选规则编辑（左侧图层列表 + 4 个分类桶 + 批量操作）"""

    def __init__(self, project_id: int, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._layer_rules = db.get_project_config(project_id)["layer_rules"]
        self._build_ui()
        self._refresh_left()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # 顶部说明
        tip = QLabel(
            "从左侧图层列表选择/拖动到右侧 4 个分类桶。"
            "批量操作：输入关键词 → 一键把含关键词的图层分配到指定桶。"
            "智能推荐：基于建筑背景规则一键填充「跳过」桶。")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color:{T.TEXT_HINT}; padding:4px;")
        root.addWidget(tip)

        # 主体：左 = 图层列表；右 = 4 个桶
        split = QSplitter(Qt.Horizontal)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("所有图层（按实体数排序）"))
        self.left_list = QListWidget()
        self.left_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lv.addWidget(self.left_list)
        # 双击 = 默认放设备
        self.left_list.itemDoubleClicked.connect(self._on_double_click)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        self.bucket_lists = {}
        for title, key, hint in BUCKETS:
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            tip_lbl = QLabel(hint); tip_lbl.setStyleSheet(f"color:{T.TEXT_DISABLED}; font-size:{T.FONT_SIZE_CAPTION}px;")
            tip_lbl.setWordWrap(True)
            bl.addWidget(tip_lbl)
            lw = QListWidget()
            lw.setSelectionMode(QAbstractItemView.ExtendedSelection)
            lw.setAcceptDrops(True)
            bl.addWidget(lw)
            self.bucket_lists[key] = lw
            btn_row = QHBoxLayout()
            rm = QPushButton("← 移出")
            rm.clicked.connect(lambda _=False, k=key: self._move_to_left(k))
            bl.addLayout(btn_row)
            btn_row.addWidget(rm)
            rv.addWidget(box)
        # 低分辨率保护：4 个分类桶垂直堆叠超高（1280×720 下 dialog 高约 540），
        # 包裹 QScrollArea 使桶列表可滚动而不被压缩到不可用。
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(right)
        split.addWidget(scroll)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        root.addWidget(split, 1)

        # 批量操作
        batch = QGroupBox("批量操作")
        bg = QHBoxLayout(batch)
        bg.addWidget(QLabel("关键词:"))
        self.kw_edit = QLineEdit()
        self.kw_edit.setPlaceholderText("输入图层名关键词（如 00 aten / kablo）")
        bg.addWidget(self.kw_edit, 1)
        for title, key, _ in BUCKETS:
            b = QPushButton(f"→ {title.split(' ')[0]}")
            b.clicked.connect(lambda _=False, k=key: self._batch_move_to(k))
            bg.addWidget(b)
        bg.addStretch(1)
        btn_smart = QPushButton("智能推荐：把建筑背景一键归入「跳过」")
        btn_smart.clicked.connect(self._smart_recommend_skip)
        bg.addWidget(btn_smart)
        # v3 任务二十九后续：一键全量归类（处理 139+ 个未分类图层）
        btn_auto_all = QPushButton("⚡ 一键全量归类所有未分类")
        btn_auto_all.setToolTip("按图层名启发式 + 设备关键词，把左侧所有未分类图层自动分到 4 个桶")
        btn_auto_all.setStyleSheet(f"QPushButton {{ background:{T.SUCCESS}; }} QPushButton:hover {{ background:{T.SUCCESS_HOVER}; }}")
        btn_auto_all.clicked.connect(self._auto_classify_all)
        bg.addWidget(btn_auto_all)
        root.addWidget(batch)

    def _refresh_left(self):
        self.left_list.clear()
        rows = db.summarize_layers(self._project_id)
        for r in rows:
            layer = r["layer_name"] or "(空/默认)"
            n = r["entity_count"]
            it = QListWidgetItem(f"{n:7d} × {layer}")
            it.setData(Qt.UserRole, layer)
            # 已在桶里的不在左边显示
            if self._in_any_bucket(layer):
                continue
            # 着色
            if not layer or layer == "(空/默认)":
                it.setForeground(Qt.gray)
            elif _is_building_bg_layer(layer):
                it.setForeground(Qt.darkRed)
            else:
                it.setForeground(Qt.darkBlue)
            self.left_list.addItem(it)
        # 同时刷新所有桶
        for key, lw in self.bucket_lists.items():
            lw.clear()
            for layer in self._layer_rules.get(key, []):
                it = QListWidgetItem(layer)
                lw.addItem(it)

    def _in_any_bucket(self, layer: str) -> bool:
        for kws in self._layer_rules.values():
            if layer in kws:
                return True
        return False

    def _on_double_click(self, item: QListWidgetItem):
        """双击左侧图层 → 默认归入「设备」桶"""
        layer = item.data(Qt.UserRole)
        if self._add_to_bucket("equipment", layer):
            self.left_list.takeItem(self.left_list.row(item))

    def _move_to_left(self, bucket_key: str):
        """从桶里移出（放回左侧）"""
        lw = self.bucket_lists[bucket_key]
        for item in list(lw.selectedItems()):
            layer = item.text()
            self._layer_rules[bucket_key] = [l for l in self._layer_rules[bucket_key] if l != layer]
        self._refresh_left()

    def _add_to_bucket(self, key: str, layer: str) -> bool:
        if layer in self._layer_rules.get(key, []):
            return False
        if self._in_any_bucket(layer):
            return False
        self._layer_rules.setdefault(key, []).append(layer)
        return True

    def _batch_move_to(self, key: str):
        kw = self.kw_edit.text().strip()
        if not kw:
            QMessageBox.information(self, "提示", "请先输入关键词")
            return
        upper_kw = kw.upper()
        n = 0
        for i in range(self.left_list.count()):
            it = self.left_list.item(i)
            layer = it.data(Qt.UserRole) or ""
            if upper_kw in layer.upper():
                if self._add_to_bucket(key, layer):
                    n += 1
        if n:
            self._refresh_left()
            QMessageBox.information(self, "完成", f"已把 {n} 个含「{kw}」的图层归入「{key}」桶")
        else:
            QMessageBox.information(self, "提示", f"未找到含「{kw}」且未分类的图层")

    def _smart_recommend_skip(self):
        """智能推荐：把所有「建筑背景」图层一键归入「跳过」桶"""
        rows = db.summarize_layers(self._project_id)
        n = 0
        for r in rows:
            layer = r["layer_name"]
            if not layer or _is_building_bg_layer(layer):
                if self._add_to_bucket("skip", layer):
                    n += 1
        if n:
            self._refresh_left()
        QMessageBox.information(self, "智能推荐",
            f"已归入「跳过」桶 {n} 个图层（含空图层和建筑背景关键词）。"
            "剩余「机电子件」请你按实际需要逐个归类。")

    def _auto_classify_all(self):
        """一键全量归类所有未分类图层（v3 任务二十九后续）。

        启发式规则（按顺序匹配，先命中先归类）：
        1) 建筑背景关键词（classify._is_building_bg_layer） → skip
        2) 设备关键词（block_rules.device_type） → equipment
        3) 规格关键词（block_rules.spec_keywords） → equipment
        4) 设备层名模式（_DEVICE_LAYER_HINT：line / cable / wire / kanal / 桥架 / 管道 / conduit） → linear
        5) 面积层名模式（HATCH / 风管 / DUCT / 面积） → area
        6) 乱码图层（reader.is_garbled_layer_name） → skip
        7) 仍剩 → skip（安全默认，避免被错误归到 equipment/linear）
        """
        # 重新加载块规则（用户可能改了设备关键词）
        block_rules = db.get_project_config(self._project_id).get("block_rules", {})
        device_kws = [k.upper() for k in block_rules.get("device_type", []) if k]
        spec_kws = [k.upper() for k in block_rules.get("spec_keywords", []) if k]
        skip_kws = [k.upper() for k in block_rules.get("skip", []) if k]

        from app.cad.reader import is_garbled_layer_name

        # 启发式关键字（与 _is_building_bg_layer 互补，覆盖更多）
        line_hints = ["LINE", "WIRE", "KABLO", "KANAL", "CONDUIT", "TRAY",
                      "桥架", "线槽", "管道", "导线", "CABLE"]
        area_hints = ["HATCH", "DUCT", "AHU", "PIPE", "风管", "水管", "防火分区"]
        equip_hints = ["LAMP", "CAMERA", "DETECTOR", "OUTLET", "SWITCH", "PANEL",
                       "SPEAKER", "SENSOR", "VALVE", "灯具", "探头", "插座", "开关",
                       "喇叭", "配电箱", "UPS", "AP", "ACCESS"]

        rows = db.summarize_layers(self._project_id)
        n_total = 0
        skipped_already = 0
        from collections import Counter
        by_bucket = Counter()
        for r in rows:
            n_total += 1
            layer = r["layer_name"]
            if not layer:
                if self._add_to_bucket("skip", ""):
                    by_bucket["skip"] += 1
                continue
            if self._in_any_bucket(layer):
                skipped_already += 1
                continue

            upper = layer.upper()
            target = None

            # 1) 用户显式 skip 关键词优先
            if any(kw in upper for kw in skip_kws):
                target = "skip"
            # 2) 乱码图层
            elif is_garbled_layer_name(layer):
                target = "skip"
            # 3) 建筑背景
            elif _is_building_bg_layer(layer):
                target = "skip"
            # 4) 设备关键词 / 块名包含设备提示词
            elif any(kw in upper for kw in device_kws) or any(kw in upper for kw in equip_hints):
                target = "equipment"
            elif any(kw in upper for kw in spec_kws):
                target = "equipment"
            elif any(kw in upper for kw in line_hints):
                target = "linear"
            elif any(kw in upper for kw in area_hints):
                target = "area"
            else:
                # 默认安全归 skip（避免把不认识的归到 equipment 产生假阳性）
                target = "skip"

            if self._add_to_bucket(target, layer):
                by_bucket[target] += 1

        self._refresh_left()
        bucket_names = {"equipment": "设备", "linear": "导线", "area": "面积", "skip": "跳过"}
        QMessageBox.information(
            self, "一键全量归类完成",
            f"共扫描 {n_total} 个图层，已归类 {sum(by_bucket.values())} 个（{skipped_already} 之前已分类）。\n\n"
            + "\n".join(f"  • {bucket_names.get(k, k)}: {v} 个" for k, v in by_bucket.items())
            + "\n\n提示：「保守归 skip」意味着未识别图层默认跳过——避免把机电子件混入设备桶产生假阳性。"
              "请人工检查「跳过」桶的「乱码」与「未识别」项，按需移出。")

    def get_rules(self) -> dict:
        return self._layer_rules


class BlockRulesTab(QWidget):
    """Tab 2：设备筛选规则（按 block_name 关键词）"""

    def __init__(self, project_id: int, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._block_rules = db.get_project_config(project_id)["block_rules"]
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        tip = QLabel("按块名关键词归类（classifier 与 device_type 推断的依据）。"
                     "支持多关键词，逗号分隔。")
        tip.setStyleSheet(f"color:{T.TEXT_HINT}; padding:4px;")
        tip.setWordWrap(True)
        root.addWidget(tip)

        form = QFormLayout()
        self.edit_dev = QLineEdit()
        self.edit_dev.setPlaceholderText("如 camera, detector, lamp, outlet, switch, panel, ap, speaker, sensor, valve")
        form.addRow("设备类型关键词（device_type）:", self.edit_dev)

        self.edit_spec = QLineEdit()
        self.edit_spec.setPlaceholderText("如 4MP, 1080P, 100mm, DN100, 30W, IP65")
        form.addRow("规格关键词（spec_keywords）:", self.edit_spec)

        self.edit_skip = QLineEdit()
        self.edit_skip.setPlaceholderText("如 *U, XREF, ANNO, GARBAGE")
        form.addRow("跳过关键词（skip）:", self.edit_skip)
        root.addLayout(form)

        btn_apply = QPushButton("应用（保存时生效）")
        btn_apply.clicked.connect(self._on_apply)
        root.addWidget(btn_apply)
        root.addStretch(1)

    def _refresh(self):
        self.edit_dev.setText(", ".join(self._block_rules.get("device_type", [])))
        self.edit_spec.setText(", ".join(self._block_rules.get("spec_keywords", [])))
        self.edit_skip.setText(", ".join(self._block_rules.get("skip", [])))

    def _parse_kw(self, text: str) -> list:
        return [t.strip() for t in text.split(",") if t.strip()]

    def _on_apply(self):
        self._block_rules = {
            "device_type": self._parse_kw(self.edit_dev.text()),
            "spec_keywords": self._parse_kw(self.edit_spec.text()),
            "skip": self._parse_kw(self.edit_skip.text()),
        }
        QMessageBox.information(self, "已应用", "点底部「保存」写入数据库")

    def get_rules(self) -> dict:
        return self._block_rules


class SourcesTab(QWidget):
    """Tab 3：图纸 / BOQ 来源（只读回溯）"""

    def __init__(self, project_id: int, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        # 图纸
        root.addWidget(QLabel("图纸列表（点击列头排序）："))
        self.sheet_table = QTableWidget()
        self.sheet_table.setColumnCount(5)
        self.sheet_table.setHorizontalHeaderLabels(["ID", "文件名", "源路径", "DXF 路径", "实体数"])
        self.sheet_table.setAlternatingRowColors(True)
        self.sheet_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sheet_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.sheet_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sheet_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        root.addWidget(self.sheet_table, 1)
        # BOQ
        root.addWidget(QLabel("BOQ 来源："))
        self.boq_edit = QTextEdit()
        self.boq_edit.setReadOnly(True)
        self.boq_edit.setMaximumHeight(80)
        root.addWidget(self.boq_edit)

    def _refresh(self):
        sheets = db.get_sheets(self._project_id)
        self.sheet_table.setRowCount(len(sheets))
        for i, s in enumerate(sheets):
            ent_n = db.get_conn().execute(
                "SELECT COUNT(*) FROM entity WHERE sheet_id=?", (s.id,)).fetchone()[0]
            self.sheet_table.setItem(i, 0, QTableWidgetItem(str(s.id)))
            self.sheet_table.setItem(i, 1, QTableWidgetItem(s.filename))
            self.sheet_table.setItem(i, 2, QTableWidgetItem(s.src_path or ""))
            self.sheet_table.setItem(i, 3, QTableWidgetItem(s.dxf_path or ""))
            self.sheet_table.setItem(i, 4, QTableWidgetItem(str(ent_n)))
        # BOQ
        proj = db.get_project(self._project_id)
        boq_n = len(db.get_boq_items(self._project_id))
        eo_n = len(db.get_engineering_objects(self._project_id))
        cand_n = sum(1 for _ in db.get_candidates(self._project_id))
        accepted_n = sum(1 for c in db.get_candidates(self._project_id) if c.status == "ACCEPTED")
        legend_n = len(db.get_block_legend(self._project_id))
        txt = (
            f"项目：{proj.name if proj else '?'}\n"
            f"BOQ 路径：{proj.boq_path if proj else ''}\n"
            f"BOQ 条目：{boq_n}\n"
            f"工程对象：{eo_n}\n"
            f"候选数：{cand_n}（ACCEPTED {accepted_n}）\n"
            f"图例标定：{legend_n}"
        )
        self.boq_edit.setPlainText(txt)


class MetaTab(QWidget):
    """Tab 4：项目基础信息（可编辑）"""

    def __init__(self, project_id: int, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.edit_type = QLineEdit()
        form.addRow("类型 (type):", self.edit_type)
        self.edit_region = QLineEdit()
        form.addRow("区域 (region):", self.edit_region)
        self.edit_specialty = QLineEdit()
        form.addRow("专业 (specialty):", self.edit_specialty)
        self.edit_notes = QTextEdit()
        self.edit_notes.setMaximumHeight(120)
        form.addRow("备注 (notes):", self.edit_notes)
        root.addLayout(form)
        root.addStretch(1)

    def _refresh(self):
        m = db.get_project_config(self._project_id)["meta"]
        self.edit_type.setText(m.get("type", ""))
        self.edit_region.setText(m.get("region", ""))
        self.edit_specialty.setText(m.get("specialty", ""))
        self.edit_notes.setPlainText(m.get("notes", ""))

    def get_meta(self) -> dict:
        return {
            "type": self.edit_type.text().strip(),
            "region": self.edit_region.text().strip(),
            "specialty": self.edit_specialty.text().strip(),
            "notes": self.edit_notes.toPlainText().strip(),
        }


class ProjectSettingsDialog(QDialog):
    """项目设置主弹窗：4 个标签页（图层规则/设备规则/来源/元信息）。"""

    # 选中样式：由 theme.py 统一生成（替换原 _LIST_QSS 硬编码）
    _LIST_QSS = __import__('app.ui.theme', fromlist=['generate_item_selected_qss']).generate_item_selected_qss()

    def __init__(self, project_id: int, parent=None):
        super().__init__(parent)
        self._project_id = project_id
        proj = db.get_project(project_id)
        self.setWindowTitle(f"项目设置 — {proj.name if proj else project_id}")
        self.setStyleSheet(T.MAIN_QSS + self._LIST_QSS)   # 全局样式 + 列表选中样式
        self._build_ui()
        # 屏幕适配：clamp 尺寸到可用区域 + 居中
        from .ui_utils import fit_dialog_to_screen
        fit_dialog_to_screen(self, (1200, 800), "config")

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tab_layer = LayerRulesTab(self._project_id)
        self.tab_block = BlockRulesTab(self._project_id)
        self.tab_source = SourcesTab(self._project_id)
        self.tabs.addTab(self.tab_layer, "① 图层筛选规则")
        self.tabs.addTab(self.tab_block, "② 设备筛选规则")
        self.tabs.addTab(self.tab_source, "③ 图纸/BOQ 来源")
        # 注意：项目基础信息（类型/区域/专业/备注）已移至右侧属性面板
        root.addWidget(self.tabs, 1)

        # 底部按钮（统一层级：primary=主操作 / 其余 secondary）
        btn_row = QHBoxLayout()
        btn_import = QPushButton("导入 JSON")
        btn_import.clicked.connect(self._on_import)
        btn_row.addWidget(btn_import)
        btn_export = QPushButton("导出 JSON")
        btn_export.clicked.connect(self._on_export)
        btn_row.addWidget(btn_export)
        btn_row.addStretch(1)
        btn_reset = QPushButton("恢复默认")
        btn_reset.clicked.connect(self._on_reset)
        btn_row.addWidget(btn_reset)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_ok = QPushButton("保存到项目")
        btn_ok.setObjectName("primaryBtn")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_save)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    def _on_save(self):
        # 触发 block tab 的应用
        if hasattr(self.tab_block, "_on_apply"):
            self.tab_block._on_apply()
        layer_rules = self.tab_layer.get_rules()
        block_rules = self.tab_block.get_rules()
        # 项目基础信息已移至右侧属性面板，此处只保存规则
        db.set_project_config(self._project_id,
                              layer_rules=layer_rules,
                              block_rules=block_rules)
        QMessageBox.information(self, "已保存",
            f"已写入项目配置。\n"
            f"  图层规则: {sum(len(v) for v in layer_rules.values())} 个\n"
            f"  设备规则: {sum(len(v) for v in block_rules.values())} 个\n"
            f"（项目基础信息请在右侧「项目属性」标签页中编辑）")
        self.accept()

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入项目配置", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            db.import_project_config(self._project_id, data)
            QMessageBox.information(self, "已导入", "配置已合并（部分字段可能未刷新，重打开弹窗查看）。")
            # 刷新各 tab
            self.tab_layer = LayerRulesTab(self._project_id)
            self.tab_layer._layer_rules = data.get("layer_rules", {})
            self.tab_block = BlockRulesTab(self._project_id)
            self.tab_block._block_rules = data.get("block_rules", {})
            self.tab_meta = MetaTab(self._project_id)
            # 不重建 tab（避免焦点丢失），仅同步显示
            for i in range(self.tabs.count()):
                if i == 0:
                    self.tab_layer._refresh()
                elif i == 1:
                    self.tab_block._refresh()
                elif i == 3:
                    self.tab_meta._refresh()
        except Exception as e:
            QMessageBox.warning(self, "导入失败", str(e))

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出项目配置",
                                                f"project_{self._project_id}_config.json",
                                                "JSON (*.json)")
        if not path:
            return
        try:
            data = db.export_project_config(self._project_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "已导出", f"已保存到：\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _on_reset(self):
        if QMessageBox.question(self, "恢复默认", "确定清空该项目所有自定义规则？") != QMessageBox.Yes:
            return
        db.set_project_config(self._project_id,
                              layer_rules={"equipment": [], "linear": [], "area": [], "skip": []},
                              block_rules={"device_type": [], "spec_keywords": [], "skip": []},
                              meta={"type": "", "region": "", "specialty": "", "notes": ""})
        QMessageBox.information(self, "已重置", "请重新打开本弹窗查看效果。")
        self.reject()
