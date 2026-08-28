"""统一主题系统：颜色 / 字体 / 间距 / QSS 生成。

v3（main.html 原型对齐）：深色顶栏 / 深色画布工具条 + 白色面板。
所有 UI 组件应从此模块导入常量，不再内联颜色值。
"""
from __future__ import annotations

# ============================================================
# Color Palette  (单一真相源)
# ============================================================

# --- Backgrounds ---
BACKGROUND       = "#F1F5F9"   # 应用底色（slate-100）
SURFACE         = "#FFFFFF"   # 面板/卡片
SURFACE_ALT     = "#EEF1F5"   # 画布底纹/交替行（保持画布渲染不受影响）
CANVAS_BG       = "#EEF1F5"
CANVAS_DOT      = "#CDD6E2"

# --- Borders ---
BORDER          = "#E2E8F0"   # slate-200
BORDER_INPUT    = "#CBD5E1"   # slate-300
BORDER_HOVER    = "#0891B2"

# --- Text ---
TEXT_PRIMARY    = "#1E293B"   # slate-800
TEXT_SECONDARY  = "#64748B"   # slate-500
TEXT_DISABLED   = "#94A3B8"   # slate-400
TEXT_HINT       = "#64748B"

# --- Accent（cyan 系） ---
ACCENT          = "#0891B2"   # cyan-600：主强调（选中/激活态）
ACCENT_HOVER    = "#06B6D4"   # cyan-500
ACCENT_BRIGHT   = "#22D3EE"   # cyan-400：深底上的高亮文字/悬停
ACCENT_LINK     = "#0E7490"   # cyan-700：白底文字链接（可读性）
ACCENT_LIGHT    = "#ECFEFF"    # cyan-50：pressed bg
ACCENT_LIGHTER  = "#CFFAFE"   # cyan-100：徽标底

# --- Semantic ---
SUCCESS         = "#059669"   # emerald-600
SUCCESS_HOVER   = "#10B981"   # emerald-500
SUCCESS_LIGHT   = "#ECFDF5"   # emerald-50
SUCCESS_BG      = "#047857"   # emerald-700（深底文字用）
SUCCESS_BORDER  = "#A7F3D0"   # emerald-200
WARNING         = "#F59E0B"
WARNING_LIGHT   = "#FEF3C7"   # amber-100
WARNING_TEXT    = "#B45309"   # amber-700
WARNING_BAR_BG  = "#FFFBEB"   # amber-50：警示条底
WARNING_BAR_TEXT = "#92400E"  # amber-800：警示条文字
ERROR           = "#DC2626"
ERROR_LIGHT     = "#FEE2E2"

# --- Selection ---
SELECTION       = "#D9F4FA"   # 浅青选中底
HOVER           = "#F1F5F9"    # hover 行底色

# --- Splitter ---
SPLITTER_BG     = "#E2E8F0"
SPLITTER_HOVER  = "#0891B2"

# --- Scrollbar ---
SCROLLBAR_BG    = "#F1F5F9"
SCROLLBAR_HANDLE = "#CBD5E1"

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
CANVAS_RUBBER_LIGHT   = "#0891B2"
CANVAS_RUBBER_DARK    = "#22D3EE"
CANVAS_HOVER_LIGHT    = "#F59E0B"
CANVAS_HOVER_DARK     = "#FBBF24"
CANVAS_SELECTED_LIGHT = "#F59E0B"
CANVAS_SELECTED_DARK  = "#FBBF24"
CANVAS_MAPPED_LIGHT   = "#0891B2"
CANVAS_MAPPED_DARK    = "#22D3EE"
CANVAS_CROSS_ERROR    = "#C83C3C"
CANVAS_HIGHLIGHT_DASH = "#F59E0B"

# --- Confidence colors (AI results) ---
# 原型徽标：高置信 cyan-100/cyan-700，中置信 amber-100/amber-700，低置信红
CONFIDENCE_HIGH       = "#CFFAFE"    # cyan-100
CONFIDENCE_MID        = "#FEF3C7"    # amber-100
CONFIDENCE_LOW        = "#FEE2E2"    # 红
CONFLICT_BG           = "#FCD4D4"

