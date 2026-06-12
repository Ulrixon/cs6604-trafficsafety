"""
Cloud endpoint smoke tests for the deployed FastAPI backend.

These tests intentionally hit Cloud Run. They are skipped unless
RUN_CLOUD_TESTS=1 is set so the normal local test suite stays deterministic.
Override CLOUD_BACKEND_URL when testing a preview or replacement service.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pytest
import requests


pytestmark = [
    pytest.mark.cloud,
    pytest.mark.skipif(
        os.getenv("RUN_CLOUD_TESTS") != "1",
        reason="Cloud endpoint tests are disabled. Set RUN_CLOUD_TESTS=1 to execute them.",
    ),
]


BACKEND_URL = os.getenv(
    "CLOUD_BACKEND_URL",
    "https://cs6604-trafficsafety-180117512369.europe-west1.run.app",
).rstrip("/")
API_URL = os.getenv("CLOUD_BACKEND_API_URL", f"{BACKEND_URL}/api/v1").rstrip("/")
TIMEOUT_SECONDS = float(os.getenv("CLOUD_TEST_TIMEOUT_SECONDS", "60"))


@pytest.fixture(scope="module")
def http() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    return session


def get_json(http: requests.Session, url: str, **kwargs):
    response = http.get(url, timeout=TIMEOUT_SECONDS, **kwargs)
    assert response.status_code < 500, response.text[:500]
    assert response.ok, response.text[:500]
    return response.json()


def numeric(value) -> float:
    parsed = float(value)
    assert parsed == parsed
    return parsed


def test_health_endpoint_reports_service_and_cache(http: requests.Session):
    data = get_json(http, f"{BACKEND_URL}/health")

    assert data["status"] in {"ok", "degraded"}
    assert "version" in data
    assert "database" in data
    assert "cache" in data
    assert data["cache"]["backend"] in {"memory", "redis"}


def test_openapi_schema_exposes_expected_routes(http: requests.Session):
    data = get_json(http, f"{BACKEND_URL}/openapi.json")
    paths = data["paths"]

    assert "/health" in paths
    assert "/api/v1/safety/index/" in paths
    assert "/api/v1/chat/tools" in paths


def test_safety_index_list_is_live_and_not_placeholder_zeros(http: requests.Session):
    data = get_json(http, f"{API_URL}/safety/index/", params={"alpha": 0.7})

    assert isinstance(data, list)
    assert len(data) > 0

    scores = [numeric(row.get("safety_index", 0)) for row in data]
    assert any(score > 0 for score in scores), "all cloud safety_index values are zero"

    required_keys = {"intersection_id", "intersection_name", "safety_index"}
    for row in data[:5]:
        assert required_keys.issubset(row.keys())


def test_intersection_catalog_returns_names(http: requests.Session):
    data = get_json(http, f"{API_URL}/safety/index/intersections/list")

    assert "intersections" in data
    assert isinstance(data["intersections"], list)
    assert len(data["intersections"]) > 0
    assert all(isinstance(name, str) and name for name in data["intersections"][:10])


def test_time_range_endpoint_returns_structured_payload(http: requests.Session):
    data = get_json(
        http,
        f"{API_URL}/safety/index/time/range",
        params={
            "intersection": "glebe-potomac",
            "start_time": "2025-11-01T08:00:00",
            "end_time": "2025-11-01T10:00:00",
            "bin_minutes": 15,
            "alpha": 0.7,
            "include_correlations": "true",
        },
    )

    assert "time_series" in data
    assert isinstance(data["time_series"], list)
    assert "metadata" in data
    assert data["metadata"]["bin_minutes"] == 15


def test_demo_validation_endpoint_returns_rows(http: requests.Session):
    metrics = get_json(
        http,
        f"{API_URL}/analytics/correlation",
        params={
            "start_date": "2025-11-01",
            "end_date": "2025-11-03",
            "threshold": 60,
            "proximity_radius": 500,
            "demo": "true",
        },
    )
    scatter = get_json(
        http,
        f"{API_URL}/analytics/scatter-data",
        params={
            "start_date": "2025-11-01",
            "end_date": "2025-11-03",
            "proximity_radius": 500,
            "demo": "true",
        },
    )

    assert metrics["data_status"] == "demo"
    assert metrics["total_intervals"] > 0
    assert metrics["total_crashes"] > 0
    assert isinstance(scatter, list)
    assert len(scatter) > 0
    assert any(row["had_crash"] for row in scatter)


def test_chat_tools_endpoint_is_available_without_openai_call(http: requests.Session):
    data = get_json(http, f"{API_URL}/chat/tools")

    assert "tools" in data
    assert isinstance(data["tools"], list)
    tool_names = {tool["function"]["name"] for tool in data["tools"]}
    assert {"get_safety_score", "compare_intersections", "get_trend_data"}.issubset(tool_names)


def test_cloud_response_has_current_http_date_header(http: requests.Session):
    response = http.get(f"{BACKEND_URL}/health", timeout=TIMEOUT_SECONDS)
    assert response.ok
    assert "date" in response.headers

    # The header confirms the request reached Cloud Run now, not a local mock.
    server_date = parsedate_to_datetime(response.headers["date"])
    assert server_date.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - server_date).total_seconds()) < 300
