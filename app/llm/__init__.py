"""LLM 层：结构化输出校验 / Prompt / 审计 / Embedding / 统一调用 / 配置中心。"""
from .schema import (BindingSuggestion, SchemaError, parse_binding_suggestion,
                     binding_json_schema)
from .prompts import build_binding_prompt, BINDING_SYSTEM_PROMPT
from .audit import log_llm_call, list_runs
from .embeddings import (EmbeddingProvider, OllamaEmbeddingProvider,
                         OpenAIEmbeddingProvider,
                         create_embedding_provider, cosine_similarity)
from .runner import run_llm_with_retry
from . import settings as llm_settings   # 配置中心（P2）

__all__ = [
    "BindingSuggestion", "SchemaError", "parse_binding_suggestion",
    "binding_json_schema",
    "build_binding_prompt", "BINDING_SYSTEM_PROMPT",
    "log_llm_call", "list_runs",
    "EmbeddingProvider", "OllamaEmbeddingProvider", "OpenAIEmbeddingProvider",
    "create_embedding_provider", "cosine_similarity",
    "run_llm_with_retry",
    "llm_settings",
]
