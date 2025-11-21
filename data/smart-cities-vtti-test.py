from trino import dbapi
from trino.auth import OAuth2Authentication

conn = dbapi.connect(
    host="smart-cities-trino.pre-prod.cloud.vtti.vt.edu",
    port=443,
    http_scheme="https",
    auth=OAuth2Authentication(),   # <-- this is the right one
    catalog="smartcities_iceberg",  # optional default
    # schema="...",                # optional default
)
cur = conn.cursor()
cur.execute("SHOW SCHEMAS")
print(cur.fetchall())