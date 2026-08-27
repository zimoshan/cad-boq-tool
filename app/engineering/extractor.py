"""工程对象提取：CAD Entity → EngineeringObject（设备/线性/面积三类）。

V2 第二版（任务二十八）：按"项目级 layer_rules"白名单驱动分类
- 项目无配置时退化到全局 BUILDING_BG_KEYWORDS 过滤
- 用户在「项目设置」里把图层归到 4 个桶（设备/导线/面积/跳过）
- 未归类的图层（无规则 + 不在背景黑名单）默认按"设备"处理（兼容旧项目）
"""
from __future__ import annotations

from .. import db
from ..takeoff.aggregate import extract_typical_sizes
from .classifier import (infer_object_meta, LINEAR_TYPES, AREA_TYPES,
                          _is_building_bg_layer)
from .object_model import make_engineering_object
from .specification import infer_spec_from_block

# 溯源锚点上限：超过部分靠 block/layer 反查（entity_ids 只存直接锚点）
MAX_TRACE_IDS = 2000

# 类别常量（与 project_config.layer_rules 的 key 对齐）
CAT_EQUIPMENT = "equipment"
CAT_LINEAR = "linear"
CAT_AREA = "area"
CAT_SKIP = "skip"
_ALL_CATS = (CAT_EQUIPMENT, CAT_LINEAR, CAT_AREA, CAT_SKIP)


def _legend_confirmed(project_id: int) -> dict:
    """{block_name: legend_row} 已确认图例（提升置信度/规格）"""
    return {k: v for k, v in db.get_block_legend_map(project_id).items()
            if v.get("confirmed")}


def _attribs_from_entities(ents: list) -> dict:
    """从 INSERT 实体的 geom_json 中聚合块属性（ATTRIB）。

    取第一个含 attribs 的实体，返回 {tag: value}；无则 {}。
    """
    import json
    for e in ents:
        if not e.geom_json:
            continue
        try:
            g = json.loads(e.geom_json)
        except Exception:
            continue
        if isinstance(g, dict) and g.get("attribs"):
            return g["attribs"]
    return {}


def _spec_from_attribs(attribs: dict) -> str:
    """从块属性中提取规格片段（型号/口径/功率等），无则空串。

    优先取常见规格 tag（MODEL/TYPE/SPEC/SIZE/DN/型号/规格），
    否则把所有非空 value 拼接去重。
    """
    if not attribs:
        return ""
    preferred = ("MODEL", "TYPE", "SPEC", "SIZE", "DN", "POWER", "WATT",
                 "型号", "规格", "口径", "功率")
    vals = []
    for tag, val in attribs.items():
        t = str(tag).upper()
        v = str(val).strip()
        if not v:
            continue
        if any(p in t for p in preferred):
            vals.append(v)
    if not vals:
        vals = [str(v).strip() for v in attribs.values() if str(v).strip()]
    # 去重保序
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return " ".join(out)[:200]


def _infer_rule_from_geometry(ents: list, fallback: str) -> str:
    """从实体几何类型推断计量规则（count/length/area）。

    统计各类实体数量，取占比最高者；无有效实体时用 fallback。
    """
    if not ents:
        return fallback
    counts = {"count": 0, "length": 0, "area": 0}
    for e in ents:
        t = (e.dxf_type or "").upper()
        if t == "INSERT":
            counts["count"] += 1
        elif t in AREA_TYPES or (t == "LWPOLYLINE" and (e.area or 0) > 0):
            counts["area"] += 1
        elif t in LINEAR_TYPES and (e.length or 0) > 0:
            counts["length"] += 1
    best = max(counts, key=lambda k: counts[k])
    return best if counts[best] > 0 else fallback


def _resolve_layer_category(layer_name: str, project_layer_rules: dict) -> str | None:
    """根据项目规则+全局背景判断图层类别。返回 None 表示「未分类」。"""
    if not layer_name or layer_name == "0":
        return CAT_SKIP  # 空/默认 = 跳过
    upper = layer_name.upper()
    # 1) 先看项目白名单（按 token 包含关键词）
    if project_layer_rules:
        for cat in _ALL_CATS:
            kws = project_layer_rules.get(cat, [])
            for kw in kws:
                if kw and kw.upper() in upper:
                    return cat
    # 2) 未配置规则 → 退化全局 BUILDING_BG 判定
    if _is_building_bg_layer(layer_name):
        return CAT_SKIP
    return None  # 未分类：交给调用方按"无规则默认设备"逻辑


