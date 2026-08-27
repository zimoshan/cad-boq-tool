"""绑定工作台（V2 任务二十六）：人工复核 AI/规则候选 → 正式绑定。

组合现有能力，不重做 UI：
- 工程对象列表：app/engineering（提取/分类）
- 审核队列：app/binding（候选生成/确认/拒绝/批量确认）
- 来源定位：复用画布 flash_entities/zoom_to_entities（经主窗口转发）

工作流：选择 CAD 对象 → 显示属性/AI 推荐 → 确认/选择 BOQ → 保存 Binding → 重新计算。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QPushButton, QCheckBox, QSplitter, QAbstractItemView,
                               QLineEdit, QTableView)

from .. import db
from ..binding import (generate_candidates, confirm_binding, reject_binding,
                       auto_confirm_rule_candidates)
from ..engineering import extract_and_store_engineering_objects
from . import theme as T

TYPE_LABELS = {"equipment": "设备", "linear": "线性", "area": "面积"}
RULE_LABELS = {"count": "计数", "length": "长度", "area": "面积"}
METHOD_LABELS = {"RULE": "规则", "EMBEDDING": "语义", "LLM": "AI", "MANUAL": "人工"}

OBJ_COLS = ["实体数", "类型", "块名/图层", "系统", "规格", "规则", "置信", "状态", "所在图纸"]
QUEUE_COLS = ["候选#", "BOQ 编号", "BOQ 描述", "方法", "置信", "理由", "操作"]


class _ObjectGroupModel(QAbstractTableModel):
    """工程对象分组表的虚拟模型（P2-1：QTableWidget → QAbstractTableModel）。

    行数据按需取：QTableView 只对可见行调用 data()，过滤/刷新不再创建
    上万 QTableWidgetItem。列0的 UserRole 携带分组 key（选中行复用旧逻辑）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[tuple] = []       # [(key, g)]，g 为分组 dict
        self.sheets_map: dict = {}
        self.cand_summary: dict = {}

    def set_rows(self, rows: list, sheets_map: dict, cand_summary: dict) -> None:
        self.beginResetModel()
        self._rows = rows
        self.sheets_map = sheets_map or {}
        self.cand_summary = cand_summary or {}
        self.endResetModel()

    # ---- QAbstractTableModel 接口 ----
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(OBJ_COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return OBJ_COLS[section] if 0 <= section < len(OBJ_COLS) else None
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        key, g = self._rows[index.row()]
        col = index.column()
        if role == Qt.UserRole and col == 0:
            return key
        if role == Qt.DisplayRole:
            return self._cell_text(g, col)
        return None

    # ---- 单元格格式化（与旧 _render_objects 一致） ----
    def _cell_text(self, g: dict, col: int) -> str:
        if col == 0:
            return str(len(g["all_entity_ids"]))
        if col == 1:
            return TYPE_LABELS.get(g["object_type"], g["object_type"])
        if col == 2:
            return g["block_name"] or g["layer_name"]
        if col == 3:
            return g["system"] or "-"
        if col == 4:
            return g["specification"] or "-"
        if col == 5:
            return RULE_LABELS.get(g["quantity_rule"], g["quantity_rule"])
        if col == 6:
            return f"{g['confidence']:.0%}"
        if col == 7:
            return self._obj_state(g)
        # col 8：所在图纸
        names = [self.sheets_map.get(sid, f"#{sid}") for sid in g["sheets"]]
        return ", ".join(names) if names else "-"

    def _obj_state(self, g: dict) -> str:
        eo = g["representative"]
        accepted = self.cand_summary.get((eo.id, "ACCEPTED"), 0)
        if accepted:
            return "✓ 已绑定"
        n = self.cand_summary.get((eo.id, "PENDING"), 0)
        if n:
            return f"待审核({n})"
        if self.cand_summary.get((eo.id, "REJECTED"), 0):
            return "已拒绝"
        return "未匹配"


class _BindingWorker(QThread):
    """后台生成候选（LLM 可能慢，不阻塞 UI）"""
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, project_id: int, use_llm: bool, sheet_id=None, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.use_llm = use_llm
        self.sheet_id = sheet_id

    def run(self):
        try:
            res = generate_candidates(self.project_id, sheet_id=self.sheet_id,
                                      use_llm=self.use_llm)
            self.finished_ok.emit(res)
        except Exception as e:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class _ClassifyWorker(QThread):
    """后台 LLM 语义补充分类（T4 第3层接线：低置信对象喂给大模型）"""
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, project_id: int, limit: int = 100, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.limit = limit

    def run(self):
        try:
            from ..engineering.llm_classify import llm_classify_uncertain
            res = llm_classify_uncertain(self.project_id, limit=self.limit)
            self.finished_ok.emit(res)
        except Exception as e:  # noqa: BLE001
            import traceback
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class BindingWorkbench(QWidget):
    locateRequested = Signal(int, str)         # (sheet_id, block_name_or_layer_name)
    statusMessage = Signal(str)
    bindingChanged = Signal()               # 确认/拒绝后主窗口刷新计量口径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_id = None
        self._objects = []                  # list[EngineeringObject]
        self._queue = []                    # list[BindingCandidate]
        self._cand_summary: dict = {}       # {(eo_id, status): count}，_render_objects/_update_status 刷新
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # 工具栏
        bar = QHBoxLayout()
        self.btn_extract = QPushButton("提取工程对象")
        self.btn_extract.clicked.connect(self._on_extract)
        self.btn_generate = QPushButton("生成候选")
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_generate.setToolTip(
            "分层候选：历史确认 → 规则 → 语义召回 → LLM 精排。\n"
            "历史确认/规则强命中的对象不消耗 LLM；LLM 后端不可用时自动降级为纯本地层。")
        self.btn_auto = QPushButton("批量确认(规则满置信)")
        self.btn_auto.clicked.connect(self._on_auto_confirm)
        self.btn_llm_classify = QPushButton("LLM 补充分类")
        self.btn_llm_classify.setToolTip("对规则/知识库未命中的低置信功能对象调用大模型补充分类（需配置 LLM）")
        self.btn_llm_classify.clicked.connect(self._on_llm_classify)
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.clicked.connect(lambda: self.load_project(self._project_id))
        for w in (self.btn_extract, self.btn_generate,
                  self.btn_auto, self.btn_llm_classify, self.btn_refresh):
            bar.addWidget(w)
        bar.addStretch(1)
        root.addLayout(bar)

        # 过滤行（大批量对象时定位用）
        flt = QHBoxLayout()
        flt.addWidget(QLabel("过滤:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("块名 / 图层 / 系统 / 图纸名…")
        self.search_box.textChanged.connect(lambda _t: self._render_objects())
        flt.addWidget(self.search_box, 1)
        self.chk_only_mep = QCheckBox("只看机电")
        self.chk_only_mep.setChecked(True)
        self.chk_only_mep.setToolTip(
            "默认勾选：过滤建筑/装饰背景（FURN/DTL/STAIR/DOOR/WALL 等），只显示真正的设备/管线/区域。"
            "取消勾选可显示全部（含建筑背景）。")
        self.chk_only_mep.toggled.connect(lambda _v: self._render_objects())
        flt.addWidget(self.chk_only_mep)
        self.chk_unmatched = QCheckBox("只看未匹配")
        self.chk_unmatched.setToolTip("只显示尚无 ACCEPTED 候选（未绑定）的工程对象")
        self.chk_unmatched.toggled.connect(lambda _v: self._render_objects())
        flt.addWidget(self.chk_unmatched)
        root.addLayout(flt)

        # 上下分栏：工程对象 / 审核队列
        split = QSplitter(Qt.Vertical)

        top = QWidget()
        tv = QVBoxLayout(top)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.addWidget(QLabel("工程对象（点击行 → 下方审核其候选）"))
        self._obj_model = _ObjectGroupModel(self)
        self.obj_table = QTableView()
        self.obj_table.setModel(self._obj_model)
        self.obj_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.obj_table.setAlternatingRowColors(True)
        self.obj_table.verticalHeader().setVisible(False)
        self.obj_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.obj_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.obj_table.selectionModel().selectionChanged.connect(self._on_obj_selected)
        tv.addWidget(self.obj_table)
        split.addWidget(top)

        bottom = QWidget()
        bv = QVBoxLayout(bottom)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.addWidget(QLabel("审核队列（AI/规则候选，确认后才写入正式映射）"))
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(len(QUEUE_COLS))
        self.queue_table.setHorizontalHeaderLabels(QUEUE_COLS)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        bv.addWidget(self.queue_table, 1)

        ops = QHBoxLayout()
        self.btn_confirm = QPushButton("确认选中")
        self.btn_confirm.clicked.connect(self._on_confirm)
        self.btn_reject = QPushButton("拒绝选中")
        self.btn_reject.clicked.connect(self._on_reject)
        self.btn_locate = QPushButton("查看来源→定位")
        self.btn_locate.clicked.connect(self._on_locate)
        for w in (self.btn_confirm, self.btn_reject, self.btn_locate):
            ops.addWidget(w)
        ops.addStretch(1)
        self.status_label = QLabel("未选择项目")
        self.status_label.setStyleSheet(f"color:{T.TEXT_HINT};font-size:{T.FONT_SIZE_CAPTION}px;")
        ops.addWidget(self.status_label)
        bv.addLayout(ops)
        split.addWidget(bottom)

        split.setSizes([260, 380])
        root.addWidget(split, 1)

    # ---------- 数据加载 ----------
    def refresh_enabled(self, has_project: bool | None = None):
        """P1-12：按钮与上下文对齐 — 无项目时禁用全部操作按钮。

        has_project 显式传入以覆盖内部 _project_id（主窗口可能已切项目
        但本工作台尚未 load_project）；None 则用内部状态。
        """
        ok = self._project_id is not None if has_project is None else has_project
        for bt in (self.btn_extract, self.btn_generate, self.btn_auto,
                   self.btn_llm_classify, self.btn_refresh,
                   self.btn_confirm, self.btn_reject, self.btn_locate):
            bt.setEnabled(ok)

    def load_project(self, project_id):
        self._project_id = project_id
        self._objects = []
        self._queue = []
        self._sheets_map = {s.id: s.filename for s in db.get_sheets(project_id or 0)}
        self.refresh_enabled()
        if project_id is None:
            self._render_objects()
            self._render_queue()
            self.status_label.setText("未选择项目")
            return
        self._objects = db.get_engineering_objects(project_id)
        # 大批量项目（>2000 候选）会拖死 QTableWidget；批量确认页才是主入口
        # 默认 1000 行足够 review，状态栏显示真实总数
        self._queue = db.get_pending_candidates(project_id, limit=1000)
        self._render_objects()
        self._render_queue()
        self._update_status()

    def _render_objects(self):
        kw = self.search_box.text().strip().lower() if hasattr(self, "search_box") else ""
        only_mep = self.chk_only_mep.isChecked() if hasattr(self, "chk_only_mep") else False
        only_unmatched = self.chk_unmatched.isChecked() if hasattr(self, "chk_unmatched") else False
        # 批量预取候选状态（性能优化：替代每行 N+1 查询）
        self._cand_summary = db.candidate_status_summary(self._project_id or 0) \
            if self._project_id else {}
        objs = self._objects
        if kw:
            objs = [e for e in objs
                    if kw in f"{e.block_name} {e.layer_name} {e.system} "
                       f"{self._sheets_map.get(e.sheet_id, '')}".lower()]
        if only_mep:
            objs = [e for e in objs if e.discipline and e.discipline != "BUILDING_BG"]
        # 只看未匹配：过滤掉已有 ACCEPTED 候选的对象
        if only_unmatched:
            accepted = {eid for (eid, st) in self._cand_summary if st == "ACCEPTED"}
            objs = [e for e in objs if e.id not in accepted]

        # 按 (block_name/layer_name, system, object_type) 同名同层同系统合并
        from collections import OrderedDict
        groups: OrderedDict[tuple, dict] = OrderedDict()
        for eo in objs:
            key = (eo.block_name or eo.layer_name, eo.system or "", eo.object_type)
            if key not in groups:
                groups[key] = {
                    "block_name": eo.block_name,
                    "layer_name": eo.layer_name,
                    "system": eo.system,
                    "object_type": eo.object_type,
                    "specification": eo.specification,
                    "quantity_rule": eo.quantity_rule,
                    "confidence": eo.confidence,
                    "sheets": {},       # {sheet_id: entity_ids}
                    "all_entity_ids": [],
                    "representative": eo,  # 保留一个用于状态查询
                }
            g = groups[key]
            g["sheets"][eo.sheet_id] = eo.entity_ids
            g["all_entity_ids"].extend(eo.entity_ids)
            # 取最高置信度
            if eo.confidence > g["confidence"]:
                g["confidence"] = eo.confidence
                g["specification"] = eo.specification or g["specification"]
                g["representative"] = eo

        self._grouped = groups  # 缓存供 _on_locate 使用
        # P2-1：虚拟模型一次性替换整表（不再逐格创建 QTableWidgetItem）
        self._obj_model.set_rows(list(groups.items()), self._sheets_map, self._cand_summary)

    def _render_queue(self, filter_eoid=None):
        self.queue_table.setRowCount(0)
        items = {it.id: it for it in db.get_boq_items(self._project_id or 0)}
        rows = [c for c in self._queue
                if filter_eoid is None
                or (isinstance(filter_eoid, set) and c.engineering_object_id in filter_eoid)
                or (not isinstance(filter_eoid, set) and c.engineering_object_id == filter_eoid)]
        # T7 主动学习难例挖掘：低置信优先（升序），便于优先复核难例
        rows.sort(key=lambda c: (c.confidence, c.id))
        self.queue_table.setRowCount(len(rows))
        for i, c in enumerate(rows):
            bi = items.get(c.boq_item_id)
            vals = [
                str(c.id),
                bi.code if bi else str(c.boq_item_id),
                bi.description if bi else "-",
                METHOD_LABELS.get(c.method, c.method),
                f"{c.confidence:.0%}",
                c.reason or "",
            ]
            # 难例高亮：置信 < 0.6 标橙，< 0.4 标红
            bg = None
            if c.confidence < 0.4:
                bg = T.CONFIDENCE_LOW
            elif c.confidence < 0.6:
                bg = T.CONFIDENCE_MID
            for col, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setData(Qt.UserRole, c.id)
                if bg:
                    it.setBackground(bg)
                self.queue_table.setItem(i, col, it)
            # P1-11 审批行内确认/拒绝按钮：免「先选中再点下方按钮」两步
            self.queue_table.setCellWidget(i, len(vals), self._make_inline_ops(c.id))

    def _update_status(self):
        if self._project_id is None:
            self.status_label.setText("未选择项目")
            return
        summary = db.candidate_status_summary(self._project_id)
        accepted_ids = {eid for (eid, st) in summary if st == "ACCEPTED"}
        bound = sum(1 for eo in self._objects if eo.id in accepted_ids)
        self._cand_summary = summary
        all_pending = db.count_candidates(self._project_id, status="PENDING")
        rendered = len(self._queue)
        only_mep = self.chk_only_mep.isChecked() if hasattr(self, "chk_only_mep") else False
        extra_obj = "（已过滤建筑背景）" if only_mep else "（含建筑底图）"
        pending_extra = ""
        if rendered < all_pending:
            pending_extra = f"（UI 仅显示前 {rendered} 条，用「批量确认」处理全部）"
        self.status_label.setText(
            f"工程对象 {len(self._objects)}{extra_obj} · 已绑定 {bound} · "
            f"待审核 {all_pending}{pending_extra}")

    # ---------- 工具栏动作 ----------
    def _on_extract(self):
        if self._project_id is None:
            self.statusMessage.emit("请先新建/选择项目")
            return
        sheets = db.get_sheets(self._project_id)
        total = 0
        for s in sheets:
            res = extract_and_store_engineering_objects(self._project_id, s.id)
            total += res["created"]
        self.load_project(self._project_id)
        self.statusMessage.emit(f"已提取 {total} 个工程对象（{len(sheets)} 张图纸）")

    def _on_generate(self):
        if self._project_id is None:
            self.statusMessage.emit("请先新建/选择项目")
            return
        if not db.get_engineering_objects(self._project_id):
            self.statusMessage.emit("请先「提取工程对象」")
            return
        self.btn_generate.setEnabled(False)
        self.statusMessage.emit("生成候选中…（历史→规则→语义→LLM 精排，规则强命中不耗 LLM）")
        self._worker = _BindingWorker(self._project_id, True, parent=self)
        self._worker.finished_ok.connect(self._on_generate_done)
        self._worker.failed.connect(self._on_generate_failed)
        self._worker.start()

    def _on_generate_done(self, res):
        self.btn_generate.setEnabled(True)
        self.load_project(self._project_id)
        st = res["stats"]
        llm_note = ""
        if st.get("llm_unavailable"):
            llm_note = f" / ⚠ LLM 不可用已降级（{st['llm_unavailable']} 个对象仅用本地层）"
        self.statusMessage.emit(
            f"候选生成完成：规则 {st['rule']} / 语义 {st['embedding']} / AI {st['llm']} / "
            f"已绑定跳过 {st['skipped_bound']} / 未匹配 {st['no_match']}{llm_note}")

    def _on_generate_failed(self, err: str):
        self.btn_generate.setEnabled(True)
        self.statusMessage.emit(f"候选生成失败：{err[:120]}")

    def _on_auto_confirm(self):
        if self._project_id is None:
            return
        res = auto_confirm_rule_candidates(self._project_id)
        self.load_project(self._project_id)
        self.bindingChanged.emit()
        self.statusMessage.emit(f"批量确认完成：{res['auto_confirmed']} 条（规则满置信）")

    def _on_llm_classify(self):
        """LLM 语义补充分类（T4 第3层接线）：后台跑低置信对象分类，不阻塞 UI。"""
        if self._project_id is None:
            self.statusMessage.emit("请先新建/选择项目")
            return
        if not db.get_engineering_objects(self._project_id):
            self.statusMessage.emit("请先「提取工程对象」")
            return
        self.btn_llm_classify.setEnabled(False)
        self.statusMessage.emit("LLM 补充分类中…（可稍后查看结果）")
        self._class_worker = _ClassifyWorker(self._project_id, parent=self)
        self._class_worker.finished_ok.connect(self._on_llm_classify_done)
        self._class_worker.failed.connect(self._on_llm_classify_failed)
        self._class_worker.start()

    def _on_llm_classify_done(self, res):
        self.btn_llm_classify.setEnabled(True)
        self.load_project(self._project_id)
        self.statusMessage.emit(
            f"LLM 补充分类完成：成功 {res.get('classified', 0)} / 失败 "
            f"{res.get('failed', 0)} / 跳过 {res.get('skipped', 0)}"
            f"{'（另外 ' + str(res.get('deferred', 0)) + ' 个低置信对象待下次）' if res.get('deferred') else ''}")

    def _on_llm_classify_failed(self, err: str):
        self.btn_llm_classify.setEnabled(True)
        self.statusMessage.emit(f"LLM 补充分类失败：{err[:120]}")

    # ---------- 行操作 ----------
    def _selected_group_key(self):
        """当前对象表选中行的分组 key（模型 UserRole，兼容 QTableView）"""
        idx = self.obj_table.currentIndex()
        if not idx.isValid():
            return None
        return idx.siblingAtColumn(0).data(Qt.UserRole)

    def _on_obj_selected(self):
        key = self._selected_group_key()
        if key is None:
            return
        # 过滤审核队列：只显示该分组下所有 EO 的候选
        grouped = getattr(self, "_grouped", {})
        g = grouped.get(key)
        if g is None:
            return
        eids_in_group = {eo.id for sheet_eids in g["sheets"].values()
                         for eo in [r for r in self._objects
                                    if r.sheet_id in g["sheets"]
                                    and (r.block_name or r.layer_name) == g["block_name"]
                                    and (r.system or "") == g["system"]
                                    and r.object_type == g["object_type"]]}
        self._render_queue(filter_eoid=eids_in_group if eids_in_group else None)

    def _selected_candidate(self):
        row = self.queue_table.currentRow()
        if row < 0:
            return None
        it = self.queue_table.item(row, 0)
        cid = int(it.data(Qt.UserRole))
        return db.get_candidate(cid)

    def _make_inline_ops(self, candidate_id: int) -> QWidget:
        """P1-11：候选行内直接「确认 / 拒绝」，免去选中行再点下方按钮。"""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)
        ok = QPushButton("✓ 确认")
        ok.setObjectName("primaryBtn")
        ok.setToolTip("确认该候选为正式映射")
        ok.clicked.connect(lambda _=False, cid=candidate_id: self._do_confirm(cid))
        no = QPushButton("✗ 拒绝")
        no.setObjectName("dangerBtn")
        no.setToolTip("拒绝该候选，不再推荐此组合")
        no.clicked.connect(lambda _=False, cid=candidate_id: self._do_reject(cid))
        lay.addWidget(ok)
        lay.addWidget(no)
        return w

    def _do_confirm(self, candidate_id: int):
        try:
            res = confirm_binding(self._project_id, candidate_id)
        except Exception as e:  # noqa: BLE001
            self.statusMessage.emit(f"确认失败：{e}")
            return
        self.load_project(self._project_id)
        self.bindingChanged.emit()
        self.statusMessage.emit(
            f"已确认 BOQ#{res['boq_item_id']}（{res['mapping_mode']} 映射），"
            f"数量 {res['qty']:g}")

    def _on_confirm(self):
        c = self._selected_candidate()
        if c is None:
            self.statusMessage.emit("请先在审核队列选中一条候选")
            return
        self._do_confirm(c.id)

    def _do_reject(self, candidate_id: int):
        reject_binding(candidate_id, "人工拒绝")
        self.load_project(self._project_id)
        self.bindingChanged.emit()
        self.statusMessage.emit(f"已拒绝候选 #{candidate_id}，不再推荐该组合")

    def _on_reject(self):
        c = self._selected_candidate()
        if c is None:
            self.statusMessage.emit("请先在审核队列选中一条候选")
            return
        self._do_reject(c.id)

    def _on_locate(self):
        """定位当前选中对象/候选到画布（同图例标定效果，支持跨图纸）"""
        if self._project_id is None:
            return
        # 优先定位审核队列选中候选的工程对象
        c = self._selected_candidate()
        if c is not None:
            eo = db.get_engineering_object(c.engineering_object_id)
            if eo and eo.sheet_id:
                self.locateRequested.emit(eo.sheet_id, eo.block_name or eo.layer_name or "")
                self.statusMessage.emit(f"定位 {eo.block_name or eo.layer_name}")
                return
        # 否则定位对象表选中的分组
        key = self._selected_group_key()
        if key is None:
            self.statusMessage.emit("请先选中工程对象或候选")
            return
        grouped = getattr(self, "_grouped", {})
        g = grouped.get(key)
        if g is None:
            self.statusMessage.emit("未找到分组数据")
            return
        first_sheet_id = next(iter(g["sheets"]), None)
        if not first_sheet_id:
            self.statusMessage.emit("该对象无可定位实体（无溯源锚点）")
            return
        total = len(g["all_entity_ids"])
        sheet_count = len(g["sheets"])
        self.locateRequested.emit(first_sheet_id, g["block_name"] or g["layer_name"] or "")
        self.statusMessage.emit(
            f"定位 {g['block_name'] or g['layer_name']}："
            f"{total} 个实体（{sheet_count} 张图纸，当前定位到 {self._sheets_map.get(first_sheet_id, '')}）")
