"""/api/llm 路由（Phase 2.2）"""

# 不使用 from __future__ import annotations：Pydantic 2.8 + FastAPI 0.115 forward ref 解析问题
import contextlib

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from webapi.auth.decorators import requires
from webapi.db import get_db
from webapi.schemas.llm import (
    ChatRequest,
    ChatResponse,
    LlmSettingsRead,
    LlmSettingsUpdate,
)
from webapi.services import llm as llm_service

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/settings", response_model=LlmSettingsRead)
@requires("llm:read")
async def get_settings(db: AsyncSession = Depends(get_db)) -> LlmSettingsRead:
    """读 llm_settings 单例表（#9 后端转发 5 后端配置）"""
    data = await llm_service.get_llm_settings(db)
    return LlmSettingsRead(**data)


@router.put("/settings", response_model=LlmSettingsRead)
@requires("llm:write")
async def update_settings(req: LlmSettingsUpdate, db: AsyncSession = Depends(get_db)) -> LlmSettingsRead:
    """部分字段更新 llm_settings"""
    updates = req.model_dump(exclude_unset=True)
    data = await llm_service.update_llm_settings(db, updates)
    return LlmSettingsRead(**data)


@router.post("/chat", response_model=ChatResponse)
@requires("llm:chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """通用 chat 端点（#9 后端转发）"""
    import base64

    images_bytes: list[bytes] = []
    for img_b64 in req.images:
        with contextlib.suppress(Exception):
            images_bytes.append(base64.b64decode(img_b64))
    result = await llm_service.chat_completion(db, req.system, req.user, images_bytes or None, req.task_type)
    return ChatResponse(**result)
