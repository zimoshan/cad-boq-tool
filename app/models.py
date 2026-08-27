"""数据模型（dataclass，与 SQLite 表一一对应）"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    id: int
    name: str
    created_at: str = ""
    boq_path: str = ""


@dataclass
class Sheet:
    id: int
    project_id: int
    filename: str
    src_path: str = ""
    dxf_path: str = ""
    status: str = "ready"          # converting / ready / failed
    scale: float = 1.0
    entity_count: int = 0
    layer_count: int = 0
    blocks_json: str = ""          # 块几何缓存（JSON），切换图纸免重新解析
    is_base: int = 0               # 1=该图纸为建筑底图（图层减法基准）


@dataclass
class Entity:
    """解析后的 CAD 实体（跨会话稳定 ID = handle）"""
    id: int = 0
    sheet_id: int = 0
    handle: str = ""
    dxf_type: str = ""
    layer: str = ""
    block_name: str = ""           # INSERT 时有效
    bbox: tuple = (0, 0, 0, 0)     # (min_x, min_y, max_x, max_y)
    geom_json: str = ""            # 原始几何（JSON），计量时反序列化
    length: float = 0.0            # 预计算长度（可计量实体）
    area: float = 0.0              # 预计算面积（闭合实体）
    color: tuple = (255, 255, 255) # 渲染颜色


@dataclass
class BoqItem:
    id: int = 0
    project_id: int = 0
    row_index: int = 0
    code: str = ""
    description: str = ""
    unit: str = ""
    original_qty: float = 0.0
    rule_type: str = "length"      # length / area / count
    scale_factor: float = 1.0
    mapped_count: int = 0          # 已映射实体数（运行时）
    measured_qty: float = 0.0      # 计量结果（运行时）


@dataclass
class Mapping:
    id: int = 0
    boq_item_id: int = 0
    sheet_id: int = 0
    mode: str = "entity"           # entity / layer / block
    entity_id: Optional[int] = None
    layer_name: str = ""
    block_name: str = ""
    created_at: str = ""


@dataclass
class LayerInfo:
    name: str
    entity_count: int
    visible: bool = True
    color: tuple = (128, 128, 128)     # Phase 2: 图层代表色（来自首个实体）


@dataclass
class BlockInfo:
    name: str
    entity_count: int


# ---------- V2：工程对象 / 绑定候选 / LLM 审计 ----------

@dataclass
class EngineeringObject:
    """CAD 中具有工程意义的对象（V2 binding 管线的核心实体）"""
    id: int = 0
    project_id: int = 0
    sheet_id: int = 0
    object_type: str = ""              # equipment / linear / area
    discipline: str = ""               # ELV / LV / FIRE / HVAC / PLUMBING ...
    system: str = ""                   # CCTV / LIGHTING / FA ...
    subsystem: str = ""
    block_name: str = ""               # INSERT 块名（设备类）
    layer_name: str = ""               # 图层名（线性/面积类）
    tag: str = ""                      # 图元近旁 TEXT 抽取的标签
    specification: str = ""            # 4MP Dome Camera / DN100 ...
    material: str = ""
    unit: str = ""                     # No. / m / m²
    quantity_rule: str = "count"       # count / length / area（确定性计量用）
    confidence: float = 0.0
    source: str = ""                   # rule / llm / manual
    entity_ids: list = field(default_factory=list)   # [entity_id,...] 溯源锚点
    created_at: str = ""
    updated_at: str = ""


@dataclass
class BindingCandidate:
    """AI/规则产出的绑定候选（未确认，不得进入正式 mapping）"""
    id: int = 0
    project_id: int = 0
    engineering_object_id: int = 0
    boq_item_id: int = 0
    method: str = "LLM"                # RULE / EMBEDDING / LLM / MANUAL
    score: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    model: str = ""
    model_version: str = ""
    prompt_version: str = ""
    llm_run_id: Optional[int] = None
    status: str = "PENDING"            # PENDING / ACCEPTED / REJECTED / SUPERSEDED
    created_at: str = ""


@dataclass
class LlmRun:
    """一次 LLM 调用审计记录"""
    id: int = 0
    project_id: int = 0
    task_type: str = ""                # legend / binding / classify / embedding
    model: str = ""
    model_version: str = ""
    prompt_version: str = ""
    temperature: float = 0.0
    input_hash: str = ""
    output_hash: str = ""
    input_text: str = ""               # 完整输入（system+user），供 prompt 分析优化
    output_text: str = ""              # 模型原始输出全文
    duration_ms: int = 0
    token_input: int = 0
    token_output: int = 0
    status: str = "ok"                 # ok / error / retried
    error: str = ""
    created_at: str = ""


@dataclass
class SymbolLibrary:
    """图例符号知识库（人工标定沉淀，可学习）"""
    id: int = 0
    project_id: int = 0
    block_name: str = ""
    layer_name: str = ""
    discipline: str = ""
    system: str = ""
    spec: str = ""
    unit: str = ""
    quantity_rule: str = ""            # count / length / area
    source: str = "manual"             # manual / llm / rule
    confirmed_by: str = ""
    confirmed_at: str = ""
    updated_at: str = ""
