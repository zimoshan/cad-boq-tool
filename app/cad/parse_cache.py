"""DWG/DXF 解析缓存（任务二十四：性能优化第一优先）。

Cache key = sha256(absolute_path | mtime_ns | file_size | parser_version)
命中后二次打开从 47s → <1s。

存储（cache/<key>/）：
  entities.parquet   # 实体（pyarrow 可用时；否则 entities.json 降级）
  blocks.json        # block_refs / blocks_with_count（INSERT 引用）
  metadata.json      # layers / layer_colors / blocks 定义几何 / 统计

只缓存解析结果（Entity.id=0 阶段），入库时 replace_entities 重新分配 id。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ..config import DATA_DIR, PARSE_CACHE_MAX_ENTRIES
from ..models import Entity

CACHE_DIR = DATA_DIR / "drawing_cache"
PARSER_VERSION = "v2"   # v2: 嵌套 INSERT 递归解析（块显示不全修复）


def _max_entries() -> int:
    """缓存条目上限（P2-5 配置化）：每次执行时取最新 config 值，支持运行时调整"""
    try:
        return max(1, int(PARSE_CACHE_MAX_ENTRIES))
    except (TypeError, ValueError):
        return 100

try:
    import importlib.util
    _HAS_PARQUET = importlib.util.find_spec("pyarrow") is not None
except Exception:
    _HAS_PARQUET = False


def _entity_to_dict(e: Entity) -> dict:
    return {
        "handle": e.handle, "dxf_type": e.dxf_type, "layer": e.layer,
        "block_name": e.block_name, "bbox": json.dumps(list(e.bbox)),
        "geom_json": e.geom_json, "length": e.length, "area": e.area,
        "color": json.dumps(list(e.color)),
    }


def _dict_to_entity(d: dict) -> Entity:
    try:
        bbox = tuple(json.loads(d.get("bbox") or "[0,0,0,0]"))
    except Exception:
        bbox = (0, 0, 0, 0)
    try:
        color = tuple(json.loads(d.get("color") or "[255,255,255]"))
    except Exception:
        color = (255, 255, 255)
    return Entity(
        handle=d.get("handle", ""), dxf_type=d.get("dxf_type", ""),
        layer=d.get("layer", ""), block_name=d.get("block_name", ""),
        bbox=bbox, geom_json=d.get("geom_json", ""),
        length=float(d.get("length") or 0), area=float(d.get("area") or 0),
        color=color,
    )


def cache_key(path: str) -> str:
    """路径+元数据+解析器版本 → 稳定 key（文件变更即失效）"""
    p = Path(path)
    try:
        st = p.stat()
        sig = f"{p.resolve()}|{st.st_mtime_ns}|{st.st_size}|{PARSER_VERSION}"
    except OSError:
        sig = f"{p.resolve()}|missing|{PARSER_VERSION}"
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()


def _cache_dir_for(path: str) -> Path:
    return CACHE_DIR / cache_key(path)


# ---------- 读 ----------
def get_cached_drawing(path: str):
    """命中返回 ParsedDrawing，未命中返回 None"""
    from .cad_parser import ParsedDrawing
    d = _cache_dir_for(path)
    meta_file = d / "metadata.json"
    blocks_file = d / "blocks.json"
    if not (meta_file.exists() and blocks_file.exists()):
        return None

    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        with open(blocks_file, "r", encoding="utf-8") as f:
            blk = json.load(f)
        if meta.get("parser_version") != PARSER_VERSION:
            return None

        entities = _load_entities(d, meta.get("entity_count", 0))
        if entities is None:
            return None

        drawing = ParsedDrawing(
            entities=entities,
            layers=meta.get("layers", {}),
            layer_colors={k: tuple(v) for k, v in meta.get("layer_colors", {}).items()},
            blocks=meta.get("blocks", {}),
            block_refs=blk.get("block_refs", {}),
            blocks_with_count={
                k: [_dict_to_entity(x) for x in v]
                for k, v in blk.get("blocks_with_count", {}).items()},
        )
        return drawing
    except Exception:
        return None


def _load_entities(d: Path, count: int):
    """parquet 优先，JSON 降级"""
    if _HAS_PARQUET:
        pf = d / "entities.parquet"
        if pf.exists():
            try:
                import pandas as pd
                df = pd.read_parquet(pf)
                return [_dict_to_entity(row) for row in df.to_dict("records")]
            except Exception:
                pass
    jf = d / "entities.json"
    if jf.exists():
        try:
            with open(jf, "r", encoding="utf-8") as f:
                return [_dict_to_entity(x) for x in json.load(f)]
        except Exception:
            return None
    return None


# ---------- 写 ----------
def cache_drawing(path: str, drawing) -> bool:
    """持久化解析结果。失败静默（缓存非关键路径）"""
    try:
        d = _cache_dir_for(path)
        d.mkdir(parents=True, exist_ok=True)

        # entities
        rows = [_entity_to_dict(e) for e in drawing.entities]
        if _HAS_PARQUET:
            try:
                import pandas as pd
                pd.DataFrame(rows).to_parquet(d / "entities.parquet", index=False)
            except Exception:
                with open(d / "entities.json", "w", encoding="utf-8") as f:
                    json.dump(rows, f, ensure_ascii=False)
        else:
            with open(d / "entities.json", "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False)

        with open(d / "blocks.json", "w", encoding="utf-8") as f:
            json.dump({
                "block_refs": drawing.block_refs,
                "blocks_with_count": {
                    k: [_entity_to_dict(e) for e in v]
                    for k, v in drawing.blocks_with_count.items()},
            }, f, ensure_ascii=False)

        with open(d / "metadata.json", "w", encoding="utf-8") as f:
            json.dump({
                "parser_version": PARSER_VERSION,
                "entity_count": len(drawing.entities),
                "layers": drawing.layers,
                "layer_colors": {k: list(v) for k, v in drawing.layer_colors.items()},
                "blocks": drawing.blocks,
                "cached_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, f, ensure_ascii=False)

        _enforce_cap()
        return True
    except Exception:
        return False


def _enforce_cap() -> None:
    """缓存目录数超上限时，按 mtime 清理最旧"""
    if not CACHE_DIR.is_dir():
        return
    entries = sorted(CACHE_DIR.iterdir(), key=lambda p: p.stat().st_mtime)
    while len(entries) > _max_entries():
        victim = entries.pop(0)
        try:
            import shutil
            shutil.rmtree(victim)
        except Exception:
            pass


# ---------- 管理 ----------
def clear_cache() -> int:
    """清空缓存目录，返回清理的条目数"""
    n = 0
    if CACHE_DIR.is_dir():
        import shutil
        for p in CACHE_DIR.iterdir():
            try:
                shutil.rmtree(p)
                n += 1
            except Exception:
                pass
    return n


def cache_stats() -> dict:
    """缓存统计（UI/调试用）"""
    entries = []
    if CACHE_DIR.is_dir():
        for p in sorted(CACHE_DIR.iterdir(), key=lambda x: x.stat().st_mtime):
            entries.append({"key": p.name,
                            "size_mb": round(sum(f.stat().st_size for f in p.iterdir()) / 1e6, 2)})
    return {"dir": str(CACHE_DIR), "parquet": _HAS_PARQUET, "entries": entries,
            "count": len(entries)}
