"""UI 工具类：屏幕适配 / 窗口居中 / 状态持久化 / 按钮工厂。

所有新代码优先使用这些工具，替代散落的 resize() / setStyleSheet() 调用。
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication, QPushButton, QWidget,
)

from . import theme

# ============================================================
# Friendly message boxes  (P0-6)
# ============================================================

def error_box(parent, title: str, hint: str, detail: str = "",
              log: object = None) -> None:
    """友好错误弹窗：给用户「原因+建议」而非原始堆栈。

    Args:
        parent: 父窗口
        title: 弹窗标题
        hint: 面向用户的一句/几句原因与解决方案
        detail: 技术详情（堆栈/原始异常），用户点「显示详情」查看
        log_extra: 可选，用于记录日志（None 则不记）
    """
    _message_box_with_detail(parent, "critical", title, hint, detail)

def warning_box(parent, title: str, hint: str, detail: str = "") -> None:
    """友好警告弹窗（同上，级别为警告）。"""
    _message_box_with_detail(parent, "warning", title, hint, detail)

def info_box(parent, title: str, text: str) -> None:
    """信息弹窗（无 detail）。"""
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information(parent, title, text)

def _message_box_with_detail(parent, kind: str, title: str,
                             hint: str, detail: str) -> None:
    """QMessageBox 封装：detail 非空时加「显示详情」按钮弹出原始信息。"""
    from PySide6.QtWidgets import (QMessageBox, QTextEdit, QDialog,
                               QVBoxLayout, QHBoxLayout, QPushButton)

    detail = (detail or "").strip()
    if not detail:
        # 无详情：直接标准弹窗
        if kind == "critical":
            QMessageBox.critical(parent, title, hint)
        else:
            QMessageBox.warning(parent, title, hint)
        return

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Critical if kind == "critical" else QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(hint)
    box.setStandardButtons(QMessageBox.Ok)
    btn_detail = box.addButton("显示详情", QMessageBox.ActionRole)

    def _show_detail():
        dlg = QDialog(box)
        dlg.setWindowTitle("技术详情")
        dlg.resize(620, 360)
        lay = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(detail)
        lay.addWidget(te, 1)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)
        dlg.exec()

    btn_detail.clicked.connect(_show_detail)
    box.exec()


# ============================================================
# Screen / Dialog Fitting
# ============================================================

def get_available_geometry(widget: QWidget):
    """获取 widget 所在屏幕的可用几何区域（排除任务栏）。"""
    screen = widget.screen() or QApplication.primaryScreen()
    if screen is None:
        return None
    return screen.availableGeometry()


def fit_dialog_to_screen(dialog, preferred: tuple[int, int] | None = None,
                         policy: str = "medium", avail=None):
    """根据屏幕可用尺寸 clamp Dialog 大小并居中到父窗口。

    Args:
        dialog: QDialog 实例
        preferred: (width, height) 期望尺寸；None 则用 DIALOG_PREFERRED[policy]
        policy: "small" / "medium" / "large" / "review" / "config" / "fullscreen"
        avail: 可选，QRect 可用区域（测试注入用）；None 则取 dialog 所在屏幕
    """
    if preferred is None:
        preferred = theme.DIALOG_PREFERRED.get(policy, (720, 540))

    if avail is None:
        avail = get_available_geometry(dialog)
    if avail is None:
        # 无屏幕信息时直接用 preferred
        dialog.resize(*preferred)
        return

    max_ratio = theme.DIALOG_SIZE_POLICY.get(policy, (0.80, 0.80))
    max_w = int(avail.width() * max_ratio[0])
    max_h = int(avail.height() * max_ratio[1])

    # 期望尺寸 clamp 到屏幕可用区域
    w = min(preferred[0], max_w)
    h = min(preferred[1], max_h)

    # 最小下限（仅当屏幕放得下时生效；屏幕比 minimumSize 还小时
    # 主动降低 minimumSize，避免 setMinimumSize 把 clamp 顶回去导致超出屏幕）
    min_w = max(dialog.minimumWidth(), 400)
    min_h = max(dialog.minimumHeight(), 300)
    if max_w >= min_w:
        w = max(w, min_w)
    else:
        dialog.setMinimumWidth(max_w)
        w = max_w
    if max_h >= min_h:
        h = max(h, min_h)
    else:
        dialog.setMinimumHeight(max_h)
        h = max_h

    dialog.resize(w, h)
    center_on_parent(dialog)


def center_on_parent(dialog):
    """将 Dialog 居中到父窗口（而非 primaryScreen）。"""
    parent = dialog.parentWidget()
    if parent is None:
        # 无父窗口 → 居中到可用屏幕
        avail = get_available_geometry(dialog)
        if avail is not None:
            dialog.move(
                avail.x() + (avail.width() - dialog.width()) // 2,
                avail.y() + (avail.height() - dialog.height()) // 2
            )
        return

    # 居中到父窗口
    px = parent.x() + (parent.width() - dialog.width()) // 2
    py = parent.y() + (parent.height() - dialog.height()) // 2

    # 确保 dialog 不超出可用屏幕
    avail = get_available_geometry(dialog)
    if avail is not None:
        px = max(avail.x(), min(px, avail.x() + avail.width() - dialog.width()))
        py = max(avail.y(), min(py, avail.y() + avail.height() - dialog.height()))

    dialog.move(px, py)


# ============================================================
# Window State Persistence
# ============================================================

def save_window_state(settings, main_window, splitter=None):
    """保存主窗口完整状态到 QSettings。"""
    settings.setValue("geometry", main_window.saveGeometry())
    if splitter is not None:
        settings.setValue("splitter", splitter.saveState())
    settings.setValue("dark", getattr(main_window, "_dark", False))
    settings.setValue("fullscreen", getattr(main_window, "_fullscreen", False))
    # 左右栏可见性
    left = getattr(main_window, "_left_panel", None)
    right = getattr(main_window, "_right_panel", None)
    if left is not None:
        settings.setValue("left_visible", left.isVisible())
    if right is not None:
        settings.setValue("right_visible", right.isVisible())
    # 当前 tab
    tabs = getattr(main_window, "right_tabs", None)
    if tabs is not None:
        settings.setValue("right_tab_index", tabs.currentIndex())
    # 最近项目 ID
    pid = getattr(main_window, "_project_id", None)
    if pid is not None:
        settings.setValue("recent_project_id", pid)


def restore_window_state(settings, main_window, splitter=None):
    """从 QSettings 恢复主窗口完整状态。返回 True 表示成功恢复。"""
    restored = False
    geom = settings.value("geometry")
    if geom:
        main_window.restoreGeometry(geom)
        restored = True

    if splitter is not None:
        sp = settings.value("splitter")
        if sp:
            splitter.restoreState(sp)

    dark = settings.value("dark", False, type=bool)
    if dark:
        main_window._dark = False
        tb = getattr(main_window, "canvas_toolbar", None)
        if tb and hasattr(tb, "btn_theme"):
            tb.btn_theme.setChecked(True)
            main_window._on_theme_toggle()

    # 恢复面板可见性
    left = getattr(main_window, "_left_panel", None)
    right = getattr(main_window, "_right_panel", None)
    if left is not None:
        lv = settings.value("left_visible", True, type=bool)
        left.setVisible(lv)
        tb = getattr(main_window, "canvas_toolbar", None)
        if tb and hasattr(tb, "btn_left"):
            tb.btn_left.setChecked(lv)
    if right is not None:
        rv = settings.value("right_visible", True, type=bool)
        right.setVisible(rv)
        tb = getattr(main_window, "canvas_toolbar", None)
        if tb and hasattr(tb, "btn_right"):
            tb.btn_right.setChecked(rv)

    # 恢复 tab index
    tabs = getattr(main_window, "right_tabs", None)
    if tabs is not None:
        idx = settings.value("right_tab_index", 0, type=int)
        if 0 <= idx < tabs.count():
            tabs.setCurrentIndex(idx)

    return restored


# ============================================================
# Button Factory
# ============================================================

def create_primary_button(text: str, parent=None) -> QPushButton:
    """主操作按钮（蓝色填充）。"""
    btn = QPushButton(text, parent)
    btn.setObjectName("primaryBtn")
    return btn


def create_danger_button(text: str, parent=None) -> QPushButton:
    """危险操作按钮（红色填充）。"""
    btn = QPushButton(text, parent)
    btn.setObjectName("dangerBtn")
    return btn


def create_secondary_button(text: str, parent=None) -> QPushButton:
    """次要按钮（白底蓝边）。"""
    btn = QPushButton(text, parent)
    return btn


# ============================================================
# Dialog Helpers
# ============================================================

def make_scrollable(content_widget: QWidget, parent=None) -> QWidget:
    """将 content_widget 包裹在 QScrollArea 中。

    用于 Dialog 内容区：Header 固定 + Content 滚动 + Footer 固定。
    """
    from PySide6.QtWidgets import QScrollArea

    scroll = QScrollArea(parent)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setWidget(content_widget)
    scroll.setObjectName("dialogScrollArea")
    return scroll
