"""工程对象（V2 binding 管线第一层）。

从 CAD Entity 提取具有工程意义的对象（设备/线性/面积三类），
为 BOQ 绑定与确定性计量提供语义载体。
"""

from .classifier import (
    AREA_TYPES,
    LINEAR_TYPES,
    infer_discipline,
    infer_equipment_type,
    infer_object_meta,
    infer_system,
)
from .extractor import MAX_TRACE_IDS, extract_and_store_engineering_objects, get_object_trace, list_project_objects
from .object_model import (
    OBJECT_TYPES,
    QUANTITY_RULES,
    SOURCES,
    UNIT_BY_TYPE,
    EngineeringObject,
    make_engineering_object,
)
from .specification import extract_specifications, infer_spec_from_block

__all__ = [
    "EngineeringObject",
    "OBJECT_TYPES",
    "QUANTITY_RULES",
    "UNIT_BY_TYPE",
    "SOURCES",
    "make_engineering_object",
    "infer_object_meta",
    "infer_discipline",
    "infer_system",
    "infer_equipment_type",
    "LINEAR_TYPES",
    "AREA_TYPES",
    "extract_specifications",
    "infer_spec_from_block",
    "extract_and_store_engineering_objects",
    "list_project_objects",
    "get_object_trace",
    "MAX_TRACE_IDS",
]
