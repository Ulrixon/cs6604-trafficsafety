"""Check vdot_crashes table schema"""

import psycopg2

DB_HOST = "34.140.49.230"
DB_PORT = 5432
DB_NAME = "vtsi"
DB_USER = "jason"
DB_PASSWORD = "*9ZS^l(HGq].BA]6"

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

# Get column names and types
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'vdot_crashes'
    ORDER BY ordinal_position
""")

print("\nvdot_crashes table schema:")
print("-" * 60)
for col_name, col_type in cur.fetchall():
    print(f"{col_name:30s} {col_type}")

# Get sample row
cur.execute("SELECT * FROM vdot_crashes LIMIT 1")
row = cur.fetchone()
columns = [desc[0] for desc in cur.description]

print("\n\nSample row (first 10 columns):")
print("-" * 60)
for i, (col, val) in enumerate(zip(columns[:10], row[:10] if row else [])):
    print(f"{col:30s} {val}")

cur.close()
conn.close()
