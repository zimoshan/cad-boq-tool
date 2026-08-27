"""Embedding Provider：语义召回向量化（任务十一）。

支持 OpenAI 兼容协议 embedding（text-embedding-* 等）。
未配置 embedding 模型时 is_available()=False，调用方自动跳过该层，不影响离线模式。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from .. import config


class EmbeddingProvider(ABC):
    """向量化抽象"""
    name: str = "abstract"

    @abstractmethod
    def embed(self, texts: list) -> list:
        """返回 list[list[float]]，与输入同序"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class OllamaEmbeddingProvider(EmbeddingProvider):
    """本地 Ollama embedding"""
    name = "ollama"

    def __init__(self, model: str = None, host: str = None):
        self.model = model or config.EMBEDDING_MODEL
        self.host = host or "http://127.0.0.1:11434"

    def is_available(self) -> bool:
        if not self.model:
            return False
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=3) as r:
                data = r.read()
            return self.model in str(data)
        except Exception:
            return False

    def embed(self, texts: list) -> list:
        try:
            import ollama
        except ImportError as e:
            raise RuntimeError("ollama SDK 未装：pip install ollama") from e
        if not texts:
            return []
        client = ollama.Client(host=self.host, timeout=120)
        resp = client.embed(model=self.model, input=list(texts))
        emb = resp.get("embeddings")
        if not emb:
            raise RuntimeError(f"Ollama embed 返回空: {resp}")
        return emb


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI 兼容端点 embedding（text-embedding-3-small 等）"""
    name = "custom"

    def __init__(self, model: str = "", base_url: str = "", api_key: str = ""):
        self.model = model or config.EMBEDDING_MODEL
        self.base_url = base_url
        self.api_key = api_key

    def is_available(self) -> bool:
        return bool(self.model and self.base_url)

    def embed(self, texts: list) -> list:
        if not texts:
            return []
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("openai SDK 未装：pip install openai") from e
        client = OpenAI(api_key=self.api_key or "no-key-required", base_url=self.base_url)
        resp = client.embeddings.create(model=self.model, input=list(texts))
        # 按输入顺序返回向量
        ordered = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in ordered]


def create_embedding_provider(provider: str = None) -> EmbeddingProvider:
    """工厂：按名称创建（缺省与 LLM 活跃 backend 对齐）。

    对齐规则：
      - provider 显式传入 ollama → OllamaEmbeddingProvider（原生 /api/embed，走 ollama SDK）
      - 活跃 backend 为 ollama → OllamaEmbeddingProvider
      - 其余（custom/dashscope/openai/deepseek）→ OpenAI 兼容端点，读 `custom_embedding_model`
        及对应 base_url/api_key；未配置 embedding 模型时 is_available()=False，调用方自动跳过。
    """
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    from ..llm.settings import load_active
    llmc = load_active()
    active = llmc.primary_backend or config.MODEL_PROVIDER
    if provider is None and str(active).lower() == "ollama":
        return OllamaEmbeddingProvider()
    # OpenAI 兼容（provider 显式指定 或 活跃后端为云端/custom）
    try:
        ep = llmc.custom_endpoints.get("custom", {}) or {}
        return OpenAIEmbeddingProvider(
            model=ep.get("embedding_model", "") or config.EMBEDDING_MODEL,
            base_url=ep.get("base_url", ""),
            api_key=ep.get("api_key", ""),
        )
    except Exception:
        return OpenAIEmbeddingProvider(
            model=config.EMBEDDING_MODEL,
            base_url="",
            api_key="",
        )


def cosine_similarity(a: list, b: list) -> float:
    """余弦相似度"""
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1e-12
    return float(np.dot(va, vb) / denom)
