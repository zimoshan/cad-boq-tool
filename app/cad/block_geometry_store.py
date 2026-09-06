"""B3 块几何外置存储（v2.0 §2.3，2026-09-06）

设计：
  - 原始 sheet.blocks_json TEXT 34MB → 外置到 <BLOCK_GEOMETRY_DIR>/<sha256>.parquet
  - sheet.blocks_json 字段内容改为 sha256 引用：{"sha256": "...", "block_count": N, "size": bytes}
  - 用 pyarrow parquet 写（已加入 requirements.txt）

接口：
  - write_block_geometry(blocks_dict) -> str (sha256)
  - read_block_geometry(sha256) -> dict
  - get_block_geometry_path(sha256) -> Path
  - parse_sheet_blocks_ref(blocks_json_str) -> dict | None（解析 sheet.blocks_json 字段）
  - serialize_sheet_blocks_ref(sha256, block_count, size_bytes) -> str
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ..config import BLOCK_GEOMETRY_DIR


def _get_base_dir() -> Path:
    """BLOCK_GEOMETRY_DIR 支持 env 覆盖（webapi 部署期 env 化）"""
    base = os.environ.get("BLOCK_GEOMETRY_DIR", BLOCK_GEOMETRY_DIR)
    return Path(base).expanduser()


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_block_geometry_path(sha256: str) -> Path:
    """<BASE>/<sha256[0:2]>/<sha256>.parquet（按前 2 字符分目录，避免单目录文件过多）"""
    return _get_base_dir() / sha256[:2] / f"{sha256}.parquet"


def write_block_geometry(blocks_dict: dict[str, list[dict[str, Any]]]) -> str:
    """序列化 blocks dict → parquet → 写盘 → 返回 sha256

    blocks_dict 形如：{block_name: [geom_dict, ...]}
    geom_dict 是 app.cad.cad_parser._entity_geom 输出的 dict（含 type/length/area/insert 等字段）
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    # 序列化每个 block 的 geom 列表为 JSON 字符串（parquet 单元格存字符串）
    rows = []
    for block_name, geoms in blocks_dict.items():
        rows.append(
            {
                "block_name": block_name,
                "geom_count": len(geoms),
                "geom_json": json.dumps(geoms, ensure_ascii=False),
            }
        )
    table = pa.Table.from_pylist(rows)

    # 算 sha256（基于规范化 JSON，确保相同内容产生相同 hash）
    normalized = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")
    sha256 = compute_sha256(normalized)

    path = get_block_geometry_path(sha256)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pq.write_table(table, path)

    return sha256


def read_block_geometry(sha256: str) -> dict[str, list[dict[str, Any]]]:
    """读 parquet → 反序列化 → 返回 blocks dict"""
    import pyarrow.parquet as pq

    path = get_block_geometry_path(sha256)
    if not path.exists():
        return {}
    table = pq.read_table(path)
    blocks: dict[str, list[dict[str, Any]]] = {}
    for row in table.to_pylist():
        blocks[row["block_name"]] = json.loads(row["geom_json"])
    return blocks


def serialize_sheet_blocks_ref(sha256: str, block_count: int, size_bytes: int) -> str:
    """sheet.blocks_json 字段内容（JSON 引用）"""
    return json.dumps(
        {"sha256": sha256, "block_count": block_count, "size": size_bytes, "format": "parquet"},
        ensure_ascii=False,
    )


def parse_sheet_blocks_ref(blocks_json_str: str) -> dict[str, Any] | None:
    """解析 sheet.blocks_json 字段；旧 TEXT-JSON 格式直接返回 None（外层兼容读）"""
    if not blocks_json_str:
        return None
    try:
        v = json.loads(blocks_json_str)
        if isinstance(v, dict) and "sha256" in v:
            return v
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def is_blocks_ref(blocks_json_str: str) -> bool:
    """判断 sheet.blocks_json 是否为外置引用（vs 旧 TEXT-JSON）"""
    return parse_sheet_blocks_ref(blocks_json_str) is not None
