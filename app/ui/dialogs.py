"""统一 Dialog 工厂 + 基础 Dialog 类型。

替代业务代码中直接 QDialog() 然后自行设计。

类型：
- BaseDialog     — 所有 Dialog 基类（自动屏幕适配 + 居中 + QScrollArea）
- ConfirmDialog  — 确认操作（[取消] [确认]）
- ConfigDialog   — 复杂配置（Header + Scrollable Content + Footer）
- ProgressDialog — 进度（与 QProgressDialog 兼容但统一样式）
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
)

from . import theme
from .ui_utils import fit_dialog_to_screen, make_scrollable


# ============================================================
# BaseDialog — 所有自定义 Dialog 的基类
# ============================================================

class BaseDialog(QDialog):
    """自动适配屏幕 + 居中父窗口 + 可选滚动。

    子类通过 set_content_widget() 设置主内容区，
    通过 set_footer_buttons() 设置底部按钮行。
    """

    def __init__(self, parent=None, title: str = "", policy: str = "medium",
                 preferred: tuple[int, int] | None = None,
                 scrollable: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._policy = policy
        self._preferred = preferred
        self._scrollable = scrollable
        self._content_widget: QWidget | None = None
        self._footer_layout: QHBoxLayout | None = None

        self._build_skeleton()

    def _build_skeleton(self):
        """构建 Header + Content + Footer 三段结构。"""
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(
            theme.DIALOG_MARGIN, theme.DIALOG_MARGIN,
            theme.DIALOG_MARGIN, theme.DIALOG_MARGIN
        )
        self._root.setSpacing(theme.DIALOG_SPACING)

        # Content 区（子类填充）
        self._content_container = QVBoxLayout()
        self._root.addLayout(self._content_container, 1)

        # Footer 按钮行
        self._footer_layout = QHBoxLayout()
        self._footer_layout.addStretch(1)
        self._root.addLayout(self._footer_layout)

    def set_content_widget(self, widget: QWidget):
        """设置主内容区。如果 scrollable=True，包裹 QScrollArea。"""
        if self._content_widget is not None:
            self._content_widget.deleteLater()
        self._content_widget = widget
        if self._scrollable:
            scroll = make_scrollable(widget, self)
            self._content_container.addWidget(scroll)
        else:
            self._content_container.addWidget(widget)

    def add_footer_button(self, text: str, role: str = "secondary",
                          on_click=None) -> QPushButton:
        """在底部按钮行添加一个按钮。

        role: "primary" / "secondary" / "danger"
        """
        from .ui_utils import create_primary_button, create_danger_button, create_secondary_button
        if role == "primary":
            btn = create_primary_button(text, self)
        elif role == "danger":
            btn = create_danger_button(text, self)
        else:
            btn = create_secondary_button(text, self)
        if on_click:
            btn.clicked.connect(on_click)
        # 插到 stretch 后面
        self._footer_layout.insertWidget(self._footer_layout.count() - 1, btn)
        return btn

    def showEvent(self, event):
        """在 show 时 fit 到屏幕。"""
        if not hasattr(self, "_fitted"):
            fit_dialog_to_screen(self, self._preferred, self._policy)
            self._fitted = True
        super().showEvent(event)


# ============================================================
# ConfirmDialog — 确认操作
# ============================================================

class ConfirmDialog(BaseDialog):
    """简单确认对话框：消息 + [取消] [确认]。

    用法:
        dlg = ConfirmDialog(parent, "删除项目？", "该操作将删除所有图纸和映射。", danger=True)
        if dlg.exec() == QDialog.Accepted:
            ...
    """

    def __init__(self, parent=None, title: str = "确认", message: str = "",
                 confirm_text: str = "确认", cancel_text: str = "取消",
                 danger: bool = False, policy: str = "small"):
        super().__init__(parent, title, policy=policy, scrollable=False)
        self._build_content(message, confirm_text, cancel_text, danger)

    def _build_content(self, message, confirm_text, cancel_text, danger):
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        self.set_content_widget(msg_label)

        self.add_footer_button(cancel_text, "secondary", self.reject)
        role = "danger" if danger else "primary"
        self.add_footer_button(confirm_text, role, self.accept)


# ============================================================
# ConfigDialog — 复杂配置（可滚动）
# ============================================================

class ConfigDialog(BaseDialog):
    """复杂配置对话框：Header + Scrollable Content + Footer。

    用法:
        dlg = ConfigDialog(parent, "项目设置", policy="config")
        dlg.set_content_widget(my_config_widget)
        dlg.add_footer_button("取消", "secondary", dlg.reject)
        dlg.add_footer_button("保存", "primary", dlg.accept)
    """

    def __init__(self, parent=None, title: str = "", policy: str = "config",
                 preferred: tuple[int, int] | None = None,
                 scrollable: bool = True):
        super().__init__(parent, title, policy=policy,
                        preferred=preferred, scrollable=scrollable)


# ============================================================
# DialogFactory — 统一创建入口
# ============================================================

class DialogFactory:
    """统一 Dialog 创建工厂。

    业务代码不再直接 QDialog()，而是通过此工厂创建。
    """

    @staticmethod
    def confirm(parent, title: str, message: str,
                confirm_text: str = "确认", cancel_text: str = "取消",
                danger: bool = False) -> ConfirmDialog:
        return ConfirmDialog(parent, title, message,
                             confirm_text, cancel_text, danger)

    @staticmethod
    def config(parent, title: str, scrollable: bool = True,
                policy: str = "config") -> ConfigDialog:
        return ConfigDialog(parent, title, policy=policy, scrollable=scrollable)

    @staticmethod
    def review(parent, title: str, scrollable: bool = False) -> ConfigDialog:
        """AI 审核专用 Dialog（不滚动，表格自身有滚动）。"""
        return ConfigDialog(parent, title, policy="review", scrollable=scrollable)
