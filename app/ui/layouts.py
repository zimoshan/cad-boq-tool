"""统一间距 / 布局常量 + 布局工厂。

替代各文件中散落的 setContentsMargins(7, 11, 13, ...) 等随机值。
"""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QFormLayout

from . import theme


# ============================================================
# Layout Factory — 统一 margins / spacing
# ============================================================

def vbox(margins: int = theme.PANEL_MARGIN, spacing: int = theme.PANEL_SPACING) -> QVBoxLayout:
    """标准垂直布局。"""
    lay = QVBoxLayout()
    lay.setContentsMargins(margins, margins, margins, margins)
    lay.setSpacing(spacing)
    return lay


def hbox(margins: int = 0, spacing: int = theme.SP_2) -> QHBoxLayout:
    """标准水平布局。"""
    lay = QHBoxLayout()
    lay.setContentsMargins(margins, margins, margins, margins)
    lay.setSpacing(spacing)
    return lay


def form(spacing: int = theme.SP_2) -> QFormLayout:
    """标准表单布局。"""
    lay = QFormLayout()
    lay.setSpacing(spacing)
    lay.setLabelAlignment(__import__('PySide6').QtCore.Qt.AlignRight)
    return lay


def tight_vbox() -> QVBoxLayout:
    """紧凑垂直布局（零边距，4px spacing）。"""
    lay = QVBoxLayout()
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(theme.SP_1)
    return lay


def dialog_vbox() -> QVBoxLayout:
    """Dialog 标准布局。"""
    lay = QVBoxLayout()
    lay.setContentsMargins(
        theme.DIALOG_MARGIN, theme.DIALOG_MARGIN,
        theme.DIALOG_MARGIN, theme.DIALOG_MARGIN
    )
    lay.setSpacing(theme.DIALOG_SPACING)
    return lay
