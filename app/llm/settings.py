"""LLM 配置中心（任务二十九 P2/P3 支撑层）。

职责：
- `LLMConfigLoader.load_active()` 从 DB 拉取 llm_settings，转成 `LLMConfig` dataclass；
  缺字段时回退 `app.config` 全局默认值，保持向后兼容。
- `probe_backend()` 主动测速：Ollama 走 `/api/tags`，OpenAI 兼容走 `GET /models`。
- `resolve_runtime()` 一次性返回 (primary_backend, fallback_backend, llm_config, threshold)，
  给 runner.py 调用，减少重复读取。
"""
from __future__ import annotations

import time
from typing import Optional, Tuple

from .. import db, config
from ..takeoff.llm_backends import LLMConfig


# ---- 低层：DB dict → LLMConfig dataclass ----
def _settings_to_llm_config(s: dict) -> LLMConfig:
    """db.llm_settings 行（dict）→ LLMConfig。

    LLMConfig 字段定义见 takeoff/llm_backends.py：
    - primary_backend / primary_model / ollama_host
    - fallback_backend / fallback_model
    - api_keys: {dashscope, openai, deepseek}
    - custom_endpoints: {custom: {base_url, api_key, model}}
    - auto_fallback / quality_threshold
    """
    api_keys = {
        "dashscope": s.get("dashscope_api_key", "") or "",
        "openai": s.get("openai_api_key", "") or "",
        "deepseek": s.get("deepseek_api_key", "") or "",
        "custom": s.get("custom_api_key", "") or "",
    }
    custom_endpoints = {
        "custom": {
            "base_url": s.get("custom_base_url", "") or "",
            "api_key": s.get("custom_api_key", "") or "",
            "model": s.get("custom_model", "") or "",
            "embedding_model": s.get("custom_embedding_model", "") or "",
        }
    }
    primary = (s.get("active_backend", "custom") or "custom").lower()
    model_map = {
        "ollama": s.get("ollama_model", "") or "qwen2.5:7b",
        "dashscope": s.get("dashscope_model", "") or "qwen-vl-max-0809",
        "openai": s.get("openai_model", "") or "gpt-4o-mini",
        "deepseek": s.get("deepseek_model", "") or "deepseek-chat",
        "custom": s.get("custom_model", "") or "",
    }
    primary_model = model_map[primary]
    fallback_enabled = bool(s.get("fallback_enabled", 0))
    fallback_backend = (s.get("fallback_backend", "") or "").lower() if fallback_enabled else ""
    fallback_model = model_map.get(fallback_backend, "") if fallback_backend else None

    return LLMConfig(
        primary_backend=primary,
        primary_model=primary_model,
        ollama_host=s.get("ollama_host", "http://127.0.0.1:11434") or "http://127.0.0.1:11434",
        fallback_backend=fallback_backend or None,
        fallback_model=fallback_model or None,
        api_keys=api_keys,
        custom_endpoints=custom_endpoints,
        auto_fallback=fallback_enabled,
        quality_threshold=float(s.get("quality_threshold", 0.7)),
    )


def load_active() -> LLMConfig:
    """读取活跃 LLM 配置（含回退到 app.config 默认值）。"""
    s = db.get_llm_settings()
    llmc = _settings_to_llm_config(s)
    # 回退：若 DB 行字段全空（极旧库），保底用 config.py 的硬编码默认
    if not llmc.primary_model:
        fallback_model = getattr(config, "MODEL_NAME", "") or ""
        if fallback_model:
            llmc.primary_model = fallback_model
    if not llmc.ollama_host:
        llmc.ollama_host = "http://127.0.0.1:11434"
    return llmc


