"""工程对象模型：常量、工厂与校验。

EngineeringObject 本体定义在 app/models.py（与表结构一一对应），
此处提供合法取值常量与便捷构造/校验函数。
"""
from __future__ import annotations

from ..models import EngineeringObject

# 对象类型
OBJECT_TYPES = ("equipment", "linear", "area")

# 计量规则（与 boq_item.rule_type / block_legend.count_rule 对齐）
QUANTITY_RULES = ("count", "length", "area", "manual")

# 第一版三类对象的单位约定
UNIT_BY_TYPE = {"equipment": "个", "linear": "m", "area": "m²"}

# 允许落库的 source 取值
SOURCES = ("rule", "llm", "manual")


def make_engineering_object(project_id: int, sheet_id: int = 0, object_type: str = "equipment",
                            discipline: str = "", system: str = "", subsystem: str = "",
                            block_name: str = "", layer_name: str = "", tag: str = "",
                            specification: str = "", material: str = "", unit: str = "",
                            quantity_rule: str = "count", confidence: float = 0.0,
                            source: str = "rule", entity_ids: list = None) -> EngineeringObject:
    """构造 EngineeringObject（含默认值与校验修正）"""
    if object_type not in OBJECT_TYPES:
        raise ValueError(f"非法 object_type: {object_type}（可选 {OBJECT_TYPES}）")
    if quantity_rule not in QUANTITY_RULES:
        raise ValueError(f"非法 quantity_rule: {quantity_rule}（可选 {QUANTITY_RULES}）")
    if source not in SOURCES:
        raise ValueError(f"非法 source: {source}（可选 {SOURCES}）")
    return EngineeringObject(
        project_id=project_id, sheet_id=sheet_id, object_type=object_type,
        discipline=discipline, system=system, subsystem=subsystem,
        block_name=block_name, layer_name=layer_name, tag=tag,
        specification=specification, material=material,
        unit=unit or UNIT_BY_TYPE.get(object_type, ""),
        quantity_rule=quantity_rule, confidence=max(0.0, min(1.0, confidence)),
        source=source, entity_ids=list(entity_ids or []),
    )
