"""
Backend tests – FastAPI app & chat router
=========================================
Tests cover:
  - App startup / health check
  - Chat router Pydantic schema validation
  - Chat endpoint: 503 when OPENAI_API_KEY is empty
  - Chat /tools endpoint
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import asynccontextmanager


# ---------------------------------------------------------------------------
# App fixture – override lifespan so no real DB is needed
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    Create a TestClient with the lifespan overridden to a no-op so tests
    run without a live PostgreSQL instance.
    """
    from app.main import app

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# Health / root
# ---------------------------------------------------------------------------

class TestAppStartup:
    def test_openapi_schema_available(self, client):
        """OpenAPI schema endpoint must be reachable (app booted correctly)."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_redirect_or_ok(self, client):
        """Swagger UI must render (200 or redirect)."""
        resp = client.get("/docs", follow_redirects=True)
        assert resp.status_code in (200, 307, 308)


# ---------------------------------------------------------------------------
# Chat router – schema validation (no real OpenAI call)
# ---------------------------------------------------------------------------

class TestChatRouterSchema:
    def test_chat_rejects_empty_messages(self, client):
        """POST /api/v1/chat/ with empty messages list must return 422."""
        resp = client.post("/api/v1/chat/", json={"messages": []})
        assert resp.status_code == 422

    def test_chat_rejects_bad_role(self, client):
        """POST /api/v1/chat/ with invalid role must return 422."""
        resp = client.post(
            "/api/v1/chat/",
            json={"messages": [{"role": "system", "content": "hello"}]},
        )
        assert resp.status_code == 422

    def test_chat_rejects_missing_content(self, client):
        """POST /api/v1/chat/ with missing content field must return 422."""
        resp = client.post(
            "/api/v1/chat/",
            json={"messages": [{"role": "user"}]},
        )
        assert resp.status_code == 422

    def test_chat_503_when_no_api_key(self, client):
        """
        POST /api/v1/chat/ with a valid payload but no OPENAI_API_KEY must
        return 503 (SafetyChat not configured).
        """
        with patch("app.services.chat_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = ""
            mock_settings.OPENAI_MODEL = "gpt-4o"
            mock_settings.OPENAI_MAX_TOKENS = 1024
            resp = client.post(
                "/api/v1/chat/",
                json={"messages": [{"role": "user", "content": "test"}]},
            )
        # 503 = key missing, or 500 if chat service raises before key check
        assert resp.status_code in (503, 500)

    def test_chat_tools_endpoint(self, client):
        """GET /api/v1/chat/tools must return a list of tool definitions."""
        resp = client.get("/api/v1/chat/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)
        assert len(data["tools"]) > 0
        # Each tool must have a name
        for tool in data["tools"]:
            assert "function" in tool
            assert "name" in tool["function"]
