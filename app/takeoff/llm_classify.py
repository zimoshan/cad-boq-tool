"""LLM 分类：调用本地 Ollama 把汇总数据转成 BOQ 条目。

Phase 22A-3：
- 强制只采用输入的汇总值（不让 LLM 算数值）
- 鲁棒 JSON 解析
- 0 依赖 ollama（运行时 import）
"""
from __future__ import annotations

import json
import re
from typing import Optional


SYSTEM_PROMPT = """你是中国工程造价师，专长 CAD 图纸算量。

# 工作原则（严格遵守）
1. **数值必须直接采用输入的"汇总"字段**，严禁估算、四舍五入、推算
2. **单位**：长度=米(m)，面积=平方米(m²)，体积=立方米(m³)，数量=个(个)，质量=千克(kg)
3. **清单命名**参考《建设工程工程量清单计价规范》GB 50500 通用格式
4. **不确定的条目** confidence 必须 < 0.7，并在 reasoning 中说明
5. **不输出**未在汇总中出现的数值；不确定的宁可不输出
6. **严格 JSON 输出**，不要 ```json 等 Markdown 格式符号，不要任何解释性文字

# 输入格式
你会收到 CAD 图纸的多层汇总：每个图层含 entity_count、total_length_m、total_area_m2、type_breakdown、sample_texts（典型尺寸/规格）。

# 输出格式
{"items": [{"code": "X-X", "description": "标准清单条目", "unit": "m/m²/个/kg", "quantity": 数值, "source_layer": "对应图层名", "confidence": 0.0-1.0, "reasoning": "判断依据，1-2 句"}]}
"""


USER_PROMPT_TEMPLATE = """# 项目
- 项目类型: {project_type}
- 地区: {region}
- 专业范围: {specialty}

# CAD 图纸汇总
{layer_summaries}

# 检测到的典型尺寸/规格
{typical_sizes}

# 块引用统计（每个块被 INSERT 引用次数）
{block_inserts}

# 人工已确认的「块图例」（最高优先级，必须遵守）
{block_legend_section}

# 你的任务
按汇总值输出 BOQ 条目。同名同分类的图层应合并为 1 条；量纲不同的拆开（如给水主管 vs 阀门）。
块引用统计里的每个块，若出现在上面图例中，请直接使用图例给定的「设备类型/规格/单位/计量方式」生成条目，不要另起名字。
严格按 JSON 格式输出，不要任何其他文字。
"""


def build_prompt(agg_dict: dict, project_type: str = "医院", region: str = "北京",
                 specialty: str = "给排水+暖通+电气",
                 block_legend: dict = None) -> tuple[str, str]:
    """构建 (system_prompt, user_prompt)

    Args:
        block_legend: {block_name: legend_dict} 人工已确认的图例标定（接管算量用）
    """
    if block_legend:
        lines = []
        for bname, row in block_legend.items():
            if not (row.get("device_type") or row.get("category")):
                continue
            lines.append(
                f"- 块[{bname}] => 类型:{row.get('device_type','')} "
                f"类别:{row.get('category','')} 规格:{row.get('spec','')} "
                f"单位:{row.get('unit','个')} 计量:{row.get('count_rule','count')}")
        section = "\n".join(lines) if lines else "（无）"
    else:
        section = "（无）"
    user = USER_PROMPT_TEMPLATE.format(
        project_type=project_type,
        region=region,
        specialty=specialty,
        layer_summaries=json.dumps(agg_dict.get("layers", []), ensure_ascii=False, indent=2),
        typical_sizes=", ".join(agg_dict.get("typical_sizes", [])),
        block_inserts=json.dumps(agg_dict.get("block_inserts", {}), ensure_ascii=False),
        block_legend_section=section,
    )
    return SYSTEM_PROMPT, user


