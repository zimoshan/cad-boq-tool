"""webapi observability 测试（structlog + request_id）"""
from __future__ import annotations

import io
import json
import sys
import uuid

import pytest
import structlog


class TestStructlog:
    """structlog 配置 + 上下文绑定"""

    def test_setup_logging_human(self):
        """开发模式人类可读（ConsoleRenderer）"""
        from webapi.observability import setup_logging
        setup_logging(level="INFO", json_output=False)
        logger = structlog.get_logger("test")
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            logger.info("test_event", key="value")
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        assert "test_event" in output
        assert "value" in output

    def test_setup_logging_json(self):
        """生产模式 JSON 输出"""
        from webapi.observability import setup_logging
        setup_logging(level="INFO", json_output=True)
        logger = structlog.get_logger("test_json")
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            logger.info("json_event", count=42)
            output = sys.stdout.getvalue().strip()
        finally:
            sys.stdout = old_stdout
        # JSON 格式：应能解析
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if parsed.get("event") == "json_event":
                    assert parsed["count"] == 42
                    break
            except json.JSONDecodeError:
                continue
        else:
            pytest.fail(f"未找到 json_event JSON 行: {output[:200]}")

    def test_request_id_binding(self):
        """contextvars bind/unbind request_id"""
        from webapi.observability import bind_request_id, clear_request_id
        clear_request_id()
        bind_request_id("test-rid-12345")
        import structlog.contextvars as cvars
        ctx = cvars.get_contextvars()
        assert ctx.get("request_id") == "test-rid-12345"
        clear_request_id()
        ctx = cvars.get_contextvars()
        assert ctx.get("request_id") is None


class TestRequestIdMiddleware:
    """RequestIdMiddleware + X-Request-ID 头"""

    def test_middleware_generates_request_id(self):
        from webapi.middleware import RequestIdMiddleware
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)

        @app.get("/test")
        def test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # 应该是 UUID 格式
        uuid.UUID(response.headers["X-Request-ID"])

    def test_middleware_preserves_existing_request_id(self):
        from webapi.middleware import RequestIdMiddleware
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)

        @app.get("/test")
        def test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        custom_id = "my-custom-rid-12345"
        response = client.get("/test", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id
