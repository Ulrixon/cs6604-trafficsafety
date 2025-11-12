"""
Trino database client for querying smart-cities data.

Handles OAuth2 authentication and provides helper functions for querying
BSM, PSM, safety-event, and count data from the Trino/Iceberg database.
"""

from typing import List, Tuple, Optional
import os
import pandas as pd
from trino import dbapi
from trino.auth import OAuth2Authentication, BasicAuthentication, JWTAuthentication
from ..core.config import settings


class TrinoClient:
    """Singleton Trino client for reusing connections"""

    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_auth(self):
        """
        Get authentication method based on environment variables.

        Priority:
        1. JWT token (if TRINO_JWT_TOKEN set)
        2. Basic auth (if TRINO_USERNAME and TRINO_PASSWORD set)
        3. OAuth2 (default)
        """
        # Option 1: JWT Authentication
        jwt_token = os.getenv('TRINO_JWT_TOKEN')
        if jwt_token:
            print("Using JWT authentication for Trino")
            return JWTAuthentication(jwt_token)

        # Option 2: Basic Authentication
        username = os.getenv('TRINO_USERNAME')
        password = os.getenv('TRINO_PASSWORD')
        if username and password:
            print("Using Basic authentication for Trino")
            return BasicAuthentication(username, password)

        # Option 3: OAuth2 (default)
        print("Using OAuth2 authentication for Trino (browser required)")
        return OAuth2Authentication()

    def get_connection(self):
        """Get or create Trino connection"""
        if self._connection is None:
            self._connection = dbapi.connect(
                host=settings.TRINO_HOST,
                port=settings.TRINO_PORT,
                http_scheme=settings.TRINO_HTTP_SCHEME,
                auth=self._get_auth(),
                catalog=settings.TRINO_CATALOG,
            )
        return self._connection
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """
        Execute a query and return results as a pandas DataFrame.
        
        Args:
            query: SQL query string
            
        Returns:
            DataFrame with query results
        """
        conn = self.get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            results = cur.fetchall()
            return pd.DataFrame(results, columns=columns)
        except Exception as e:
            raise RuntimeError(f"Trino query failed: {e}") from e


# Global client instance
trino_client = TrinoClient()


def build_timestamp_filter(
    timestamp_col: str,
    start_timestamp_micros: Optional[int] = None,
    end_timestamp_micros: Optional[int] = None
) -> str:
    """
    Build WHERE clause for timestamp filtering.
    
    Args:
        timestamp_col: Name of timestamp column (publish_timestamp or time_at_site)
        start_timestamp_micros: Start time in microseconds since epoch
        end_timestamp_micros: End time in microseconds since epoch
        
    Returns:
        WHERE clause string
    """
    conditions = [
        f"{timestamp_col} > 0",
        f"{timestamp_col} < 9999999999999999"  # Filter corrupted timestamps
    ]
    
    if start_timestamp_micros:
        conditions.append(f"{timestamp_col} >= {start_timestamp_micros}")
    
    if end_timestamp_micros:
        conditions.append(f"{timestamp_col} <= {end_timestamp_micros}")
    
    return " AND ".join(conditions)
