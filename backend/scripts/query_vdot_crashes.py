"""
Query VDOT crashes from GCP PostgreSQL database

This script loads crash data from the vdot_crashes table in the GCP database
for use in crash correlation analysis.
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import psycopg2
from typing import Optional

# GCP Database connection details
DB_HOST = "34.140.49.230"
DB_PORT = 5432
DB_NAME = "vtsi"
DB_USER = "jason"
DB_PASSWORD = "*9ZS^l(HGq].BA]6"


def load_vdot_crashes(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    locality: Optional[str] = None,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """
    Load crash data from VDOT crashes table in GCP PostgreSQL.

    Args:
        start_date: Start date for crash data
        end_date: End date for crash data
        locality: Filter by locality name (e.g., 'Fairfax', 'Arlington')
        limit: Maximum number of records to return

    Returns:
        DataFrame with crash records
    """

    print(f"\n{'='*80}")
    print("Loading VDOT Crash Data from GCP PostgreSQL")
    print(f"{'='*80}\n")

    try:
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=10
        )

        print(f"OK Connected to GCP database: {DB_NAME}")

        # Build query
        where_clauses = []
        params = {}

        if start_date:
            where_clauses.append("crash_date >= %(start_date)s")
            params['start_date'] = start_date.date()

        if end_date:
            where_clauses.append("crash_date <= %(end_date)s")
            params['end_date'] = end_date.date()

        if locality:
            where_clauses.append("locality = %(locality)s")
            params['locality'] = locality

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT
                objectid,
                document_nbr,
                crash_date,
                crash_time,
                locality,
                vdot_district,
                longitude,
                latitude,
                severity,
                total_vehicles,
                total_pedestrians,
                total_bicyclists,
                light_condition,
                weather_condition,
                road_surface
            FROM vdot_crashes
            WHERE {where_clause}
            ORDER BY crash_date DESC, crash_time DESC
            {"LIMIT " + str(limit) if limit else ""}
        """

        print(f"Executing query...")
        print(f"  Filters: {where_clauses if where_clauses else 'None'}")

        # Execute query
        df = pd.read_sql_query(query, conn, params=params)

        conn.close()

        print(f"\nOK Loaded {len(df):,} crash records")

        if len(df) > 0:
            print(f"  Date range: {df['crash_date'].min()} to {df['crash_date'].max()}")
            print(f"  Localities: {df['locality'].nunique()} unique")
            print(f"  Severity breakdown:")
            for severity, count in df['severity'].value_counts().items():
                print(f"    - {severity}: {count:,}")

        return df

    except Exception as e:
        print(f"\nERROR: Failed to load crash data")
        print(f"       {str(e)}")
        return pd.DataFrame()


def analyze_crash_data(df: pd.DataFrame):
    """Provide summary analysis of crash data."""

    if df.empty:
        print("\nNo crash data to analyze")
        return

    print(f"\n{'='*80}")
    print("Crash Data Analysis")
    print(f"{'='*80}\n")

    # Time distribution
    df['crash_datetime'] = pd.to_datetime(df['crash_date'].astype(str) + ' ' + df['crash_time'].astype(str))
    df['hour'] = df['crash_datetime'].dt.hour
    df['day_of_week'] = df['crash_datetime'].dt.dayofweek

    print("Time Distribution:")
    print(f"  Peak hour: {df['hour'].mode().values[0] if len(df) > 0 else 'N/A'}:00")
    print(f"  Peak day: {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][df['day_of_week'].mode().values[0]] if len(df) > 0 else 'N/A'}")

    # VRU involvement
    vru_crashes = df[(df['total_pedestrians'] > 0) | (df['total_bicyclists'] > 0)]
    print(f"\nVRU Involvement:")
    print(f"  Total VRU crashes: {len(vru_crashes):,} ({len(vru_crashes)/len(df)*100:.1f}%)")
    print(f"  Pedestrian crashes: {len(df[df['total_pedestrians'] > 0]):,}")
    print(f"  Bicyclist crashes: {len(df[df['total_bicyclists'] > 0]):,}")

    # Weather conditions
    if 'weather_condition' in df.columns and df['weather_condition'].notna().any():
        print(f"\nWeather Conditions:")
        for weather, count in df['weather_condition'].value_counts().head(5).items():
            print(f"  {weather}: {count:,} ({count/len(df)*100:.1f}%)")

    # Top localities
    print(f"\nTop 5 Localities:")
    for locality, count in df['locality'].value_counts().head(5).items():
        print(f"  {locality}: {count:,} crashes")


if __name__ == "__main__":
    # Example: Load crashes from 2024
    crashes = load_vdot_crashes(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        limit=10000  # Limit for testing
    )

    if not crashes.empty:
        analyze_crash_data(crashes)
        print(f"\n{'='*80}\n")
