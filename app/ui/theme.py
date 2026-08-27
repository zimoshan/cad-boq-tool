"""统一主题系统：颜色 / 字体 / 间距 / QSS 生成。

替换原来散落在 9 个文件中的 18 种硬编码颜色。
所有 UI 组件应从此模块导入常量，不再内联颜色值。
"""
from __future__ import annotations

# ============================================================
# Color Palette  (单一真相源)
# ============================================================

# --- Backgrounds ---
BACKGROUND       = "#F4F6F9"   # 应用底色
SURFACE         = "#FFFFFF"   # 面板/卡片
SURFACE_ALT     = "#EEF1F5"   # 画布底纹
CANVAS_BG       = "#EEF1F5"
CANVAS_DOT      = "#CDD6E2"

# --- Borders ---
BORDER          = "#E3E8EF"
BORDER_INPUT    = "#D5DCE6"
BORDER_HOVER    = "#185FA5"

# --- Text ---
TEXT_PRIMARY    = "#1F2733"
TEXT_SECONDARY  = "#5A6675"
TEXT_DISABLED   = "#9AA1AC"
TEXT_HINT       = "#666666"

# --- Accent ---
ACCENT          = "#185FA5"   # 腾讯蓝
ACCENT_HOVER    = "#0C447C"
ACCENT_LIGHT    = "#EAF2FB"    # pressed bg

# --- Semantic ---
SUCCESS         = "#16A34A"
SUCCESS_HOVER   = "#22C55E"
SUCCESS_LIGHT   = "#DCFCE7"
SUCCESS_BG      = "#1a7a2f"
WARNING         = "#F59E0B"
WARNING_LIGHT   = "#FEF3C7"
WARNING_TEXT    = "#b8860b"
ERROR           = "#DC2626"
ERROR_LIGHT     = "#FEE2E2"

# --- Selection ---
SELECTION       = "#DBE9F7"   # 浅蓝选中底
HOVER           = "#F2F6FC"    # hover 行底色

# --- Splitter ---
SPLITTER_BG     = "#E3E8EF"
SPLITTER_HOVER  = "#185FA5"

# --- Scrollbar ---
SCROLLBAR_BG    = "#F4F6F9"
SCROLLBAR_HANDLE = "#C9D2DE"

# --- Button hierarchy ---
BTN_PRIMARY_BG     = ACCENT
BTN_PRIMARY_HOVER  = ACCENT_HOVER
BTN_PRIMARY_TEXT   = "#FFFFFF"

BTN_SECONDARY_BG   = SURFACE
BTN_SECONDARY_BORDER = BORDER_INPUT
BTN_SECONDARY_TEXT  = TEXT_PRIMARY

BTN_DANGER_BG      = ERROR
BTN_DANGER_HOVER   = "#B91C1C"
BTN_DANGER_TEXT    = "#FFFFFF"

BTN_DISABLED_BG    = "#94A3B8"

# --- Canvas (light/dark themes) ---
CANVAS_DEFAULT_LIGHT  = "#3C3C3C"
CANVAS_DEFAULT_DARK   = "#B4B4B4"
CANVAS_BG_DARK        = "#1E1E1E"
CANVAS_RUBBER_LIGHT   = "#0078D7"
CANVAS_RUBBER_DARK    = "#00B4FF"
CANVAS_HOVER_LIGHT    = "#FFC800"
CANVAS_HOVER_DARK     = "#FFDC50"
CANVAS_SELECTED_LIGHT = "#FFB400"
CANVAS_SELECTED_DARK  = "#FFC828"
CANVAS_MAPPED_LIGHT   = "#1E64DC"
CANVAS_MAPPED_DARK    = "#64AAFF"
CANVAS_CROSS_ERROR    = "#C83C3C"
CANVAS_HIGHLIGHT_DASH = "#FFC800"

# --- Confidence colors (AI results) ---
CONFIDENCE_HIGH       = "#DCFCE7"    # 绿
CONFIDENCE_MID        = "#FEF3C7"    # 橙
CONFIDENCE_LOW        = "#FEE2E2"    # 红
CONFLICT_BG           = "#FCD4D4"

# --- Flash highlight ---
FLASH_COLORS          = ["#FFEB78", "#FFFFC8"]

# --- Selection / Interaction ---
SELECTED_TEXT          = "#FFFFFF"
CHECKBOX_BORDER       = "#C2CCDA"
CHECKBOX_TEXT          = "#3A4654"
TOOLTIP_BG            = TEXT_PRIMARY
TOOLTIP_TEXT          = "#FFFFFF"

# ============================================================
# Typography
# ============================================================

FONT_FAMILY      = '"Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif'

# Font sizes (px)
FONT_SIZE_APP_TITLE  = 15   # 顶栏品牌
FONT_SIZE_SECTION    = 14   # 区块标题
FONT_SIZE_PANEL      = 13   # 面板标题
FONT_SIZE_BODY       = 13   # 正文
FONT_SIZE_SECONDARY  = 12   # 次要文字
FONT_SIZE_CAPTION    = 11   # 说明/提示
FONT_SIZE_STATUS     = 11   # 状态栏

