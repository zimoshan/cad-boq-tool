"""画布工具栏（v3 main.html 1:1）：清单/计量/图例/AI/属性 + 拾取 + 整图 + − % ＋ + 已加载。

原型中不存在的入口（深色画布/全屏/左右栏/实体过滤/缩放历史）保留为 QAction /
信号，由主窗口收拢进顶栏「更多 ▾」菜单与快捷键，功能不丢、界面不减配。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QToolBar, QComboBox, QPushButton,
                               QLabel, QWidget, QHBoxLayout, QMenu)

from . import theme as T

MODE_LABELS = {"pick": "拾取", "layer": "图层", "block": "块"}
ENTITY_TYPES = ["LINE", "LWPOLYLINE", "ARC", "CIRCLE", "SPLINE", "HATCH", "INSERT", "TEXT"]

# 上下文模式 → 右侧标签页（与主窗口 _mode_tab_map 互逆）
CONTEXT_MODES = [
    ("browse", "清单"),    # 0 绑定工作台 / 清单语义
    ("mapping", "计量"),   # 1 计量
    ("legend", "图例"),    # 2 图例标定
    ("ai", "AI"),          # 3 绑定工作台
    ("props", "属性"),     # 4 项目属性
]


class CanvasToolbar(QToolBar):
    """画布顶部工具栏：发出高层信号，由主窗口转发到画布与状态"""

    modeChanged = Signal(str)                # "pick"/"layer"/"block"
    contextModeChanged = Signal(str)         # browse/mapping/legend/ai/props
    zoomFitRequested = Signal()
    zoomInRequested = Signal()               # ＋（原型 zoom(10)）
    zoomOutRequested = Signal()              # －（原型 zoom(-10)）
    zoomActualRequested = Signal()           # 100%（QAction/快捷键，无按钮）
    zoomBackRequested = Signal()             # 缩放历史
    zoomForwardRequested = Signal()
    themeToggleRequested = Signal()          # 浅<->深
    fullscreenToggleRequested = Signal()
    entityTypeVisibilityChanged = Signal(str, bool)  # type_name, visible
    isolateLayerRequested = Signal(str)      # layer name or "" for none
    leftPanelToggleRequested = Signal()      # 左栏显隐
    rightPanelToggleRequested = Signal()     # 右栏显隐

    def __init__(self, parent=None):
        super().__init__("画布工具栏", parent)
        self.setMovable(False)
        self.setIconSize(self.iconSize())
        self._build()

    def _build(self):
        # ---- 工作区：清单 / 计量 / 图例 / AI / 属性（active = cyan-600 白字） ----
        self.context_group = QWidget()
        context_layout = QHBoxLayout(self.context_group)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(2)
        self.context_buttons: dict[str, QPushButton] = {}
        for key, label in CONTEXT_MODES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(f"切换到 {label} 工作模式")
            btn.clicked.connect(lambda _checked, k=key: self._set_context_mode(k))
            self.context_buttons[key] = btn
            context_layout.addWidget(btn)
        self.addWidget(self.context_group)
        self._set_context_mode("browse")

        self.addSeparator()

        # ---- 拾取模式（原型「拾取▾」按钮；QComboBox 承载 拾取/图层/块 三态） ----
        self.mode_combo = QComboBox()
        self.mode_combo.setToolTip("拾取：点选单个实体；图层/块：左树右键批量关联")
        for k, v in MODE_LABELS.items():
            self.mode_combo.addItem(v, k)
        self.mode_combo.setCurrentIndex(0)  # 默认拾取
        self.mode_combo.currentIndexChanged.connect(
            lambda _: self.modeChanged.emit(self.mode_combo.currentData()))
        self.addWidget(self.mode_combo)

        self.addSeparator()

        # ---- 缩放（原型：整图 + − % ＋） ----
        self.btn_fit = QPushButton("整图")
        self.btn_fit.setToolTip("适应窗口 (Ctrl+0)")
        self.btn_fit.clicked.connect(self.zoomFitRequested)
        self.addWidget(self.btn_fit)

        self.btn_zoom_out = QPushButton(T.ICONS.get("zoom_out", "－"))
        self.btn_zoom_out.setToolTip("缩小")
        self.btn_zoom_out.setObjectName("toolIconBtn")
        self.btn_zoom_out.clicked.connect(self.zoomOutRequested)
        self.addWidget(self.btn_zoom_out)

        self.zoom_pct = QLabel("100%")
        self.zoom_pct.setObjectName("zoomPct")
        self.addWidget(self.zoom_pct)

        self.btn_zoom_in = QPushButton(T.ICONS.get("zoom_in", "＋"))
        self.btn_zoom_in.setToolTip("放大")
        self.btn_zoom_in.setObjectName("toolIconBtn")
        self.btn_zoom_in.clicked.connect(self.zoomInRequested)
        self.addWidget(self.btn_zoom_in)

        # ---- 缩放历史 / 100%（QAction 承载快捷键语义，主窗口接入） ----
        self.act_zoom_actual = QAction("100% 缩放", self)
        self.act_zoom_actual.triggered.connect(self.zoomActualRequested)
        self.act_zoom_back = QAction("上一步缩放", self)
        self.act_zoom_back.triggered.connect(self.zoomBackRequested)
        self.act_zoom_fwd = QAction("下一步缩放", self)
        self.act_zoom_fwd.triggered.connect(self.zoomForwardRequested)

        # ---- 隐藏动作组：视图（收拢到顶栏「更多 ▾ → 视图」） ----
        self.btn_theme = QAction("🌙 深色画布", self, checkable=True)
        self.btn_theme.setToolTip("深色/浅色画布切换")
        self.btn_theme.triggered.connect(lambda: self.themeToggleRequested.emit())

        self.btn_full = QAction("⛶ 全屏 (F11)", self)
        self.btn_full.triggered.connect(self.fullscreenToggleRequested)

        self.btn_left = QAction("◧ 左栏", self, checkable=True)
        self.btn_left.setChecked(True)
        self.btn_left.triggered.connect(lambda: self.leftPanelToggleRequested.emit())

        self.btn_right = QAction("◨ 右栏", self, checkable=True)
        self.btn_right.setChecked(True)
        self.btn_right.triggered.connect(lambda: self.rightPanelToggleRequested.emit())

        # ---- 隐藏动作组：实体类型过滤（更多 ▾ → 实体类型过滤） ----
        self.type_actions: dict[str, QAction] = {}
        defaults_off = {"HATCH", "TEXT"}
        for t in ENTITY_TYPES:
            act = QAction(t, self, checkable=True)
            act.setChecked(t not in defaults_off)
            act.toggled.connect(lambda v, _t=t: self.entityTypeVisibilityChanged.emit(_t, v))
            self.type_actions[t] = act

        # ---- 右侧：已加载文件名（cyan 圆点 + 文件名） ----
        from PySide6.QtWidgets import QSizePolicy
        stretch = QWidget()
        stretch.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(stretch)

        self.file_label = QLabel("")
        self.file_label.setToolTip("当前图纸")
        self.addWidget(self.file_label)

    def _set_context_mode(self, mode: str):
        self._context_mode = mode
        for k, btn in self.context_buttons.items():
            btn.setChecked(k == mode)
        self.contextModeChanged.emit(mode)

    # tab 索引 → 工作区模式（与主窗口 _mode_tab_map 互逆；rail 点击时镜像高亮）
    # 绑定0/清单1/计量2/图例3 有镜像；实体属性4/记录6 无；项目属性5 → props
    TAB_TO_CONTEXT = {0: "ai", 1: "browse", 2: "mapping", 3: "legend",
                      4: None, 5: "props", 6: None}

    def sync_context_from_tab(self, tab_idx: int):
        """右栏 tab 被 rail/快捷键切换时，同步工作区按钮选中态（不回发信号）。"""
        mode = self.TAB_TO_CONTEXT.get(tab_idx)
        if mode is None:
            return
        self._context_mode = mode
        for k, btn in self.context_buttons.items():
            btn.setChecked(k == mode)

    # ---- 外部 API ----
    def set_mode(self, mode: str):
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

    def set_type_visible(self, type_name: str, visible: bool):
        act = self.type_actions.get(type_name)
        if act is not None:
            act.blockSignals(True)
            act.setChecked(visible)
            act.blockSignals(False)

    def set_zoom_pct(self, scale: float):
        """画布缩放读数（原型 zoomText）。scale 为视图变换 m11。"""
        self.zoom_pct.setText(f"{round(scale * 100)}%")

    def set_loaded_file(self, filename: str):
        """右侧「● 已加载：xxx.dwg」标签（cyan 圆点）；空串隐藏"""
        if filename:
            self.file_label.setText(
                f"<span style='color:#22D3EE;'>●</span> 已加载：{filename}")
            self.file_label.show()
        else:
            self.file_label.setText("")
            self.file_label.hide()
