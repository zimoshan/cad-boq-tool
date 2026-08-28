"""实体属性面板（v3）：画布当前选择的对象摘要。

数据源：canvas.pending_summary()（主窗口在待选变化时推送）。
操作：「分配至清单项」→ 主窗口 _commit_pending（与选择条/Enter 同一入口）。
"""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame,
                               QGridLayout, QPushButton)

from . import theme as T


class EntityPropertiesPanel(QWidget):
    """对象摘要：实体数 / 类型分布 / 图层分布 + 分配入口。"""

    assignRequested = Signal()      # 分配至清单项（转发到 _commit_pending）

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.lbl_context = QLabel("当前选择：0 个实体")
        self.lbl_context.setObjectName("secTitle")
        root.addWidget(self.lbl_context)

        # 对象摘要卡片
        card = QFrame()
        card.setObjectName("panel")
        card.setStyleSheet(
            f"QFrame {{ background: {T.SURFACE}; border: 1px solid {T.BORDER};"
            f" border-radius: 4px; }}")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(10, 8, 10, 10)
        cap = QLabel("对象摘要")
        cap.setStyleSheet(
            f"color:{T.TEXT_PRIMARY}; font-weight:{T.FONT_WEIGHT_SEMIBOLD};"
            f" border:none; background:transparent;")
        cv.addWidget(cap)
        cap.setStyleSheet(cap.styleSheet() +
                          f"border-bottom: 1px solid {T.BORDER}; padding-bottom: 5px;")

        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(12)
        self.val_count = QLabel("—")
        self.val_types = QLabel("—")
        self.val_layers = QLabel("—")
        self.val_types.setWordWrap(True)
        self.val_layers.setWordWrap(True)
        for row, (name, val) in enumerate((
                ("实体数", self.val_count),
                ("类型", self.val_types),
                ("所属图层", self.val_layers))):
            key = QLabel(name)
            key.setStyleSheet(
                f"color:{T.TEXT_SECONDARY}; border:none; background:transparent;")
            val.setStyleSheet(
                f"color:{T.TEXT_PRIMARY}; border:none; background:transparent;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(key, row, 0)
            grid.addWidget(val, row, 1)
        grid.setColumnStretch(1, 1)
        cv.addLayout(grid)
        root.addWidget(card)

        root.addStretch(1)

        self.btn_assign = QPushButton("分配至清单项")
        self.btn_assign.setObjectName("primaryBtn")
        self.btn_assign.setToolTip("把当前待选实体分配到选中的 BOQ 条目（同 Enter / 选择条「分配」）")
        self.btn_assign.setEnabled(False)
        self.btn_assign.clicked.connect(self.assignRequested)
        root.addWidget(self.btn_assign)

        self.hint = QLabel("拾取模式下在画布点选/框选实体后，此处显示对象摘要。")
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(
            f"color:{T.TEXT_DISABLED};font-size:{T.FONT_SIZE_CAPTION}px;")
        root.addWidget(self.hint)

    # ---------- 数据 ----------
    def update_from_summary(self, rows: list[tuple[int, str, str]]):
        """rows: canvas.pending_summary() 结果 [(eid, layer, dxf_type)]。"""
        n = len(rows)
        self.lbl_context.setText(f"当前选择：{n} 个实体")
        self.btn_assign.setEnabled(n > 0)
        if not n:
            self.val_count.setText("—")
            self.val_types.setText("—")
            self.val_layers.setText("—")
            return
        self.val_count.setText(str(n))
        types = Counter(t for _, _, t in rows if t)
        layers = Counter(l for _, l, _ in rows if l)
        self.val_types.setText(self._fmt_counter(types))
        self.val_layers.setText(self._fmt_counter(layers))

    @staticmethod
    def _fmt_counter(counter: Counter, top: int = 3) -> str:
        if not counter:
            return "—"
        items = counter.most_common(top)
        parts = [f"{k}×{v}" for k, v in items]
        rest = sum(counter.values()) - sum(v for _, v in items)
        if rest > 0:
            parts.append(f"等 {len(counter)} 类")
        return "、".join(parts)
