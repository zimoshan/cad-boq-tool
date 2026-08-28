"""CAD 画布：渲染 / 缩放 / 平移 / 点选 / 框选 / 主题 / 缩放历史"""
from __future__ import annotations

import json
import logging
import math
import time

from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QLineF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QPixmap
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsPathItem, QGraphicsLineItem,
                               QGraphicsEllipseItem, QGraphicsSimpleTextItem,
                               QGraphicsScene, QGraphicsView, QGraphicsItemGroup,
                               QGraphicsRectItem)

from . import theme as T

from ..models import Entity

logger = logging.getLogger(__name__)

# item data 槽位
DATA_ENTITY_ID = 0
DATA_LAYER = 1
DATA_IS_TEXT = 2
DATA_COLOR = 3
DATA_TYPE = 4

# LOD 概览模式阈值：场景单位/设备像素 > 该值 → 简化绘制（关抗锯齿）
_LOD_OVERVIEW_PPU = 6.0

# 主题色 — 全部引用 theme.py 常量，不再硬编码
THEME_LIGHT = {
    "bg": QColor(T.SURFACE_ALT),
    "default": QColor(T.CANVAS_DEFAULT_LIGHT),
    "rubber_pen": QColor(T.CANVAS_RUBBER_LIGHT + "CC"),   # 80% alpha
    "rubber_fill": QColor(T.CANVAS_RUBBER_LIGHT + "28"),  # 16% alpha
    "hover": QColor(T.CANVAS_HOVER_LIGHT),
    "selected": QColor(T.CANVAS_SELECTED_LIGHT),
    "mapped": QColor(T.CANVAS_MAPPED_LIGHT),
}
THEME_DARK = {
    "bg": QColor(T.CANVAS_BG_DARK),
    "default": QColor(T.CANVAS_DEFAULT_DARK),
    "rubber_pen": QColor(T.CANVAS_RUBBER_DARK + "DD"),   # 87% alpha
    "rubber_fill": QColor(T.CANVAS_RUBBER_DARK + "3C"),  # 24% alpha
    "hover": QColor(T.CANVAS_HOVER_DARK),
    "selected": QColor(T.CANVAS_SELECTED_DARK),
    "mapped": QColor(T.CANVAS_MAPPED_DARK),
}


def to_scene(p):
    """DXF 世界坐标 → Qt 场景坐标（Y 翻转）"""
    return QPointF(p[0], -p[1])


