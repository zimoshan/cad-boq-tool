"""Embedding 语义召回：EngineeringObject → BOQ Top-N（任务十一）。

不建向量数据库：BOQ ≤5000 条时内存余弦即可。Ollama 不可用 → 返回空（跳过）。

性能优化（2026-08-26）：
- BOQ 向量跨 EO 不变 → 进程内缓存按 project_id 复用（首次 1 次 embedding，
  后续每个 EO 只算 1 条向量）；BOQ 变更时调用 ``invalidate_embedding_cache`` 失效。
- P2-3 落盘：向量存 ``~/.cad-boq-tool/embedding_cache/``（npy + meta 指纹），
  **跨会话复用**；BOQ 内容/模型任一变化 → 指纹不符自动重建，无需手动失效。
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import numpy as np

from .. import db, config
from ..llm.embeddings import create_embedding_provider, cosine_similarity
from .text_norm import boq_searchable, normalize

# ---- L1 进程内缓存：project_id → (items, boq_vectors) ----
_BOQ_VECTOR_CACHE: dict[int, tuple] = {}
_BOQ_CACHE_MAX = 8          # 同时缓存的项目数上限（LRU 语义，超出清最旧）
_CACHE_LOCK = threading.Lock()

# ---- L2 磁盘缓存（跨会话）：~/.cad-boq-tool/embedding_cache/ ----
_EMBED_CACHE_DIR: Path = config.DATA_DIR / "embedding_cache"


def _model_key(provider) -> str:
    """缓存校验用模型 key（换模型即失效）"""
    return f"{provider.name}:{getattr(provider, 'model', '') or ''}"


def _boq_fingerprint(items: list) -> str:
    """BOQ 内容指纹：item id + 检索文本，任一变更 → hash 不同 → 缓存自动失效"""
    h = hashlib.sha256()
    for it in items:
        h.update(f"{it.id}:{boq_searchable(it)}\n".encode("utf-8"))
    return h.hexdigest()


def _disk_files(project_id: int) -> tuple[Path, Path]:
    return (_EMBED_CACHE_DIR / f"boq_{project_id}.vectors.npy",
            _EMBED_CACHE_DIR / f"boq_{project_id}.meta.json")


def _load_disk_vectors(project_id: int, provider, items: list):
    """L2 磁盘命中校验：指纹 + 模型 + 条数全对才复用，否则 None"""
    vec_path, meta_path = _disk_files(project_id)
    try:
        if not (vec_path.exists() and meta_path.exists()):
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("fingerprint") != _boq_fingerprint(items):
            return None
        if meta.get("model") != _model_key(provider):
            return None
        arr = np.load(vec_path, allow_pickle=False)
        if arr.shape[0] != len(items):
            return None
        return [r.tolist() for r in arr]
    except Exception:
        return None


def _save_disk_vectors(project_id: int, provider, items: list, vectors: list) -> None:
    """写盘（非关键路径，失败静默）"""
    try:
        vec_path, meta_path = _disk_files(project_id)
        vec_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(vec_path, np.asarray(vectors, dtype="float32"))
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "project_id": project_id,
                "model": _model_key(provider),
                "fingerprint": _boq_fingerprint(items),
                "count": len(items),
            }, f, ensure_ascii=False)
    except Exception:
        pass


def invalidate_embedding_cache(project_id: int) -> None:
    """BOQ 变更时调用：丢弃缓存的向量（内存 + 磁盘；下次按新内容重建）"""
    with _CACHE_LOCK:
        _BOQ_VECTOR_CACHE.pop(project_id, None)
    for p in _disk_files(project_id):
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def _clear_embedding_cache() -> None:
    """测试/调试用：清空全部缓存（含磁盘）"""
    with _CACHE_LOCK:
        _BOQ_VECTOR_CACHE.clear()
    try:
        if _EMBED_CACHE_DIR.is_dir():
            for p in _EMBED_CACHE_DIR.glob("*"):
                try:
                    if p.is_file():
                        p.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def _get_project_vectors(project_id: int, provider, items: list):
    """取 BOQ 向量（L1 进程内 → L2 磁盘 → 实时计算三级缓存）。返回 (items, boq_vectors)。"""
    with _CACHE_LOCK:
        hit = _BOQ_VECTOR_CACHE.get(project_id)
        if hit is not None:
            return hit[0], hit[1]

    boq_texts = [boq_searchable(it) for it in items]

    # L2 磁盘命中（指纹/模型/条数校验）→ 直接升 L1
    disk_vecs = _load_disk_vectors(project_id, provider, items)
    if disk_vecs is not None:
        with _CACHE_LOCK:
            _BOQ_VECTOR_CACHE[project_id] = (items, disk_vecs)
        return items, disk_vecs

    try:
        vectors = provider.embed(boq_texts)
    except Exception:
        return items, None
    if len(vectors) != len(items):
        return items, None
    _save_disk_vectors(project_id, provider, items, vectors)
    with _CACHE_LOCK:
        if project_id in _BOQ_VECTOR_CACHE:
            # 并发下另一线程已写入，复用其值
            return _BOQ_VECTOR_CACHE[project_id]
        if len(_BOQ_VECTOR_CACHE) >= _BOQ_CACHE_MAX:
            # 简单 LRU：淘汰最早写入的 key（dict 保持插入序）
            _BOQ_VECTOR_CACHE.pop(next(iter(_BOQ_VECTOR_CACHE)))
        _BOQ_VECTOR_CACHE[project_id] = (items, vectors)
    return items, vectors


def enriched_eo_text(project_id: int, eo) -> str:
    """构建 EO 的富文本（用于 Embedding 召回 / 关键词兜底）。

    在 block/layer/system/spec/tag 基础上，追加知识库（symbol_library）规格，
    提升召回子集命中真实 BOQ 的概率。
    """
    parts = [normalize(eo.block_name), normalize(eo.layer_name),
             normalize(eo.system), normalize(eo.specification), normalize(eo.tag)]
    try:
        sym = db.get_symbol(project_id, block_name=eo.block_name, layer_name=eo.layer_name)
        if sym:
            if sym.spec:
                parts.append(normalize(sym.spec))
            if sym.system:
                parts.append(normalize(sym.system))
    except Exception:
        pass
    return " ".join(x for x in parts if x)


def semantic_candidates(project_id: int, eo, top_n: int = None) -> list:
    """EO → [(boq_item_id, score, reason)]，按相似度降序。

    Ollama embedding 不可用 / 无 BOQ → 返回 []。
    """
    top_n = top_n or config.EMBEDDING_TOP_N
    provider = create_embedding_provider()
    if not provider.is_available():
        return []

    items = db.get_boq_items(project_id)
    if not items:
        return []

    # EO 侧文本：block/layer/system/spec/tag + 知识库规格（富文本提升召回）
    eo_text = enriched_eo_text(project_id, eo)
    if not eo_text.strip():
        return []

    items, boq_vectors = _get_project_vectors(project_id, provider, items)
    if boq_vectors is None:
        return []  # BOQ 侧向量计算失败，本层跳过

    try:
        ev = provider.embed([eo_text])[0]
    except Exception:
        return []  # 单次失败不阻断流程

    scored = []
    for it, bv in zip(items, boq_vectors):
        s = cosine_similarity(ev, bv)
        if s > 0.3:  # 低相似度直接丢弃
            scored.append((it.id, round(s, 4), f"语义相似 {s:.2f}（BOQ {it.code}）"))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]