from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from ..services.db_client import get_db_client
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/tables", response_model=List[str])
async def get_tables():
    """
    Get a list of all tables in the public schema.
    """
    try:
        client = get_db_client()
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE';
        """
        results = client.execute_query(query)
        return [row['table_name'] for row in results]
    except Exception as e:
        logger.error(f"Error fetching tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schema/{table_name}", response_model=List[Dict[str, str]])
async def get_table_schema(table_name: str):
    """
    Get the schema (columns and types) for a specific table.
    """
    try:
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
    filter_val: Optional[str] = None
):
    """
    Get data from a specific table with pagination and optional simple filtering.
    """
    try:
        client = get_db_client()
        
        # Sanitize table name (basic check)
        # Ideally, check against a whitelist of existing tables
        tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        valid_tables = [t['table_name'] for t in client.execute_query(tables_query)]
        
        if table_name not in valid_tables:
             raise HTTPException(status_code=404, detail=f"Table {table_name} not found")

        # Handle table names with hyphens by quoting them
        quoted_table_name = f'"{table_name}"'
        
        if filter_col and filter_val:
            # Basic SQL injection prevention for column name: check if it exists in the table
            cols_query = "SELECT column_name FROM information_schema.columns WHERE table_name = %s"
            valid_cols = [c['column_name'] for c in client.execute_query(cols_query, (table_name,))]
            
            if filter_col not in valid_cols:
                raise HTTPException(status_code=400, detail=f"Invalid filter column: {filter_col}")
                
            query = f"SELECT * FROM {quoted_table_name} WHERE \"{filter_col}\" = %s LIMIT %s OFFSET %s"
            results = client.execute_query(query, (filter_val, limit, offset))
        else:
            query = f"SELECT * FROM {quoted_table_name} LIMIT %s OFFSET %s"
            results = client.execute_query(query, (limit, offset))
        
        # Handle datetime serialization if necessary (FastAPI usually handles this, but just in case)
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching data for {table_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