def arc_sample_points(cx, cy, r, a0_deg, a1_deg, step=2.0):
    pts = []
    sweep = a1_deg - a0_deg
    if sweep < 0:
        sweep += 360.0
    n = max(2, int(sweep / step))
    for i in range(n + 1):
        ang = math.radians(a0_deg + sweep * i / n)
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def build_geom_item(geom: dict, entity_id: int, color: tuple, tf=None):
    """按几何 dict 构建 QGraphicsItem。tf: 点变换函数（INSERT 用）；None=场景坐标"""
    if tf is None:
        def tf(p):
            return (p[0], -p[1])
    gtype = geom.get("type", "")
    qcolor = QColor(*color)

    def P(p):
        x, y = tf((p[0], p[1]))
        return QPointF(x, y)

    if gtype == "line":
        item = QGraphicsLineItem(QLineF(P(geom["start"]), P(geom["end"])))
        item.setPen(QPen(qcolor, 0))
        return item

    if gtype in ("polyline", "lwpolyline", "spline"):
        path = QPainterPath()
        pts = [P(p) for p in geom["points"]]
        if not pts:
            return None
        path.moveTo(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        if geom.get("closed"):
            path.closeSubpath()
        item = QGraphicsPathItem(path)
        item.setPen(QPen(qcolor, 0))
        return item

    if gtype == "circle":
        c = geom["center"]; r = geom["radius"]
        p0 = P((c[0] - r, c[1] - r))
        item = QGraphicsEllipseItem(QRectF(p0, QPointF(p0.x() + 2 * r, p0.y() + 2 * r)))
        item.setPen(QPen(qcolor, 0))
        return item

    if gtype == "arc":
        pts = arc_sample_points(geom["center"][0], geom["center"][1], geom["radius"],
                                geom["start_angle"], geom["end_angle"])
        path = QPainterPath()
        qpts = [P(p) for p in pts]
        path.moveTo(qpts[0])
        for pt in qpts[1:]:
            path.lineTo(pt)
        item = QGraphicsPathItem(path)
        item.setPen(QPen(qcolor, 0))
        return item

    if gtype == "ellipse":
        c = geom["center"]; a = geom["major"]; ratio = geom["ratio"]
        # 参数化采样
        r_major = math.hypot(a[0], a[1])
        ang0 = math.atan2(a[1], a[0])
        pts = []
        step = 5.0
        for i in range(int(360 / step) + 1):
            t = math.radians(i * step)
            pts.append((c[0] + r_major * math.cos(t) * math.cos(ang0) - r_major * ratio * math.sin(t) * math.sin(ang0),
                        c[1] + r_major * math.cos(t) * math.sin(ang0) + r_major * ratio * math.sin(t) * math.cos(ang0)))
        path = QPainterPath()
        qpts = [P(p) for p in pts]
        path.moveTo(qpts[0])
        for pt in qpts[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        item = QGraphicsPathItem(path)
        item.setPen(QPen(qcolor, 0))
        return item

    if gtype == "hatch":
        boundary = geom.get("boundary") or []
        if len(boundary) < 3:
            return None
        path = QPainterPath()
        qpts = [P(p) for p in boundary]
        path.moveTo(qpts[0])
        for pt in qpts[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        item = QGraphicsPathItem(path)
        item.setPen(QPen(qcolor, 0))
        brush = QColor(*color)
        brush.setAlpha(60)
        item.setBrush(brush)
        return item

    if gtype == "text":
        pos = P(geom.get("pos", [0, 0]))
        text = geom.get("text", "")
        if not text:
            return None
        item = QGraphicsSimpleTextItem(text)
        item.setPos(pos)
        item.setBrush(QColor(*color))
        font = item.font()
        font.setPointSizeF(max(6.0, min(36.0, font.pointSizeF() * 1.0)))
        item.setFont(font)
        item.setData(DATA_IS_TEXT, True)
        return item

    if gtype == "insert":
        # 由调用方处理（需要块定义）
        return None

    return None


def make_block_group(geom, entity_id, color, block_geoms: dict, tf) -> QGraphicsItemGroup:
    """INSERT 渲染：用块定义构建子项组"""
    group = QGraphicsItemGroup()
    group.setData(DATA_ENTITY_ID, entity_id)
    bname = geom.get("block", "")
    insert = geom.get("insert", [0, 0])
    scale = geom.get("scale", [1.0, 1.0])
    rot = geom.get("rotation", 0.0)

    def bt(p):
        rad = math.radians(rot)
        c, s = math.cos(rad), math.sin(rad)
        x = p[0] * scale[0] * c - p[1] * scale[1] * s + insert[0]
        y = p[0] * scale[0] * s + p[1] * scale[1] * c + insert[1]
        return (x, -y)

    for sub in block_geoms.get(bname, []):
        item = build_geom_item(sub, entity_id, color, tf=bt)
        if item:
            item.setData(DATA_ENTITY_ID, entity_id)
            group.addToGroup(item)
    # 块定义缺失时画叉标记
    if not group.childItems():
        cross = QGraphicsPathItem()
        p = QPainterPath()
        ip = QPointF(insert[0], -insert[1])
        p.moveTo(ip.x() - 2, ip.y() - 2); p.lineTo(ip.x() + 2, ip.y() + 2)
        p.moveTo(ip.x() - 2, ip.y() + 2); p.lineTo(ip.x() + 2, ip.y() - 2)
        cross.setPath(p)
        cross.setPen(QPen(QColor(T.CANVAS_CROSS_ERROR), 0))
        cross.setData(DATA_ENTITY_ID, entity_id)
        group.addToGroup(cross)
    return group


class CanvasView(QGraphicsView):
    entityPicked = Signal(int)         # 双击
    entitiesPicked = Signal(list)      # 框选
    entityHovered = Signal(int)        # 鼠标悬停（Phase 3 用）
    scaleChanged = Signal(float)       # 缩放读数联动（工具条 − % ＋）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        # 大图平移/缩放：SmartViewportUpdate 由 Qt 按变更区域选择最省的重绘方式
        #（FullViewportUpdate 每次滚动全窗重画，6k+ 实体时掉帧明显）
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)

        # LOD 概览模式：场景单位/设备像素超过阈值 → 关抗锯齿简化绘制（fit 大图不掉帧）
        self._lod_overview = False

        self._theme = THEME_LIGHT
        self._dot_pixmap = self._make_dot_pixmap()
        self._apply_bg()

        self._entity_items: dict[int, QGraphicsItem] = {}   # entity_id -> item/group
        self._layer_items: dict[str, list] = {}             # layer -> [items]
        self._type_items: dict[str, list] = {}              # dxf_type -> [items]
        self._block_geoms: dict = {}
        self._mapping_colors: dict = {}                     # boq_item_id -> QColor
        self._pending_ids: set[int] = set()                 # 待分配拾取集（Phase 3）
        self._pending_color = self._theme["selected"]

        self._panning = False
        self._pan_last = None
        self._rubber = None
        self._rubber_origin = None

        # 缩放历史栈（Phase 1）
        self._zoom_hist: list[tuple[float, QPointF]] = []  # (scale, center)
        self._zoom_fut: list[tuple[float, QPointF]] = []

        # 实体类型显隐（默认全部可见；HATCH/TEXT 在 toolbar 启动后关闭）
        self._type_visible: dict[str, bool] = {t: True for t in [
            "LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE",
            "ELLIPSE", "HATCH", "INSERT", "TEXT", "MTEXT", "POINT",
        ]}

        # 定位高亮状态（目标保持原色 + 虚线框，其余变暗）
        self._highlight_on: bool = False
        self._highlight_ids: set = set()
        self._highlight_rect: QGraphicsRectItem | None = None

        # 图层隔离状态（Phase 2）
        self._isolated: bool = False
        self._saved_opacity: dict | None = None

        # hover 高亮（Phase 3）
        self._hovered_eid: int | None = None

        # 延迟 fit 标记（首次 show 时自动 fit）
        self._needs_fit = False
        self._initial_fit_done = False

    def showEvent(self, event):
        """首次显示时自动 fit，确保画布不因初始尺寸未确定而留白。"""
        super().showEvent(event)
        if self._needs_fit and not self._scene.itemsBoundingRect().isEmpty():
            self._needs_fit = False
            self._initial_fit_done = True
            self.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            self._update_lod()

    def resizeEvent(self, event):
        """窗口缩放后自动重新 fit，保证画布始终铺满可视区域。"""
        super().resizeEvent(event)
        if not self._scene.itemsBoundingRect().isEmpty():
            # 仅在尚未完成初始 fit 时自动 fit；用户手动缩放后不再重置
            if not self._initial_fit_done:
                self._initial_fit_done = True
                self.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                self._update_lod()

    # ---------- 主题 ----------
    def set_theme(self, dark: bool):
        self._theme = THEME_DARK if dark else THEME_LIGHT
        self._apply_bg()
        self._pending_color = self._theme["selected"]
        # 重绘所有 item（颜色按主题 default 调整）
        self._refresh_all_colors()

    # ---------- 背景点阵（v2 英雄画布） ----------
    def _make_dot_pixmap(self):
        """生成 24x24 淡灰点阵纹理，作为画布底纹"""
        pm = QPixmap(24, 24)
        pm.fill(QColor(T.SURFACE_ALT))          # 淡灰底
        p = QPainter(pm)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.CANVAS_DOT))        # 点阵点
        p.drawEllipse(11, 11, 2, 2)
        p.end()
        return pm

    def _apply_bg(self):
        if self._theme is THEME_DARK:
            self.setBackgroundBrush(QColor(T.CANVAS_BG_DARK))
        else:
            self.setBackgroundBrush(QBrush(self._dot_pixmap))

    def _refresh_all_colors(self):
        default = self._theme["default"]
        for item in self._entity_items.values():
            if isinstance(item, QGraphicsItemGroup):
                for child in item.childItems():
                    self._apply_default(child, default)
            else:
                self._apply_default(item, default)
        # 重新套映射色 + 待选色
        for boq_id, color in self._mapping_colors.items():
            for eid, item in self._entity_items.items():
                # 简化：所有已映射 item 重涂
                pass
        if self._pending_ids:
            self._highlight_pending()

    def _apply_default(self, item, color: QColor):
        if isinstance(item, (QGraphicsLineItem, QGraphicsPathItem, QGraphicsEllipseItem)):
            item.setPen(QPen(color, 0))
        elif isinstance(item, QGraphicsSimpleTextItem):
            item.setBrush(color)

    # ---------- 构建 ----------
    # 大图跳过的类型：标注/填充在 CAD 中主要辅助阅读，不影响算量
    _DEFERRED_TYPES = {"TEXT", "MTEXT", "HATCH", "DIMENSION", "LEADER", "MLEADER"}

    def build(self, entities: list, block_geoms: dict):
        started = time.perf_counter()
        # 冻结场景更新 + 关闭索引，避免逐项触发布局/重绘
        self._scene.blockSignals(True)
        self._scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.setUpdatesEnabled(False)
        self._scene.clear()
        self._entity_items.clear()
        self._layer_items.clear()
        self._type_items.clear()
        self._block_geoms = block_geoms or {}
        self._pending_ids.clear()
        self._zoom_hist.clear()
        self._zoom_fut.clear()
        self._initial_fit_done = False
        self._lod_overview = False
        # 大图策略：跳过 TEXT/HATCH/标注等非算量类型，减少 Qt 图形项数量
        skip_deferred = len(entities) > self._DEFERRED_THRESHOLD
        self._deferred_skipped = []   # 被跳过的实体，按需加载
        if skip_deferred:
            self._deferred_types_active = True
        else:
            self._deferred_types_active = False
        for e in entities:
            self._add_entity(e, skip_deferred=skip_deferred)
        build_elapsed = time.perf_counter() - started
        # 解冻：恢复索引 + 一次性刷新
        self._scene.setItemIndexMethod(QGraphicsScene.BspTreeIndex)
        self._scene.blockSignals(False)
        self.setUpdatesEnabled(True)
        self._scene.update()
        # 标记需要 fit（如果 view 已可见则立即 fit，否则等 showEvent）
        if self.isVisible():
            self._initial_fit_done = True
            self.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            self._update_lod()
        else:
            self._needs_fit = True
        skipped = len(self._deferred_skipped) if skip_deferred else 0
        logger.debug("canvas build: entities=%d items=%d skipped_deferred=%d build_ms=%.1f fit_ms=%.1f total_ms=%.1f",
                     len(entities), len(self._entity_items), skipped,
                     build_elapsed * 1000,
                     (time.perf_counter() - started - build_elapsed) * 1000,
                     (time.perf_counter() - started) * 1000)

    def load_deferred_types(self):
        """按需加载被跳过的 TEXT/HATCH/标注（用户主动请求时调用）"""
        if not self._deferred_skipped:
            return
        self._scene.blockSignals(True)
        self.setUpdatesEnabled(False)
        count = 0
        for e in self._deferred_skipped:
            self._add_entity(e, skip_deferred=False)
            count += 1
        self._deferred_skipped.clear()
        self._deferred_types_active = False
        self._scene.blockSignals(False)
        self.setUpdatesEnabled(True)
        self._scene.update()
        logger.info("canvas load_deferred_types: loaded %d items", count)

    def _add_entity(self, e: Entity, skip_deferred: bool = False):
        try:
            geom = json.loads(e.geom_json)
        except Exception:
            return
        dxf_type = e.dxf_type or geom.get("type", "").upper()
        # 大图策略：跳过 TEXT/HATCH/标注等非算量类型，存入延迟队列
        if skip_deferred and dxf_type in self._DEFERRED_TYPES:
            self._deferred_skipped.append(e)
            return
        if geom.get("type") == "insert":
            item = make_block_group(geom, e.id, e.color, self._block_geoms, None)
        else:
            item = build_geom_item(geom, e.id, e.color)
        if item is None:
            return
        item.setData(DATA_ENTITY_ID, e.id)
        item.setData(DATA_LAYER, e.layer)
        item.setData(DATA_COLOR, tuple(e.color))
        item.setData(DATA_TYPE, dxf_type)
        item.setFlag(QGraphicsItem.ItemIsSelectable, True)
        # hover 显示实体属性（"这个块是什么"）
        tip_parts = [f"类型: {dxf_type}"]
        if e.layer:
            tip_parts.append(f"图层: {e.layer}")
        if e.block_name:
            tip_parts.append(f"块: {e.block_name}")
        if e.length:
            tip_parts.append(f"长度: {e.length:.1f}")
        if e.area:
            tip_parts.append(f"面积: {e.area:.1f}")
        item.setToolTip("\n".join(tip_parts))
        self._scene.addItem(item)
        self._entity_items[e.id] = item
        self._layer_items.setdefault(e.layer, []).append(item)
        self._type_items.setdefault(dxf_type, []).append(item)
        # 应用类型可见性
        if not self._type_visible.get(dxf_type, True):
            item.setVisible(False)

    def entities_from_rect(self, rect: QRectF) -> list:
        """框选：返回命中实体 id 列表（仅可见项）"""
        ids = []
        for item in self._scene.items(rect, Qt.IntersectsItemShape):
            if not item.isVisible():
                continue
            eid = item.data(DATA_ENTITY_ID)
            if eid is not None and eid not in ids:
                ids.append(eid)
        return ids

    def entity_at(self, scene_pos) -> int | None:
        item = self._scene.itemAt(scene_pos, self.transform())
        if item is None or not item.isVisible():
            return None
        eid = item.data(DATA_ENTITY_ID)
        return eid if eid is not None else None

    # ---------- 图层显隐 ----------
    def set_layer_visible(self, layer: str, visible: bool):
        for item in self._layer_items.get(layer, []):
            item.setVisible(visible)

    # ---------- 实体类型显隐（Phase 1） ----------
    def set_type_visible(self, type_name: str, visible: bool):
        self._type_visible[type_name] = visible
        # 如果大图跳过了该类型且用户现在要显示，先按需加载
        if visible and getattr(self, "_deferred_types_active", False):
            if type_name in self._DEFERRED_TYPES and self._deferred_skipped:
                self.load_deferred_types()
        for item in self._type_items.get(type_name, []):
            item.setVisible(visible)

    # ---------- 图层透明度 / 隔离 / 锁定（Phase 2） ----------
    def set_layer_opacity(self, layer: str, alpha: int):
        """对单图层设透明度（0-255）。不影响其他图层"""
        items = self._layer_items.get(layer, [])
        for item in items:
            self._apply_opacity(item, alpha)

    def isolate_layer(self, target_layer: str, others_alpha: int = 64):
        """LAYISO 等价：保留 target_layer 满色，其他图层淡化到 others_alpha"""
        if not self._isolated:
            self._saved_opacity = {}
        self._isolated = True
        for layer, items in self._layer_items.items():
            if layer == target_layer:
                self._apply_opacity_to_items(items, 255)
            else:
                self._apply_opacity_to_items(items, others_alpha)

    def restore_layers(self):
        """LAYUNISO 等价：所有图层恢复满色"""
        if not self._isolated:
            return
        for layer, items in self._layer_items.items():
            self._apply_opacity_to_items(items, 255)
        self._isolated = False
        self._saved_opacity = None

    def _apply_opacity_to_items(self, items, alpha: int):
        for item in items:
            self._apply_opacity(item, alpha)

    def _apply_opacity(self, item, alpha: int):
        if isinstance(item, QGraphicsItemGroup):
            for child in item.childItems():
                self._apply_opacity(child, alpha)
            return
        # 已有 setPen / setBrush
        pen = item.pen() if hasattr(item, "pen") else None
        if pen is not None and not pen.isCosmetic() or (pen is not None and pen.style() != Qt.NoPen):
            color = pen.color()
            color.setAlpha(alpha)
            item.setPen(QPen(color, pen.widthF(), pen.style(), pen.capStyle(), pen.joinStyle()))
        brush = item.brush() if hasattr(item, "brush") else None
        if brush is not None and brush.style() != Qt.NoBrush:
            color = brush.color()
            color.setAlpha(alpha)
            item.setBrush(color)

    def zoom_to_entities(self, eids: list):
        """跨高亮：fitInView 到指定实体集合的范围（相对 15% padding，自适应实体大小）"""
        if not eids:
            return
        items = [self._entity_items.get(eid) for eid in eids if eid in self._entity_items]
        items = [i for i in items if i is not None]
        if not items:
            return
        rect = QRectF()
        for it in items:
            r = it.sceneBoundingRect()
            rect = rect.united(r)
        if not rect.isEmpty():
            self._push_zoom()
            w = max(rect.width(), 1.0)
            h = max(rect.height(), 1.0)
            self.fitInView(rect.adjusted(-w * 0.15, -h * 0.15, w * 0.15, h * 0.15),
                           Qt.KeepAspectRatio)

    # ---------- 定位高亮（目标高亮 + 其余变暗 + 虚线框） ----------
    def highlight_entities(self, eids: list, max_dim: int = 20000):
        """进入定位高亮模式：目标实体保持原色，其余变暗，目标区域画黄色虚线框。

        Args:
            eids: 目标实体 id 列表（不限长度，只对命中者高亮）
            max_dim: 其余实体变暗的遍历上限（防超大图卡顿，超过则跳过变暗）
        """
        self.clear_highlight()
        if not eids:
            return
        self._highlight_ids = set(eids)
        targets = [self._entity_items.get(e) for e in eids if e in self._entity_items]
        targets = [i for i in targets if i is not None]
        if not targets:
            self._highlight_ids = set()
            return

        # 目标保持原色（opacity 1.0），其余变暗
        n_entities = len(self._entity_items)
        if n_entities <= max_dim:
            for eid, item in self._entity_items.items():
                item.setOpacity(1.0 if eid in self._highlight_ids else 0.22)
        else:
            # 超大图：只对目标集合做清理，跳过全量变暗（保性能）
            for t in targets:
                t.setOpacity(1.0)

        # 目标区域黄色虚线框（zValue 置顶）
        rect = QRectF()
        for t in targets:
            rect = rect.united(t.sceneBoundingRect())
        if not rect.isEmpty():
            w = max(rect.width(), 1.0)
            h = max(rect.height(), 1.0)
            box = rect.adjusted(-w * 0.12, -h * 0.12, w * 0.12, h * 0.12)
            self._highlight_rect = self._scene.addRect(
                box, QPen(QColor(T.CANVAS_HIGHLIGHT_DASH), 0, Qt.DashLine), QBrush(Qt.NoBrush))
            self._highlight_rect.setZValue(10_000)
        self._highlight_on = True

    def clear_highlight(self):
        """退出高亮模式：恢复全部实体透明度，移除虚线框"""
        if not self._highlight_on:
            return
        for item in self._entity_items.values():
            item.setOpacity(1.0)
        if self._highlight_rect is not None:
            self._scene.removeItem(self._highlight_rect)
            self._highlight_rect = None
        self._highlight_on = False
        self._highlight_ids = set()

    def flash_entities(self, eids: list, color: QColor = None, times: int = 3, interval_ms: int = 180):
        """跨高亮：闪烁若干次"""
        if not eids:
            return
        if color is None:
            color = self._theme["hover"]
        # 用 QTimer 异步闪烁，避免阻塞
        from PySide6.QtCore import QTimer
        if not hasattr(self, "_flash_state"):
            self._flash_state = {"i": 0, "items": [], "backup": {}}
        # 取消上一次
        QTimer.singleShot(0, lambda: self._do_flash(eids, color, times, interval_ms))

    def _do_flash(self, eids, color, times, interval_ms):
        from PySide6.QtCore import QTimer
        items = [self._entity_items.get(eid) for eid in eids if eid in self._entity_items]
        items = [i for i in items if i is not None]
        if not items:
            return
        # 备份颜色
        backup = {}
        for i, it in enumerate(items):
            if hasattr(it, "pen"):
                backup[i] = (it.pen(), it.brush() if hasattr(it, "brush") else None)
        state = {"i": 0, "items": items, "backup": backup, "color": color, "times": times}

        def step():
            if state["i"] >= state["times"] * 2:
                # 恢复
                for i, (pen, brush) in state["backup"].items():
                    it = state["items"][i]
                    it.setPen(pen)
                    if brush is not None:
                        it.setBrush(brush)
                return
            show = (state["i"] % 2 == 0)
            for idx, it in enumerate(state["items"]):
                if idx not in state["backup"]:
                    # 无 pen 属性的项（如 ItemGroup）未备份，跳过闪烁
                    continue
                if show:
                    it.setPen(QPen(state["color"], 2.0))
                else:
                    pen, brush = state["backup"][idx]
                    it.setPen(pen)
                    if brush is not None:
                        it.setBrush(brush)
            state["i"] += 1
            QTimer.singleShot(interval_ms, step)

        step()

    # ---------- 定位浮标签（v3 main.html：定位后在目标上方显示名称标签） ----------
    def show_tag(self, text: str, eids: list, duration_ms: int = 2400):
        """在目标实体包围盒上方显示名称标签，duration 后自动消失。

        标签用 ItemIgnoresTransformations：任意缩放级别下文字尺寸恒定，
        保证小图元（插座等）在缩小后仍可读。
        """
        items = [self._entity_items.get(eid) for eid in eids if eid in self._entity_items]
        items = [i for i in items if i is not None]
        if not items:
            return
        self._clear_tag()
        r = QRectF()
        for it in items:
            r = r.united(it.sceneBoundingRect())

        txt = QGraphicsSimpleTextItem(text)
        f = txt.font()
        f.setPointSize(10)
        f.setBold(True)
        txt.setFont(f)
        txt.setBrush(QColor(T.OVERLAY_TEXT))
        txt.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        tb = txt.boundingRect()

        bg = QGraphicsRectItem(0, 0, tb.width() + 16, tb.height() + 8)
        bg.setBrush(QColor(15, 23, 42, 235))          # OVERLAY_BG 不透明
        bg.setPen(QPen(QColor(T.OVERLAY_ACCENT), 1))
        bg.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        bg.setZValue(9998)
        txt.setZValue(9999)

        # 场景坐标：包围盒上方居中；贴边时夹回场景内
        w, h = bg.rect().width(), bg.rect().height()
        x = r.center().x() - w / 2
        y = r.top() - h - 8
        scene_r = self._scene.itemsBoundingRect()
        x = max(scene_r.left(), min(x, scene_r.right() - w))
        y = max(scene_r.top(), min(y, scene_r.bottom() - h))
        bg.setPos(x, y)
        txt.setPos(x + 8, y + 4)
        self._scene.addItem(bg)
        self._scene.addItem(txt)
        self._tag_items = [bg, txt]

        from PySide6.QtCore import QTimer
        QTimer.singleShot(duration_ms, self._clear_tag)

    def _clear_tag(self):
        for it in getattr(self, "_tag_items", []):
            try:
                self._scene.removeItem(it)
            except RuntimeError:
                pass    # 换图重建后 C++ 对象已释放，无需重复移除
        self._tag_items = []

    # ---------- 缩放历史（Phase 1） ----------
    def _push_zoom(self):
        s = self.transform().m11()
        c = self.mapToScene(self.viewport().rect().center())
        self._zoom_hist.append((s, QPointF(c)))
        if len(self._zoom_hist) > 20:
            self._zoom_hist.pop(0)
        self._zoom_fut.clear()

    def _apply_zoom(self, scale: float, center: QPointF):
        self.resetTransform()
        self.scale(scale, scale)
        self.centerOn(center)
        self._update_lod()
        self.scaleChanged.emit(self.transform().m11())

    def zoom_fit(self):
        self._push_zoom()
        self.fitInView(self._scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        self._update_lod()
        self.scaleChanged.emit(self.transform().m11())

    def zoom_actual(self):
        self._push_zoom()
        c = self.mapToScene(self.viewport().rect().center())
        self._apply_zoom(1.0, c)
        self._update_lod()

    def zoom_step(self, mult: float):
        """步进缩放（工具条 −/＋，原型 zoom(±10)：每步 ×1.15）。"""
        s = self.transform().m11() * mult
        c = self.mapToScene(self.viewport().rect().center())
        self._push_zoom()
        self._apply_zoom(s, c)
        self._update_lod()

    def zoom_back(self):
        if not self._zoom_hist:
            return
        s_now = self.transform().m11()
        c_now = self.mapToScene(self.viewport().rect().center())
        self._zoom_fut.append((s_now, QPointF(c_now)))
        s, c = self._zoom_hist.pop()
        self._apply_zoom(s, c)

    def zoom_forward(self):
        if not self._zoom_fut:
            return
        s_now = self.transform().m11()
        c_now = self.mapToScene(self.viewport().rect().center())
        self._zoom_hist.append((s_now, QPointF(c_now)))
        s, c = self._zoom_fut.pop()
        self._apply_zoom(s, c)

    def current_scale(self) -> float:
        return self.transform().m11()

    # ---------- LOD：缩放阈值简化绘制（P1-4） ----------
    # 概览模式下每个实体只占几个像素，逐像素抗锯齿光栅化是大图 fit/缩小的最大开销。
    # 关掉 AA 后 6k+ 实体全景平移/缩放可保持流畅；透视图仍为逐像素绘制同一批可见项。
    def _update_lod(self):
        """按当前缩放切换渲染质量：概览模式关抗锯齿（大图 fit/缩小不掉帧）"""
        spo = 1.0 / max(self.transform().m11(), 1e-6)   # 场景单位/设备像素
        overview = spo > _LOD_OVERVIEW_PPU
        if overview == self._lod_overview:
            return
        self._lod_overview = overview
        self.setRenderHint(QPainter.Antialiasing, not overview)
        self.setRenderHint(QPainter.TextAntialiasing, not overview)
        self.viewport().update()
        logger.debug("canvas LOD: overview=%s (scene_unit/px=%.2f)", overview, spo)

    # 大图跳过类型的阈值：超过该实体数即按需延迟 TEXT/HATCH/标注（非算量类型）。
    # BspTreeIndex 本身裁剪视口外绘制，此为构建层裁剪——压低阈值让中等大图也受益。
    _DEFERRED_THRESHOLD = 15_000

    def _after_transform(self):
        """缩放/平移/重建后统一刷 LOD 状态"""
        self._update_lod()

    # ---------- 关联着色 ----------
    def color_mapped_entities(self, boq_item_id: int, entity_ids: list):
        color = self._theme["mapped"]
        for eid in entity_ids:
            item = self._entity_items.get(eid)
            if item is not None:
                self._paint_override(item, color)
        self._mapping_colors[boq_item_id] = color

    def clear_item_colors(self):
        default = self._theme["default"]
        for item in self._entity_items.values():
            if isinstance(item, QGraphicsItemGroup):
                for child in item.childItems():
                    self._apply_default(child, default)
            else:
                self._apply_default(item, default)
        self._mapping_colors.clear()
        if self._pending_ids:
            self._highlight_pending()

    def _restore_color(self, item):
        self._apply_default(item, self._theme["default"])

    def _paint_override(self, item, color: QColor):
        if isinstance(item, QGraphicsItemGroup):
            for child in item.childItems():
                self._paint_override(child, color)
        elif isinstance(item, (QGraphicsLineItem, QGraphicsPathItem, QGraphicsEllipseItem)):
            item.setPen(QPen(color, 1.2))
        elif isinstance(item, QGraphicsSimpleTextItem):
            item.setBrush(color)

    # ---------- 待选区（Phase 3 占位） ----------
    def set_pending(self, eids: list[int]):
        """设置待分配拾取集；非空时画黄边高亮"""
        self._clear_hover()  # Phase 3: pending 优先于 hover
        # 先清除旧高亮
        if self._pending_ids:
            for eid in self._pending_ids:
                item = self._entity_items.get(eid)
                if item is not None:
                    self._restore_color(item)
        self._pending_ids = set(eids)
        self._highlight_pending()

    def _highlight_pending(self):
        for eid in self._pending_ids:
            item = self._entity_items.get(eid)
            if item is not None:
                self._paint_override(item, self._pending_color)

    def get_pending(self) -> list[int]:
        return list(self._pending_ids)

    def pending_summary(self) -> list[tuple[int, str, str]]:
        """待选实体摘要 [(entity_id, layer, dxf_type)]，供实体属性面板。"""
        out = []
        for eid in self._pending_ids:
            item = self._entity_items.get(eid)
            if item is None:
                continue
            out.append((eid, item.data(DATA_LAYER) or "",
                        item.data(DATA_TYPE) or ""))
        return out

    def clear_pending(self):
        if self._pending_ids:
            for eid in self._pending_ids:
                item = self._entity_items.get(eid)
                if item is not None:
                    self._restore_color(item)
            self._pending_ids.clear()

    # ---------- 事件 ----------
    def wheelEvent(self, event):
        # 仅在 Ctrl 修饰时视为缩放；裸滚轮让位给滚动条（避免误缩放）
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            self._update_lod()
            self.scaleChanged.emit(self.transform().m11())
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_last = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton and event.modifiers() & Qt.ShiftModifier:
            # 框选模式
            self._rubber_origin = self.mapToScene(event.position().toPoint())
            self._rubber = self._scene.addRect(
                QRectF(self._rubber_origin, self._rubber_origin),
                QPen(self._theme["rubber_pen"], 0),
                self._theme["rubber_fill"])
            event.accept()
            return
        # 定位高亮：点击空白处取消
        if event.button() == Qt.LeftButton and self._highlight_on:
            scene_pos = self.mapToScene(event.position().toPoint())
            if self.entity_at(scene_pos) is None:
                self.clear_highlight()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_last
            self._pan_last = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        if self._rubber is not None and self._rubber_origin is not None:
            cur = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._rubber_origin, cur).normalized()
            self._rubber.setRect(rect)
            event.accept()
            return
        # Phase 3: hover 高亮
        scene_pos = self.mapToScene(event.position().toPoint())
        eid = self.entity_at(scene_pos)
        if eid != self._hovered_eid:
            self._clear_hover()
            self._hovered_eid = eid
            if eid is not None and eid not in self._pending_ids:
                self._apply_hover(eid)
        super().mouseMoveEvent(event)

    def _apply_hover(self, eid: int):
        item = self._entity_items.get(eid)
        if item is None:
            return
        if isinstance(item, QGraphicsItemGroup):
            for child in item.childItems():
                if hasattr(child, "setPen"):
                    pen = child.pen()
                    pen.setColor(self._theme["hover"])
                    pen.setWidthF(max(pen.widthF(), 1.5))
                    child.setPen(pen)
        else:
            if hasattr(item, "setPen"):
                pen = item.pen()
                pen.setColor(self._theme["hover"])
                pen.setWidthF(max(pen.widthF(), 1.5))
                item.setPen(pen)

    def _clear_hover(self):
        if self._hovered_eid is None:
            return
        eid = self._hovered_eid
        self._hovered_eid = None
        # 跳过 pending / mapped 的
        if eid in self._pending_ids:
            return
        item = self._entity_items.get(eid)
        if item is None:
            return
        # 恢复原色（用 _paint_override 模式回 default）
        self._apply_default(item, self._theme["default"])

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._rubber is not None:
            cur = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._rubber_origin, cur).normalized()
            self._scene.removeItem(self._rubber)
            self._rubber = None
            ids = self.entities_from_rect(rect)
            if ids:
                self.entitiesPicked.emit(ids)
            self._rubber_origin = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            eid = self.entity_at(self.mapToScene(event.position().toPoint()))
            if eid is not None:
                self.entityPicked.emit(eid)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        # 画布内快捷键
        if event.key() == Qt.Key_Escape and self._highlight_on:
            self.clear_highlight()
            event.accept(); return
        if event.key() == Qt.Key_0 and event.modifiers() & Qt.ControlModifier:
            self.zoom_fit()
            event.accept(); return
        if event.key() == Qt.Key_1 and event.modifiers() & Qt.ControlModifier:
            self.zoom_actual()
            event.accept(); return
        if event.key() == Qt.Key_Left and event.modifiers() & Qt.AltModifier:
            self.zoom_back()
            event.accept(); return
        if event.key() == Qt.Key_Right and event.modifiers() & Qt.AltModifier:
            self.zoom_forward()
            event.accept(); return
        super().keyPressEvent(event)
