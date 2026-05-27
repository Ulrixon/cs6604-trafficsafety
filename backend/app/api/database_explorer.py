from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from psycopg2 import sql
from ..core.config import settings
from ..core.redis_cache import response_cache
from ..services.db_client import get_db_client
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def _validate_identifier(value: str, allowed_values: set[str], label: str) -> str:
    """
    Validate an SQL identifier against database-discovered names.

    SQL parameters cannot bind table or column names. These endpoints therefore
    discover the allowed identifiers first and compose the final statement with
    psycopg2.sql.Identifier after an exact allowlist check.
    """
    if value not in allowed_values:
        raise HTTPException(status_code=404 if label == "table" else 400, detail=f"Invalid {label}: {value}")
    return value


@router.get("/tables", response_model=List[str])
async def get_tables():
    """
    Get a list of all tables in the public schema.
    """
    try:
        cache_key = response_cache.make_key("db-explorer-tables")
        hit, cached = response_cache.get(cache_key, settings.DB_EXPLORER_CACHE_TTL_SECONDS)
        if hit:
            return cached

        client = get_db_client()
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE';
        """
        results = client.execute_query(query)
        tables = [row["table_name"] for row in results]
        response_cache.set(
            cache_key,
            tables,
            settings.DB_EXPLORER_CACHE_TTL_SECONDS,
            cache_empty=True,
        )
        return tables
    except Exception as e:
        logger.error(f"Error fetching tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/{table_name}", response_model=List[Dict[str, str]])
async def get_table_schema(table_name: str):
    """
    Get the schema (columns and types) for a specific table.
    """
    try:
        cache_key = response_cache.make_key("db-explorer-schema", table_name)
        hit, cached = response_cache.get(cache_key, settings.DB_EXPLORER_CACHE_TTL_SECONDS)
        if hit:
            return cached

        client = get_db_client()
        # Validate table name to prevent SQL injection (basic check)
        # In a real app, we should verify against the list of known tables

        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position;
        """
        results = client.execute_query(query, (table_name,))

        if not results:
            raise HTTPException(status_code=404, detail=f"Table {table_name} not found")

        response_cache.set(
            cache_key,
            results,
            settings.DB_EXPLORER_CACHE_TTL_SECONDS,
            cache_empty=True,
        )
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching schema for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/{table_name}")
async def get_table_data(
    table_name: str,
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    filter_col: Optional[str] = None,
    filter_val: Optional[str] = None,
):
    """
    Get data from a specific table with pagination and optional simple filtering.
    """
    try:
        cache_key = response_cache.make_key(
            "db-explorer-data",
            table_name,
            limit,
            offset,
            filter_col,
            filter_val,
        )
        hit, cached = response_cache.get(cache_key, settings.DB_EXPLORER_CACHE_TTL_SECONDS)
        if hit:
            return cached

        client = get_db_client()

        # Sanitize table name (basic check)
        # Ideally, check against a whitelist of existing tables
        tables_query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type = %s
        """
        valid_tables = [
            t["table_name"]
            for t in client.execute_query(tables_query, ("public", "BASE TABLE"))
        ]
        safe_table_name = _validate_identifier(table_name, set(valid_tables), "table")

        if filter_col and filter_val:
            # Basic SQL injection prevention for column name: check if it exists in the table
            cols_query = "SELECT column_name FROM information_schema.columns WHERE table_name = %s"
            valid_cols = [
                c["column_name"]
                for c in client.execute_query(cols_query, (table_name,))
            ]

            safe_filter_col = _validate_identifier(filter_col, set(valid_cols), "column")

            query = sql.SQL("SELECT * FROM {table} WHERE {column} = %s LIMIT %s OFFSET %s").format(
                table=sql.Identifier(safe_table_name),
                column=sql.Identifier(safe_filter_col),
            )
            results = client.execute_query(query, (filter_val, limit, offset))
        else:
            query = sql.SQL("SELECT * FROM {table} LIMIT %s OFFSET %s").format(
                table=sql.Identifier(safe_table_name),
            )
            results = client.execute_query(query, (limit, offset))

        # Debug logging
        if results:
            logger.info(f"First row type: {type(results[0])}")
            # logger.info(f"First row content: {results[0]}") # Commented out to avoid log spam

            # Process results to handle non-serializable types (like bytea/memoryview)
            processed_results = []
            for row in results:
                processed_row = dict(row)
                for key, value in processed_row.items():
                    # Handle bytes/memoryview (Postgres bytea)
                    if isinstance(value, (bytes, memoryview)):
                        processed_row[key] = "<binary data>"
                processed_results.append(processed_row)

            results = processed_results

        # Handle datetime serialization if necessary (FastAPI usually handles this, but just in case)
        response_cache.set(
            cache_key,
            results,
            settings.DB_EXPLORER_CACHE_TTL_SECONDS,
            cache_empty=True,
        )
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching data for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
