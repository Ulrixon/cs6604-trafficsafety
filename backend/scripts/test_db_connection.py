"""
Quick test script to verify PostgreSQL connection and query safety indices.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.db.connection import db_session, init_db
from app.core.config import settings
from sqlalchemy import text

def test_connection():
    """Test PostgreSQL connection and query safety indices."""

    print("\n" + "="*80)
    print("PostgreSQL Connection Test")
    print("="*80 + "\n")

    # Initialize database connection
    # Replace 'db:5432' with 'localhost:5433' for running outside Docker
    database_url = settings.DATABASE_URL.replace("@db:5432", "@localhost:5433")
    print(f"Connecting to: {database_url.split('@')[1]}")  # Don't show password
    init_db(database_url, settings.DB_POOL_SIZE, settings.DB_MAX_OVERFLOW)

    try:
        with db_session() as session:
            # Test basic connection
            result = session.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"OK Connected to PostgreSQL")
            print(f"   Version: {version[:50]}...\n")

            # Check available tables
            result = session.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"OK Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")

            # Check safety indices count
            print("\n" + "-"*80)
            print("Safety Indices Data")
            print("-"*80 + "\n")

            result = session.execute(text("""
                SELECT COUNT(*) as total,
                       MIN(timestamp) as earliest,
                       MAX(timestamp) as latest,
                       COUNT(DISTINCT intersection_id) as intersections
                FROM safety_indices_realtime
            """))
            row = result.fetchone()

            if row[0] > 0:
                print(f"OK Total safety index records: {row[0]:,}")
                print(f"   Date range: {row[1]} to {row[2]}")
                print(f"   Unique intersections: {row[3]}")

                # Sample data
                print("\n   Sample records (latest 5):")
                result = session.execute(text("""
                    SELECT timestamp, intersection_id, combined_index, vru_index, vehicle_index
                    FROM safety_indices_realtime
                    ORDER BY timestamp DESC
                    LIMIT 5
                """))

                for row in result.fetchall():
                    print(f"     {row[0]} | Int:{row[1]} | Combined:{row[2]:.1f} | VRU:{row[3]:.1f} | Vehicle:{row[4]:.1f}")
            else:
                print("WARNING: No safety index records found in database")

            print("\n" + "="*80)
            print("Test Complete - Database connection successful!")
            print("="*80 + "\n")

    except Exception as e:
        print(f"\nERROR: Database connection failed")
        print(f"       {str(e)}\n")
        return False

    return True

if __name__ == "__main__":
    test_connection()