# --- Flash highlight ---
FLASH_COLORS          = ["#A5F3FC", "#ECFEFF"]

# --- Selection / Interaction ---
SELECTED_TEXT          = "#FFFFFF"
CHECKBOX_BORDER       = "#CBD5E1"
CHECKBOX_TEXT          = "#334155"
TOOLTIP_BG            = TEXT_PRIMARY
TOOLTIP_TEXT          = "#FFFFFF"

# ============================================================
# Dark Chrome（v3 深色顶栏/工具条/浮层 — main.html 对齐）
# ============================================================

TOPBAR_BG          = "#0F172A"   # slate-900：顶栏
TOPBAR_BORDER      = "#334155"   # slate-700
TOPBAR_BTN_BG      = "#1E293B"   # slate-800
TOPBAR_BTN_BORDER  = "#475569"   # slate-600
TOPBAR_BTN_HOVER   = "#334155"   # slate-700
TOPBAR_TEXT        = "#F1F5F9"   # slate-100
TOPBAR_TEXT_DIM    = "#94A3B8"   # slate-400
TOPBAR_ACCENT_TEXT = "#22D3EE"   # cyan-400：品牌高亮 "CAD·BOQ"

TOOLSTRIP_BG       = "#1E293B"   # 画布工具条
TOOLSTRIP_BORDER   = "#334155"
TOOLSTRIP_TEXT     = "#CBD5E1"   # slate-300

OVERLAY_BG         = "#0F172A"   # 选择条/提示/Toast 浮层
OVERLAY_BORDER     = "#475569"
OVERLAY_TEXT       = "#F1F5F9"
OVERLAY_TEXT_DIM   = "#CBD5E1"
OVERLAY_ACCENT     = "#67E8F9"   # cyan-300：选中计数

CANVAS_AREA_BG     = "#334155"   # 画布区 surround（slate-700）

RAIL_BG            = "#F8FAFC"   # slate-50：右栏图标 rail
RAIL_BORDER        = "#E2E8F0"
RAIL_TEXT          = "#64748B"
RAIL_HOVER         = "#E2E8F0"
RAIL_ACTIVE        = ACCENT

STATUS_FOOT_TEXT   = "#64748B"   # 状态栏文字
STATUS_FOOT_VALUE  = "#334155"   # 状态栏数值

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
RIGHT_RAIL_W          = 45   # v3：右栏图标 rail 宽度

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
    """生成全局 QSS — v3 深色 chrome + 白面板：紧凑间距、小圆角、清晰边界。"""
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

/* ---- 画布区（深色 surround） ---- */
QWidget#canvasWrap {{ background: {CANVAS_AREA_BG}; }}