def to_settings_dict(llmc: LLMConfig) -> dict:
    """LLMConfig → db.llm_settings 行 dict（UI 写入时使用）"""
    return {
        "active_backend": llmc.primary_backend,
        "ollama_host": llmc.ollama_host,
        "ollama_model": llmc.primary_model if llmc.primary_backend == "ollama" else (
            llmc.fallback_model if llmc.fallback_backend == "ollama" else ""),
        "dashscope_api_key": llmc.api_keys.get("dashscope", ""),
        "dashscope_model": llmc.primary_model if llmc.primary_backend == "dashscope" else (
            llmc.fallback_model if llmc.fallback_backend == "dashscope" else ""),
        "openai_api_key": llmc.api_keys.get("openai", ""),
        "openai_model": llmc.primary_model if llmc.primary_backend == "openai" else (
            llmc.fallback_model if llmc.fallback_backend == "openai" else ""),
        "deepseek_api_key": llmc.api_keys.get("deepseek", ""),
        "deepseek_model": llmc.primary_model if llmc.primary_backend == "deepseek" else (
            llmc.fallback_model if llmc.fallback_backend == "deepseek" else ""),
        "custom_base_url": llmc.custom_endpoints.get("custom", {}).get("base_url", ""),
        "custom_api_key": llmc.custom_endpoints.get("custom", {}).get("api_key", ""),
        "custom_model": llmc.custom_endpoints.get("custom", {}).get("model", ""),
        "custom_embedding_model": llmc.custom_endpoints.get("custom", {}).get("embedding_model", ""),
        "fallback_enabled": int(bool(llmc.auto_fallback and llmc.fallback_backend)),
        "fallback_backend": llmc.fallback_backend or "",
        "quality_threshold": llmc.quality_threshold,
    }


# ---- 测速：probe ----
def probe_backend(name: str, llmc: LLMConfig, timeout: float = 5.0) -> dict:
    """测试指定 backend 的连通性。

    Returns:
        {"ok": bool, "latency_ms": int, "models_sample": [str, ...], "error": str}
    """
    name = (name or llmc.primary_backend or "ollama").lower()
    t0 = time.time()
    try:
        if name == "ollama":
            import urllib.request, json
            host = llmc.ollama_host or "http://127.0.0.1:11434"
            req = urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=timeout)
            data = json.loads(req.read().decode("utf-8", errors="replace"))
            models = [m.get("name", "") for m in data.get("models", [])][:5]
            latency = int((time.time() - t0) * 1000)
            return {"ok": True, "latency_ms": latency, "models_sample": models, "error": ""}

        # OpenAI 兼容测速（dashscope/openai/deepseek/custom）
        api_key_map = {
            "dashscope": llmc.api_keys.get("dashscope", ""),
            "openai": llmc.api_keys.get("openai", ""),
            "deepseek": llmc.api_keys.get("deepseek", ""),
        }
        base_url_map = {
            "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "custom": (llmc.custom_endpoints.get("custom", {}) or {}).get("base_url", ""),
        }
        api_key = api_key_map.get(name, "") or (llmc.custom_endpoints.get("custom", {}) or {}).get("api_key", "")
        base_url = (base_url_map.get(name, "") or "").rstrip("/")
        if not api_key or not base_url:
            return {"ok": False, "latency_ms": 0, "models_sample": [],
                    "error": "API Key 或 base_url 未配置"}
        try:
            import urllib.request, json
            req = urllib.request.Request(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            models = [m.get("id", m.get("name", "")) for m in data.get("data", [])][:5]
            latency = int((time.time() - t0) * 1000)
            return {"ok": True, "latency_ms": latency, "models_sample": models, "error": ""}
        except Exception as e:  # noqa: BLE001
            # OpenAI SDK 兜底
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
                models_resp = client.models.list()
                models = [m.id for m in models_resp.data][:5]
                latency = int((time.time() - t0) * 1000)
                return {"ok": True, "latency_ms": latency, "models_sample": models, "error": ""}
            except Exception as e2:  # noqa: BLE001
                return {"ok": False, "latency_ms": 0, "models_sample": [],
                        "error": f"{e} / {e2}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "latency_ms": 0, "models_sample": [],
                "error": str(e)}


def resolve_runtime() -> Tuple[LLMConfig, Optional[str], float]:
    """一次性返回 (LLMConfig, fallback_backend, quality_threshold)。runner.py 使用。

    注意：fallback_backend 只在 auto_fallback=True 且 fallback 非空时返回；否则为 None。
    """
    llmc = load_active()
    fb = llmc.fallback_backend if (llmc.auto_fallback and llmc.fallback_backend) else None
    return llmc, fb, llmc.quality_threshold
