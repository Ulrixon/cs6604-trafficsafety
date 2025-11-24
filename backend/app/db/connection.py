"""
Database connection management for PostgreSQL + PostGIS.

Provides:
- SQLAlchemy engine with connection pooling
- Session management with context manager support
- GeoAlchemy2 integration for spatial types
- Connection health checking
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Global engine instance (initialized on first use)
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def create_database_engine(database_url: str, pool_size: int = 5, max_overflow: int = 10) -> Engine:
    """
    Create SQLAlchemy engine with connection pooling.

    Args:
        database_url: PostgreSQL connection string (postgresql://user:pass@host:port/dbname)
        pool_size: Number of connections to maintain in the pool
        max_overflow: Maximum overflow connections beyond pool_size

    Returns:
        SQLAlchemy Engine instance
    """
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections after 1 hour
        echo=False,          # Set to True for SQL query logging (dev only)
        future=True,         # Use SQLAlchemy 2.0 style
    )

    # Add event listener to verify PostGIS availability
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Verify PostGIS is available on new connections."""
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("SELECT PostGIS_Version();")
            version = cursor.fetchone()[0]
            logger.debug(f"PostGIS version: {version}")
        except Exception as e:
            logger.error(f"PostGIS not available: {e}")
            raise
        finally:
            cursor.close()

    logger.info(f"Created database engine with pool_size={pool_size}, max_overflow={max_overflow}")
    return engine


def init_db(database_url: str, pool_size: int = 5, max_overflow: int = 10) -> None:
    """
    Initialize the global database engine and session factory.

    This should be called once at application startup.

    Args:
        database_url: PostgreSQL connection string
        pool_size: Number of connections to maintain in the pool
        max_overflow: Maximum overflow connections beyond pool_size
    """
    global _engine, _SessionLocal

    if _engine is not None:
        logger.warning("Database engine already initialized. Closing existing connections.")
        close_db()

    _engine = create_database_engine(database_url, pool_size, max_overflow)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

    # Test connection
    try:
        with _engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1, "Database connection test failed"
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


def get_db_engine() -> Engine:
    """
    Get the global database engine.

    Returns:
        SQLAlchemy Engine instance

    Raises:
        RuntimeError: If database has not been initialized
    """
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_db_session() -> Session:
    """
    Get a new database session.

    Returns:
        SQLAlchemy Session instance

    Raises:
        RuntimeError: If database has not been initialized

    Example:
        ```python
        session = get_db_session()
        try:
            result = session.execute(text("SELECT * FROM intersections"))
            # ... process result ...
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
        ```
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic cleanup.

    Yields:
        SQLAlchemy Session instance

    Example:
        ```python
        with db_session() as session:
            result = session.execute(text("SELECT * FROM intersections"))
            # ... process result ...
            # session.commit() is called automatically if no exception
        ```
    """
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_health() -> dict:
    """
    Check database connection health and return status.

    Returns:
        Dictionary with health check results:
        {
            "status": "healthy" | "unhealthy",
            "database": "trafficsafety",
            "postgis_version": "3.3 USE_GEOS=1 USE_PROJ=1 USE_STATS=1",
            "connection_pool": {
                "size": 5,
                "checked_in": 4,
                "checked_out": 1,
                "overflow": 0
            },
            "error": None | "Error message"
        }
    """
    if _engine is None:
        return {
            "status": "unhealthy",
            "error": "Database not initialized"
        }

    try:
        with _engine.connect() as conn:
            # Check basic connectivity
            conn.execute(text("SELECT 1"))

            # Get PostGIS version
            postgis_version = conn.execute(text("SELECT PostGIS_Version()")).scalar()

            # Get current database name
            database_name = conn.execute(text("SELECT current_database()")).scalar()

            # Get connection pool stats
            pool = _engine.pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

            return {
                "status": "healthy",
                "database": database_name,
                "postgis_version": postgis_version,
                "connection_pool": pool_stats,
                "error": None
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def close_db() -> None:
    """
    Close all database connections and dispose of the engine.

    This should be called at application shutdown.
    """
    global _engine, _SessionLocal

    if _engine is not None:
        _engine.dispose()
        logger.info("Database connections closed")
        _engine = None
        _SessionLocal = None


def execute_raw_sql(sql: str, params: Optional[dict] = None) -> list[dict]:
    """
    Execute raw SQL query and return results as list of dictionaries.

    Args:
        sql: SQL query string
        params: Optional dictionary of query parameters

    Returns:
        List of dictionaries (one per row)

    Example:
        ```python
        results = execute_raw_sql(
            "SELECT * FROM intersections WHERE id = :id",
            params={"id": 0}
        )
        ```
    """
    with db_session() as session:
        result = session.execute(text(sql), params or {})

        # Convert to list of dictionaries
        columns = result.keys()
        rows = [dict(zip(columns, row)) for row in result.fetchall()]

        return rows


# FastAPI dependency for injecting database sessions
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage:
        ```python
        from fastapi import Depends

        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            result = db.execute(text("SELECT * FROM items"))
            return result.fetchall()
        ```
    """
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
