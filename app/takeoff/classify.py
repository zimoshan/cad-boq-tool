"""规则分类：基于图层名/块名的启发式分类。

Phase 22A-2：
- 输入：图层名 / 块名
- 输出：[(分类, 置信度)]
- 0 依赖 0 GPU，秒级出结果
- 用于先于 LLM 跑（节省 LLM 调用）
"""
from __future__ import annotations

import re
from typing import List, Tuple


# 行业常见图层命名规则（基于 CAD 标准 + 广联达 + 鸿业 + 探索者 等）
LAYER_RULES: dict = {
    "给水": {
        "layer_kw": ["WATER", "WS", "P-", "WSUP", "CWS", "HWS", "DOMW", "给水", "PIPE-WATER"],
        "block_kw": ["VALVE", "TAP", "TEE", "ELBOW", "COUPLING", "WATER_METER", "GATE_VALVE"],
    },
    "排水": {
        "layer_kw": ["DRAIN", "RAIN", "W-", "WDR", "CDR", "DDR", "DWV", "SOIL", "WASTE", "排水", "排雨"],
        "block_kw": ["CLEANOUT", "FLOOR_DRAIN", "FLOOR_DRAIN_G", "ROOF_DRAIN", "P-TRAP", "GREASE_TRAP"],
    },
    "喷淋": {
        "layer_kw": ["SPRINKLER", "FP", "FIRE-PRO", "SP-", "FIRE_PROT", "喷淋", "自动喷淋", "SP"],
        "block_kw": ["SPRINKLER_HEAD", "SPRINKLER", "PENDENT", "UPRIGHT", "SIDEWALL", "FIRE_DEPT"],
    },
    "消防": {
        "layer_kw": ["FIRE", "F-", "FIRE_PROT", "FPT", "消防", "消火栓", "灭火"],
        "block_kw": ["FIRE_EXTINGUISHER", "FIRE_HYDRANT", "HOSE", "STANDPIPE", "FIRE_PUMP"],
    },
    "暖通-风": {
        "layer_kw": ["HVAC", "DUCT", "H-", "AIR", "SUPPLY", "RETURN", "EXHAUST", "风", "送风", "排风", "回风"],
        "block_kw": ["DIFFUSER", "VAV", "VAV_BOX", "DAMPER", "FAN", "AHU", "FILTER", "GRILLE", "REGISTER"],
    },
    "暖通-水": {
        "layer_kw": ["CHILLER", "BOILER", "COOLING", "HEATING", "HW-", "CHW-", "COND", "冷热", "冷冻", "冷却", "采暖"],
        "block_kw": ["PUMP", "CHILLER", "BOILER", "EXPANSION_TANK", "AIR_SEPARATOR"],
    },
    "电气-强电": {
        "layer_kw": ["E-", "ELEC", "POWER", "LITE", "LIGHT", "电", "照明", "动力", "强电", "配电"],
        "block_kw": ["OUTLET", "SWITCH", "LIGHT", "PANEL", "BREAKER", "RECEPTACLE", "MCC", "TRANSFORMER"],
    },
    "电气-弱电": {
        "layer_kw": ["T-", "TELE", "DATA", "弱电", "通讯", "电话", "网络", "光纤", "监控", "BA", "FA"],
        "block_kw": ["DATA_OUTLET", "TELE_OUTLET", "CAMERA", "SPEAKER", "SENSOR", "ACCESS_POINT"],
    },
    "桥架": {
        "layer_kw": ["CT-", "CABLE", "TRAY", "LADDER", "桥架", "电缆桥"],
        "block_kw": ["TRAY", "CABLE_TRAY", "LADDER"],
    },
    "暖通-管": {
        "layer_kw": ["PIPE", "PIPING", "P-", "管"],
        "block_kw": ["PIPE", "JOINT", "FLANGE"],
    },
}


