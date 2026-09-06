"""webapi 中间件（request_id + access log）"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from webapi.observability import bind_request_id, clear_request_id, logger


class RequestIdMiddleware(BaseHTTPMiddleware):
    """每个请求生成 UUID + 加 X-Request-ID 响应头 + access log"""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(__import__("uuid").uuid4())
        bind_request_id(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        except Exception as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "http_request_error",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=duration_ms,
            )
            raise
        finally:
            clear_request_id()
