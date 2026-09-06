"""llm 域 schema"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class LlmSettingsRead(BaseModel):
    """llm_settings 单例表读取（PG/PG-asyncio 同步）"""
    model_config = {"protected_namespaces": ()}  # 允许 model_version 字段
    id: int = 1
    active_backend: str = "ollama"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    dashscope_api_key: str = ""
    dashscope_model: str = "qwen-vl-max-0809"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""
    custom_embedding_model: str = ""
    fallback_enabled: int = 0
    fallback_backend: str = ""
    quality_threshold: float = 0.7
    temperature: float = 0.1
    timeout: int = 120
    max_tokens: int = 4000
    updated_at: str = ""


class LlmSettingsUpdate(BaseModel):
    """部分字段更新"""
    active_backend: Optional[str] = None
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    dashscope_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    custom_base_url: Optional[str] = None
    custom_api_key: Optional[str] = None
    custom_model: Optional[str] = None
    custom_embedding_model: Optional[str] = None
    fallback_enabled: Optional[int] = None
    fallback_backend: Optional[str] = None
    quality_threshold: Optional[float] = None
    temperature: Optional[float] = None
    timeout: Optional[int] = None
    max_tokens: Optional[int] = None


class ChatRequest(BaseModel):
    system: str = ""
    user: str
    images: list[str] = Field(default_factory=list, description="base64 编码图片列表（Phase 2 占位）")
    task_type: str = "chat"


class ChatResponse(BaseModel):
    task_type: str
    model: str
    output: Any
