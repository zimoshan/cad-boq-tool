"""AI 算量主流程：parse_dxf → aggregate → 规则分类 → LLM 分类 → 冲突检测 → 输出。

Phase 22A-4：
- 主入口 takeoff_pipeline()
- 6 阶段进度回调（与 UI 配套）
- 规则层先跑（秒级 0 成本），LLM 仅在规则不确定时补位
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..cad import cad_parser as cad_parser
from .aggregate import aggregate
from .classify import get_top_category
from .llm_classify import llm_classify_openai


# 阶段常量（用于 UI 显示）
PHASE_PARSE = "解析"
PHASE_AGGREGATE = "聚合"
PHASE_RULE_CLASSIFY = "规则分类"
PHASE_LLM_CLASSIFY = "LLM 分类"
PHASE_RECONCILE = "冲突检测"
PHASE_EXPORT = "导出"

ALL_PHASES = [PHASE_PARSE, PHASE_AGGREGATE, PHASE_RULE_CLASSIFY,
              PHASE_LLM_CLASSIFY, PHASE_RECONCILE, PHASE_EXPORT]


@dataclass
class TakeoffConfig:
    """算量配置"""
    project_id: int = 0
    project_type: str = "医院"        # 医院/机场/住宅/办公/市政/其他
    region: str = "北京"
    specialty: str = "给排水+暖通+电气"
    llm_model: str = "qwen2.5:7b"
    ollama_host: str = "http://127.0.0.1:11434"   # 显式 IPv4 避免 SDK 默认走 IPv6 失败
    timeout: int = 120
    use_rule_layer: bool = True       # 是否先用规则层（秒级 0 成本）

    # Phase 22B：质量门槛 + 选择性 fallback
    auto_fallback: bool = True        # 质量不达标自动调 fallback
    quality_threshold: float = 0.7    # 条目 confidence < 此值 → 触发 fallback
    fallback_backend: object = None   # 预留：可传 LLMBackend 实例（云端）


@dataclass
class TakeoffItem:
    """算量结果条目（喂 LLM 前的预定义）"""
    code: str
    description: str
    unit: str
    quantity: float
    source_layer: str = ""
    source_block: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    raw: dict = field(default_factory=dict)   # 原始 LLM 输出


@dataclass
class TakeoffResult:
    """算量结果"""
    success: bool
    items: list = field(default_factory=list)        # list[TakeoffItem]
    errors: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)         # 性能统计
    config: Optional[TakeoffConfig] = None


def _block_takeoff_item(bname: str, count: int, legend_map: dict) -> Optional["TakeoffItem"]:
    """块引用 → 候选 BOQ 条目。

    优先使用人工已确认的图例标定（device_type/spec/unit），否则回退到规则层块名匹配。
    """
    row = legend_map.get(bname)
    if row and row.get("confirmed") and (row.get("device_type") or row.get("category")):
        dtype = row.get("device_type") or row.get("category")
        spec = row.get("spec", "")
        unit = row.get("unit") or "个"
        desc = f"{dtype}（{spec + ' ' if spec else ''}块 {bname}）".strip()
        return TakeoffItem(
            code=f"LEG-{dtype}",
            description=desc,
            unit=unit,
            quantity=float(count),
            source_layer="",
            source_block=bname,
            confidence=0.95,
            reasoning=f"图例标定（人工已确认）：{dtype} {spec}".strip(),
        )
    from .classify import classify_block
    res = classify_block(bname)
    if not res:
        return None
    bcat, bconf = res[0]
    return TakeoffItem(
        code=f"AUTO-BLK-{bcat}",
        description=f"{bcat}（块 {bname}）",
        unit="个",
        quantity=float(count),
        source_layer="",
        source_block=bname,
        confidence=bconf,
        reasoning=f"块名匹配 {bcat}",
    )


def takeoff_pipeline(
    file_path: str,
    config: TakeoffConfig = None,
    progress_cb: Optional[Callable[[str, float, str], None]] = None,
    legend: dict = None,
) -> TakeoffResult:
    """主入口：单文件 DWG/DXF → BOQ 草稿。

    Args:
        file_path: DWG/DXF 路径
        config: 算量配置
        progress_cb: 进度回调 (phase_name, progress_0_1, message)

    Returns:
        TakeoffResult: 含 items/errors/stats
    """
    if config is None:
        config = TakeoffConfig()

    legend_map = legend or {}

    result = TakeoffResult(success=False, config=config)
    stats = {"phases": {}, "errors": []}

    def _progress(phase: str, p: float, msg: str = ""):
        if progress_cb:
            progress_cb(phase, p, msg)
        stats["phases"][phase] = {"progress": p, "message": msg}

    # ===== 阶段 1: 解析 =====
    t0 = time.time()
    _progress(PHASE_PARSE, 0.0, f"开始解析 {Path(file_path).name}")
    try:
        from ..cad import parse_cache
        drawing = parse_cache.get_cached_drawing(file_path)
        if drawing is None:
            drawing = cad_parser.parse_dxf(file_path)
            parse_cache.cache_drawing(file_path, drawing)
    except Exception as e:
        stats["errors"].append(f"解析失败: {e}")
        result.errors = stats["errors"]
        return result
    _progress(PHASE_PARSE, 1.0, f"解析完成: {len(drawing.entities)} 实体")
    stats["phases"][PHASE_PARSE]["elapsed"] = time.time() - t0

    # ===== 阶段 2: 聚合 =====
    t0 = time.time()
    _progress(PHASE_AGGREGATE, 0.0)
    agg = aggregate(drawing)
    agg_dict = agg.to_llm_dict()
    _progress(PHASE_AGGREGATE, 1.0,
              f"{len(agg.layers)} 图层 / {len(agg.block_inserts)} 块 / {len(agg.typical_sizes)} 尺寸")
    stats["phases"][PHASE_AGGREGATE]["elapsed"] = time.time() - t0
    stats["entity_count"] = len(drawing.entities)
    stats["layer_count"] = len(agg.layers)

    # ===== 阶段 3: 规则分类 =====
    rule_items = []
    if config.use_rule_layer:
        t0 = time.time()
        _progress(PHASE_RULE_CLASSIFY, 0.0)
        for ls in agg.layers:
            cat, conf = get_top_category(ls.name)
            if conf >= 0.7:  # 高置信度规则
                # 用聚合的数值（这是 ezdxf 算的，0 误差）
                if ls.total_length_mm > 0:
                    rule_items.append(TakeoffItem(
                        code=f"AUTO-{cat}",
                        description=f"{cat}（{ls.name}）",
                        unit="m",
                        quantity=round(ls.total_length_mm / 1000, 2),
                        source_layer=ls.name,
                        confidence=conf,
                        reasoning=f"规则层分类：{cat}（置信度 {conf:.0%}）",
                    ))
                if ls.total_area_mm2 > 0:
                    rule_items.append(TakeoffItem(
                        code=f"AUTO-{cat}-AREA",
                        description=f"{cat}（{ls.name}）",
                        unit="m²",
                        quantity=round(ls.total_area_mm2 / 1_000_000, 2),
                        source_layer=ls.name,
                        confidence=conf,
                        reasoning=f"规则层分类：{cat}（置信度 {conf:.0%}）",
                    ))
        # 块引用（count 规则）—— 优先图例标定，否则规则层块名匹配
        for bname, count in agg.block_inserts.items():
            item = _block_takeoff_item(bname, count, legend_map)
            if item:
                rule_items.append(item)
        _progress(PHASE_RULE_CLASSIFY, 1.0, f"规则层生成 {len(rule_items)} 条")
        stats["phases"][PHASE_RULE_CLASSIFY]["elapsed"] = time.time() - t0
        stats["rule_items"] = len(rule_items)

    # ===== 阶段 4: LLM 分类 =====
    llm_items = []
    try:
        t0 = time.time()
        _progress(PHASE_LLM_CLASSIFY, 0.0, "调用 LLM...")
        llm_result = llm_classify_openai(
            agg_dict,
            project_id=config.project_id,
            project_type=config.project_type,
            region=config.region,
            specialty=config.specialty,
            block_legend=legend_map,
        )
        if llm_result["items"]:
            for it in llm_result["items"]:
                llm_items.append(TakeoffItem(
                    code=it["code"],
                    description=it["description"],
                    unit=it["unit"],
                    quantity=it["quantity"],
                    source_layer=it.get("source_layer", ""),
                    confidence=it["confidence"],
                    reasoning=it.get("reasoning", ""),
                    raw=it,
                ))
        _progress(PHASE_LLM_CLASSIFY, 1.0,
                  f"LLM 生成 {len(llm_items)} 条 ({llm_result['latency_ms']}ms)")
        stats["phases"][PHASE_LLM_CLASSIFY]["elapsed"] = time.time() - t0
        stats["llm_items"] = len(llm_items)
        stats["llm_tokens_in"] = llm_result.get("tokens_in", 0)
        stats["llm_tokens_out"] = llm_result.get("tokens_out", 0)

        # ===== 22B-2: 质量门槛 + 选择性 fallback =====
        if config.auto_fallback and config.fallback_backend is not None:
            low_conf = [i for i in llm_items if i.confidence < config.quality_threshold]
            if low_conf:
                _progress(PHASE_LLM_CLASSIFY, 1.0,
                          f"本地 {len(low_conf)} 条低置信度，自动调 fallback")
                try:
                    from .llm_classify import build_prompt, parse_json_robust, validate_item
                    system, user = build_prompt(
                        agg_dict, config.project_type, config.region, config.specialty,
                        block_legend=legend_map)
                    # 追加指令：只重算低置信度条目
                    user += f"\n\n# 注意：上一轮输出有 {len(low_conf)} 个低置信度条目（<{config.quality_threshold}），请重新分析这些条目并输出完整 JSON。"
                    fb_resp = config.fallback_backend.chat(system, user)
                    fb_parsed = parse_json_robust(fb_resp["content"])
                    if fb_parsed and "items" in fb_parsed:
                        # 用 fallback 结果替换低置信度条目
                        fb_items = [i for i in fb_parsed["items"] if validate_item(i)]
                        for fb_it in fb_items:
                            # 找匹配的低置信度条目替换
                            for i, ex in enumerate(llm_items):
                                if ex.confidence < config.quality_threshold and ex.code == fb_it.get("code"):
                                    llm_items[i] = TakeoffItem(
                                        code=fb_it["code"], description=fb_it["description"],
                                        unit=fb_it["unit"], quantity=fb_it["quantity"],
                                        source_layer=fb_it.get("source_layer", ""),
                                        confidence=fb_it["confidence"],
                                        reasoning=f"fallback 修正: {fb_it.get('reasoning','')}",
                                        raw=fb_it,
                                    )
                                    break
                        stats["fallback_used"] = True
                        stats["fallback_items"] = len(fb_items)
                        stats["fallback_tokens_in"] = fb_resp.get("tokens_in", 0)
                        stats["fallback_tokens_out"] = fb_resp.get("tokens_out", 0)
                except Exception as e:
                    stats["errors"].append(f"Fallback 失败: {e}")
    except Exception as e:
        stats["errors"].append(f"LLM 调用失败: {e}")
        _progress(PHASE_LLM_CLASSIFY, 1.0, f"LLM 失败: {e}")

    # ===== 阶段 5: 冲突检测 =====
    t0 = time.time()
    _progress(PHASE_RECONCILE, 0.0)
    # 简单合并：LLM 优先，规则补漏
    seen_codes = set()
    final_items = []
    for it in llm_items:  # LLM 先
        key = (it.code, it.unit)
        if key not in seen_codes:
            final_items.append(it)
            seen_codes.add(key)
    for it in rule_items:  # 规则补漏
        key = (it.code, it.unit)
        if key not in seen_codes:
            final_items.append(it)
            seen_codes.add(key)
    _progress(PHASE_RECONCILE, 1.0, f"合并后 {len(final_items)} 条")
    stats["phases"][PHASE_RECONCILE]["elapsed"] = time.time() - t0
    stats["final_items"] = len(final_items)

    # ===== 阶段 6: 导出 =====
    t0 = time.time()
    _progress(PHASE_EXPORT, 0.0)
    result.items = final_items
    result.success = True
    result.stats = stats
    _progress(PHASE_EXPORT, 1.0, f"完成: {len(final_items)} 条")
    stats["phases"][PHASE_EXPORT]["elapsed"] = time.time() - t0

    return result