def _apply_knowledge_base(project_id: int, meta: dict, block_name: str = "",
                          layer_name: str = "") -> dict:
    """知识库层：用 symbol_library 覆盖规则推断的语义（三重兜底第 2 层）。

    命中知识库 → 覆盖 discipline/system/spec/quantity_rule，并提升置信度。
    未命中 → 原样返回（交给规则/LLM）。
    """
    try:
        sym = db.get_symbol(project_id, block_name=block_name, layer_name=layer_name)
    except Exception:
        return meta
    if not sym:
        return meta
    if sym.discipline:
        meta["discipline"] = sym.discipline
    if sym.system:
        meta["system"] = sym.system
    if sym.spec:
        meta["spec"] = sym.spec
    if sym.quantity_rule:
        meta["quantity_rule"] = sym.quantity_rule
    meta["confidence"] = max(meta.get("confidence", 0.0), 0.9)  # 人工标定 → 高置信
    meta["from_knowledge_base"] = True
    return meta


def extract_and_store_engineering_objects(project_id: int, sheet_id: int,
                                          layer_rules: dict = None) -> dict:
    """从一张图纸的 entity 提取三类工程对象并落库（幂等：先清旧）。

    Args:
        project_id: 项目 ID
        sheet_id: 图纸 ID
        layer_rules: 项目级图层筛选规则（None 时从 db 读取；空 dict 退化到全局背景过滤）

    Returns:
        {"created": int, "stats": {...}, "object_ids": [int,...]}
    """
    if layer_rules is None:
        cfg = db.get_project_config(project_id)
        layer_rules = cfg.get("layer_rules", {})

    has_project_rules = any(layer_rules.get(c) for c in _ALL_CATS)

    db.delete_eo_for_sheet(sheet_id)   # 幂等重建
    confirmed_legend = _legend_confirmed(project_id)
    created: list[int] = []
    stats = {"equipment": 0, "linear": 0, "area": 0,
             "skipped_anonymous_blocks": 0, "skipped_building_bg": 0,
             "skipped_unclassified": 0}

    # ===== 设备类：INSERT 块 =====
    for bname, cnt in db.distinct_blocks(sheet_id):
        if not bname or bname.startswith("*"):
            stats["skipped_anonymous_blocks"] += 1
            continue
        ents = db.get_entities(sheet_id, block=bname)
        layer = ents[0].layer if ents else ""
        cat = _resolve_layer_category(layer, layer_rules)
        if cat is None:
            if has_project_rules:
                # 已配置规则但未归类 → 严格跳过
                stats["skipped_unclassified"] += 1
                continue
            else:
                # 无项目规则 → 兼容旧行为，归设备
                cat = CAT_EQUIPMENT
        if cat == CAT_SKIP:
            stats["skipped_building_bg"] += 1
            continue
        if cat != CAT_EQUIPMENT:
            # 设备/INSERT 仅走 equipment 桶；其它桶（linear/area）在图层聚合段处理
            continue
        meta = infer_object_meta(block_name=bname, layer_name=layer)
        # 知识库层（三重兜底第 2 层）：人工标定优先于规则
        meta = _apply_knowledge_base(project_id, meta, block_name=bname, layer_name=layer)
        spec = meta.get("spec") or infer_spec_from_block(bname)
        # 置信语义（三重兜底第 3 层 LLM 补充的输入）：
        #   规则未命中 → 0.4（低置信，供 llm_classify_uncertain 按 <0.5 触发 LLM）
        conf = 0.8 if meta["confidence"] > 0 else 0.4
        legend = confirmed_legend.get(bname)
        if legend:
            spec = legend.get("spec") or spec
            conf = 0.95                       # 人工确认 → 高置信
        elif meta.get("from_knowledge_base"):
            conf = 0.9                        # 知识库命中 → 高置信
        else:
            # 块属性（ATTRIB）优先于块名正则：型号/规格/材质直接入库
            attribs = _attribs_from_entities(ents)
            attr_spec = _spec_from_attribs(attribs)
            if attr_spec:
                spec = attr_spec
                conf = max(conf, 0.85)        # 有块属性 → 置信度提升
        qty_rule = meta.get("quantity_rule") or "count"
        eo = make_engineering_object(
            project_id, sheet_id, object_type="equipment",
            discipline=meta["discipline"], system=meta["system"],
            block_name=bname, layer_name=layer, specification=spec,
            unit="个", quantity_rule=qty_rule, confidence=conf,
            source="rule", entity_ids=[e.id for e in ents][:MAX_TRACE_IDS])
        created.append(db.create_engineering_object(
            project_id, sheet_id, object_type=eo.object_type,
            discipline=eo.discipline, system=eo.system,
            block_name=eo.block_name, layer_name=eo.layer_name,
            specification=eo.specification, unit=eo.unit,
            quantity_rule=eo.quantity_rule, confidence=eo.confidence,
            source=eo.source, entity_ids=eo.entity_ids))
        stats["equipment"] += 1

    # ===== 线性 / 面积类：图层聚合 =====
    for lname, _cnt in db.distinct_layers(sheet_id):
        if not lname:
            continue
        cat = _resolve_layer_category(lname, layer_rules)
        if cat is None:
            if has_project_rules:
                stats["skipped_unclassified"] += 1
                continue
            else:
                cat = CAT_LINEAR  # 旧行为默认
        if cat == CAT_SKIP or cat == CAT_EQUIPMENT:
            if cat == CAT_SKIP:
                stats["skipped_building_bg"] += 1
            continue
        ents = db.get_entities(sheet_id, layer=lname)
        lin = [e for e in ents if e.dxf_type in LINEAR_TYPES and (e.length or 0) > 0]
        area = [e for e in ents
                if (e.dxf_type in AREA_TYPES or e.dxf_type == "LWPOLYLINE")
                and (e.area or 0) > 0]
        meta = infer_object_meta(layer_name=lname)
        # 知识库层（三重兜底第 2 层）：人工标定优先于规则
        meta = _apply_knowledge_base(project_id, meta, layer_name=lname)
        # 规格从图层名提取（实证：电气导线图层名即电缆型号，如 "00 aten line NHXMH 4x1.5"）
        specs = extract_typical_sizes([lname])
        spec = meta.get("spec") or (specs[0] if specs else "")
        # 计量规则从几何推断（而非仅按类型桶）：闭合多段线→area、线→length
        rule = meta.get("quantity_rule") or _infer_rule_from_geometry(ents, fallback="length")
        lin_conf = 0.7 if meta["confidence"] > 0 else 0.4   # 低置信留给 LLM 第3层补充
        if cat == CAT_LINEAR and lin:
            obj_type = "area" if rule == "area" else "linear"
            unit = "m²" if rule == "area" else "m"
            eo = make_engineering_object(
                project_id, sheet_id, object_type=obj_type,
                discipline=meta["discipline"], system=meta["system"],
                layer_name=lname, specification=spec, unit=unit,
                quantity_rule=rule, confidence=lin_conf, source="rule",
                entity_ids=[e.id for e in (area if rule == "area" else lin)][:MAX_TRACE_IDS])
            created.append(db.create_engineering_object(
                project_id, sheet_id, object_type=eo.object_type,
                discipline=eo.discipline, system=eo.system,
                layer_name=eo.layer_name, specification=spec, unit=unit,
                quantity_rule=eo.quantity_rule, confidence=eo.confidence,
                source=eo.source, entity_ids=eo.entity_ids))
            stats["area" if rule == "area" else "linear"] += 1
        if cat == CAT_AREA and area:
            obj_type = "linear" if rule == "length" else "area"
            unit = "m" if rule == "length" else "m²"
            rule = rule if rule in ("length", "area") else "area"
            eo = make_engineering_object(
                project_id, sheet_id, object_type=obj_type,
                discipline=meta["discipline"], system=meta["system"],
                layer_name=lname, specification=spec, unit=unit,
                quantity_rule=rule, confidence=lin_conf, source="rule",
                entity_ids=[e.id for e in (lin if rule == "length" else area)][:MAX_TRACE_IDS])
            created.append(db.create_engineering_object(
                project_id, sheet_id, object_type=eo.object_type,
                discipline=eo.discipline, system=eo.system,
                layer_name=eo.layer_name, specification=spec, unit=unit,
                quantity_rule=eo.quantity_rule, confidence=eo.confidence,
                source=eo.source, entity_ids=eo.entity_ids))
            stats["linear" if rule == "length" else "area"] += 1

    return {"created": len(created), "stats": stats, "object_ids": created}


def list_project_objects(project_id: int, object_type: str = None) -> list:
    """项目级工程对象列表（供 Binding Workbench 左侧使用）"""
    return db.get_engineering_objects(project_id, object_type=object_type)


def get_object_trace(eoid: int) -> dict:
    """溯源：工程对象 → 实体 handle/bbox → 图纸路径。

    Returns:
        {"object": EngineeringObject, "entities": [Entity...], "sheet": Sheet|None}
    """
    eo = db.get_engineering_object(eoid)
    if not eo:
        return {"object": None, "entities": [], "sheet": None}
    ents = []
    for eid in eo.entity_ids:
        e = db.get_entity(eo.sheet_id, eid)
        if e:
            ents.append(e)
    sheet = None
    if eo.sheet_id:
        for s in db.get_sheets(eo.project_id):
            if s.id == eo.sheet_id:
                sheet = s
                break
    return {"object": eo, "entities": ents, "sheet": sheet}
