"""
PostgreSQL Database Client for VTTI Database

Adapted from data-integration/gcp_postgres_client.py for backend use.
"""

import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


class VTTIPostgresClient:
    """
    Client for connecting to VTTI Google Cloud PostgreSQL database via Cloud SQL Proxy.

    Connection Details:
    - Host: 127.0.0.1 (Cloud SQL Proxy)
    - Database: vtsi
    - User: postgres
    - Port: 9470 (Cloud SQL Proxy port)
    - Instance: symbolic-cinema-305010:europe-west1:vtsi-postgres
    """

    def __init__(
        self,
        host: str = None,
        database: str = None,
        user: str = None,
        password: str = None,
        port: int = None,
        min_connections: int = 1,
        max_connections: int = 10,
    ):
        """
        Initialize the PostgreSQL client with connection pooling.

        Args:
            host: Database host (default from VTTI_DB_HOST env or 127.0.0.1)
            database: Database name (default from VTTI_DB_NAME env or vtsi)
            user: Database user (default from VTTI_DB_USER env or postgres)
            password: Database password (default from VTTI_DB_PASSWORD env)
            port: Database port (default from VTTI_DB_PORT env or 9470)
            min_connections: Minimum connections in pool
            max_connections: Maximum connections in pool
        """
        load_dotenv()  # Load environment variables from .env file
        self.database = database or os.getenv("VTTI_DB_NAME", "vtsi")
        self.user = user or os.getenv("VTTI_DB_USER", "postgres")
        self.password = password or os.getenv("VTTI_DB_PASSWORD")
        instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")

        # If Cloud SQL instance connection name is provided → use Unix socket
        if instance_connection_name:
            # Cloud Run automatically mounts sockets here
            self.host = f"/cloudsql/{instance_connection_name}"
            self.port = None  # socket mode ignores port
        else:
            # Local / TCP fallback
            self.host = host or os.getenv("VTTI_DB_HOST", "127.0.0.1")
            self.port = int(port or os.getenv("VTTI_DB_PORT", "9470"))
        if not self.password:
            raise ValueError(
                "Database password must be provided via VTTI_DB_PASSWORD environment variable or password parameter"
            )

        try:
            # Create connection pool
            if self.port is None:
                # Unix socket mode
                self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                    min_connections,
                    max_connections,
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                )
            else:
                self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                    min_connections,
                    max_connections,
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    port=self.port,
                )
            logger.info(
                f"✓ Connected to PostgreSQL database: {self.database}@{self.host}"
            )
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool using context manager.

        Usage:
            with client.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")
        """
        conn = self.connection_pool.getconn()
        try:
            yield conn
        finally:
            self.connection_pool.putconn(conn)

    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """
        Get a cursor with automatic connection management.

        Args:
            dict_cursor: If True, returns RealDictCursor (rows as dictionaries)

        Usage:
            with client.get_cursor() as cursor:
                cursor.execute("SELECT * FROM table")
                results = cursor.fetchall()
        """
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries.

        Args:
            query: SQL query string
            params: Query parameters (for parameterized queries)

        Returns:
            List of dictionaries representing rows
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            # Convert RealDictRow to plain dict to avoid serialization issues
            return [dict(row) for row in results]

    def execute_update(self, query: str, params: tuple = None) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Number of rows affected
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def close(self):
        """Close all connections in the pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("✓ All database connections closed")


# Global database client instance
_db_client: Optional[VTTIPostgresClient] = None


def get_db_client() -> VTTIPostgresClient:
    """
    Get or create the global database client instance.
    Uses configuration from settings.

    Returns:
        VTTIPostgresClient instance
    """
    global _db_client
    if _db_client is None:
        from ..core.config import settings

        _db_client = VTTIPostgresClient(
            host=settings.VTTI_DB_HOST,
            database=settings.VTTI_DB_NAME,
            user=settings.VTTI_DB_USER,
            password=settings.VTTI_DB_PASSWORD,
            port=settings.VTTI_DB_PORT,
        )
    return _db_client


def close_db_client():
    """Close the global database client."""
    global _db_client
    if _db_client is not None:
        _db_client.close()
        _db_client = None