/* ---- 顶部品牌栏（深色） ---- */
QWidget#topbar {{
    background: {TOPBAR_BG};
    border-bottom: 1px solid {TOPBAR_BORDER};
}}
QWidget#topbar QLabel {{ color: {TOPBAR_TEXT}; background: transparent; }}
QLabel#brandIcon {{
    background: {ACCENT_HOVER};
    border-radius: 4px;
    color: #020617;
    font-size: 17px;
}}
QLabel#brandTitle {{ font-size: 13px; font-weight: {FONT_WEIGHT_SEMIBOLD}; color: {TOPBAR_TEXT}; }}
QLabel#brandSub {{ font-size: 10px; color: {TOPBAR_TEXT_DIM}; }}
QWidget#topbar QPushButton {{
    background: transparent;
    border: 1px solid {TOPBAR_BTN_BORDER};
    border-radius: 4px;
    padding: 5px 12px;
    color: {TOPBAR_TEXT};
    font-size: {FONT_SIZE_SECONDARY}px;
}}
QWidget#topbar QPushButton:hover {{
    background: {TOPBAR_BTN_BG};
    border-color: {ACCENT_HOVER};
}}
QWidget#topbar QPushButton:pressed {{ background: {TOPBAR_BTN_HOVER}; }}
QWidget#topbar QPushButton:disabled {{ color: {TOPBAR_TEXT_DIM}; border-color: {TOPBAR_BORDER}; }}
QWidget#topbar QPushButton#iconBtn {{
    padding: 5px 8px;
    font-size: 14px;
}}
QWidget#topbar QPushButton#heroBtn {{
    background: {ACCENT_HOVER};
    border: 1px solid {ACCENT_HOVER};
    color: #020617;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    padding: 5px 16px;
}}
QWidget#topbar QPushButton#heroBtn:hover {{ background: {ACCENT_BRIGHT}; border-color: {ACCENT_BRIGHT}; }}
QWidget#topbar QPushButton#heroBtn:pressed {{ background: {ACCENT_HOVER}; }}
QWidget#topbar QPushButton#heroBtn:disabled {{ background: {TOPBAR_BTN_BG}; color: {TOPBAR_TEXT_DIM}; }}
QWidget#topbar QComboBox {{
    background: {TOPBAR_BTN_BG};
    border: 1px solid {TOPBAR_BTN_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TOPBAR_TEXT};
    min-height: 20px;
}}
QWidget#topbar QComboBox:hover {{ border-color: {ACCENT_HOVER}; }}
QWidget#topbar QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER_INPUT};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: {SELECTED_TEXT};
}}
QWidget#topbar QComboBox::down-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TOPBAR_TEXT_DIM};
}}

/* ---- 面板头部（v3 1:1：标题+副标题+右侧图标按钮） ---- */
QWidget#panelHeader {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QLabel#panelTitle {{ color: {TEXT_PRIMARY}; font-size: 13px; font-weight: {FONT_WEIGHT_SEMIBOLD}; }}
QLabel#panelSub {{ color: {TEXT_SECONDARY}; font-size: 10px; }}
QPushButton#panelIconBtn {{
    background: transparent; border: none; border-radius: 4px;
    color: {TEXT_DISABLED}; font-size: 15px; padding: 3px;
}}
QPushButton#panelIconBtn:hover {{ background: {ACCENT_LIGHT}; color: {ACCENT_LINK}; }}
QPushButton#panelIconBtnDanger:hover {{ background: {ERROR_LIGHT}; color: {ERROR}; }}

/* ---- 三段切换（原型：slate-100 圆角容器 + 白色活动段） ---- */
QFrame#segHost {{ background: {BACKGROUND}; border-radius: 6px; }}
QPushButton#segTab {{
    background: transparent; border: none; border-radius: 4px;
    color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px; padding: 5px 6px;
}}
QPushButton#segTab:hover {{ color: {TEXT_PRIMARY}; }}
QPushButton#segTab:checked {{
    background: {SURFACE}; color: {TEXT_PRIMARY};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    border: 1px solid {BORDER};
}}

/* ---- 深色底部大按钮 / 文字链接按钮 ---- */
QPushButton#darkBtn {{
    background: {TOPBAR_BTN_BG}; border: none; border-radius: 4px;
    color: #FFFFFF; font-weight: {FONT_WEIGHT_SEMIBOLD};
    padding: 8px 12px; font-size: {FONT_SIZE_SECONDARY}px;
}}
QPushButton#darkBtn:hover {{ background: {TOPBAR_BTN_HOVER}; }}
QPushButton#darkBtn:disabled {{ background: {BORDER}; color: {TEXT_DISABLED}; }}
QPushButton#linkBtn {{
    background: transparent; border: none; border-radius: 3px;
    color: {ACCENT_LINK}; font-weight: {FONT_WEIGHT_SEMIBOLD};
    font-size: {FONT_SIZE_CAPTION}px; padding: 1px 4px;
}}
QPushButton#linkBtn:hover {{ text-decoration: underline; color: {ACCENT}; }}
QPushButton#miniBtn {{
    background: {SURFACE}; border: 1px solid {BORDER_INPUT}; border-radius: 4px;
    color: {TEXT_PRIMARY}; font-size: {FONT_SIZE_CAPTION}px; padding: 3px 10px;
}}
QPushButton#miniBtn:hover {{ background: {HOVER}; border-color: {BORDER_HOVER}; }}