def parse_json_robust(content: str) -> Optional[dict]:
    """鲁棒 JSON 解析：处理 LLM 偶尔夹带 ```json 块、前后多余文字等情况"""
    if not content:
        return None
    content = content.strip()

    # 1. 直接尝试
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. 提取 ```json ... ``` 块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 提取第一个 { ... } 平衡块
    depth = 0
    start = content.find("{")
    if start < 0:
        return None
    for i in range(start, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(content[start:i + 1])
                except json.JSONDecodeError:
                    break
    return None


def validate_item(item: dict) -> bool:
    """校验 BOQ 条目结构合理性"""
    required = ("code", "description", "unit", "quantity", "source_layer", "confidence")
    if not all(k in item for k in required):
        return False
    if not isinstance(item["quantity"], (int, float)):
        return False
    if item["quantity"] < 0:
        return False
    if not (0 <= item["confidence"] <= 1):
        return False
    if item["unit"] not in ("m", "m²", "m3", "个", "kg", "m2"):
        return False
    return True


def llm_classify_ollama(agg_dict: dict, model: str = "qwen2.5:7b",
                        host: str = "http://localhost:11434",
                        project_type: str = "医院", region: str = "北京",
                        specialty: str = "给排水+暖通+电气",
                        timeout: int = 120,
                        block_legend: dict = None) -> dict:
    """调用本地 Ollama，返回 {content, tokens_in, tokens_out, latency_ms, parsed_items}

    Args:
        block_legend: {block_name: legend_dict} 人工已确认的图例标定

    Raises:
        ImportError: ollama 未装
        RuntimeError: 调用失败或解析失败
    """
    import time
    import ollama

    system, user = build_prompt(agg_dict, project_type, region, specialty,
                                block_legend=block_legend)

    # 用 Client 实例显式指定 host（避免模块级 ollama.chat() 默认走 IPv6 失败）
    client = ollama.Client(host=host)

    t0 = time.time()
    try:
        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": 0.1, "num_predict": 4000},  # 低温度，输出上限 4000 tokens
        )
    except Exception as e:
        raise RuntimeError(f"Ollama 调用失败: {e}") from e
    t1 = time.time()

    content = resp["message"]["content"]
    parsed = parse_json_robust(content)

    if not parsed or "items" not in parsed:
        return {
            "content": content,
            "parsed": None,
            "items": [],
            "latency_ms": int((t1 - t0) * 1000),
            "error": "LLM 输出无法解析为 JSON items",
        }

    # 过滤无效条目
    valid_items = [i for i in parsed["items"] if validate_item(i)]
    invalid_count = len(parsed["items"]) - len(valid_items)

    # Ollama 响应里 tokens 字段（不同版本可能不在）
    tokens_in = resp.get("prompt_eval_count", 0) or 0
    tokens_out = resp.get("eval_count", 0) or 0

    return {
        "content": content,
        "parsed": parsed,
        "items": valid_items,
        "invalid_count": invalid_count,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": int((t1 - t0) * 1000),
    }


def is_ollama_available(host: str = "http://localhost:11434") -> bool:
    """检查 Ollama 是否可达"""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def llm_classify_openai(agg_dict: dict, project_id: int = 0,
                        project_type: str = "医院", region: str = "北京",
                        specialty: str = "给排水+暖通+电气",
                        block_legend: dict = None) -> dict:
    """调用 OpenAI 兼容端点（走统一 runner），返回与 llm_classify_ollama 相同结构。

    配置（base_url/api_key/model）从 app.llm.settings.load_active() 读取。
    """
    import time
    from ..llm.runner import run_llm_with_retry

    system, user = build_prompt(agg_dict, project_type, region, specialty,
                                block_legend=block_legend)

    def _validate(content: str):
        parsed = parse_json_robust(content)
        if not parsed or "items" not in parsed:
            raise ValueError("LLM 输出无法解析为 JSON items")
        return parsed

    t0 = time.time()
    resp = run_llm_with_retry(
        project_id, task_type="classify", system=system, user=user,
        validator=_validate, prompt_version="classify-v1")
    t1 = time.time()

    content = resp.get("content", "")
    parsed = resp.get("parsed")
    if not resp.get("ok") or parsed is None:
        return {
            "content": content,
            "parsed": None,
            "items": [],
            "latency_ms": int((t1 - t0) * 1000),
            "error": resp.get("error", "LLM 调用失败"),
        }

    valid_items = [i for i in parsed["items"] if validate_item(i)]
    invalid_count = len(parsed["items"]) - len(valid_items)

    return {
        "content": content,
        "parsed": parsed,
        "items": valid_items,
        "invalid_count": invalid_count,
        "tokens_in": resp.get("tokens_in", 0),
        "tokens_out": resp.get("tokens_out", 0),
        "latency_ms": int((t1 - t0) * 1000),
    }


def list_ollama_models(host: str = "http://localhost:11434") -> list:
    """列出 Ollama 可用模型"""
    try:
        import urllib.request, json
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []
