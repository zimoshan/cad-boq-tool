"""图层 / 块名树：显隐开关 + 批量关联入口 + Isolate/锁定（Phase 2）

v3 任务二十九 P5 后续：自定义 selected 样式，移除 focus outline，
避免「选定框压文字」视觉重叠。
"""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QMenu, QColorDialog,
                               QHeaderView, QWidget, QVBoxLayout, QHBoxLayout,
                               QLineEdit, QPushButton)

from . import theme as T

logger = logging.getLogger(__name__)

# 选中样式：由 theme.py 统一生成（替换原 _SELECTED_QSS 硬编码）
_SELECTED_QSS = T.generate_item_selected_qss()

# 搜索过滤模式
_FILTER_MODES = [
    ("全部", "all"),
    ("已勾选", "visible"),
    ("未勾选", "hidden"),
]


class LayerTreeWidget(QWidget):
    """带搜索/过滤的图层树容器（替代原来直接使用 LayerTree 的场景）"""
    layerVisibilityChanged = Signal(str, bool)
    layerAssociateRequested = Signal(str)
    blockAssociateRequested = Signal(str)
    layerIsolateRequested = Signal(str)
    layersRestoreRequested = Signal()
    layerLockRequested = Signal(str, bool)
    layerColorOverrideRequested = Signal(str, tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        # 搜索行
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索图层/块名...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_box, 1)
        root.addLayout(search_row)

        # 过滤按钮行
        filter_row = QHBoxLayout()
        filter_row.setSpacing(2)
        self._filter_btns: dict[str, QPushButton] = {}
        for label, key in _FILTER_MODES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, k=key: self._set_filter_mode(k))
            self._filter_btns[key] = btn
            filter_row.addWidget(btn)
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        # 图层树本体
        self.tree = LayerTree()
        root.addWidget(self.tree, 1)

        # 透传信号
        self.tree.layerVisibilityChanged.connect(self.layerVisibilityChanged)
        self.tree.layerAssociateRequested.connect(self.layerAssociateRequested)
        self.tree.blockAssociateRequested.connect(self.blockAssociateRequested)
        self.tree.layerIsolateRequested.connect(self.layerIsolateRequested)
        self.tree.layersRestoreRequested.connect(self.layersRestoreRequested)
        self.tree.layerLockRequested.connect(self.layerLockRequested)
        self.tree.layerColorOverrideRequested.connect(self.layerColorOverrideRequested)

        self._filter_mode = "all"
        self._set_filter_mode("all")

    def _set_filter_mode(self, mode: str):
        self._filter_mode = mode
        for k, btn in self._filter_btns.items():
            btn.setChecked(k == mode)
        self._apply_filter(self.search_box.text())

    def _apply_filter(self, text: str):
        """根据搜索文本 + 过滤模式筛选可见项"""
        keyword = text.strip().upper()
        mode = self._filter_mode
        for group in (self.tree._layer_group, self.tree._block_group):
            if group is None:
                continue
            visible_count = 0
            for i in range(group.childCount()):
                child = group.child(i)
                data = child.data(0, Qt.UserRole)
                if not data:
                    continue
                name = data[1] if len(data) > 1 else ""
                name_match = (not keyword) or (keyword in name.upper())
                vis = child.checkState(2) == Qt.Checked
                if mode == "visible" and not vis:
                    child.setHidden(True)
                    continue
                if mode == "hidden" and vis:
                    child.setHidden(True)
                    continue
                child.setHidden(not name_match)
                if name_match:
                    visible_count += 1
            # 更新分组标题计数
            title = group.text(1).split("(")[0].strip()
            group.setText(1, f"{title} ({visible_count})")

    # 透传底层 API
    def rebuild(self, *args, **kwargs):
        self.tree.rebuild(*args, **kwargs)
        self._apply_filter(self.search_box.text())

    def set_base_layers(self, *args, **kwargs):
        self.tree.set_base_layers(*args, **kwargs)
        self._apply_filter(self.search_box.text())

    def uncheck_base_layers(self, *args, **kwargs):
        result = self.tree.uncheck_base_layers(*args, **kwargs)
        self._apply_filter(self.search_box.text())
        return result


