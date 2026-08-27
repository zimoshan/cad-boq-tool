"""工程对象语义推断：block/layer → discipline/system/object_type。

复用 app/takeoff/classify.py 的启发式规则，并补充 V2 需要的
弱电系统（ELV）细分与对象类型判定。
"""
from __future__ import annotations

import re

from ..takeoff.classify import classify_block, get_top_category

# 电气弱电系统细分（块名/图层名关键词 → system）
ELV_SYSTEM_RULES: dict = {
    "CCTV":     ["CAM", "CCTV", "CAMERA"],
    "FA":       ["SMOKE", "DETECTOR", "FA-", "FIRE_ALARM", "FAS"],
    "LIGHTING": ["LIGHT", "LITE", "LUMINAIRE"],
    "AP/WIFI":  ["AP-", "WIFI", "ACCESS_POINT", "WAP"],
    "DATA":     ["DATA", "NETWORK", "LAN", "RJ45", "PATCH"],
    "TELEPHONE":["TELE", "TEL-", "PHONE", "EPABX"],
    "AV":       ["SPEAKER", "AUDIO", "PA-", "BGM", "AV-"],
    "ACCESS":   ["ACS", "CARD", "READER", "DOOR"],
    "UPS":      ["UPS", "PDU"],
    "BUS":      ["BUS", "BUSBAR", "TRA"]
}

# 图层名 → discipline 映射（优先于 classify 通用规则）
DISCIPLINE_LAYER_RULES: dict = {
    "ELV":    ["ELV", "T-", "TELE", "DATA", "FA", "CCTV", "BA", "AV-"],
    "LV":     ["E-", "ELEC", "POWER", "LITE", "LIGHT"],
    "FIRE":   ["FIRE", "FP", "SP-", "SPRINKLER"],
    "HVAC":   ["HVAC", "DUCT", "AHU", "VAV", "CHW", "HW-"],
    "PLUMBING": ["WS", "WATER", "DRAIN", "P-", "W-", "PLUMB"],
}

# 建筑/装饰背景图层（不算机电设备，候选生成跳过）
BUILDING_BG_KEYWORDS = [
    # 墙/柱/门窗/楼板/屋顶
    "WALL", "WALL-BRICK", "WALL-", "COLUMN", "BEAM", "FLOOR", "SLAB",
    "ROOF", "DOOR", "WINDOW", "STAIR", "RAILING", "BALUSTRADE",
    # 装饰/石膏/瓷片/石材
    "PLASTER", "CLAD", "TILE", "STONE", "PAINT", "FINISH", "DTL-",
    "SKETCH", "HATCH-WALL",
    # 家具
    "FURN", "FURN-MED", "FURN-WC", "FURN-CUSTOM", "FURN-READY",
    "FURN-MECH", "FURN-ELEC", "FURN-KITCHEN",
    # 门窗明细/剖面
    "DTL-WOOD", "DTL-STEEL", "DTL-GLASS", "DTL-PROFILE",
    "DTL-GLASS-DOOR",
    # 房间标识 / 标高
    "ROOM-IDEN", "ROOM-NAME", "ELEV", "ELEV-HIDDEN", "ELEV-5",
    # 医疗不锈钢固定件
    "STAINLESS_STEEL_OPERATION", "STAINLESS_STEEL_OPERATION_ROOM",
    "MEDICAL_GAS", "XRAY", "OPERATION_THEATER",
    # 隔墙预留/家具装饰
    "SHAFT-REZRV", "SHAFT-RES", "INSULATION",
    # 外部引用 / 草图
    "XREF", "SKETCH",
    # 医疗家具与电视（墙壁挂设备不算 BOQ 设备）
    "TV",
    # 建筑梯段/楼梯
    "STAIR",
]