/* ---- 图纸列表（v3 卡片行） ---- */
QListWidget#sheetList {{ background: {SURFACE}; border: none; border-bottom: 1px solid {BORDER}; }}
QListWidget#sheetList::item {{ border-bottom: 1px solid {BORDER}; }}
QListWidget#sheetList::item:hover {{ background: {HOVER}; }}
QListWidget#sheetList::item:selected {{ background: {ACCENT_LIGHT}; }}
QLineEdit#sheetSearch {{
    background: {BACKGROUND}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 3px 8px; font-size: {FONT_SIZE_CAPTION}px;
}}
QLineEdit#sheetSearch:focus {{ border-color: {ACCENT}; }}

/* ---- 画布工具条缩放读数 ---- */
QLabel#zoomPct {{
    color: {TOOLSTRIP_TEXT}; font-size: {FONT_SIZE_CAPTION}px;
    min-width: 34px; qproperty-alignment: AlignCenter; background: transparent;
}}

/* ---- 通用次级按钮（白底面板内） ---- */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {BTN_SECONDARY_BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    color: {TEXT_PRIMARY};
    font-size: {FONT_SIZE_SECONDARY}px;
}}
QPushButton:hover {{ border-color: {BORDER_HOVER}; color: {ACCENT_LINK}; }}
QPushButton:pressed {{ background: {ACCENT_LIGHT}; }}
QPushButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: {SELECTED_TEXT}; }}
QPushButton:disabled {{ color: {TEXT_DISABLED}; border-color: {BORDER}; background: {SURFACE}; }}

QPushButton#primaryBtn {{
    background: {BTN_PRIMARY_BG};
    border: 1px solid {BTN_PRIMARY_BG};
    color: {BTN_PRIMARY_TEXT};
    font-weight: {FONT_WEIGHT_MEDIUM};
}}
QPushButton#primaryBtn:hover {{ background: {BTN_PRIMARY_HOVER}; border-color: {BTN_PRIMARY_HOVER}; }}
QPushButton#primaryBtn:pressed {{ background: {BTN_PRIMARY_HOVER}; }}
QPushButton#primaryBtn:disabled {{ background: {BTN_DISABLED_BG}; border-color: {BTN_DISABLED_BG}; color: {SURFACE}; }}

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
QPushButton#collapseBtn:hover {{ color: {ACCENT_LINK}; background: {HOVER}; }}

/* ---- 画布工具条（深色通栏） ---- */
QWidget#floatBar {{
    background: {TOOLSTRIP_BG};
    border: none;
    border-bottom: 1px solid {TOOLSTRIP_BORDER};
}}
QWidget#floatBar QToolBar {{
    background: transparent;
    border: none;
    spacing: 2px;
    padding: 2px 6px;
}}
QWidget#floatBar QLabel {{ color: {TOOLSTRIP_TEXT}; font-size: {FONT_SIZE_SECONDARY}px; }}
QWidget#floatBar QPushButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 10px;
    color: {TOOLSTRIP_TEXT};
    font-size: {FONT_SIZE_SECONDARY}px;
}}
QWidget#floatBar QPushButton:hover {{ background: {TOPBAR_BTN_HOVER}; color: {TOPBAR_TEXT}; }}
QWidget#floatBar QPushButton:checked {{ background: {ACCENT}; color: {SELECTED_TEXT}; }}
QWidget#floatBar QPushButton:disabled {{ color: {TOPBAR_TEXT_DIM}; }}
QWidget#floatBar QCheckBox {{ color: {TOOLSTRIP_TEXT}; spacing: 3px; }}
QWidget#floatBar QCheckBox::indicator {{
    width: 12px; height: 12px;
    border: 1px solid {TOPBAR_BTN_BORDER}; border-radius: 2px;
    background: {TOPBAR_BTN_BG};
}}
QWidget#floatBar QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QWidget#floatBar QComboBox {{
    background: {TOPBAR_BTN_BG};
    border: 1px solid {TOPBAR_BTN_BORDER};
    border-radius: 4px;
    padding: 2px 6px;
    color: {TOPBAR_TEXT};
    min-height: 18px;
}}
QWidget#floatBar QComboBox:hover {{ border-color: {ACCENT_HOVER}; }}
QWidget#floatBar QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER_INPUT};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: {SELECTED_TEXT};
}}
QWidget#floatBar QComboBox::down-arrow {{
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TOPBAR_TEXT_DIM};
}}

