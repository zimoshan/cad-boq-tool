"""画布工具栏：模式/缩放/主题/实体类型过滤"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QToolBar, QComboBox, QPushButton,
                               QLabel, QCheckBox, QWidget, QHBoxLayout)

MODE_LABELS = {"pick": "拾取", "layer": "图层", "block": "块"}
ENTITY_TYPES = ["LINE", "LWPOLYLINE", "ARC", "CIRCLE", "SPLINE", "HATCH", "INSERT", "TEXT"]

# P1-14：上下文模式 → 右侧标签页 1:1 对齐（去掉双轨：原先 映射/计量 同指 1、
# 浏览/输出 同指 0，而 图例/属性 无对应按钮）
CONTEXT_MODES = [
    ("browse", "清单"),    # 0 BOQ 清单
    ("mapping", "计量"),   # 1 计量
    ("legend", "图例"),    # 2 图例标定
    ("ai", "AI"),          # 3 绑定工作台（AI/规则候选审核）
    ("props", "属性"),     # 4 项目属性
]


class CanvasToolbar(QToolBar):
    """画布顶部工具栏：发出高层信号，由主窗口转发到画布与状态"""

    modeChanged = Signal(str)                # "pick"/"layer"/"block"
    contextModeChanged = Signal(str)         # browse/mapping/legend/ai/props（对应右侧标签页）
    zoomFitRequested = Signal()
    zoomActualRequested = Signal()           # 100%
    zoomBackRequested = Signal()
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
        # ---- 工作模式：浏览 / 映射 / AI / 计量 / 输出 ----
        self.context_group = QWidget()
        context_layout = QHBoxLayout(self.context_group)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(4)
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

        # ---- 模式 ----
        self.addWidget(QLabel("  模式 "))
        self.mode_combo = QComboBox()
        for k, v in MODE_LABELS.items():
            self.mode_combo.addItem(v, k)
        self.mode_combo.setCurrentIndex(0)  # 默认拾取
        self.mode_combo.currentIndexChanged.connect(
            lambda _: self.modeChanged.emit(self.mode_combo.currentData()))
        self.addWidget(self.mode_combo)

        self.addSeparator()

        # ---- 缩放 ----
        self.addWidget(QLabel(" 缩放 "))
        self.btn_fit = QPushButton("整图")
        self.btn_fit.setToolTip("适应窗口 (Ctrl+0)")
        self.btn_fit.clicked.connect(self.zoomFitRequested)
        self.addWidget(self.btn_fit)

        self.btn_actual = QPushButton("100%")
        self.btn_actual.setToolTip("实际像素 (Ctrl+1)")
        self.btn_actual.clicked.connect(self.zoomActualRequested)
        self.addWidget(self.btn_actual)

        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip("上一步 (Alt+Left)")
        self.btn_back.clicked.connect(self.zoomBackRequested)
        self.addWidget(self.btn_back)

        self.btn_fwd = QPushButton("▶")
        self.btn_fwd.setToolTip("下一步 (Alt+Right)")
        self.btn_fwd.clicked.connect(self.zoomForwardRequested)
        self.addWidget(self.btn_fwd)

        self.addSeparator()

        # ---- 主题 ----
        self.btn_theme = QPushButton("🌙 深色")
        self.btn_theme.setCheckable(True)
        self.btn_theme.setToolTip("深色/浅色主题切换")
        self.btn_theme.clicked.connect(self._on_theme_clicked)
        self.addWidget(self.btn_theme)

        self.btn_full = QPushButton("⛶ 全屏")
        self.btn_full.setToolTip("F11 切换全屏")
        self.btn_full.clicked.connect(self.fullscreenToggleRequested)
        self.addWidget(self.btn_full)

        self.addSeparator()

        # ---- 面板显隐（v2 折叠栏） ----
        self.btn_left = QPushButton("◧ 左栏")
        self.btn_left.setCheckable(True)
        self.btn_left.setChecked(True)
        self.btn_left.setToolTip("显示 / 隐藏左侧图层面板")
        self.btn_left.clicked.connect(self.leftPanelToggleRequested)
        self.addWidget(self.btn_left)

        self.btn_right = QPushButton("◨ 右栏")
        self.btn_right.setCheckable(True)
        self.btn_right.setChecked(True)
        self.btn_right.setToolTip("显示 / 隐藏右侧清单面板")
        self.btn_right.clicked.connect(self.rightPanelToggleRequested)
        self.addWidget(self.btn_right)

        self.addSeparator()

        # ---- 实体类型过滤 ----
        self.addWidget(QLabel("  过滤 "))
        self._type_checks: dict[str, QCheckBox] = {}
        # 默认关闭 HATCH 和 TEXT（杂线元凶）
        defaults_off = {"HATCH", "TEXT"}
        for t in ENTITY_TYPES:
            cb = QCheckBox(t)
            cb.setChecked(t not in defaults_off)
            cb.toggled.connect(lambda v, _t=t: self.entityTypeVisibilityChanged.emit(_t, v))
            self._type_checks[t] = cb
            self.addWidget(cb)

    def _set_context_mode(self, mode: str):
        self._context_mode = mode
        for k, btn in self.context_buttons.items():
            btn.setChecked(k == mode)
        self.contextModeChanged.emit(mode)

    def _on_theme_clicked(self):
        is_dark = self.btn_theme.isChecked()
        self.btn_theme.setText("☀ 浅色" if is_dark else "🌙 深色")
        self.themeToggleRequested.emit()

    # ---- 外部 API ----
    def set_mode(self, mode: str):
        idx = self.mode_combo.findData(mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

    def set_type_visible(self, type_name: str, visible: bool):
        cb = self._type_checks.get(type_name)
        if cb is not None:
            cb.blockSignals(True)
            cb.setChecked(visible)
            cb.blockSignals(False)