def _is_building_bg_layer(layer_name: str = "") -> bool:
    """判断图层是否为建筑/装饰背景（不参与机电算量）。

    三种匹配方式（顺序）：
    1) 关键词作为整 token 出现在分割后的图层名（精确）
    2) 长关键词（>=4 字符）在图层名中作为连续片段出现
    3) 关键词 `'0'` 单独处理默认图层

    避免 'ELV-CCTV' 被 'TV' 误判（'TV' 是短关键词，但 'CCTV' 中确实包含）。
    """
    if layer_name is None:
        return True
    if not layer_name or layer_name == "0":
        return True  # 空 / 默认图层
    import re as _re
    upper = layer_name.upper()
    for kw in BUILDING_BG_KEYWORDS:
        ku = kw.upper().strip()
        if not ku:
            continue
        # 短关键词（<=3 字符）必须整词匹配，避免 CCTV 误判 TV
        if len(ku) <= 3:
            tokens = {t for t in _re.split(r"[\s_\-/\\.,()]+", upper) if t}
            if ku in tokens:
                return True
            continue
        # 长关键词：要求在图层名中作为完整片段（不被切成多段的字符）
        # 用 token 等值检查（'FURN-MED' 切成 {FURN, MED}，关键词 'FURN-MED' 不在 → 改用 'FURN' 单独检查）
        # 但 'DTL-WOOD' 关键词在 [DTL-WOOD] 整词列表里能命中吗？不能——'DTL-WOOD' 整体需要直接判断
        # 用分隔后的 token 全等集合匹配关键词（关键词先按 -_ 拆再 join）
        # 简化：把 layer 和 keyword 都按 token 比较是否相同任一
        kw_tokens = {t for t in _re.split(r"[\s_\-/\\.,()]+", ku) if t}
        layer_tokens = {t for t in _re.split(r"[\s_\-/\\.,()]+", upper) if t}
        # 匹配任一: keyword 任一 token 在 layer tokens 中（最宽松）
        if kw_tokens & layer_tokens:
            # 但需要避免 'ELV-CCTV' 误判 'TV'：上面已经 short=3 跳过
            # 现在处理 "FURN-MED" 这种：'FURN' 在 layer_tokens 中 → True ✓
            # "STAINLESS_STEEL_OPERATION_ROOM" 关键词：tokens = {STAINLESS,STEEL,OPERATION,ROOM}
            #   layer_tokens = {STAINLESS,STEEL,OPERATION,ROOM} → 'STAINLESS' 命中 → True ✓
            # "ELV-CCTV" 不会到这步（kw_len('TV')=2 <=3 已在上面排除掉 TV 不再入这里）
            return True
    return False

# 设备类块 → 对象类型细分（缺省 equipment）
EQUIPMENT_TYPE_RULES: dict = {
    "camera":      ["CAM", "CCTV"],
    "detector":    ["DETECTOR", "SMOKE"],
    "lamp":        ["LIGHT", "LUMINAIRE", "FIXTURE"],
    "outlet":      ["OUTLET", "RECEPTACLE"],
    "switch":      ["SWITCH"],
    "panel":       ["PANEL", "BOARD", "CABINET", "MCC"],
    "ap":          ["AP", "ACCESS_POINT", "WAP", "WIFI"],
    "speaker":     ["SPEAKER", "HORN"],
    "sensor":      ["SENSOR", "THERMOSTAT", "METER"],
    "valve":       ["VALVE", "GATE", "BALL", "CHECK"],
}

# 线性/面积判定用的几何类型
LINEAR_TYPES = ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE")
AREA_TYPES = ("HATCH",)  # 闭合 LWPOLYLINE 由 area>0 判定


def _match_any(name: str, keywords: list) -> bool:
    if not name:
        return False
    n = re.sub(r"[\s_\-]+", "", name.upper())
    return any(k and re.sub(r"[\s_\-]+", "", k.upper()) in n for k in keywords)


def infer_discipline(layer_name: str = "", block_name: str = "") -> str:
    """图层/块名 → discipline（ELV/LV/FIRE/HVAC/PLUMBING），未知返回 ''"""
    for disc, kws in DISCIPLINE_LAYER_RULES.items():
        if _match_any(layer_name, kws):
            return disc
    if block_name:
        for disc, kws in DISCIPLINE_LAYER_RULES.items():
            if _match_any(block_name, kws):
                return disc
    return ""


def infer_system(block_name: str = "", layer_name: str = "") -> str:
    """块/图层名 → ELV 子系统（CCTV/FA/LIGHTING/...），未知返回 ''"""
    for sys_name, kws in ELV_SYSTEM_RULES.items():
        if _match_any(block_name, kws) or _match_any(layer_name, kws):
            return sys_name
    return ""


def infer_equipment_type(block_name: str) -> str:
    """块名 → 设备细类（camera/detector/...），未知返回 'equipment'"""
    for etype, kws in EQUIPMENT_TYPE_RULES.items():
        if _match_any(block_name, kws):
            return etype
    return "equipment"


def infer_object_meta(block_name: str = "", layer_name: str = "") -> dict:
    """综合推断工程对象语义。

    Returns:
        {object_type, discipline, system, equipment_type, category, confidence}
      - object_type: equipment / linear / area（由调用方按几何判定后覆写）
      - category: 复用 classify.py 的中文大类（如 电气-弱电）
    """
    meta = {
        "object_type": "equipment",
        "discipline": infer_discipline(layer_name, block_name),
        "system": infer_system(block_name, layer_name),
        "equipment_type": infer_equipment_type(block_name) if block_name else "",
        "category": "",
        "confidence": 0.0,
    }
    # 中文大类（classify.py 的 LAYER_RULES/BLOCK_RULES）
    if layer_name:
        cat, conf = get_top_category(layer_name)
        if conf > 0:
            meta["category"] = cat
            meta["confidence"] = max(meta["confidence"], conf)
    if block_name and not block_name.startswith("*"):
        res = classify_block(block_name)
        if res:
            cat, conf = res[0]
            if conf > meta["confidence"]:
                meta["category"] = cat
                meta["confidence"] = conf
    return meta