/* ---- 画布浮层（选择条/提示，深色半透明） ---- */
QWidget#selOverlay {{
    background: rgba(15, 23, 42, 242);
    border: 1px solid {OVERLAY_BORDER};
    border-radius: 6px;
}}
QWidget#selOverlay QLabel {{ color: {OVERLAY_TEXT}; background: transparent; }}
QWidget#selOverlay QPushButton {{
    background: {TOPBAR_BTN_BG};
    border: 1px solid {OVERLAY_BORDER};
    border-radius: 4px;
    color: {OVERLAY_TEXT};
    padding: 3px 10px;
    font-size: {FONT_SIZE_SECONDARY}px;
}}
QWidget#selOverlay QPushButton:hover {{ background: {TOPBAR_BTN_HOVER}; border-color: {ACCENT_HOVER}; }}
QWidget#selOverlay QPushButton#primaryBtn {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
    color: #020617;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
}}
QWidget#selOverlay QPushButton#primaryBtn:hover {{ background: {ACCENT_BRIGHT}; border-color: {ACCENT_BRIGHT}; }}
QWidget#selOverlay QPushButton:disabled {{ color: {TOPBAR_TEXT_DIM}; background: {TOPBAR_BTN_BG}; }}
QLabel#hintLabel {{
    background: rgba(15, 23, 42, 230);
    border: 1px solid {OVERLAY_BORDER};
    border-radius: 4px;
    color: {OVERLAY_TEXT_DIM};
    font-size: {FONT_SIZE_CAPTION}px;
    padding: 4px 10px;
}}

/* ---- 右栏图标 rail（v3） ---- */
QWidget#railBar {{
    background: {RAIL_BG};
    border-right: 1px solid {RAIL_BORDER};
}}
QToolButton#railBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    color: {RAIL_TEXT};
    font-size: 15px;
}}
QToolButton#railBtn:hover {{ background: {RAIL_HOVER}; }}
QToolButton#railBtn:checked {{ background: {RAIL_ACTIVE}; color: {SELECTED_TEXT}; }}
QWidget#railPageHeader {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}

/* ---- 状态栏（白底） ---- */
QStatusBar {{
    background: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {STATUS_FOOT_TEXT};
    padding: 2px 6px;
    font-size: {FONT_SIZE_STATUS}px;
}}

QPushButton#llmStatusBtn {{
    background: transparent; border: none; border-radius: 3px;
    color: {STATUS_FOOT_TEXT};
    padding: 2px 8px;
    font-size: {FONT_SIZE_STATUS}px;
}}
QPushButton#llmStatusBtn:hover {{ color: {ACCENT_LINK}; background: {HOVER}; }}

QMenu {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 3px;
}}
QMenu::item {{ padding: 5px 18px; border-radius: 3px; color: {TEXT_PRIMARY}; }}
QMenu::item:selected {{ background: {ACCENT_LIGHT}; color: {ACCENT_LINK}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 3px 6px; }}

