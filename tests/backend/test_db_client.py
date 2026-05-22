"""
Backend tests - VTTIPostgresClient connection pool
==================================================
"""
from unittest.mock import patch


class TestConnectionPool:
    def test_uses_threaded_connection_pool(self):
        """
        The DB client must build a psycopg2 *ThreadedConnectionPool*.

        FastAPI runs synchronous endpoints in a worker thread pool, so several
        requests touch the connection pool concurrently. psycopg2's
        SimpleConnectionPool is documented as single-threaded; under that
        concurrency it hands the same connection to two threads and races
        getconn/putconn — the source of the intermittent
        'connection already closed' errors. ThreadedConnectionPool guards
        the same API with a lock.
        """
        with patch("app.services.db_client.psycopg2") as mock_pg:
            from app.services.db_client import VTTIPostgresClient
            VTTIPostgresClient(
                host="db.example",
                database="d",
                user="u",
                password="p",
                port=5432,
            )
            mock_pg.pool.ThreadedConnectionPool.assert_called_once()
            mock_pg.pool.SimpleConnectionPool.assert_not_called()