class LayerTree(QTreeWidget):
    layerVisibilityChanged = Signal(str, bool)
    layerAssociateRequested = Signal(str)
    blockAssociateRequested = Signal(str)
    layerIsolateRequested = Signal(str)      # Phase 2: "只看此图层"
    layersRestoreRequested = Signal()        # Phase 2: LAYUNISO
    layerLockRequested = Signal(str, bool)   # Phase 2: 锁定
    layerColorOverrideRequested = Signal(str, tuple)  # Phase 2: 颜色覆盖

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(3)                 # 列0=色块，列1=图层/块名，列2=显隐复选框
        self.setColumnWidth(0, 24)
        self.setColumnWidth(2, 26)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemChanged.connect(self._on_item_changed)  # 只连一次（rebuild 会 clear 但不重连）
        self._layer_group = None
        self._block_group = None
        self._layer_nodes: dict = {}
        self._block_nodes: dict = {}
        self._layer_color_overrides: dict[str, tuple] = {}  # layer -> (r,g,b)
        self._base_layers: set = set()      # 底图图层集（灰色斜体标识 + 自动隐藏）
        self.setStyleSheet(_SELECTED_QSS)

    def rebuild(self, layers: list, blocks: list, layer_colors: dict | None = None):
        started = time.perf_counter()
        self.clear()
        self._layer_nodes.clear()
        self._block_nodes.clear()
        if layer_colors:
            self._layer_color_overrides.update(layer_colors)

        self._layer_group = QTreeWidgetItem(["", "图层", ""])
        self._block_group = QTreeWidgetItem(["", "块引用", ""])
        self.addTopLevelItem(self._layer_group)
        self.addTopLevelItem(self._block_group)

        for info in layers:
            node = QTreeWidgetItem(["", f"{info.name}  ({info.entity_count})", ""])
            node.setFlags(node.flags() | Qt.ItemIsUserCheckable)
            node.setCheckState(2, Qt.Checked)     # 复选框独占列2，避免与色块/文字叠加
            node.setData(0, Qt.UserRole, ("layer", info.name))
            # 颜色以列0「■」色块呈现（浅色主题下不再整行涂色，避免黑底黑字）
            color = self._layer_color_overrides.get(info.name) or info.color
            if color:
                node.setText(0, "■")
                node.setForeground(0, QBrush(QColor(*color)))
            self._layer_group.addChild(node)
            self._layer_nodes[info.name] = node

        for info in blocks:
            node = QTreeWidgetItem(["", f"{info.name}  ({info.entity_count})", ""])
            node.setData(0, Qt.UserRole, ("block", info.name))
            self._block_group.addChild(node)
            self._block_nodes[info.name] = node

        self._layer_group.setExpanded(True)
        self._block_group.setExpanded(True)

        self._mark_base_layers()
        logger.debug("layer tree rebuild: layers=%d blocks=%d elapsed_ms=%.1f",
                 len(layers), len(blocks), (time.perf_counter() - started) * 1000)

    def set_base_layers(self, base_layers: set):
        """设置底图图层集合（rebuild 后自动标记灰色斜体 + 自动取消勾选）"""
        self._base_layers = base_layers or set()
        self._mark_base_layers()

    def _mark_base_layers(self):
        """在 rebuild 后为底图图层打标记：灰色斜体标识（不隐藏，保持全部图层可见）。

        底图减法只用于「运算」区分设备块（见 legend_panel._compute_base_hidden_blocks），
        不隐藏画布图层——否则底图线条缺失，无法分辨设备与底图。
        """
        if not self._base_layers or not self._layer_nodes:
            return
        base_lower = {l.lower() for l in self._base_layers}
        for name, node in self._layer_nodes.items():
            if name.lower() in base_lower:
                # 灰色斜体：标识为底图图层（与建筑图层共享视觉语言）
                font = node.font(1)
                font.setItalic(True)
                font.setWeight(font.Weight.Normal)
                node.setFont(1, font)
                node.setForeground(1, QBrush(QColor(T.TEXT_HINT)))
                # 注意：不再自动取消勾选。底图图层保持勾选可见，
                # 减法仅作用于设备块计算，不影响画布显示。

    def uncheck_base_layers(self):
        """手动批量取消所有底图图层的勾选（用户主动隐藏底图时用）。

        注意：设为底图时不再自动调用本方法——底图图层默认保持可见，
        减法只作用于设备块计算，不隐藏画布图层。
        """
        if not self._base_layers or not self._layer_nodes:
            return 0
        base_lower = {l.lower() for l in self._base_layers}
        count = 0
        for name, node in self._layer_nodes.items():
            if name.lower() in base_lower and node.checkState(2) == Qt.Checked:
                node.setCheckState(2, Qt.Unchecked)  # 触发 _on_item_changed → emit signal
                count += 1
        return count

    def _on_item_changed(self, item, column):
        if column != 2:      # 只响应复选框列
            return
        data = item.data(0, Qt.UserRole)
        if data and data[0] == "layer":
            self.layerVisibilityChanged.emit(data[1], item.checkState(2) == Qt.Checked)

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        menu = QMenu(self)
        if data[0] == "layer":
            menu.addAction("只看此图层", lambda: self.layerIsolateRequested.emit(data[1]))
            menu.addAction("恢复显示全部", lambda: self.layersRestoreRequested.emit())
            menu.addSeparator()
            menu.addAction("关联该图层到当前条目",
                           lambda: self.layerAssociateRequested.emit(data[1]))
            menu.addSeparator()
            menu.addAction("指定显示颜色…", lambda: self._pick_color(data[1]))
            menu.addAction("清除颜色覆盖", lambda: self.layerColorOverrideRequested.emit(data[1], None))
        else:
            menu.addAction("关联该块到当前条目（计数）",
                           lambda: self.blockAssociateRequested.emit(data[1]))
        menu.exec(self.viewport().mapToGlobal(pos))

    def _pick_color(self, layer: str):
        c = QColorDialog.getColor(parent=self, title=f"为图层 [{layer}] 指定显示颜色")
        if c.isValid():
            self.layerColorOverrideRequested.emit(layer, (c.red(), c.green(), c.blue()))