QComboBox {{
    border: 1px solid {BORDER_INPUT};
    border-radius: 4px;
    padding: 3px 6px;
    background: {SURFACE};
    min-height: 20px;
    color: {TEXT_PRIMARY};
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
    background: {RAIL_BG};
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
    border-radius: 4px 4px 0 0;
    padding: 5px 12px;
    color: {TEXT_SECONDARY};
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {SURFACE};
    color: {ACCENT_LINK};
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    border-bottom: 2px solid {ACCENT};
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: {SCROLLBAR_BG};
    width: 8px; height: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {SCROLLBAR_HANDLE}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

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
    border-radius: 4px;
    padding: 3px 6px;
    color: {TEXT_PRIMARY};
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
QTableWidget {{ alternate-background-color: {RAIL_BG}; }}
QTableWidget::item {{ padding: 3px 4px; }}
QTableCornerButton::section {{
    background: {RAIL_BG};
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
    background: {TOPBAR_BG};
    color: {TOPBAR_TEXT};
    border: 1px solid {TOPBAR_BORDER};
    border-radius: 3px;
    padding: 3px 6px;
    font-size: {FONT_SIZE_CAPTION}px;
}}

/* ---- QMessageBox 按钮间距 ---- */
QMessageBox QPushButton {{ min-width: 72px; }}

/* ---- Toast 浮层（v3，底部居中） ---- */
QLabel#toastLabel {{
    background: rgba(15, 23, 42, 242);
    color: {OVERLAY_TEXT};
    border: 1px solid {OVERLAY_BORDER};
    border-radius: 6px;
    padding: 8px 18px;
    font-size: {FONT_SIZE_SECONDARY}px;
}}
"""


# 全局 QSS 常量（避免各模块重复调用 generate_main_qss）
MAIN_QSS = generate_main_qss()


# ============================================================
# Icon font（v3 1:1：Segoe Fluent Icons，Win11 自带；缺字体回退 None）
# ============================================================

def icon_font_family() -> str | None:
    """返回可用的 Fluent 图标字体族；都没有则 None（调用方回退文字标签）。"""
    try:
        from PySide6.QtGui import QFontDatabase
        fams = set(QFontDatabase.families())
        for fam in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if fam in fams:
                return fam
    except Exception:
        pass
    return None


# 常用图标码点（Segoe MDL2/Fluent Assets）
ICONS = {
    "document":  "",   # Document（品牌方块：图纸）
    "folder":    "",   # Folder（项目）
    "add":       "",   # Add（新建 / 添加图纸）
    "open":      "",   # OpenFile（打开图纸）
    "magic":     "",   # LightningBolt（AI 算量）
    "export":    "",   # Share（导出）
    "settings":  "",   # Setting（齿轮）
    "chevron":   "",   # ChevronDown
    "search":    "",   # Search
    "trash":     "",   # Delete（删除图纸）
    "link":      "",   # Link（rail 绑定工作台）
    "list":      "",   # BulletedList（rail BOQ 清单）
    "page":      "",   # Page（rail 实体属性）
    "history":   "",   # History（rail 操作记录）
    "help":      "",   # Help（rail 帮助）
    "collapse":  "",   # ChevronLeft（收起资源面板）
    "zoom_in":   "",   # ZoomIn
    "zoom_out":  "",   # ZoomOut
    "warning":   "",   # Warning（警示三角）
    "check":     "",   # CheckMark（已确认）
    "info":      "",   # Info（信息圆圈）
    "meter":     "",   # Calculator（rail 计量）
    "tag":       "",   # Tag（rail 图例标定）
    "project":   "",   # Multiple?（rail 项目属性）
    "cursor":    "",   # Cursor（拾取）
}


def make_icon_font(pixel_size: int = 16):
    """Fluent 图标 QFont；无图标字体时返回 None（调用方回退文字）。"""
    fam = icon_font_family()
    if fam is None:
        return None
    from PySide6.QtGui import QFont
    f = QFont(fam)
    f.setPixelSize(pixel_size)
    return f




def generate_item_selected_qss() -> str:
    """统一的 item:selected 样式（浅青选中底 + 保字色 + 无 focus outline）。
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
QHeaderView::section {{ background: {RAIL_BG}; padding: 4px; border: none; }}
"""
