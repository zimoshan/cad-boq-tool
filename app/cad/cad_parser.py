"""CAD 解析：ezdxf 读取 DXF → Entity 模型 + 图层/块索引"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from ezdxf import colors as ezcolors

from ..models import Entity, LayerInfo, BlockInfo
from . import geometry as G


@dataclass
class ParsedDrawing:
    entities: list = field(default_factory=list)          # list[Entity]
    layers: dict = field(default_factory=dict)            # name -> count
    layer_colors: dict = field(default_factory=dict)      # name -> (r,g,b)  Phase 2
    blocks: dict = field(default_factory=dict)            # block name -> [geom_json, ...]
    block_refs: dict = field(default_factory=dict)        # block name -> INSERT 引用数
    blocks_with_count: dict = field(default_factory=dict) # block name -> Entity(INSERT) 列表

    @property
    def entity_count(self) -> int:
        return len(self.entities)


# 可渲染/可计量的实体类型
GEOMETRIC_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE",
                   "ELLIPSE", "INSERT", "HATCH", "TEXT", "MTEXT", "POINT"}


def _aci_to_rgb(entity, layer_rgb_cache: dict) -> tuple:
    """实体颜色：true_color > layer.rgb 缓存 > ACI 调色板 > 白色"""
    try:
        tc = entity.rgb
        if tc is not None:
            return tuple(tc)
    except AttributeError:
        pass
    try:
        rgb = layer_rgb_cache.get(entity.dxf.layer)
        if rgb:
            return rgb
    except Exception:
        pass
    try:
        aci = entity.dxf.color
        if aci is not None and aci > 0:
            return ezcolors.int2rgb(aci)
    except Exception:
        pass
    return (255, 255, 255)


def _vec2(p):
    """兼容 Vec3 / numpy 数组的取点"""
    if p is None:
        return None
    try:
        return [float(p.x), float(p.y)]
    except AttributeError:
        return [float(p[0]), float(p[1])]


def _entity_geom(entity) -> dict:
    """提取实体几何 → dict（可 JSON 序列化）；返回 (geom, length, area, bbox)"""
    # 兼容 _EntityWrapper（属性） 和 原生 ezdxf 实体（方法）
    etype = entity.dxftype if hasattr(entity, "dxftype") and not callable(getattr(entity, "dxftype", None)) else entity.dxftype()
    g = {"type": etype.lower()}
    length = 0.0
    area = 0.0
    pts = []

    if etype == "LINE":
        s = _vec2(entity.dxf.start)
        e = _vec2(entity.dxf.end)
        g.update({"start": s, "end": e})
        length = G.dist2d(s, e)
        pts = [s, e]

    elif etype == "LWPOLYLINE":
        # 兼容 ezdxf.get_points() 和 ezdwg dxf['points'] 两种接口
        try:
            raw = entity.get_points()  # ezdxf
        except AttributeError:
            # ezdwg: 从 dxf dict 取
            d = entity.dxf
            points_3d = d.get("points") or []
            raw = [(p[0], p[1], 0.0, 0.0, p[4]) if len(p) >= 5 else (p[0], p[1], 0.0, 0.0, 0.0)
                   for p in points_3d]
        points = [(p[0], p[1]) for p in raw]
        bulges = [p[4] if len(p) > 4 else 0.0 for p in raw]
        closed = bool(entity.closed)
        g.update({"points": points, "bulges": bulges, "closed": closed})
        if closed and len(points) >= 3:
            area = G.closed_polyline_area(points)
        length = G.polyline_length(points, bulges)
        pts = points

    elif etype == "POLYLINE":
        # 2D/3D 多段线（旧式）——一次迭代取位置与 bulge
        verts = list(entity.vertices)
        points = []
        bulges = []
        for v in verts:
            points.append(_vec2(v.dxf.location))
            bulges.append(v.dxf.bulge if v.dxf.hasattr("bulge") else 0.0)
        closed = bool(entity.is_closed)
        g.update({"points": points, "bulges": bulges, "closed": closed})
        if closed and len(points) >= 3:
            area = G.closed_polyline_area(points)
        length = G.polyline_length(points, bulges)
        pts = points

    elif etype == "ARC":
        c = _vec2(entity.dxf.center)
        r = entity.dxf.radius
        sa = math.radians(entity.dxf.start_angle)
        ea = math.radians(entity.dxf.end_angle)
        g.update({"center": c, "radius": r,
                  "start_angle": entity.dxf.start_angle, "end_angle": entity.dxf.end_angle})
        length = G.arc_length(r, sa, ea)
        pts = [(c[0] + r * math.cos(sa), c[1] + r * math.sin(sa)),
               (c[0] + r * math.cos(ea), c[1] + r * math.sin(ea))]

    elif etype == "CIRCLE":
        c = _vec2(entity.dxf.center)
        r = entity.dxf.radius
        g.update({"center": c, "radius": r})
        length = 2 * math.pi * r
        area = math.pi * r * r
        pts = [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]

    elif etype == "SPLINE":
        ctrl = [_vec2(p) for p in entity.control_points]
        g.update({"points": ctrl})
        length = G.spline_length(ctrl)
        pts = ctrl

    elif etype == "ELLIPSE":
        c = _vec2(entity.dxf.center)
        major = _vec2(entity.dxf.major_axis)
        # 字段名兼容：ezdxf 用 ratio，ezdwg 用 axis_ratio
        ratio = entity.dxf.get("axis_ratio") or entity.dxf.get("ratio")
        g.update({"center": c, "major": major, "ratio": ratio,
                  "start": _vec2(entity.dxf.start_point) if hasattr(entity, "start_point") else None,
                  "end": _vec2(entity.dxf.end_point) if hasattr(entity, "end_point") else None})
        if ratio is None:
            # ELLIPSE 数据不完整，跳过
            return None
        a = math.hypot(major[0], major[1])
        b = a * ratio
        # Ramanujan 近似周长
        length = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
        area = math.pi * a * b
        pts = [(c[0] - a, c[1] - b), (c[0] + a, c[1] + b)]

    elif etype == "INSERT":
        ins = _vec2(entity.dxf.insert)
        block_name = entity.dxf.name
        attribs = {}
        try:
            attribs = entity.attribs or {}
        except Exception:
            attribs = {}
        g.update({"block": block_name, "insert": ins,
                  "attribs": attribs,
                  "scale": [entity.dxf.xscale if entity.dxf.hasattr("xscale") else 1.0,
                            entity.dxf.yscale if entity.dxf.hasattr("yscale") else 1.0],
                  "rotation": entity.dxf.rotation if entity.dxf.hasattr("rotation") else 0.0})
        pts = [tuple(ins)]

    elif etype == "HATCH":
        # 取第一个闭合边界路径的顶点序列（近似面积）
        boundary = []
        for path in entity.paths:
            if not path:
                continue
            if hasattr(path, "edges"):
                for edge in path.edges:
                    sp = getattr(edge, "start_point", None)
                    if sp is not None:
                        v = _vec2(sp)
                        if v:
                            boundary.append(tuple(v))
            elif hasattr(path, "vertices"):
                for v in path.vertices:
                    boundary.append((v[0], v[1]))
            break  # 仅取第一个外环
        g.update({"boundary": boundary})
        if len(boundary) >= 3:
            area = G.closed_polyline_area(boundary)
        pts = boundary if boundary else [(0, 0)]

    elif etype in ("TEXT", "MTEXT"):
        try:
            ins = _vec2(entity.dxf.insert)
            pts = [tuple(ins)] if ins else [(0, 0)]
        except Exception:
            pts = [(0, 0)]
        g.update({"pos": list(pts[0]),
                  "text": getattr(entity, "text", "")[:200] if hasattr(entity, "text") else ""})

    elif etype == "POINT":
        p = _vec2(entity.dxf.location)
        pts = [tuple(p)] if p else [(0, 0)]
        g.update({"pos": list(pts[0])})

    else:
        return None, 0.0, 0.0, None

    if not pts:
        return None, 0.0, 0.0, None

    bbox = G.bbox_of_points(pts)
    return g, length, area, bbox


def _apply_insert_transform(geom: dict, insert: list, scale: list, rot: float) -> dict:
    """对几何 dict 应用 INSERT 变换（位移+缩放+旋转），返回新 dict。
    用于嵌套块展开：将子块几何变换到父块的局部坐标系。
    """
    rad = math.radians(rot)
    c, s = math.cos(rad), math.sin(rad)
    sx, sy = scale[0] if scale else 1.0, scale[1] if scale else 1.0
    ix, iy = insert[0] if insert else 0.0, insert[1] if insert else 0.0

    def tx(p):
        x = p[0] * sx * c - p[1] * sy * s + ix
        y = p[0] * sx * s + p[1] * sy * c + iy
        return [x, y]

    g = dict(geom)  # 浅拷贝

    # 点列表（LWPOLYLINE / POLYLINE / SPLINE）
    if "points" in g and isinstance(g["points"], list):
        g["points"] = [tx(p) for p in g["points"]]

    # LINE
    if "start" in g and isinstance(g["start"], list):
        g["start"] = tx(g["start"])
    if "end" in g and isinstance(g["end"], list):
        g["end"] = tx(g["end"])

    # ARC / CIRCLE
    if "center" in g and isinstance(g["center"], list):
        g["center"] = tx(g["center"])
        if "radius" in g:
            # 非均匀缩放下圆变椭圆——近似用平均缩放
            g["radius"] = g["radius"] * (abs(sx) + abs(sy)) / 2
        if "start_angle" in g:
            g["start_angle"] = g["start_angle"] + rot
        if "end_angle" in g:
            g["end_angle"] = g["end_angle"] + rot

    # ELLIPSE
    if "major" in g and isinstance(g["major"], list):
        mx, my = g["major"]
        # 旋转向量 + 缩放
        g["major"] = [mx * sx * c - my * sy * s,
                      mx * sx * s + my * sy * c]

    # HATCH
    if "boundary" in g and isinstance(g["boundary"], list):
        g["boundary"] = [tx(p) for p in g["boundary"]]

    # TEXT / MTEXT / POINT
    if "pos" in g and isinstance(g["pos"], list):
        g["pos"] = tx(g["pos"])

    return g


def _collect_block_geometry(doc, layer_rgb_cache: dict, only_blocks: set | None = None) -> dict:
    """收集块定义几何（供 INSERT 渲染）。

    支持嵌套块：递归展开子 INSERT 引用的块定义几何，应用 INSERT 变换后并入父块。

    兼容 ezdxf + ezdwg：
    - ezdxf: doc.blocks 是 BlocksSection
    - ezdwg: 暂不暴露 blocks（INSERT 渲染时画红叉占位）
    """
    blocks = getattr(doc, "blocks", None)
    if blocks is None:
        return {}

    # 建 block name -> block 对象索引
    block_map = {}
    for block in blocks:
        bname = getattr(block, "name", None) or block.dxf.name
        if bname and not bname.startswith("*"):
            block_map[bname] = block

    # 递归展开，带深度限制和环检测
    _cache: dict = {}
    _resolving: set = set()

    def _resolve(bname: str, depth: int = 0) -> list:
        if bname in _cache:
            return _cache[bname]
        if depth > 8 or bname in _resolving:
            return []  # 深度过大或环引用，截断

        _resolving.add(bname)
        block = block_map.get(bname)
        if block is None:
            _resolving.discard(bname)
            return []

        geoms = []
        for e in block:
            et = e.dxftype() if hasattr(e, "dxftype") and callable(getattr(e, "dxftype", None)) else e.dxftype
            if et not in GEOMETRIC_TYPES:
                continue
            try:
                g, _, _, _ = _entity_geom(e)
            except Exception:
                continue
            if not g:
                continue
            if g.get("type") == "insert":
                # 嵌套 INSERT：递归展开子块，应用变换后追加
                nested_name = g.get("block", "")
                nested_geoms = _resolve(nested_name, depth + 1)
                if nested_geoms:
                    ins = g.get("insert", [0, 0])
                    sc = g.get("scale", [1.0, 1.0])
                    rt = g.get("rotation", 0.0)
                    for ng in nested_geoms:
                        geoms.append(_apply_insert_transform(ng, ins, sc, rt))
            else:
                geoms.append(g)

        _resolving.discard(bname)
        _cache[bname] = geoms
        return geoms

    target = only_blocks if only_blocks is not None else set(block_map.keys())
    result = {}
    for bname in target:
        if bname in block_map:
            geoms = _resolve(bname)
            if geoms:
                result[bname] = geoms
    return result


def parse_dxf(path: str, progress_callback=None) -> ParsedDrawing:
    """解析 DXF/DWG 文件 → ParsedDrawing。

    progress_callback(done: int, total: int | None)：解析期间周期性回调
    （实体阶段每 1000 个一次；块收集阶段回调一次 (-1, block_count)）。

    Phase 24：通过 reader.py 抽象层自动选 backend
    - .dwg → ezdwg（R14-R2018 DWG 直读，2026）
    - .dxf → ezdxf（DXF R12-R2018）
    """
    from .reader import read_cad
    doc = read_cad(path)
    raw_doc = doc.raw
    msp = doc.modelspace()

    layer_rgb_cache = {}
    # 图层 RGB 缓存（兼容 ezdxf；ezdwg 不支持 layer.rgb 走 fallback）
    if doc.backend == "ezdxf":
        for layer in raw_doc.layers:
            try:
                if layer.rgb is not None:
                    layer_rgb_cache[layer.dxf.name] = tuple(layer.rgb)
            except Exception:
                pass

    drawing = ParsedDrawing()
    referenced_blocks = set()

    try:
        total = len(msp)
    except Exception:
        total = None   # ezdwg 无 len 且解码受限时容错，进度回调用 None
    for idx, entity in enumerate(msp):
        if progress_callback and idx % 1000 == 0:
            progress_callback(idx, total)
        etype = entity.dxftype
        if etype not in GEOMETRIC_TYPES:
            continue
        # 单实体全链路容错：ODA 生成的 DXF 可能含畸形实体（如非法 axis_ratio），
        # 任一步失败跳过该实体，不中断整图解析
        try:
            geom, length, area, bbox = _entity_geom(entity)
            if geom is None:
                continue
            color = _aci_to_rgb(entity, layer_rgb_cache)
            ent = Entity(
                sheet_id=0,
                handle=entity.handle,
                dxf_type=etype,
                layer=entity.layer,
                block_name=entity.block_name,
                bbox=bbox,
                geom_json=json.dumps(geom, ensure_ascii=False),
                length=length,
                area=area,
                color=color,
            )
            drawing.entities.append(ent)
            drawing.layers[ent.layer] = drawing.layers.get(ent.layer, 0) + 1
            # Phase 2: 记录图层代表色（首个实体的颜色）
            if ent.layer not in drawing.layer_colors and ent.color:
                drawing.layer_colors[ent.layer] = ent.color
            if etype == "INSERT":
                drawing.block_refs[ent.block_name] = drawing.block_refs.get(ent.block_name, 0) + 1
                drawing.blocks_with_count.setdefault(ent.block_name, []).append(ent)
                referenced_blocks.add(ent.block_name)
        except Exception:
            continue

    if progress_callback:
        progress_callback(total, total)
        progress_callback(-1, len(referenced_blocks))

    drawing.blocks = _collect_block_geometry(raw_doc, layer_rgb_cache, referenced_blocks)
    if progress_callback:
        progress_callback(total + 1, total + 1)
    return drawing


def layer_infos(drawing: ParsedDrawing) -> list:
    return [LayerInfo(name=k, entity_count=v) for k, v in
            sorted(drawing.layers.items(), key=lambda x: -x[1])]


def block_infos(drawing: ParsedDrawing) -> list:
    return [BlockInfo(name=k, entity_count=v) for k, v in
            sorted(drawing.block_refs.items(), key=lambda x: -x[1])]