# 块名分类规则（INSERT 块名）
BLOCK_RULES: dict = {
    "阀门":       ["VALVE", "GATE", "BALL", "CHECK", "BUTTERFLY", "阀门"],
    "传感器":     ["SENSOR", "DETECTOR", "THERMOSTAT", "METER", "传感器"],
    "喷头":       ["SPRINKLER_HEAD", "SPRINKLER", "PENDENT", "UPRIGHT", "SIDEWALL", "喷头"],
    "风口":       ["DIFFUSER", "GRILLE", "REGISTER", "风口", "散流器"],
    "灯具":       ["LIGHT", "LUMINAIRE", "FIXTURE", "灯具", "灯"],
    "插座":       ["OUTLET", "RECEPTACLE", "插座"],
    "开关":       ["SWITCH", "开关"],
    "配电箱":     ["PANEL", "BOARD", "CABINET", "配电箱", "配电柜"],
    "风机盘管":   ["FCU", "FAN_COIL", "风机盘管"],
    "水泵":       ["PUMP", "水泵"],
    "水表":       ["WATER_METER", "METER", "水表"],
    "地漏":       ["FLOOR_DRAIN", "DRAIN", "地漏"],
    "检查井":     ["CLEANOUT", "C/O", "检查井", "清扫口"],
}


def normalize(name: str) -> str:
    """统一大小写、去空格/特殊字符"""
    return re.sub(r"[\s_\-]+", "", str(name).upper())


def classify_layer(layer_name: str) -> List[Tuple[str, float]]:
    """返回 [(分类, 置信度)] 列表，按置信度降序"""
    if not layer_name:
        return []
    norm = normalize(layer_name)
    scores = []
    for category, rules in LAYER_RULES.items():
        # 过滤过短的关键字（避免 "P"/"W"/"H" 误判）
        layer_hits = [kw for kw in rules["layer_kw"]
                      if len(normalize(kw)) >= 2 and normalize(kw) in norm]
        block_hits = [kw for kw in rules["block_kw"]
                      if len(normalize(kw)) >= 2 and normalize(kw) in norm]
        if layer_hits:
            # 置信度按最长关键字长度
            best = max(layer_hits, key=lambda k: len(normalize(k)))
            conf = min(0.95, 0.6 + len(normalize(best)) * 0.05)
            scores.append((category, conf))
        elif block_hits:
            best = max(block_hits, key=lambda k: len(normalize(k)))
            conf = min(0.6, 0.4 + len(normalize(best)) * 0.03)
            scores.append((category, conf))
    return sorted(scores, key=lambda x: -x[1])


def classify_block(block_name: str) -> List[Tuple[str, float]]:
    """返回块名分类"""
    if not block_name or block_name.startswith("*"):
        return []
    norm = normalize(block_name)
    scores = []
    for category, keywords in BLOCK_RULES.items():
        if any(normalize(kw) in norm for kw in keywords):
            scores.append((category, 0.85))
    return scores


def classify_all_layers(layer_names: list) -> dict:
    """批量分类所有图层名，返回 {layer_name: [(category, confidence)]}"""
    return {name: classify_layer(name) for name in layer_names}


def get_top_category(layer_name: str) -> Tuple[str, float]:
    """获取最高置信度分类（便捷 API）"""
    results = classify_layer(layer_name)
    if results:
        return results[0]
    return ("未分类", 0.0)


def suggest_boq_categories(layer_summaries: list) -> list:
    """从图层级汇总推断可能的 BOQ 分类（喂 LLM 前的预筛）

    Args:
        layer_summaries: list of {name, entity_count, ...} (来自 aggregate.py)

    Returns:
        list of (boq_category, [layer_names], total_entity_count)
    """
    category_layers: dict = {}
    for ls in layer_summaries:
        name = ls["name"] if isinstance(ls, dict) else ls.name
        cat, conf = get_top_category(name)
        if conf >= 0.7:
            category_layers.setdefault(cat, []).append(name)

    return [
        (cat, layers, len(layers))
        for cat, layers in sorted(category_layers.items(), key=lambda x: -len(x[1]))
    ]
