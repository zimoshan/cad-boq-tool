"""LLM 调用审计：每次真实调用落一条 llm_run（任务二十一）。

可回答「这条绑定是哪个模型 / 哪版 Prompt / 什么时候生成的」。
"""
from __future__ import annotations

import hashlib

from .. import db


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def log_llm_call(project_id: int, task_type: str, model: str,
                 prompt_version: str, temperature: float,
                 input_text: str, output_text: str = "",
                 duration_ms: int = 0, token_input: int = 0, token_output: int = 0,
                 status: str = "ok", error: str = "") -> int:
    """记录一次 LLM 调用，返回 run_id。"""
    return db.create_llm_run(
        project_id=project_id, task_type=task_type, model=model,
        model_version="", prompt_version=prompt_version,
        temperature=temperature,
        input_hash=_sha256(input_text), output_hash=_sha256(output_text),
        duration_ms=duration_ms, token_input=token_input, token_output=token_output,
        status=status, error=error or "")


def list_runs(project_id: int, limit: int = 50) -> list:
    return db.list_llm_runs(project_id, limit=limit)
