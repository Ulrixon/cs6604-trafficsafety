"""
Test connection to GCP PostgreSQL database
"""

import sys
from pathlib import Path
import psycopg2

# Database connection details
DB_HOST = "34.140.49.230"
DB_PORT = 5432
DB_NAME = "vtsi"
DB_USER = "jason"
DB_PASSWORD = "*9ZS^l(HGq].BA]6"

def test_gcp_connection():
    """Test connection to GCP PostgreSQL database."""

    print("\n" + "="*80)
    print("GCP PostgreSQL Connection Test")
    print("="*80 + "\n")

    print(f"Connecting to: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"User: {DB_USER}\n")

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

        print("OK Connected to GCP PostgreSQL")

        # Create cursor
        cur = conn.cursor()

        # Get PostgreSQL version
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"   Version: {version[:50]}...\n")

        # List tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]

        print(f"OK Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table}")

        # Check for crash-related tables
        crash_tables = [t for t in tables if 'crash' in t.lower() or 'accident' in t.lower()
                       or 'incident' in t.lower() or 'safety' in t.lower()]

        if crash_tables:
            print(f"\n" + "-"*80)
            print(f"Crash/Safety Related Tables:")
            print("-"*80 + "\n")

            for table in crash_tables:
                # Quote table names with hyphens
                quoted_table = f'"{table}"' if '-' in table else table
                cur.execute(f"SELECT COUNT(*) FROM {quoted_table}")
                count = cur.fetchone()[0]
                print(f"   {table}: {count:,} records")

                # Get sample data
                if count > 0:
                    cur.execute(f"SELECT * FROM {quoted_table} LIMIT 3")
                    columns = [desc[0] for desc in cur.description]
                    print(f"      Columns: {', '.join(columns[:10])}")

        cur.close()
        conn.close()

        print("\n" + "="*80)
        print("Test Complete - GCP Database connection successful!")
        print("="*80 + "\n")

        return True

    except Exception as e:
        print(f"\nERROR: Database connection failed")
        print(f"       {str(e)}\n")
        return False

if __name__ == "__main__":
    test_gcp_connection()
