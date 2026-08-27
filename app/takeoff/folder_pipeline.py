"""文件夹批量算量主流程（23-3）。

主入口：run_folder_pipeline()
- 扫描文件夹 DWG/DXF
- 顺序处理（流式聚合）
- 跨文件累计 + 智能分块喂 LLM
- 冲突检测 + 去重
- 输出总 BOQ
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .context_infer import scan_folder, infer_trade, infer_floor
from .stream_aggregate import (
    aggregate_file_streaming, AggregatedProject,
)
from .llm_classify import llm_classify_openai
from .quality import reconcile_across_files, detect_conflicts
from .orchestrator import TakeoffConfig, TakeoffItem


@dataclass
class FolderPipelineResult:
    """文件夹算量结果"""
    success: bool
    project_name: str
    items: list = field(default_factory=list)        # list[TakeoffItem]
    files_processed: int = 0
    files_failed: int = 0
    llm_calls: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    errors: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


PHASE_SCAN = "扫描"
PHASE_AGGREGATE_FILES = "逐图聚合"
PHASE_LLM_CHUNKS = "LLM 分类"
PHASE_RECONCILE = "冲突检测+去重"


def run_folder_pipeline(
    folder: Path,
    config: TakeoffConfig = None,
    progress_cb: Optional[Callable[[str, float, str], None]] = None,
    legend: dict = None,
) -> FolderPipelineResult:
    """主入口：文件夹 → 总 BOQ。

    Args:
        folder: 包含 DWG/DXF 的文件夹路径
        config: TakeoffConfig
        progress_cb: 进度回调 (phase, progress_0_1, message)
        legend: {block_name: legend_dict} 人工已确认的图例标定（接管算量用）
    """
    if config is None:
        config = TakeoffConfig()
    legend_map = legend or {}

    result = FolderPipelineResult(success=False, project_name=folder.name)
    stats = {"phases": {}, "files": []}

    def _progress(phase: str, p: float, msg: str = ""):
        if progress_cb:
            progress_cb(phase, p, msg)
        stats["phases"][phase] = {"progress": p, "message": msg}

    # ===== 阶段 1: 扫描 =====
    _progress(PHASE_SCAN, 0.0, f"扫描 {folder.name}...")
    files = scan_folder(folder)
    if not files:
        result.errors.append(f"文件夹 {folder} 下未找到 DWG/DXF")
        return result
    _progress(PHASE_SCAN, 1.0, f"发现 {len(files)} 个文件")
    result.stats = stats
    trade = infer_trade(folder.name)
    aggregator = AggregatedProject(project_name=folder.name, trade=trade)

    # ===== 阶段 2: 顺序聚合每张图 =====
    t_phase = time.time()
    for i, f in enumerate(files, 1):
        _progress(PHASE_AGGREGATE_FILES, (i - 1) / len(files), f"聚合 {f.name} ({i}/{len(files)})")
        floor = infer_floor(f.name)
        fs = aggregate_file_streaming(str(f), floor=floor)
        if fs.parse_error:
            result.files_failed += 1
            result.errors.append(f"{f.name}: {fs.parse_error}")
            continue
        result.files_processed += 1
        aggregator.add_file(fs, fs._agg_dict)
        stats["files"].append({"path": f.name, "floor": floor, "entities": fs.entity_count})
        # 主动释放（防止 Python 延迟 GC）
        del fs
    _progress(PHASE_AGGREGATE_FILES, 1.0,
              f"完成: {result.files_processed} 张 / 失败 {result.files_failed}")
    stats["phases"][PHASE_AGGREGATE_FILES] = {"elapsed": time.time() - t_phase}

    # ===== 阶段 3: 智能分块 + LLM 分类 =====
    llm_items: List[TakeoffItem] = []
    chunks = list(aggregator.to_llm_chunks())
    t_phase = time.time()
    for j, chunk in enumerate(chunks, 1):
        _progress(PHASE_LLM_CHUNKS, (j - 1) / len(chunks),
                  f"LLM 分类 chunk {j}/{len(chunks)} ({chunk.get('project_name','')})")
        try:
            llm_result = llm_classify_openai(
                chunk,
                project_id=config.project_id,
                project_type=config.project_type,
                region=config.region,
                specialty=config.specialty,
                block_legend=legend_map,
            )
            result.llm_calls += 1
            result.total_tokens_in += llm_result.get("tokens_in", 0)
            result.total_tokens_out += llm_result.get("tokens_out", 0)
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
        except Exception as e:
            result.errors.append(f"LLM chunk {j}: {e}")
    _progress(PHASE_LLM_CHUNKS, 1.0,
              f"LLM 完成: {len(llm_items)} 条 / {result.llm_calls} 调用")
    stats["phases"][PHASE_LLM_CHUNKS] = {"elapsed": time.time() - t_phase}

    # ===== 阶段 4: 冲突检测 + 跨图去重 =====
    t_phase = time.time()
    _progress(PHASE_RECONCILE, 0.0)
    # 合并：先跨图去重（累加同 code+unit），再冲突检测
    merged = reconcile_across_files(llm_items)
    conflicts = detect_conflicts(merged, threshold=0.10)
    _progress(PHASE_RECONCILE, 1.0, f"合并 {len(llm_items)}→{len(merged)} 条")
    stats["phases"][PHASE_RECONCILE] = {"elapsed": time.time() - t_phase}

    result.items = conflicts
    result.success = True
    return result
