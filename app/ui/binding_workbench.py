"""绑定工作台（V2 任务二十六 / v3 main.html 1:1）：人工复核 AI/规则候选 → 正式绑定。

组合现有能力，不重做数据层：
- 审核队列：app/binding（候选生成/确认/拒绝/批量确认）
- 来源定位：复用画布 flash_entities/zoom_to_entities（经主窗口转发）

v3 1:1（design/main.html #panel-bind）：
- 头部：标题/副标题 + info 图标 + 三段切换（待复核/已确认/已忽略，bg-slate-100 圆角容器）
- 琥珀条：「N 个 AI 候选需要复核」+ 青色「全部确认」链接（规则满置信批量确认）
- 卡片流：32px 类型徽标 + 标题 + 置信度徽标 + 块名/图层/图纸元信息 + 建议绑定 + 行内 定位/忽略/确认
- 底部：通栏深色按钮「将已选 N 个实体分配至 BOQ」（信号 assignRequested → 主窗口）

原工具栏（提取/生成候选/批量确认/LLM 分类/刷新）收敛为公开方法 run_*，
由顶栏「AI 算量▾」与「更多▾」调用——界面与原型一致、功能不丢。
确认/拒绝仍走 confirm_binding/reject_binding 单一数据源。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QFrame, QSizePolicy)

from .. import db
from ..binding import (generate_candidates, confirm_binding, reject_binding,
                       auto_confirm_rule_candidates)
from . import theme as T

TYPE_LABELS = {"equipment": "设备", "linear": "线性", "area": "面积"}
METHOD_LABELS = {"RULE": "规则", "EMBEDDING": "语义", "LLM": "AI", "MANUAL": "人工"}

# 卡片渲染上限：候选可能上千，全量建卡会拖慢 UI；超出部分提示用「全部确认」
CARD_RENDER_CAP = 200

# 类型徽标配色（原型：cyan-100 设备 / blue-50 线性 / violet-50 面积）
_TYPE_CHIP = {
    "equipment": ("设", "#CFFAFE", "#0E7490"),
    "linear": ("线", "#EFF6FF", "#2563EB"),
    "area": ("面", "#F5F3FF", "#7C3AED"),
}
_TYPE_CHIP_FALLBACK = ("对", "#F1F5F9", "#475569")


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


class _CandidateCard(QFrame):
    """单条候选卡片（原型 1:1）：

    [32px 类型徽标] [标题 …… 置信度徽标]
                    块名：… · 图层：… · 图纸：…
                    建议绑定：<b>…</b>   [定位][忽略][确认]
    ACCEPTED → emerald 单行「✓ 已确认并写入 BOQ · 数量已更新」；
    REJECTED → 灰色单行「该候选已忽略」+ 恢复待审。
    """

    def __init__(self, candidate, eo, boq_item, sheet_name: str, status: str,
                 on_confirm, on_reject, on_locate, on_restore=None, parent=None):
        super().__init__(parent)
        self.candidate_id = candidate.id
        self._status = status
        self._apply_status_style(candidate.confidence)

        body = QHBoxLayout(self)
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(8)

        # 左：32px 类型徽标
        chip_txt, chip_bg, chip_fg = _TYPE_CHIP.get(
            getattr(eo, "object_type", ""), _TYPE_CHIP_FALLBACK)
        glyph = QLabel(chip_txt)
        glyph.setFixedSize(32, 32)
        glyph.setAlignment(Qt.AlignCenter)
        glyph.setStyleSheet(
            f"background:{chip_bg}; color:{chip_fg}; border-radius:6px;"
            f"font-size:13px; font-weight:{T.FONT_WEIGHT_SEMIBOLD};")
        body.addWidget(glyph, 0, Qt.AlignTop)

        # 右：标题/元信息/底部操作行
        col = QVBoxLayout()
        col.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        name = eo.block_name if (eo is not None and eo.block_name) else \
            (eo.layer_name if eo is not None else f"EO#{candidate.engineering_object_id}")
        title = QLabel(str(name))
        title.setStyleSheet(
            f"color:{T.TEXT_PRIMARY}; font-size:12px;"
            f"font-weight:700;")
        title_row.addWidget(title, 1)
        if status == "PENDING":
            conf = QLabel(f"置信度 {candidate.confidence:.0%}")
            conf.setStyleSheet(self._conf_qss(candidate.confidence))
            title_row.addWidget(conf, 0, Qt.AlignTop)
        col.addLayout(title_row)

        if status == "ACCEPTED":
            done_row = QHBoxLayout()
            done_row.setSpacing(6)
            done = QLabel("✓ 已确认并写入 BOQ")
            done.setStyleSheet(
                f"color:{T.SUCCESS_TEXT}; font-size:12px;"
                f"font-weight:{T.FONT_WEIGHT_SEMIBOLD};")
            done_row.addWidget(done)
            done_row.addStretch(1)
            sync = QLabel("数量已更新")
            sync.setStyleSheet(
                f"color:{T.SUCCESS_BG}; font-size:{T.FONT_SIZE_CAPTION}px;")
            done_row.addWidget(sync)
            col.addLayout(done_row)
        else:
            if status == "REJECTED":
                done = QLabel("该候选已忽略")
                done.setStyleSheet(
                    f"color:{T.TEXT_SECONDARY}; font-size:12px;")
                col.addWidget(done)

        method = METHOD_LABELS.get(candidate.method, candidate.method)
        info_parts = []
        if eo is not None and eo.block_name:
            info_parts.append(f"块名：{eo.block_name}")
        if eo is not None:
            info_parts.append(f"图层：{eo.layer_name or '-'}")
        info_parts.append(f"方式：{method}")
        if sheet_name:
            info_parts.append(f"图纸：{sheet_name}")
        lbl_info = QLabel(" · ".join(info_parts))
        lbl_info.setStyleSheet(
            f"color:{T.TEXT_SECONDARY}; font-size:{T.FONT_SIZE_CAPTION}px;")
        col.addWidget(lbl_info)

        # 依据（reason）：LLM/规则生成的辅助确认文字（含「需复核」标记）。
        # v3 卡片化时曾被遗漏，此处恢复为独立行，等宽换行显示完整说明。
        if getattr(candidate, "reason", ""):
            prefix = "依据" if status == "PENDING" else "原因"
            lbl_reason = QLabel(f"{prefix}：{candidate.reason}")
            lbl_reason.setWordWrap(True)
            lbl_reason.setStyleSheet(
                f"color:{T.TEXT_SECONDARY}; font-size:{T.FONT_SIZE_CAPTION}px;")
            col.addWidget(lbl_reason)

        # 底部行：建议绑定 + 行内操作（ACCEPTED 用 emerald 提示替代绑定行）
        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        if status == "PENDING":
            if boq_item is not None:
                bind = QLabel(
                    f"建议绑定：<b style='color:{T.TEXT_PRIMARY};'>"
                    f"{boq_item.code} {boq_item.description}</b>")
            else:
                bind = QLabel(f"BOQ#{candidate.boq_item_id}（已删除）")
            bind.setTextFormat(Qt.RichText)
            bind.setStyleSheet(
                f"color:{T.TEXT_SECONDARY}; font-size:{T.FONT_SIZE_CAPTION}px;")
            bottom.addWidget(bind, 1)

            if eo is not None:
                btn_loc = self._make_link_btn("定位", "在画布中定位该候选实体（支持跨图纸）")
                btn_loc.clicked.connect(
                    lambda _=False: on_locate(
                        eo.sheet_id, eo.block_name or eo.layer_name or ""))
                bottom.addWidget(btn_loc)
            btn_no = QPushButton("忽略")
            btn_no.setObjectName("cardGhostBtn")
            btn_no.setToolTip("拒绝该候选，不再推荐此组合")
            btn_no.clicked.connect(lambda _=False: on_reject(candidate.id))
            bottom.addWidget(btn_no)
            btn_ok = QPushButton("确认")
            btn_ok.setObjectName("cardPrimaryBtn")
            btn_ok.setToolTip("确认该候选为正式映射，BOQ 数量同步更新")
            btn_ok.clicked.connect(lambda _=False: on_confirm(candidate.id))
            bottom.addWidget(btn_ok)
        else:
            bottom.addStretch(1)
            if eo is not None:
                btn_loc = self._make_link_btn(
                    "恢复待审" if status == "REJECTED" else "定位",
                    "撤销忽略，重新进入待复核队列" if status == "REJECTED"
                    else "在画布中定位该候选实体（支持跨图纸）")
                if status == "REJECTED":
                    btn_loc.clicked.connect(
                        lambda _=False: on_restore(candidate.id)
                        if on_restore else on_reject(candidate.id))
                else:
                    btn_loc.clicked.connect(
                        lambda _=False: on_locate(
                            eo.sheet_id, eo.block_name or eo.layer_name or ""))
                bottom.addWidget(btn_loc)
        col.addLayout(bottom)
        body.addLayout(col, 1)

    @staticmethod
    def _make_link_btn(text: str, tip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("cardLinkBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tip)
        return btn

    def _apply_status_style(self, confidence: float = 0.0):
        """卡片底色：高置信候选 = 青色浅底，其余白底；确认 = emerald；忽略 = 白底。"""
        if self._status == "PENDING" and confidence >= 0.95:
            bg, bd = "rgba(236,254,255,0.6)", "#A5F3FC"     # cyan-50/60, cyan-200
        elif self._status == "ACCEPTED":
            bg, bd = "#ECFDF5", "#A7F3D0"                    # emerald-50/200
        else:
            bg, bd = T.SURFACE, T.BORDER                     # 白底 / slate-200
        self.setStyleSheet(
            f"_CandidateCard {{ background: {bg}; border: 1px solid {bd};"
            f" border-radius: 6px; }}")

    @staticmethod
    def _conf_qss(conf: float) -> str:
        """置信度徽标（原型：98% 青 / 86%、82% 琥珀）：≥0.95 青 / ≥0.6 琥珀 / 其余红。"""
        if conf >= 0.95:
            return (f"background:#CFFAFE; color:#0E7490; border-radius:4px;"
                    f"padding:1px 6px; font-size:{T.FONT_SIZE_CAPTION}px;"
                    f"font-weight:{T.FONT_WEIGHT_MEDIUM};")
        if conf >= 0.6:
            return (f"background:#FEF3C7; color:#B45309; border-radius:4px;"
                    f"padding:1px 6px; font-size:{T.FONT_SIZE_CAPTION}px;"
                    f"font-weight:{T.FONT_WEIGHT_MEDIUM};")
        return (f"background:#FEE2E2; color:#B91C1C; border-radius:4px;"
                f"padding:1px 6px; font-size:{T.FONT_SIZE_CAPTION}px;"
                f"font-weight:{T.FONT_WEIGHT_MEDIUM};")


class BindingWorkbench(QWidget):
    locateRequested = Signal(int, str)         # (sheet_id, block_name_or_layer_name)
    statusMessage = Signal(str)
    bindingChanged = Signal()               # 确认/拒绝后主窗口刷新计量口径
    assignRequested = Signal()              # 底部深色按钮 → 主窗口分配已选实体
    busyChanged = Signal(bool)             # 内部 worker 启停 → 主窗口统一 busy 收口（P0 C1）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_id = None
        self._objects = []                  # list[EngineeringObject]
        self._queue = []                    # list[BindingCandidate]
        self._sheets_map: dict = {}
        self._queue_status = "PENDING"      # 卡片过滤：PENDING / ACCEPTED / REJECTED
        self._pending_selection = 0         # 画布已选实体数（底部按钮文案）
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 头部：标题/副标题 + info 图标 + 三段切换 ----
        head = QWidget()
        head.setObjectName("panelHeader")
        hv = QVBoxLayout(head)
        hv.setContentsMargins(16, 10, 12, 10)
        hv.setSpacing(8)
        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        t = QLabel("绑定工作台")
        t.setObjectName("panelTitle")
        title_col.addWidget(t)
        sub = QLabel("将图纸实体关联至 BOQ 清单项")
        sub.setObjectName("panelSub")
        title_col.addWidget(sub)
        title_row.addLayout(title_col, 1)
        self.btn_info = QPushButton(T.ICONS.get("info", "i")
                                    if T.icon_font_family() else "i")
        self.btn_info.setObjectName("panelIconBtn")
        self.btn_info.setToolTip(
            "AI 识别规则：电气设备块 / 尺寸标注 / 图例。\n"
            "候选分层：历史确认 → 规则 → 语义召回 → LLM 精排。")
        if T.icon_font_family():
            f = T.make_icon_font(15)
            if f:
                self.btn_info.setFont(f)
        title_row.addWidget(self.btn_info)
        hv.addLayout(title_row)

        seg_host = QWidget()
        seg_host.setObjectName("segHost")
        seg_row = QHBoxLayout(seg_host)
        seg_row.setContentsMargins(2, 2, 2, 2)
        seg_row.setSpacing(2)
        self.seg_buttons: dict[str, QPushButton] = {}
        for key, label in (("PENDING", "待复核"), ("ACCEPTED", "已确认"),
                           ("REJECTED", "已忽略")):
            btn = QPushButton(f"{label} 0")
            btn.setObjectName("segTab")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked, k=key: self._switch_queue_status(k))
            self.seg_buttons[key] = btn
            seg_row.addWidget(btn)
        self.seg_buttons["PENDING"].setChecked(True)
        hv.addWidget(seg_host)
        root.addWidget(head)

        # ---- 琥珀条：N 个 AI 候选需要复核 + 全部确认（青色链接） ----
        self.warn_bar = QFrame()
        self.warn_bar.setObjectName("amberBar")
        wl = QHBoxLayout(self.warn_bar)
        wl.setContentsMargins(16, 6, 16, 6)
        self.warn_label = QLabel("")
        self.warn_label.setStyleSheet(
            f"color:{T.WARNING_BAR_TEXT}; font-size:{T.FONT_SIZE_CAPTION}px;")
        wl.addWidget(self.warn_label)
        wl.addStretch(1)
        self.btn_confirm_all = QPushButton("全部确认")
        self.btn_confirm_all.setObjectName("linkBtn")
        self.btn_confirm_all.setCursor(Qt.PointingHandCursor)
        self.btn_confirm_all.setToolTip(
            "批量确认规则满置信候选；低置信/AI 候选仍需逐条复核")
        self.btn_confirm_all.clicked.connect(self._on_auto_confirm)
        wl.addWidget(self.btn_confirm_all)
        root.addWidget(self.warn_bar)

        # ---- 卡片滚动区 ----
        self.cards_host = QWidget()
        self.cards_host.setObjectName("cardsHost")
        self.cards_lay = QVBoxLayout(self.cards_host)
        self.cards_lay.setContentsMargins(12, 12, 12, 12)
        self.cards_lay.setSpacing(8)
        self.cards_lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_host)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll, 1)

        # ---- 底部：通栏深色按钮「将已选 N 个实体分配至 BOQ」 ----
        foot = QWidget()
        foot.setObjectName("workbenchFooter")
        fv = QVBoxLayout(foot)
        fv.setContentsMargins(12, 10, 12, 12)
        self.btn_assign = QPushButton("将已选 0 个实体分配至 BOQ")
        self.btn_assign.setObjectName("darkBtn")
        self.btn_assign.setCursor(Qt.PointingHandCursor)
        self.btn_assign.setToolTip("把画布中已拾取的实体分配到选中的 BOQ 清单项")
        self.btn_assign.clicked.connect(self.assignRequested)
        fv.addWidget(self.btn_assign)
        root.addWidget(foot)

    def _switch_queue_status(self, status: str):
        self._queue_status = status
        for key, btn in self.seg_buttons.items():
            btn.setChecked(key == status)
        self._render_queue()

    # ---------- 外部入口（顶栏 AI/更多 菜单调用；功能不丢） ----------
    def extract_objects(self):
        """提取工程对象（原工具栏「提取工程对象」）。"""
        if self._project_id is None:
            self.statusMessage.emit("请先新建/选择项目")
            return
        sheets = db.get_sheets(self._project_id)
        total = 0
        for s in sheets:
            from ..engineering import extract_and_store_engineering_objects
            res = extract_and_store_engineering_objects(self._project_id, s.id)
            total += res["created"]
        self.load_project(self._project_id)
        self.bindingChanged.emit()   # 新工程对象 → 图纸列表徽标联动
        self.statusMessage.emit(f"已提取 {total} 个工程对象（{len(sheets)} 张图纸）")

    def run_generate(self):
        """生成候选（原工具栏「生成候选」；分层：历史→规则→语义→LLM）。"""
        if self._project_id is None:
            self.statusMessage.emit("请先新建/选择项目")
            return
        if not db.get_engineering_objects(self._project_id):
            self.statusMessage.emit("请先提取工程对象 —— 顶栏「AI 算量 ▾ → 提取工程对象」")
            return
        if not db.get_boq_items(self._project_id):
            self.statusMessage.emit(
                "请先导入 BOQ 清单 —— 顶栏「更多 ▾ → 导入 BOQ」（绑定候选是「工程对象 ↔ BOQ 条目」的匹配建议，无清单无法生成）")
            self.statusMessage.emit("→ 导入 BOQ 后重新执行「生成绑定候选」，已提取的工程对象不会丢失")
            return
        self.statusMessage.emit("生成候选中…（历史→规则→语义→LLM 精排，规则强命中不耗 LLM）")
        self.busyChanged.emit(True)
        self._worker = _BindingWorker(self._project_id, True, parent=self)
        self._worker.finished_ok.connect(self._on_generate_done)
        self._worker.failed.connect(self._on_generate_failed)
        self._worker.start()

    def run_llm_classify(self):
        """LLM 语义补充分类（原工具栏按钮；顶栏 AI 菜单调用）。"""
        if self._project_id is None:
            self.statusMessage.emit("请先新建/选择项目")
            return
        if not db.get_engineering_objects(self._project_id):
            self.statusMessage.emit("请先提取工程对象 —— 顶栏「AI 算量 ▾ → 提取工程对象」")
            return
        self.statusMessage.emit("LLM 补充分类中…（可稍后查看结果）")
        self.busyChanged.emit(True)
        self._class_worker = _ClassifyWorker(self._project_id, parent=self)
        self._class_worker.finished_ok.connect(self._on_llm_classify_done)
        self._class_worker.failed.connect(self._on_llm_classify_failed)
        self._class_worker.start()

    def set_pending_selection(self, count: int):
        """主窗口推送画布已选实体数 → 底部按钮文案。"""
        self._pending_selection = count
        self.btn_assign.setText(f"将已选 {count} 个实体分配至 BOQ")
        self.btn_assign.setEnabled(count > 0)

    def refresh_queue(self):
        """外部数据变化后刷新（原「刷新」按钮）。"""
        self.load_project(self._project_id)

    # ---------- 数据加载 ----------
    def refresh_enabled(self, has_project: bool | None = None):
        """无项目时禁用批量操作按钮（has_project 显式传入可覆盖内部状态）。"""
        ok = self._project_id is not None if has_project is None else has_project
        self.btn_confirm_all.setEnabled(ok)
        self.btn_assign.setEnabled(ok and self._pending_selection > 0)

    def load_project(self, project_id):
        self._project_id = project_id
        self._objects = []
        self._queue = []
        self._sheets_map = {s.id: s.filename for s in db.get_sheets(project_id or 0)}
        self.refresh_enabled()
        if project_id is None:
            self._render_queue()
            self._update_status()
            return
        self._objects = db.get_engineering_objects(project_id)
        # 大批量项目（>2000 候选）会拖死 UI；待复核视图默认拉 1000 条
        self._queue = db.get_pending_candidates(project_id, limit=1000)
        self._render_queue()
        self._update_status()

    def _render_queue(self, filter_eoid=None):
        """v3：候选卡片流（三态过滤）。数据源仍以 self._queue（PENDING）为主，
        ACCEPTED/REJECTED 视图按需从 db 拉取。"""
        # 清空旧卡片（保留尾部 stretch）
        while self.cards_lay.count() > 1:
            item = self.cards_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if self._project_id is None:
            self._add_cards_placeholder("未选择项目")
            return

        items = {it.id: it for it in db.get_boq_items(self._project_id)}
        eo_map = {eo.id: eo for eo in self._objects}

        if self._queue_status == "PENDING":
            rows = [c for c in self._queue
                    if filter_eoid is None
                    or (isinstance(filter_eoid, set) and c.engineering_object_id in filter_eoid)
                    or (not isinstance(filter_eoid, set) and c.engineering_object_id == filter_eoid)]
            # 排序（2026-08-28 绑定增强 2.2）：
            #   · 跨 EO 保留 T7 主动学习难例优先——按"该 EO 最低置信"升序
            #     （先审得分最低的图块，不回退难例挖掘机制）；
            #   · EO 内部候选改为置信度降序——最佳绑定置顶（需求 1 一眼可见）。
            eo_min_conf = {}
            for c in rows:
                cur = eo_min_conf.get(c.engineering_object_id)
                if cur is None or c.confidence < cur:
                    eo_min_conf[c.engineering_object_id] = c.confidence
            rows.sort(key=lambda c: (eo_min_conf[c.engineering_object_id],
                                     -c.confidence, c.id))
        else:
            rows = db.get_candidates(self._project_id, status=self._queue_status)
            if filter_eoid is not None:
                if isinstance(filter_eoid, set):
                    rows = [c for c in rows if c.engineering_object_id in filter_eoid]
                else:
                    rows = [c for c in rows if c.engineering_object_id == filter_eoid]
            rows.sort(key=lambda c: (-c.confidence, c.id))

        total = len(rows)
        rows = rows[:CARD_RENDER_CAP]
        if not rows:
            if self._queue_status == "PENDING":
                has_obj = bool(self._objects)
                if has_obj and not db.get_boq_items(self._project_id):
                    # 无 BOQ：候选无从生成（先导线索，避免用户以为生成失败）
                    hint = ("已提取 {n} 个工程对象，但项目尚无 BOQ 清单\n"
                            "请先导入 —— 顶栏「更多 ▾ → 导入 BOQ」，再「AI 算量 ▾ → 生成绑定候选」"
                            ).format(n=len(self._objects))
                elif has_obj:
                    hint = "已提取工程对象，请生成候选 —— 顶栏「AI 算量 ▾ 生成绑定候选」"
                else:
                    hint = "尚无工程对象 —— 顶栏「AI 算量 ▾ 提取工程对象」开始"
                self._add_cards_placeholder(hint)
            else:
                self._add_cards_placeholder(
                    {"ACCEPTED": "暂无已确认绑定",
                     "REJECTED": "暂无已忽略候选"}[self._queue_status])
        for c in rows:
            eo = eo_map.get(c.engineering_object_id) or db.get_engineering_object(
                c.engineering_object_id)
            card = _CandidateCard(
                c, eo, items.get(c.boq_item_id),
                self._sheets_map.get(getattr(eo, "sheet_id", None), ""),
                self._queue_status,
                on_confirm=self._do_confirm, on_reject=self._do_reject,
                on_locate=self._locate_from_card, on_restore=self._do_restore)
            self.cards_lay.insertWidget(self.cards_lay.count() - 1, card)

        if total > CARD_RENDER_CAP:
            self._add_cards_placeholder(
                f"（仅显示前 {CARD_RENDER_CAP} 条 / 共 {total} 条，"
                f"请用「全部确认」处理规则满置信部分）")

    def _add_cards_placeholder(self, text: str):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color:{T.TEXT_DISABLED}; padding: 18px;")
        self.cards_lay.insertWidget(self.cards_lay.count() - 1, lbl)

    def _locate_from_card(self, sheet_id: int, name: str):
        self.locateRequested.emit(sheet_id, name)
        self.statusMessage.emit(f"定位 {name}")

    def _update_status(self):
        """三段计数 + 琥珀条（原型：seg 计数 / 「14 个 AI 候选需要复核」）。"""
        if self._project_id is None:
            for key, btn in self.seg_buttons.items():
                btn.setText({"PENDING": "待复核 0", "ACCEPTED": "已确认 0",
                             "REJECTED": "已忽略 0"}[key])
            self.warn_bar.hide()
            return
        all_pending = db.count_candidates(self._project_id, status="PENDING")
        all_accepted = db.count_candidates(self._project_id, status="ACCEPTED")
        all_rejected = db.count_candidates(self._project_id, status="REJECTED")
        self.seg_buttons["PENDING"].setText(f"待复核 {all_pending}")
        self.seg_buttons["ACCEPTED"].setText(f"已确认 {all_accepted}")
        self.seg_buttons["REJECTED"].setText(f"已忽略 {all_rejected}")
        if all_pending:
            self.warn_label.setText(f"⚠ {all_pending} 个 AI 候选需要复核（低置信优先）")
            self.warn_bar.show()
        else:
            self.warn_bar.hide()

    # ---------- 后台完成回调 ----------
    def _on_generate_done(self, res):
        self.busyChanged.emit(False)
        self.load_project(self._project_id)
        self.bindingChanged.emit()   # 新 PENDING 候选 → 图纸列表徽标/计量口径联动
        st = res["stats"]
        llm_note = ""
        if st.get("llm_unavailable"):
            llm_note = f" / ⚠ LLM 不可用已降级（{st['llm_unavailable']} 个对象仅用本地层）"
        self.statusMessage.emit(
            f"候选生成完成：规则 {st['rule']} / 语义 {st['embedding']} / AI {st['llm']} / "
            f"已绑定跳过 {st['skipped_bound']} / 未匹配 {st['no_match']}{llm_note}")

    def _on_generate_failed(self, err: str):
        self.busyChanged.emit(False)
        self.statusMessage.emit(f"候选生成失败：{err[:120]}")

    def _on_llm_classify_done(self, res):
        self.busyChanged.emit(False)
        self.load_project(self._project_id)
        self.statusMessage.emit(
            f"LLM 补充分类完成：成功 {res.get('classified', 0)} / 失败 "
            f"{res.get('failed', 0)} / 跳过 {res.get('skipped', 0)}"
            f"{'（另外 ' + str(res.get('deferred', 0)) + ' 个低置信对象待下次）' if res.get('deferred') else ''}")

    def _on_llm_classify_failed(self, err: str):
        self.busyChanged.emit(False)
        self.statusMessage.emit(f"LLM 补充分类失败：{err[:120]}")

    # ---------- 行操作 ----------
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

    def _do_reject(self, candidate_id: int):
        reject_binding(candidate_id, "人工拒绝")
        self.load_project(self._project_id)
        self.bindingChanged.emit()
        self.statusMessage.emit(f"已忽略候选 #{candidate_id}，不再推荐该组合")

    def _do_restore(self, candidate_id: int):
        """已忽略 → 恢复待审（撤销 reject_binding）。"""
        try:
            db.update_candidate_status(candidate_id, "PENDING")
        except Exception as e:  # noqa: BLE001
            self.statusMessage.emit(f"恢复失败：{e}")
            return
        self.load_project(self._project_id)
        self.bindingChanged.emit()
        self.statusMessage.emit(f"候选 #{candidate_id} 已恢复为待复核")

    def _on_auto_confirm(self):
        if self._project_id is None:
            return
        res = auto_confirm_rule_candidates(self._project_id)
        self.load_project(self._project_id)
        self.bindingChanged.emit()
        self.statusMessage.emit(f"批量确认完成：{res['auto_confirmed']} 条（规则满置信）")