# Font weights
FONT_WEIGHT_NORMAL   = 400
FONT_WEIGHT_MEDIUM    = 500
FONT_WEIGHT_SEMIBOLD  = 600

# ============================================================
# Spacing System  (4px base unit)
# ============================================================

SP_1  = 4     # 最小间距
SP_2  = 8     # 默认间距
SP_3  = 12    # 组件间
SP_4  = 16    # 区块间
SP_5  = 20    # 大区块间
SP_6  = 24
SP_8  = 32
SP_12 = 48

# Dialog margins
DIALOG_MARGIN    = 16
DIALOG_SPACING   = 8

# Panel margins
PANEL_MARGIN     = 8
PANEL_SPACING    = 4

# ============================================================
# Layout Constants
# ============================================================

# Main window
MAIN_WINDOW_DEFAULT_W = 1440
MAIN_WINDOW_DEFAULT_H = 900
MAIN_WINDOW_MIN_W     = 1024
MAIN_WINDOW_MIN_H     = 600

# Left panel
LEFT_PANEL_MIN_W      = 200
LEFT_PANEL_MAX_W      = 360
LEFT_PANEL_DEFAULT_W  = 260

# Right panel
RIGHT_PANEL_MIN_W     = 320
RIGHT_PANEL_DEFAULT_W = 360

# Canvas
CANVAS_MIN_W          = 400

# Top bar
TOPBAR_HEIGHT         = 52

# Splitter stretch factors
STRETCH_LEFT    = 0
STRETCH_CENTER  = 5
STRETCH_RIGHT   = 2

# ============================================================
# Dialog Size Policy  (screen-relative)
# ============================================================

# (max_width_ratio, max_height_ratio) relative to available screen
DIALOG_SIZE_POLICY = {
    "small":   (0.40, 0.40),
    "medium":  (0.60, 0.65),
    "large":   (0.80, 0.80),
    "review":  (0.75, 0.70),
    "config":  (0.70, 0.75),
    "fullscreen": (0.95, 0.90),
}

# Dialog preferred sizes (before clamping)
DIALOG_PREFERRED = {
    "small":   (480, 320),
    "medium":  (720, 540),
    "large":   (1100, 700),
    "review":  (1100, 600),
    "config":  (1000, 700),
    "fullscreen": (1400, 900),
}


# ============================================================
# QSS Generation  (从常量生成，替代硬编码 QSS 字符串)
# ============================================================

def generate_main_qss() -> str:
    """生成全局 QSS — 专业 CAD/IDE 风格：紧凑间距、小圆角、清晰边界。"""
    return f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE_BODY}px;
}}
QWidget#panel {{ background-color: {SURFACE}; }}
QLabel {{ background: transparent; }}
QCheckBox {{ background: transparent; }}

QSplitter::handle:horizontal {{
    background: {SPLITTER_BG};
    width: 1px;
    margin: 0;
}}
QSplitter::handle:horizontal:hover {{ background: {SPLITTER_HOVER}; }}

QToolBar {{
    background: transparent;
    border: none;
    spacing: {SP_1}px;
    padding: 2px 3px;
}}
QToolBar QLabel {{ color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_SECONDARY}px; }}

QWidget#topbar {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
QLabel#brand {{ font-size: {FONT_SIZE_APP_TITLE}px; font-weight: {FONT_WEIGHT_SEMIBOLD}; color: {TEXT_PRIMARY}; }}
QLabel#brandSub {{ font-size: {FONT_SIZE_CAPTION}px; color: {TEXT_DISABLED}; }}

QPushButton#primaryBtn {{
    background: {BTN_PRIMARY_BG};
    border: 1px solid {BTN_PRIMARY_BG};
    color: {BTN_PRIMARY_TEXT};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}
QPushButton#primaryBtn:hover {{ background: {BTN_PRIMARY_HOVER}; border-color: {BTN_PRIMARY_HOVER}; }}
QPushButton#primaryBtn:pressed {{ background: {BTN_PRIMARY_HOVER}; }}

QPushButton#dangerBtn {{
    background: {BTN_DANGER_BG};
    border: 1px solid {BTN_DANGER_BG};
    color: {BTN_DANGER_TEXT};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}
QPushButton#dangerBtn:hover {{ background: {BTN_DANGER_HOVER}; border-color: {BTN_DANGER_HOVER}; }}

QLabel#secTitle {{
    color: {TEXT_SECONDARY};
    font-size: {FONT_SIZE_CAPTION}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    padding: 1px 2px;
}}

QPushButton#collapseBtn {{
    background: transparent;
    border: none;
    border-top: 1px solid {BORDER};
    border-radius: 0;
    color: {TEXT_SECONDARY};
    padding: 4px;
    font-size: {FONT_SIZE_CAPTION}px;
}}

