"""项目属性面板：显示/编辑当前项目的基础信息（类型/区域/专业/备注）。

十六、项目设置类窗口优先考虑改为侧边属性区。
简单属性不弹 Dialog，直接在右侧 Properties Panel 编辑。
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QTextEdit, QPushButton, QFormLayout)

from .. import db


class ProjectPropertiesPanel(QWidget):
    """右侧项目属性面板：类型/区域/专业/备注 + 保存按钮"""

    propertiesChanged = Signal()   # 保存后发出，供主窗口刷新状态

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_id = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        title = QLabel("项目属性")
        title.setObjectName("secTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(4)

        self.edit_type = QLineEdit()
        self.edit_type.setPlaceholderText("如：医院、办公楼、住宅...")
        form.addRow("类型:", self.edit_type)

        self.edit_region = QLineEdit()
        self.edit_region.setPlaceholderText("如：Benghazi、Tripoli...")
        form.addRow("区域:", self.edit_region)

        self.edit_specialty = QLineEdit()
        self.edit_specialty.setPlaceholderText("如：电气、暖通、给排水...")
        form.addRow("专业:", self.edit_specialty)

        self.edit_notes = QTextEdit()
        self.edit_notes.setMaximumHeight(80)
        self.edit_notes.setPlaceholderText("项目备注...")
        form.addRow("备注:", self.edit_notes)

        root.addLayout(form)

        # 保存按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_save = QPushButton("保存属性")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

        root.addStretch(1)

    def refresh_enabled(self, has_project: bool):
        """P1-12：无项目时禁用「保存属性」并清空可编辑表单。"""
        self.btn_save.setEnabled(has_project)
        for e in (self.edit_type, self.edit_region, self.edit_specialty, self.edit_notes):
            e.setEnabled(has_project)

    def load_project(self, project_id: int | None):
        self._project_id = project_id
        self.refresh_enabled(project_id is not None)
        if project_id is None:
            self._clear()
            return
        m = db.get_project_config(project_id)["meta"]
        self.edit_type.setText(m.get("type", ""))
        self.edit_region.setText(m.get("region", ""))
        self.edit_specialty.setText(m.get("specialty", ""))
        self.edit_notes.setPlainText(m.get("notes", ""))

    def _clear(self):
        self.edit_type.clear()
        self.edit_region.clear()
        self.edit_specialty.clear()
        self.edit_notes.clear()

    def _on_save(self):
        if self._project_id is None:
            return
        meta = {
            "type": self.edit_type.text().strip(),
            "region": self.edit_region.text().strip(),
            "specialty": self.edit_specialty.text().strip(),
            "notes": self.edit_notes.toPlainText().strip(),
        }
        db.set_project_config(self._project_id, meta=meta)
        self.propertiesChanged.emit()

    def get_meta(self) -> dict:
        return {
            "type": self.edit_type.text().strip(),
            "region": self.edit_region.text().strip(),
            "specialty": self.edit_specialty.text().strip(),
            "notes": self.edit_notes.toPlainText().strip(),
        }
