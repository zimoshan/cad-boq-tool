"""LLM 后端抽象：Ollama + 云端服务商（22B-1）。

支持的 backend：
- OllamaBackend：本地 Ollama（默认 qwen2.5:7b）
- DashScopeBackend：阿里云 Qwen-VL-Max（OpenAI 兼容）
- OpenAIBackend：OpenAI GPT-4o/4o-mini
- DeepSeekBackend：DeepSeek-V3
- CustomOpenAIBackend：任何 OpenAI 兼容端点
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """LLM 后端配置（OpenAI 兼容协议）"""
    primary_backend: str = "custom"            # 固定 custom（OpenAI 兼容）
    primary_model: str = ""
    ollama_host: str = "http://127.0.0.1:11434"

    fallback_backend: Optional[str] = None      # 主后端质量差时调
    fallback_model: Optional[str] = None

    api_keys: dict = field(default_factory=dict)   # {"custom": "sk-xxx"}
    custom_endpoints: dict = field(default_factory=dict)  # {"custom": {"base_url", "model", "embedding_model"}}

    # fallback 策略
    auto_fallback: bool = True
    quality_threshold: float = 0.7       # 条目 confidence < 此值触发重新评估


class LLMBackend(ABC):
    """LLM 后端抽象基类"""
    name: str = "abstract"
    is_local: bool = False

    @abstractmethod
    def chat(self, system: str, user: str, images: list = None) -> dict:
        """返回 {"content": str, "tokens_in": int, "tokens_out": int, "latency_ms": int}

        Raises:
            RuntimeError: 调用失败
        """
        pass

    def is_available(self) -> bool:
        """检查后端是否可用"""
        return True


class OllamaBackend(LLMBackend):
    """本地 Ollama 后端"""
    name = "ollama"
    is_local = True

    def __init__(self, model: str = "qwen2.5:7b", host: str = "http://127.0.0.1:11434"):
        self.model = model
        self.host = host

    def chat(self, system: str, user: str, images: list = None) -> dict:
        try:
            import ollama
        except ImportError:
            raise RuntimeError("ollama Python SDK 未装：pip install ollama")

        client = ollama.Client(host=self.host)
        t0 = time.time()
        try:
            resp = client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                options={"temperature": 0.1, "num_predict": 4000},
            )
        except Exception as e:
            raise RuntimeError(f"Ollama 调用失败: {e}") from e
        t1 = time.time()

        return {
            "content": resp["message"]["content"],
            "tokens_in": resp.get("prompt_eval_count", 0) or 0,
            "tokens_out": resp.get("eval_count", 0) or 0,
            "latency_ms": int((t1 - t0) * 1000),
        }

    def is_available(self) -> bool:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.host}/api/tags", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False


class OpenAICompatibleBackend(LLMBackend):
    """OpenAI 兼容 API 后端基类（阿里/DeepSeek/OpenAI/自定义）"""
    is_local = False

    def __init__(self, name: str, model: str, api_key: str, base_url: str):
        self.name = name
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, system: str, user: str, images: list = None) -> dict:
        if not self.api_key:
            raise RuntimeError(f"{self.name} API Key 未配置")
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai Python SDK 未装：pip install openai")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # 视觉模型支持 images（base64）
        content = [{"type": "text", "text": user}]
        if images:
            import base64
            for img_path in images:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })

        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": content if images else user},
                ],
                temperature=0.1,
                max_tokens=4000,
            )
        except Exception as e:
            raise RuntimeError(f"{self.name} 调用失败: {e}") from e
        t1 = time.time()

        usage = resp.usage
        return {
            "content": resp.choices[0].message.content,
            "tokens_in": usage.prompt_tokens if usage else 0,
            "tokens_out": usage.completion_tokens if usage else 0,
            "latency_ms": int((t1 - t0) * 1000),
        }


class DashScopeBackend(OpenAICompatibleBackend):
    """阿里云 DashScope（Qwen-VL-Max）"""
    name = "dashscope"

    def __init__(self, api_key: str, model: str = "qwen-vl-max-0809"):
        super().__init__(
            name="dashscope",
            model=model,
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )


class OpenAIBackend(OpenAICompatibleBackend):
    """OpenAI 后端"""
    name = "openai"

    def __init__(self, api_key: str, model: str = ""):
        # 简化：如果 model 是 Ollama 模型名，强制改为 gpt-4o-mini 默认
        if not model or "qwen" in model.lower() or "llama" in model.lower():
            model = "gpt-4o-mini"
        super().__init__(
            name="openai",
            model=model,
            api_key=api_key,
            base_url="https://api.openai.com/v1",
        )


class DeepSeekBackend(OpenAICompatibleBackend):
    """DeepSeek 后端"""
    name = "deepseek"

    def __init__(self, api_key: str, model: str = ""):
        if not model or "qwen" in model.lower() or "llama" in model.lower():
            model = "deepseek-chat"
        super().__init__(
            name="deepseek",
            model=model,
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
        )


class CustomOpenAIBackend(OpenAICompatibleBackend):
    """自定义 OpenAI 兼容端点（Ollama / LocalAI / vLLM / LM Studio 等）"""
    name = "custom"

    def __init__(self, base_url: str, api_key: str, model: str):
        super().__init__(
            name="custom",
            model=model,
            api_key=api_key or "no-key-required",
            base_url=base_url,
        )


def create_backend(name: str, config: LLMConfig) -> LLMBackend:
    """工厂方法：根据名称创建后端实例"""
    if name == "ollama":
        return OllamaBackend(model=config.primary_model, host=config.ollama_host)
    if name == "dashscope":
        return DashScopeBackend(api_key=config.api_keys.get("dashscope", ""), model="qwen-vl-max-0809")
    if name == "openai":
        return OpenAIBackend(api_key=config.api_keys.get("openai", ""), model=config.primary_model or "gpt-4o-mini")
    if name == "deepseek":
        return DeepSeekBackend(api_key=config.api_keys.get("deepseek", ""), model=config.primary_model or "deepseek-chat")
    if name == "custom":
        ep = config.custom_endpoints.get("custom", {})
        return CustomOpenAIBackend(
            base_url=ep.get("base_url", ""),
            api_key=ep.get("api_key", ""),
            model=ep.get("model", "gpt-4o-mini"),
        )
    raise ValueError(f"未知 backend: {name}")


# 费用参考（USD/1K tokens，2026 估算）
COST_REFERENCE = {
    "ollama": 0.0,
    "dashscope:qwen-vl-max": 0.012,
    "dashscope:qwen-vl-max-0809": 0.012,
    "openai:gpt-4o-mini": 0.00015,
    "openai:gpt-4o": 0.005,
    "deepseek:deepseek-chat": 0.00014,
    "deepseek:deepseek-reasoner": 0.00055,
}


def estimate_cost(backend_name: str, model: str, tokens_in: int, tokens_out: int) -> float:
    """估算 USD 成本"""
    key = f"{backend_name}:{model}"
    rate = COST_REFERENCE.get(key) or COST_REFERENCE.get(backend_name, 0.0)
    return round((tokens_in / 1000) * rate + (tokens_out / 1000) * rate * 3, 4)  # 输出按 3x 计