QWidget#canvasWrap {{ background: {SURFACE_ALT}; }}
QWidget#floatBar {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 3px;
}}
QWidget#selOverlay {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 3px;
}}
QLabel#hintLabel {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 3px;
    color: {TEXT_DISABLED};
    font-size: {FONT_SIZE_CAPTION}px;
    padding: 3px 8px;
}}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BTN_SECONDARY_BORDER};
    border-radius: 3px;
    padding: 3px 8px;
    color: {TEXT_PRIMARY};
}}
QPushButton:hover {{ border-color: {BORDER_HOVER}; color: {BORDER_HOVER}; }}
QPushButton:pressed {{ background: {ACCENT_LIGHT}; }}
QPushButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: {SELECTED_TEXT}; }}
QPushButton:disabled {{ color: {TEXT_DISABLED}; border-color: {BORDER}; }}

QComboBox {{
    border: 1px solid {BORDER_INPUT};
    border-radius: 3px;
    padding: 3px 6px;
    background: {SURFACE};
    min-height: 20px;
}}
QComboBox:hover {{ border-color: {BORDER_HOVER}; }}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER_INPUT};
    background: {SURFACE};
    selection-background-color: {ACCENT};
    selection-color: {SELECTED_TEXT};
}}

QCheckBox {{ spacing: 4px; color: {CHECKBOX_TEXT}; }}
QCheckBox::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {CHECKBOX_BORDER}; border-radius: 2px; background: {SURFACE};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QListWidget, QTreeWidget, QTableWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 2px;
    gridline-color: {SURFACE_ALT};
    outline: 0;
}}
QListWidget::item:hover, QTreeWidget::item:hover, QTableWidget::item:hover {{ background: {HOVER}; }}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background: {ACCENT}; color: {SELECTED_TEXT};
}}
QHeaderView::section {{
    background: {BACKGROUND};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 4px 6px;
    color: {TEXT_SECONDARY};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

QTabWidget::pane {{ border: none; background: {SURFACE}; }}
QTabBar::tab {{
    background: {BACKGROUND};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-radius: 3px 3px 0 0;
    padding: 5px 12px;
    color: {TEXT_SECONDARY};
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {SURFACE};
    color: {ACCENT};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    border-bottom: 2px solid {ACCENT};
}}

QStatusBar {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_SECONDARY};
    padding: 2px 6px;
}}

QPushButton#llmStatusBtn {{
    background: transparent;
    border: 1px solid {ACCENT};
    border-radius: 3px;
    color: {ACCENT};
    padding: 2px 10px;
    font-size: {FONT_SIZE_STATUS}px;
}}
QPushButton#llmStatusBtn:hover {{ background: {ACCENT_LIGHT}; }}

QMenu {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 3px;
}}
QMenu::item {{ padding: 4px 16px; border-radius: 2px; }}
QMenu::item:selected {{ background: {ACCENT}; color: {SELECTED_TEXT}; }}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: {SCROLLBAR_BG};
    width: 8px; height: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {SCROLLBAR_HANDLE}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 2px;
    margin-top: 6px;
    padding: 8px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}

/* ---- 输入控件 ---- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background: {SURFACE};
    border: 1px solid {BORDER_INPUT};
    border-radius: 3px;
    padding: 3px 6px;
    selection-background-color: {ACCENT};
    selection-color: {SELECTED_TEXT};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {BORDER_HOVER}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
    background: {SURFACE};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    color: {TEXT_DISABLED};
    background: {BACKGROUND};
}}

/* ---- 表格 ---- */
QTableWidget {{ alternate-background-color: {SURFACE_ALT}; }}
QTableWidget::item {{ padding: 3px 4px; }}
QHeaderView::section {{
    background: {BACKGROUND};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 4px 6px;
    color: {TEXT_SECONDARY};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}
QTableCornerButton::section {{
    background: {BACKGROUND};
    border: none;
    border-bottom: 1px solid {BORDER};
}}

/* ---- 进度条 ---- */
QProgressBar {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE_CAPTION}px;
    min-height: 12px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ---- ToolTip ---- */
QToolTip {{
    background: {TEXT_PRIMARY};
    color: {TOOLTIP_TEXT};
    border: none;
    border-radius: 2px;
    padding: 3px 6px;
    font-size: {FONT_SIZE_CAPTION}px;
}}

/* ---- QMessageBox 按钮间距 ---- */
QMessageBox QPushButton {{ min-width: 72px; }}
"""


# 全局 QSS 常量（避免各模块重复调用 generate_main_qss）
MAIN_QSS = generate_main_qss()


def generate_item_selected_qss() -> str:
    """统一的 item:selected 样式（浅蓝底 + 保字色 + 无 focus outline）。
    替换 _SELECTED_QSS 和 _LIST_QSS。
    """
    return f"""
QListWidget, QTreeWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    outline: none;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 3px 4px;
    border: 1px solid transparent;
    color: inherit;
}}
QListWidget::item:hover, QTreeWidget::item:hover {{
    background: {HOVER};
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background: {SELECTION};
    color: inherit;
}}
QListWidget::item:selected:focus,
QTreeWidget::item:selected:focus,
QListWidget::item:focus,
QTreeWidget::item:focus {{
    background: {SELECTION};
    color: inherit;
    border: 1px solid transparent;
    outline: none;
}}
QListWidget:focus, QTreeWidget:focus {{ outline: none; }}
QHeaderView::section {{ background: {BACKGROUND}; padding: 4px; border: none; }}
"""
