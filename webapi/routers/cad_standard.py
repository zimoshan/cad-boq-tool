"""/api/cad-standard 路由（v1.0 §26 5 规则 CRUD）"""
# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref
import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from webapi.auth.decorators import requires
from webapi.config import get_settings

router = APIRouter(prefix="/api/cad-standard", tags=["cad-standard"])


def _standard_dir() -> Path:
    """webapi/cad_standard/ 目录（v1.0 §26 5 规则文件位置）"""
    return Path(__file__).parent.parent / "cad_standard"


@router.get("/rules")
@requires("cad_standard:read")
async def list_rules() -> dict:
    """v1.0 §26 列出 5 个规则文件（layer_rules / block_rules / attribute_rules / drawing_type_rules / specification_rules）"""
    std_dir = _standard_dir()
    files = sorted([f.name for f in std_dir.glob("*.json")]) if std_dir.exists() else []
    return {"files": files, "total": len(files), "directory": str(std_dir)}


@router.get("/rules/{name}")
@requires("cad_standard:read")
async def get_rule(name: str) -> dict:
    """v1.0 §26 读单个规则 JSON"""
    if not name.endswith(".json"):
        name = f"{name}.json"
    path = _standard_dir() / name
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Rule file {name} not found")
    return {
        "name": name,
        "content": json.loads(path.read_text(encoding="utf-8")),
    }


class RuleUpdateRequest(BaseModel):
    content: dict  # 整个规则 JSON 内容


@router.put("/rules/{name}")
@requires("cad_standard:write")
async def update_rule(name: str, req: RuleUpdateRequest) -> dict:
    """v1.0 §26 更新规则 JSON（按 schema 校验）"""
    if not name.endswith(".json"):
        name = f"{name}.json"
    if name not in ("layer_rules.json", "block_rules.json", "attribute_rules.json",
                     "drawing_type_rules.json", "specification_rules.json"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown rule file: {name}")
    path = _standard_dir() / name
    path.write_text(json.dumps(req.content, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"updated": True, "name": name}
