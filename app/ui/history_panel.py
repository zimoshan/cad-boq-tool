"""操作记录面板（v3）：状态栏消息环形缓存的时间轴视图。

数据源与状态栏「🕘 记录」浮层同源（main_window._history，
messageChanged 钩子自动抓取所有 showMessage 调用点）。
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton)

from . import theme as T

HISTORY_CAP = 200


class HistoryPanel(QWidget):
    """最近操作时间轴：新消息置顶，显示 时分秒 + 文本。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        title = QLabel("本项目最近操作")
        title.setObjectName("secTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setToolTip("仅清空本列表显示，不影响已执行的操作")
        self.btn_clear.clicked.connect(lambda: self.list.clear())
        head.addWidget(self.btn_clear)
        root.addLayout(head)

        self.list = QListWidget()
        self.list.setSelectionMode(self.list.SelectionMode.NoSelection)
        self.list.setAlternatingRowColors(True)
        root.addWidget(self.list, 1)

        self.hint = QLabel("与状态栏消息同源；打开图纸/关联/AI 识别等操作会自动记录。")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(
            f"color:{T.TEXT_DISABLED};font-size:{T.FONT_SIZE_CAPTION}px;")
        root.addWidget(self.hint)

    def add_entry(self, ts: float, text: str):
        """新增一条记录（置顶）。"""
        hh = time.strftime("%H:%M:%S", time.localtime(ts))
        it = QListWidgetItem(f"{hh}  {text}")
        it.setToolTip(text)
        it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.list.insertItem(0, it)
        if self.list.count() > HISTORY_CAP:
            self.list.takeItem(self.list.count() - 1)

    def set_entries(self, history: list[tuple[float, str]]):
        """批量载入（切项目/初始化时）。history 为 [(ts, text)] 旧→新。"""
        self.list.clear()
        for ts, text in reversed(history[-HISTORY_CAP:]):
            self.add_entry(ts, text)
