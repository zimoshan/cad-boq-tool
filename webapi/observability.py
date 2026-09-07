"""webapi observability（结构化日志 + request_id 中间件）

Phase 6 工程化：生产可观测性
- structlog 替代 stdlib logging（JSON 输出 + 上下文绑定）
- request_id 中间件：每个请求生成 UUID + 加 X-Request-ID 响应头
- access log：自动记录 method/path/status/duration_ms

使用：
    from webapi.observability import setup_logging, RequestIdMiddleware
    setup_logging()
    app.add_middleware(RequestIdMiddleware)
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO", json_output: bool = False, log_file: str | None = None) -> None:
    """配置 structlog + stdlib logging

    - json_output=False: 开发期人类可读（控制台）
    - json_output=True: 生产期 JSON 输出（聚合/搜索友好）
    - log_file: 可选，写到文件（生产期用）
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # structlog processors 链
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # 同步 stdlib logging（FastAPI/Uvicorn 用）
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        try:
            import os

            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except (OSError, PermissionError):
            pass  # 写文件失败时只用 stdout
    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=log_level,
    )


# 全局 logger 实例
logger = structlog.get_logger("cadboq")


def bind_request_id(request_id: str) -> None:
    """绑定 request_id 到 contextvars（structlog 自动合并）"""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_id() -> None:
    """清理 request_id contextvars"""
    structlog.contextvars.unbind_contextvars("request_id")
