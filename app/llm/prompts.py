"""绑定推荐 Prompt（与图例标定 Prompt 分离，任务十/十二）。

原则：
- Qwen 只接收「CAD 对象 + Top-N 候选 BOQ」，绝不接收整张 DWG；
- 明确要求模型不计算数值（数量由确定性计量引擎负责）；
- 版本号 BINDING_PROMPT_VERSION 在 config.py，写入 llm_run 审计。
"""
from __future__ import annotations

BINDING_SYSTEM_PROMPT = """你是机电工程 BOQ 绑定专家。任务：判断图纸上的一个 CAD 对象对应清单中的哪一条 BOQ 清单项。

# 输入字段含义
- block_name：块名（设备图块的名称，最可靠的判断依据）
- layer_name：图层名（按 CAD 图层命名约定，如 E-LIGHTING=电气照明）
- system：系统缩写（如 LIGHTING/POWER/FP/BMS）
- discipline：专业代码（LV 强电 / ELV 弱电 / FIRE 消防等）
- specification：规格型号
- nearby_text：对象附近的标注文字（常含编号、容量、规格）
- 候选列表格式：code | 清单描述 | 单位

# 判定规则（按优先级依次应用）
1. 先按功能类别对齐：设备块↔设备安装项；电缆/电线/桥架等敷设类↔管线敷设项。
   类别不同的候选（插座 vs 灯具）即使文字相似也排除。
2. 名称语义对照（中英混排、同义词均算一致）：LIGHTING↔照明灯具、SOCKET/POWER POINT↔插座、UPS↔不间断电源。
3. 用 specification / nearby_text 中的容量·功率·电压等级做一致性确认：一致则提高 confidence；
   冲突则降低 confidence 或置 needs_review=true。
4. 编号、序号、数量的差异忽略不计，不作为否决依据。

# 输出要求
1. 只输出一行严格 JSON，无 ```json 标记、无任何解释文字
2. 字段：selected_boq_id（必须取候选列表中的 code）、confidence(0.0-1.0)、reason(一句话≤30字)、
   alternative_boq_ids(备选 code，≤2个)、needs_review(bool)、no_match(bool)
3. 完全确定 → needs_review=false；勉强匹配或拿不准 → needs_review=true
4. 候选与对象全都不匹配 → no_match=true 且 selected_boq_id=null，绝不强行选一个

# 示例
候选：EL-L01 | 吸顶灯 LED 18W | 套；PS-D02 | 单相插座 16A | 个
对象：block_name="CEILING LIGHT 18W" layer_name="E-LIGHTING"
输出：{"selected_boq_id":"EL-L01","confidence":0.92,"reason":"ceiling light 即吸顶灯，容量18W一致","alternative_boq_ids":[],"needs_review":false,"no_match":false}
"""

BINDING_USER_TEMPLATE = """# CAD 对象
- block_name: {block_name}
- layer_name: {layer_name}
- system: {system}
- discipline: {discipline}
- specification: {specification}
- nearby_text: {tag}

# 候选 BOQ（selected_boq_id 只能从中选择）
{boq_lines}

# 输出
一行严格 JSON。全都不匹配则 no_match=true 且 selected_boq_id=null。"""


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
