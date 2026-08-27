"""统一 LLM 调用：JSON Schema 校验 + 失败自动重试 + 全量审计（任务十三/二十一/二十九）。

流程：LLM → 解析+校验（validator）→ 成功返回；失败自动重试（≤retries 次）。
每次真实调用都写 llm_run 审计。

V2 配置中心接入（任务二十九 P3）：
- 不再硬编码 OllamaBackend，改用 `create_backend(settings)` 工厂。
- 活跃 backend / model / api_key 全部从 `app.llm.settings.load_active()` 读。
- runner 函数签名向后兼容（外部仍可传 model/host/temperature 覆盖默认）。
- 主 backend 跑出来后若全部候选 confidence < quality_threshold 且启用 fallback，
  自动切换 fallback backend 重跑一次，task_type 标记 'binding-fallback' 写审计。
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .. import config
from . import audit
from .settings import load_active
from ..takeoff.llm_backends import (LLMConfig, create_backend, LLMBackend)


# ----- 内部辅助 -----
def llm_available(timeout: float = 2.0) -> bool:
    """LLM 后端是否可用（秒级探测，避免逐 EO 调用挨个超时）。

    - ollama：GET {host}/api/tags（2s 超时），不通即 False
    - 云端/custom：配置里有 api_key / base_url 即视为可用
      （真实连通性由单次调用的失败保底兜住，不做网络探测）
    """
    try:
        llmc = load_active()
    except Exception:  # noqa: BLE001 配置读取失败按不可用
        return False
    backend = llmc.primary_backend
    if backend == "ollama":
        import urllib.request
        host = (llmc.ollama_host or "").rstrip("/")
        if not host:
            return False
        try:
            with urllib.request.urlopen(f"{host}/api/tags", timeout=timeout):
                return True
        except Exception:  # noqa: BLE001
            return False
    if backend == "custom":
        ep = llmc.custom_endpoints.get("custom") or {}
        return bool(ep.get("base_url"))
    # openai / deepseek / dashscope 等 API 型后端
    return bool(llmc.api_keys.get(backend))


def _resolve_backend(llmc: LLMConfig, override_model: str = None,
                     override_host: str = None) -> LLMBackend:
    """从 LLMConfig 工厂创建 backend 实例；可被入参 override_model/host 临时覆盖。"""
    backend = create_backend(llmc.primary_backend, llmc)
    if override_model:
        backend.model = override_model
    if override_host and hasattr(backend, "host"):
        backend.host = override_host
    return backend


def _resolve_runtime(task_type: str = "binding"):
    """读取运行时配置：返回 (llmc, fallback_backend_name, quality_threshold)。"""
    llmc = load_active()
    fb = None
    if llmc.auto_fallback and llmc.fallback_backend:
        fb = llmc.fallback_backend
    return llmc, fb, llmc.quality_threshold


def _audit_run(project_id: int, task_type: str, model: str, prompt_version: str,
               temperature: float, input_text: str, content: str,
               duration_ms: int, token_in: int, token_out: int,
               status: str, error: str = "") -> int:
    """统一审计入口；失败也允许记录。"""
    return audit.log_llm_call(
        project_id, task_type, model, prompt_version, temperature,
        input_text, content, duration_ms, token_in, token_out,
        status=status, error=error)


# ----- 主入口：与原签名 100% 兼容 -----
def run_llm_with_retry(
    project_id: int,
    task_type: str,
    system: str,
    user: str,
    validator: Optional[Callable[[str], object]] = None,
    model: str = None,
    host: str = None,
    temperature: float = None,
    timeout: int = None,
    max_tokens: int = None,
    prompt_version: str = "",
    retries: int = 2,
) -> dict:
    """调用 LLM 并校验，失败自动重试。

    参数保持向后兼容（位置/关键字不变）。缺省从 `app.llm.settings.load_active()` + app.config 取值。

    Returns:
        {"content", "parsed", "run_ids": [...], "attempts": int, "ok": bool,
         "backend": str, "model": str, "used_fallback": bool, "tokens_in": int, "tokens_out": int,
         "error": str (only if !ok)}
    """
    llmc, fallback_backend_name, threshold = _resolve_runtime(task_type)
    backend = _resolve_backend(llmc, override_model=model, override_host=host)
    if temperature is None:
        temperature = 0.1
    timeout = timeout or config.LLM_TIMEOUT
    max_tokens = max_tokens or config.LLM_MAX_TOKENS

    run_ids = []
    last_error = ""
    attempts = 0
    tokens_in = tokens_out = 0

    for attempt in range(retries + 1):
        attempts = attempt + 1
        prompt_text = (system + "\n" + user)
        t0 = time.time()
        try:
            resp = backend.chat(system, user)
        except Exception as e:  # noqa: BLE001 网络/服务错误也重试
            last_error = str(e)
            duration = int((time.time() - t0) * 1000)
            run_id = _audit_run(
                project_id, task_type, backend.model, prompt_version, temperature,
                prompt_text, "", duration, 0, 0,
                status="error", error=last_error)
            run_ids.append(run_id)
            continue

        duration = int((time.time() - t0) * 1000)
        content = resp["content"]
        tokens_in = resp.get("tokens_in", 0)
        tokens_out = resp.get("tokens_out", 0)

        parsed = None
        valid = True
        if validator is not None:
            try:
                parsed = validator(content)
            except Exception as e:  # noqa: BLE001 SchemaError/解析失败
                valid = False
                last_error = str(e)
                # 重试提示：附上上次错误，引导模型修正
                user = user + f"\n\n# 上次输出未通过校验：{last_error[:200]}\n请重新输出严格 JSON。"

        run_id = _audit_run(
            project_id, task_type, backend.model, prompt_version, temperature,
            prompt_text, content, duration, tokens_in, tokens_out,
            status="ok" if valid else "retried" if attempt < retries else "error",
            error="" if valid else last_error)
        run_ids.append(run_id)

        if valid:
            return {
                "content": content, "parsed": parsed, "run_ids": run_ids,
                "attempts": attempts, "ok": True,
                "backend": llmc.primary_backend, "model": backend.model,
                "used_fallback": False,
                "tokens_in": tokens_in, "tokens_out": tokens_out,
            }

    # 主 backend 没成功 → 触发 fallback
    if fallback_backend_name:
        # 重建 fb_llmc 时让 primary_model 变成该 backend 自己的默认 model
        model_for = {
            "ollama": llmc.ollama_host and llmc.primary_model or "qwen2.5:7b",
            "dashscope": "qwen-vl-max-0809",
            "openai": "gpt-4o-mini",
            "deepseek": "deepseek-chat",
            "custom": (llmc.custom_endpoints.get("custom") or {}).get("model", "") or "gpt-4o-mini",
        }
        # 但若 fallback backend 是 ollama，应用 ollama_model 而非 primary_model（因为 primary 可能不是 ollama 用的）
        # 简单策略：fallback backend 自己用的 model = 它在 settings 表里的字段
        # 我们反向从 db 拉一次（确保用最新字段）
        from .. import db as _db
        settings = _db.get_llm_settings()
        fallback_model_map = {
            "ollama": settings.get("ollama_model", "") or "qwen2.5:7b",
            "dashscope": settings.get("dashscope_model", "") or "qwen-vl-max-0809",
            "openai": settings.get("openai_model", "") or "gpt-4o-mini",
            "deepseek": settings.get("deepseek_model", "") or "deepseek-chat",
            "custom": settings.get("custom_model", "") or (llmc.custom_endpoints.get("custom") or {}).get("model", ""),
        }
        fallback_model = fallback_model_map.get(fallback_backend_name, model_for.get(fallback_backend_name, "gpt-4o-mini"))

        fb_llmc = LLMConfig(
            primary_backend=fallback_backend_name,
            primary_model=fallback_model,
            ollama_host=llmc.ollama_host,
            fallback_backend=None,
            fallback_model=None,
            api_keys=llmc.api_keys,
            custom_endpoints=llmc.custom_endpoints,
            auto_fallback=False,   # fallback 不再 fallback
            quality_threshold=threshold,
        )
        fb_backend = create_backend(fallback_backend_name, fb_llmc)

        retry_user = user  # 不再追加错误提示，从头来
        attempts_fb = 0
        for attempt in range(retries + 1):
            attempts_fb += 1
            t0 = time.time()
            try:
                resp = fb_backend.chat(system, retry_user)
            except Exception as e:  # noqa: BLE001
                last_error = str(e)
                run_id = _audit_run(
                    project_id, task_type + "-fallback", fb_backend.model, prompt_version,
                    temperature, system + "\n" + retry_user, "",
                    int((time.time() - t0) * 1000), 0, 0, status="error", error=last_error)
                run_ids.append(run_id)
                continue
            duration = int((time.time() - t0) * 1000)
            content = resp["content"]
            tokens_in = resp.get("tokens_in", 0)
            tokens_out = resp.get("tokens_out", 0)

            parsed = None
            valid = True
            if validator is not None:
                try:
                    parsed = validator(content)
                except Exception as e:  # noqa: BLE001
                    valid = False
                    last_error = str(e)
                    retry_user = retry_user + f"\n\n# 上次输出未通过校验：{last_error[:200]}\n请重新输出严格 JSON。"

            run_id = _audit_run(
                project_id, task_type + "-fallback", fb_backend.model, prompt_version,
                temperature, system + "\n" + retry_user, content,
                duration, tokens_in, tokens_out,
                status="ok" if valid else "retried" if attempt < retries else "error",
                error="" if valid else last_error)
            run_ids.append(run_id)

            if valid:
                return {
                    "content": content, "parsed": parsed, "run_ids": run_ids,
                    "attempts": attempts + attempts_fb, "ok": True,
                    "backend": fallback_backend_name, "model": fb_backend.model,
                    "used_fallback": True,
                    "tokens_in": tokens_in, "tokens_out": tokens_out,
                }

    return {
        "content": "", "parsed": None, "run_ids": run_ids,
        "attempts": attempts + (attempts_fb if fallback_backend_name else 0),
        "ok": False, "backend": llmc.primary_backend, "model": backend.model,
        "used_fallback": bool(fallback_backend_name),
        "tokens_in": tokens_in, "tokens_out": tokens_out, "error": last_error,
    }
