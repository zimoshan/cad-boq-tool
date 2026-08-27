"""选择状态条：显示已选 N 个 + 分配按钮 + 清空 + 缩放百分比"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton)


class SelectionBar(QWidget):
    """Phase 3: 拾取模式状态条"""

    assignRequested = Signal()               # 点击"分配"按钮
    clearRequested = Signal()               # 点击"清空"
    commitRequested = Signal()              # 按 Enter（外层按键事件转发）

    def __init__(self, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 4, 6, 4)
        h.setSpacing(8)

        self.label = QLabel("未选")
        self.label.setMinimumWidth(220)
        h.addWidget(self.label)

        self.btn_assign = QPushButton("分配到当前 BOQ")
        self.btn_assign.setEnabled(False)
        self.btn_assign.clicked.connect(self.assignRequested)
        h.addWidget(self.btn_assign)

        self.btn_clear = QPushButton("清空选择")
        self.btn_clear.setEnabled(False)
        self.btn_clear.clicked.connect(self.clearRequested)
        h.addWidget(self.btn_clear)

        h.addStretch(1)

        self.zoom_label = QLabel("缩放 100%")
        self.zoom_label.setMinimumWidth(80)
        self.zoom_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(self.zoom_label)

    def set_pending_count(self, n: int):
        if n <= 0:
            self.label.setText("未选（双击或框选图形）")
            self.btn_assign.setEnabled(False)
            self.btn_clear.setEnabled(False)
        else:
            self.label.setText(f"已选 {n} 个  →  点击 BOQ 表格条目 / 按 Enter 分配")
            self.btn_assign.setEnabled(True)
            self.btn_clear.setEnabled(True)

    def set_zoom(self, scale: float):
        self.zoom_label.setText(f"缩放 {scale*100:.0f}%")
