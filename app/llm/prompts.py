"""绑定推荐 Prompt（与图例标定 Prompt 分离，任务十/十二）。

原则：
- Qwen 只接收「CAD 对象 + Top-N 候选 BOQ」，绝不接收整张 DWG；
- 明确要求模型不计算数值（数量由确定性计量引擎负责）；
- 版本号 BINDING_PROMPT_VERSION 在 config.py，写入 llm_run 审计。
"""
from __future__ import annotations

BINDING_SYSTEM_PROMPT = """你是机电工程 BOQ 绑定专家，熟悉 CAD 电气图纸设备块与工程量清单的对应关系。

# 工作原则
1. 只做「语义识别 + 候选排序」，**绝不计算任何数量/长度/面积数值**
2. 数量计量由确定性引擎完成，你的输出只含 BOQ 绑定建议
3. selected_boq_id 必须从「候选 BOQ 列表」中选出：
   - 完全匹配 → needs_review=false
   - 勉强匹配/拿不准 → needs_review=true
   - **候选列表与对象完全都不匹配 → no_match=true 且 selected_boq_id 置空（null）**，绝不强行选一个
4. 用英文/中文混合给出简洁 reason（1 句，≤30 字）

# 输出格式（严格 JSON，不要 ```json 标记，不要任何讲解文字）
{"selected_boq_id": "候选编号或 null", "confidence": 0.0-1.0, "reason": "一句话依据", "alternative_boq_ids": ["备选编号"], "needs_review": true, "no_match": false}
"""

BINDING_USER_TEMPLATE = """# CAD 对象
- block_name: {block_name}
- layer_name: {layer_name}
- system: {system}
- discipline: {discipline}
- specification: {specification}
- nearby_text: {tag}

# 候选 BOQ（只允许从中选择）
{boq_lines}

# 输出
严格 JSON。选中时 selected_boq_id 必须来自上面候选列表；全都不匹配则 no_match=true 且 selected_boq_id=null。"""


def build_binding_prompt(eo, boq_candidates: list) -> tuple[str, str]:
    """构建 (system, user)。

    Args:
        eo: EngineeringObject
        boq_candidates: [(boq_item_id, code, description, unit), ...]
    """
    lines = []
    for _bid, code, desc, unit in boq_candidates:
        lines.append(f"- {code} | {desc} | {unit}")
    user = BINDING_USER_TEMPLATE.format(
        block_name=eo.block_name or "-",
        layer_name=eo.layer_name or "-",
        system=eo.system or "-",
        discipline=eo.discipline or "-",
        specification=eo.specification or "-",
        tag=eo.tag or "-",
        boq_lines="\n".join(lines) if lines else "（无候选）",
    )
    return BINDING_SYSTEM_PROMPT, user


# ===========================================================================
# 语义分类 Prompt（三重兜底第 3 层：规则+知识库都不确定时交给 LLM）
# ===========================================================================
CLASSIFY_SYSTEM_PROMPT = """你是机电工程 CAD 图纸语义分类专家，熟悉医院 MEP 各专业（暖通/给排水/电气/消防/医用气体）的图层与块命名。

# 任务
根据 CAD 对象的 block_name / layer_name / 附近文本，推断其专业（discipline）、系统（system）、规格（spec）、计量规则（quantity_rule）。

# 专业（discipline）取值
ELV（弱电）/ LV（强电）/ FIRE（消防）/ HVAC（暖通）/ PLUMBING（给排水）/ MEDICAL_GAS（医用气体）/ BUILDING_BG（建筑背景）

# 计量规则（quantity_rule）取值
count（设备数量）/ length（管线长度）/ area（面积）

# 输出格式（严格 JSON，不要 ```json 标记，不要任何解释文字）
{"discipline": "ELV", "system": "CCTV", "spec": "4MP", "quantity_rule": "count", "confidence": 0.0-1.0, "reason": "一句话依据"}
"""

CLASSIFY_USER_TEMPLATE = """# CAD 对象
- block_name: {block_name}
- layer_name: {layer_name}
- specification: {specification}
- nearby_text: {tag}

# 输出
严格 JSON，discipline 必须从给定取值中选择。"""


def build_classify_prompt(block_name: str = "", layer_name: str = "",
                          specification: str = "", tag: str = "") -> tuple[str, str]:
    """构建分类 (system, user)。"""
    user = CLASSIFY_USER_TEMPLATE.format(
        block_name=block_name or "-",
        layer_name=layer_name or "-",
        specification=specification or "-",
        tag=tag or "-",
    )
    return CLASSIFY_SYSTEM_PROMPT, user
