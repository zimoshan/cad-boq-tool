"""LLM 层：结构化输出校验 / Prompt / 审计 / Embedding / 统一调用 / 配置中心。"""

from . import settings as llm_settings  # 配置中心（P2）
from .audit import list_runs, log_llm_call
from .embeddings import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
    cosine_similarity,
    create_embedding_provider,
)
from .prompts import BINDING_SYSTEM_PROMPT, build_binding_prompt
from .runner import run_llm_with_retry
from .schema import BindingSuggestion, SchemaError, binding_json_schema, parse_binding_suggestion

__all__ = [
    "BindingSuggestion",
    "SchemaError",
    "parse_binding_suggestion",
    "binding_json_schema",
    "build_binding_prompt",
    "BINDING_SYSTEM_PROMPT",
    "log_llm_call",
    "list_runs",
    "EmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
    "cosine_similarity",
    "run_llm_with_retry",
    "llm_settings",
]
