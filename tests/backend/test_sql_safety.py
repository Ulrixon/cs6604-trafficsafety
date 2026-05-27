"""
SQL safety regression tests for backend API query paths.

These tests focus on user-controlled table/column inputs exposed by the
database explorer API. SQLAlchemy covers local app database statements; the VTTI
explorer uses a psycopg2 connection pool, so identifiers must be allowlisted and
composed safely instead of interpolated into SQL strings.
"""

import pytest
from fastapi import HTTPException


class FakeDbClient:
    def __init__(self):
        self.calls = []

    def execute_query(self, query, params=None):
        self.calls.append((query, params))
        query_text = str(query)

        if "information_schema.tables" in query_text:
            return [{"table_name": "vehicle-count"}]
        if "information_schema.columns" in query_text:
            return [{"column_name": "intersection"}]
        return [{"intersection": "glebe-potomac"}]


@pytest.mark.asyncio
async def test_database_explorer_rejects_unknown_table_before_data_query(monkeypatch):
    from app.api import database_explorer

    fake_client = FakeDbClient()
    monkeypatch.setattr(database_explorer, "get_db_client", lambda: fake_client)

    with pytest.raises(HTTPException) as exc:
        await database_explorer.get_table_data('vehicle-count"; DROP TABLE users; --')

    assert exc.value.status_code == 404
    assert len(fake_client.calls) == 1
    assert "information_schema.tables" in fake_client.calls[0][0]


@pytest.mark.asyncio
async def test_database_explorer_rejects_unknown_filter_column(monkeypatch):
    from app.api import database_explorer

    fake_client = FakeDbClient()
    monkeypatch.setattr(database_explorer, "get_db_client", lambda: fake_client)

    with pytest.raises(HTTPException) as exc:
        await database_explorer.get_table_data(
            "vehicle-count",
            filter_col='intersection"; DROP TABLE users; --',
            filter_val="x",
        )

    assert exc.value.status_code == 400
    assert len(fake_client.calls) == 2
    assert "information_schema.columns" in fake_client.calls[1][0]


@pytest.mark.asyncio
async def test_database_explorer_uses_composed_identifier_query(monkeypatch):
    from app.api import database_explorer

    fake_client = FakeDbClient()
    monkeypatch.setattr(database_explorer, "get_db_client", lambda: fake_client)

    result = await database_explorer.get_table_data(
        "vehicle-count",
        filter_col="intersection",
        filter_val="glebe-potomac",
        limit=10,
        offset=0,
    )

    assert result == [{"intersection": "glebe-potomac"}]
    data_query, params = fake_client.calls[-1]
    assert params == ("glebe-potomac", 10, 0)
    assert hasattr(data_query, "as_string")
    assert "glebe-potomac" not in str(data_query)


def test_db_service_no_longer_depends_on_execute_raw_sql():
    import inspect
    from app.services import db_service

    source = inspect.getsource(db_service)
    assert "execute_raw_sql" not in source
    assert "session.execute(text(" not in source


def test_safetychat_sql_tool_rejects_multi_statement_sql():
    from app.services.chat_service import _execute_run_sql

    result = _execute_run_sql({"sql": "SELECT * FROM intersections; SELECT pg_sleep(10)"})

    assert "single SQL statement" in result["error"]


def test_safetychat_sql_tool_rejects_sql_comments():
    from app.services.chat_service import _execute_run_sql

    result = _execute_run_sql({"sql": "SELECT * FROM intersections -- hide trailing SQL"})

    assert "comments" in result["error"]


def test_mcdm_queries_bind_timestamp_and_bin_parameters():
    from datetime import datetime, timezone

    from app.services.mcdm_service import MCDMSafetyIndexService

    class FakeMcdmClient:
        def __init__(self):
            self.calls = []

        def execute_query(self, query, params=None):
            self.calls.append((query, params))
            return []

    fake_client = FakeMcdmClient()
    service = MCDMSafetyIndexService(fake_client)

    service._collect_data_matrix(
        datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        bin_minutes=15,
    )

    query, params = fake_client.calls[0]
    assert "%(start_ts)s" in query
    assert "%(end_ts)s" in query
    assert "%(bin_us)s" in query
    assert params == {
        "start_ts": 1704067200000000,
        "end_ts": 1704070800000000,
        "bin_us": 900000000,
    }
    assert "1704067200000000" not in query


def test_intersection_mapping_composes_table_identifiers():
    from app.core.intersection_mapping import validate_intersection_in_tables

    class FakeIntersectionClient:
        def __init__(self):
            self.calls = []

        def execute_query(self, query, params=None):
            self.calls.append((query, params))
            return [{"exists": 1}]

    fake_client = FakeIntersectionClient()

    result = validate_intersection_in_tables(
        "glebe_rd-potomac_ave",
        "glebe-potomac",
        fake_client,
    )

    assert result["vehicle-count"] is True
    assert result["safety-event"] is True
    assert all(hasattr(query, "as_string") for query, _ in fake_client.calls)
    assert fake_client.calls[0][1] == {"name": "glebe_rd-potomac_ave"}
    assert fake_client.calls[-1][1] == {"name": "glebe-potomac"}


def test_trino_string_literal_escapes_single_quotes_and_rejects_nulls():
    from app.services.data_collection import _trino_string_literal

    assert _trino_string_literal("x' OR 1=1 --") == "'x'' OR 1=1 --'"

    with pytest.raises(ValueError):
        _trino_string_literal("bad\x00value")
