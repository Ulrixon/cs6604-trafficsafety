# PostgreSQL + PostGIS Migration - Technical Design

**Document Version:** 1.0
**Last Updated:** 2025-11-20
**Status:** Planning
**Reviewers:** Traffic Safety Index Team

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Storage Architecture](#2-storage-architecture)
3. [Database Schema](#3-database-schema)
4. [Data Flow](#4-data-flow)
5. [API Design](#5-api-design)
6. [Migration Strategy](#6-migration-strategy)
7. [Deployment Architecture](#7-deployment-architecture)
8. [Performance Optimization](#8-performance-optimization)
9. [Monitoring and Observability](#9-monitoring-and-observability)
10. [Security](#10-security)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         VCC API (External)                       │
│              (BSM, PSM, MapData, SPAT messages)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data Collector Service                       │
│                  (Python, runs every 60 seconds)                 │
│                                                                   │
│  ┌───────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │ VCC Client    │→ │ Feature        │→ │ Safety Index     │   │
│  │               │  │ Extractor      │  │ Computer         │   │
│  └───────────────┘  └────────────────┘  └──────────────────┘   │
└─────────────┬──────────────────────┬────────────────────────────┘
              │                      │
              ▼                      ▼
┌──────────────────────┐   ┌──────────────────────────────────┐
│  GCP Cloud Storage   │   │     PostgreSQL + PostGIS         │
│   (Parquet Files)    │   │      (Operational DB)            │
│                      │   │                                  │
│  Raw Archives:       │   │  Tables:                         │
│  - BSM messages      │   │  - intersections                 │
│  - PSM messages      │   │  - safety_indices_realtime       │
│  - MapData           │   │  - safety_indices_hourly         │
│  - SPAT (future)     │   │  - safety_indices_daily          │
│                      │   │  - normalization_constants       │
│  Retention:          │   │                                  │
│  - Lifecycle: 1 year │   │  Features:                       │
│  - Nearline storage  │   │  - PostGIS spatial indexes       │
│  - Compression       │   │  - Time partitioning             │
│                      │   │  - Automated retention           │
└──────────────────────┘   └─────────────┬────────────────────┘
                                         │
                                         ▼
                           ┌──────────────────────────────────┐
                           │       FastAPI Backend             │
                           │                                   │
                           │  Services:                        │
                           │  - Intersection Service           │
                           │  - History Service                │
                           │  - Spatial Service (new)          │
                           │                                   │
                           │  Routers:                         │
                           │  - /api/v1/safety/index/          │
                           │  - /api/v1/safety/history/        │
                           │  - /api/v1/intersections/*        │
                           └─────────────┬─────────────────────┘
                                         │
                                         ▼
                           ┌──────────────────────────────────┐
                           │      Streamlit Frontend           │
                           │   (No changes required)           │
                           └───────────────────────────────────┘
```

### 1.2 Component Responsibilities

**Data Collector:**
- Fetch data from VCC API every 60 seconds
- Dual-write: Parquet (raw) + PostgreSQL (processed)
- Compute safety indices
- Handle errors gracefully (don't block either write)

**GCP Cloud Storage:**
- Immutable raw data archive
- Compliance and audit trail
- Source for reprocessing
- Cost-effective long-term storage

**PostgreSQL:**
- Fast operational queries
- ACID transactions
- Spatial indexing (PostGIS)
- Automated aggregation and retention

**FastAPI:**
- Query routing (DB for recent, Parquet for old data)
- Spatial query endpoints
- Backward-compatible responses

---

## 2. Storage Architecture

### 2.1 GCP Cloud Storage Design

**Bucket Structure:**
```
gs://trafficsafety-prod-parquet/
├── raw/
│   ├── bsm/
│   │   ├── 2025/
│   │   │   ├── 11/
│   │   │   │   ├── 20/
│   │   │   │   │   ├── bsm_2025-11-20_000000.parquet
│   │   │   │   │   ├── bsm_2025-11-20_000100.parquet
│   │   │   │   │   └── ...
│   ├── psm/
│   │   ├── 2025/11/20/...
│   ├── mapdata/
│   │   ├── 2025/11/20/...
│   └── spat/  (future)
│       └── 2025/11/20/...
└── processed/
    ├── features/
    │   ├── 2025/11/20/features_2025-11-20.parquet
    └── indices/
        └── 2025/11/20/indices_2025-11-20.parquet
```

**Bucket Configuration:**
- **Location:** us-east4 (closest to VCC servers)
- **Storage Class:**
  - Standard for last 30 days
  - Nearline for 31-365 days
  - Coldline for >365 days
  - Auto-transition via lifecycle policies
- **Versioning:** Enabled for data recovery
- **Access Control:** Service account with minimal permissions
- **Encryption:** Google-managed keys (default)

**Lifecycle Policy:**
```yaml
lifecycle:
  rules:
    - action:
        type: SetStorageClass
        storageClass: NEARLINE
      condition:
        age: 30
        matchesPrefix: ["raw/"]
    - action:
        type: SetStorageClass
        storageClass: COLDLINE
      condition:
        age: 365
        matchesPrefix: ["raw/"]
    - action:
        type: Delete
      condition:
        age: 730  # 2 years
        matchesPrefix: ["processed/"]
```

**Cost Estimation (per month):**
- Storage: ~$20/month (100GB Standard, 200GB Nearline)
- Operations: ~$5/month (write-heavy)
- Network egress: ~$10/month (reprocessing jobs)
- **Total: ~$35/month**

### 2.2 PostgreSQL Storage Design

**Database:** PostgreSQL 15 with PostGIS 3.3

**Storage Estimates:**

| Table | Rows/Day | Row Size | Daily Size | 90-Day Size | Annual Size |
|-------|----------|----------|------------|-------------|-------------|
| safety_indices_realtime | 1,440 × N | 200 bytes | 280KB × N | 25MB × N | Rotated |
| safety_indices_hourly | 24 × N | 150 bytes | 3.6KB × N | 324KB × N | 1.3MB × N |
| safety_indices_daily | 1 × N | 200 bytes | 200B × N | 18KB × N | 73KB × N |
| intersections | N | 300 bytes | - | - | 300B × N |

**Where N = number of intersections**

For **N=10 intersections:**
- Realtime (48h): 10 × 1,440 × 2 × 200B = 5.7MB
- Hourly (90d): 10 × 24 × 90 × 150B = 3.2MB
- Daily (1yr): 10 × 365 × 200B = 730KB
- **Total: ~10MB** (tiny!)

For **N=100 intersections:**
- Total: ~100MB (still small)

**Partitioning Strategy:**

```sql
-- Realtime table partitioned by day
CREATE TABLE safety_indices_realtime (
    -- columns
) PARTITION BY RANGE (timestamp);

-- Create partitions for next 7 days
CREATE TABLE safety_indices_realtime_20251120
    PARTITION OF safety_indices_realtime
    FOR VALUES FROM ('2025-11-20') TO ('2025-11-21');

-- Automated partition management via cron job
```

---

## 3. Database Schema

### 3.1 DDL Statements

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;  -- Optional but recommended

-- Intersections table
CREATE TABLE intersections (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    geometry GEOMETRY(POINT, 4326),  -- WGS84 spatial reference
    lane_count INTEGER,
    revision INTEGER,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Spatial index on geometry
CREATE INDEX idx_intersections_geometry ON intersections USING GIST (geometry);

-- Trigger to auto-update geometry from lat/lon
CREATE OR REPLACE FUNCTION update_intersection_geometry()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geometry = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_intersection_geometry
    BEFORE INSERT OR UPDATE ON intersections
    FOR EACH ROW
    EXECUTE FUNCTION update_intersection_geometry();

-- Safety indices (real-time, partitioned)
CREATE TABLE safety_indices_realtime (
    id BIGSERIAL,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    combined_index DOUBLE PRECISION NOT NULL CHECK (combined_index BETWEEN 0 AND 100),
    combined_index_eb DOUBLE PRECISION CHECK (combined_index_eb BETWEEN 0 AND 100),
    vru_index DOUBLE PRECISION CHECK (vru_index BETWEEN 0 AND 100),
    vru_index_eb DOUBLE PRECISION CHECK (vru_index_eb BETWEEN 0 AND 100),
    vehicle_index DOUBLE PRECISION CHECK (vehicle_index BETWEEN 0 AND 100),
    vehicle_index_eb DOUBLE PRECISION CHECK (vehicle_index_eb BETWEEN 0 AND 100),
    traffic_volume INTEGER NOT NULL CHECK (traffic_volume >= 0),
    vru_count INTEGER NOT NULL DEFAULT 0 CHECK (vru_count >= 0),
    vehicle_event_count INTEGER NOT NULL DEFAULT 0 CHECK (vehicle_event_count >= 0),
    vru_event_count INTEGER NOT NULL DEFAULT 0 CHECK (vru_event_count >= 0),
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Indexes
CREATE INDEX idx_sir_intersection_time ON safety_indices_realtime (intersection_id, timestamp DESC);
CREATE INDEX idx_sir_timestamp ON safety_indices_realtime (timestamp DESC);
CREATE INDEX idx_sir_combined_eb ON safety_indices_realtime (combined_index_eb);

-- Hourly aggregates
CREATE TABLE safety_indices_hourly (
    id BIGSERIAL PRIMARY KEY,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    hour_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    avg_si DOUBLE PRECISION NOT NULL,
    min_si DOUBLE PRECISION NOT NULL,
    max_si DOUBLE PRECISION NOT NULL,
    std_si DOUBLE PRECISION,
    total_volume BIGINT NOT NULL,
    avg_volume DOUBLE PRECISION NOT NULL,
    high_risk_minutes INTEGER NOT NULL DEFAULT 0,
    data_quality_score DOUBLE PRECISION CHECK (data_quality_score BETWEEN 0 AND 1),
    UNIQUE (intersection_id, hour_timestamp)
);

CREATE INDEX idx_sih_intersection_hour ON safety_indices_hourly (intersection_id, hour_timestamp DESC);
CREATE INDEX idx_sih_hour ON safety_indices_hourly (hour_timestamp DESC);

-- Daily aggregates
CREATE TABLE safety_indices_daily (
    id BIGSERIAL PRIMARY KEY,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    avg_si DOUBLE PRECISION NOT NULL,
    min_si DOUBLE PRECISION NOT NULL,
    max_si DOUBLE PRECISION NOT NULL,
    std_si DOUBLE PRECISION,
    total_volume BIGINT NOT NULL,
    avg_volume DOUBLE PRECISION NOT NULL,
    high_risk_hours INTEGER NOT NULL DEFAULT 0,
    peak_hour INTEGER CHECK (peak_hour BETWEEN 0 AND 23),
    peak_si DOUBLE PRECISION,
    UNIQUE (intersection_id, date)
);

CREATE INDEX idx_sid_intersection_date ON safety_indices_daily (intersection_id, date DESC);
CREATE INDEX idx_sid_date ON safety_indices_daily (date DESC);

-- Normalization constants
CREATE TABLE normalization_constants (
    id SERIAL PRIMARY KEY,
    computed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    constants JSONB NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_until TIMESTAMP WITH TIME ZONE,
    CHECK (valid_until IS NULL OR valid_until > valid_from)
);

CREATE INDEX idx_nc_computed ON normalization_constants (computed_at DESC);
CREATE INDEX idx_nc_valid ON normalization_constants (valid_from, valid_until);

-- Data quality log
CREATE TABLE data_quality_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    intersection_id INTEGER REFERENCES intersections(id),
    issue_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    message TEXT NOT NULL,
    metadata JSONB
);

CREATE INDEX idx_dql_timestamp ON data_quality_log (timestamp DESC);
CREATE INDEX idx_dql_intersection ON data_quality_log (intersection_id, timestamp DESC);
```

### 3.2 Partition Management

```sql
-- Function to create next day's partition
CREATE OR REPLACE FUNCTION create_realtime_partition(partition_date DATE)
RETURNS void AS $$
DECLARE
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    partition_name := 'safety_indices_realtime_' || TO_CHAR(partition_date, 'YYYYMMDD');
    start_date := partition_date::TEXT;
    end_date := (partition_date + INTERVAL '1 day')::TEXT;

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF safety_indices_realtime
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;

-- Function to drop old partitions (>48 hours)
CREATE OR REPLACE FUNCTION drop_old_realtime_partitions()
RETURNS void AS $$
DECLARE
    partition_name TEXT;
    cutoff_date DATE := CURRENT_DATE - INTERVAL '2 days';
BEGIN
    FOR partition_name IN
        SELECT tablename FROM pg_tables
        WHERE tablename LIKE 'safety_indices_realtime_%'
        AND tablename < 'safety_indices_realtime_' || TO_CHAR(cutoff_date, 'YYYYMMDD')
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || partition_name;
        RAISE NOTICE 'Dropped partition: %', partition_name;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

---

## 4. Data Flow

### 4.1 Real-time Ingestion Flow

```
┌─────────────┐
│  VCC API    │  Every 60 seconds
└──────┬──────┘
       │ 1. Fetch BSM/PSM/MapData
       ▼
┌──────────────────────────────┐
│  Data Collector Container    │
│                               │
│  ┌────────────────────────┐  │
│  │ 1. Parse VCC Response  │  │
│  └──────────┬─────────────┘  │
│             │                 │
│  ┌──────────▼─────────────┐  │
│  │ 2. Save Raw → GCS      │  │ gs://trafficsafety-prod-parquet/raw/
│  │    (Parquet)           │──┼─────────────────────────────►
│  └──────────┬─────────────┘  │
│             │                 │
│  ┌──────────▼─────────────┐  │
│  │ 3. Extract Features    │  │
│  │    (1-min aggregation) │  │
│  └──────────┬─────────────┘  │
│             │                 │
│  ┌──────────▼─────────────┐  │
│  │ 4. Compute SI          │  │
│  │    (Combined, VRU,     │  │
│  │     Vehicle, EB-adj)   │  │
│  └──────────┬─────────────┘  │
│             │                 │
│  ┌──────────▼─────────────┐  │
│  │ 5. INSERT PostgreSQL   │  │
│  │    UPSERT on conflict  │──┼────────────┐
│  └────────────────────────┘  │            │
└──────────────────────────────┘            │
                                             ▼
                               ┌──────────────────────────────┐
                               │  PostgreSQL                   │
                               │                               │
                               │  safety_indices_realtime      │
                               │  (partitioned by day)         │
                               └───────────────────────────────┘
```

### 4.2 Aggregation Flow (Hourly Job)

```
        Every hour at :05
             │
             ▼
┌────────────────────────────────────┐
│  Aggregation Job (Cron/Airflow)    │
│                                    │
│  SELECT                            │
│    intersection_id,                │
│    date_trunc('hour', ts),         │
│    AVG(combined_index_eb),         │
│    MIN, MAX, STDDEV, ...           │
│  FROM safety_indices_realtime      │
│  WHERE ts BETWEEN prev_hour        │
│     AND current_hour               │
│  GROUP BY 1, 2                     │
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│  INSERT INTO                       │
│  safety_indices_hourly             │
│  (intersection_id, hour_timestamp, │
│   avg_si, min_si, max_si, ...)     │
└────────────────────────────────────┘
```

### 4.3 Query Flow (API Request)

```
Frontend Request:
GET /api/v1/safety/history/156?days=7

         │
         ▼
┌────────────────────────────────┐
│  FastAPI Backend               │
│  history_service.py            │
│                                │
│  Query Router Logic:           │
│  IF days <= 2:                 │
│    → Query realtime table      │
│  ELIF days <= 90:              │
│    → Query hourly table        │
│  ELSE:                         │
│    → Query daily table         │
└──────────┬─────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│  PostgreSQL                    │
│                                │
│  SELECT * FROM                 │
│  safety_indices_hourly         │
│  WHERE intersection_id = 156   │
│    AND hour_timestamp >= ...   │
│  ORDER BY hour_timestamp       │
└──────────┬─────────────────────┘
           │ Result: 168 rows (7 days × 24 hours)
           ▼
┌────────────────────────────────┐
│  Pydantic Model Transform      │
│  IntersectionHistory           │
└──────────┬─────────────────────┘
           │
           ▼
     JSON Response to Frontend
```

---

## 5. API Design

### 5.1 Modified Existing Endpoints

**GET /api/v1/safety/index/**
```python
# Before (Parquet):
def get_all():
    df = parquet_storage.load_latest_indices()
    return [IntersectionRead(**row) for row in df.to_dict('records')]

# After (PostgreSQL):
def get_all():
    """Get latest safety index for all intersections."""
    query = """
        SELECT DISTINCT ON (i.id)
            i.id as intersection_id,
            i.name as intersection_name,
            si.combined_index_eb as safety_index,
            si.traffic_volume,
            i.latitude,
            i.longitude
        FROM intersections i
        LEFT JOIN LATERAL (
            SELECT * FROM safety_indices_realtime
            WHERE intersection_id = i.id
            ORDER BY timestamp DESC
            LIMIT 1
        ) si ON true
        ORDER BY i.id, si.timestamp DESC NULLS LAST
    """
    with get_db() as conn:
        result = conn.execute(query)
        return [IntersectionRead(**row) for row in result.mappings()]
```

**GET /api/v1/safety/history/{id}**
```python
def get_intersection_history(
    intersection_id: str,
    start_date: date,
    end_date: date,
    aggregation: Optional[str] = None
) -> IntersectionHistory:
    """Smart query routing based on date range."""

    # Determine which table to query
    days = (end_date - start_date).days

    if days <= 2:
        # Query realtime table (1-minute data)
        table = "safety_indices_realtime"
        time_col = "timestamp"
    elif days <= 90:
        # Query hourly table
        table = "safety_indices_hourly"
        time_col = "hour_timestamp"
    else:
        # Query daily table
        table = "safety_indices_daily"
        time_col = "date"

    query = f"""
        SELECT * FROM {table}
        WHERE intersection_id = :int_id
          AND {time_col} >= :start
          AND {time_col} <= :end
        ORDER BY {time_col}
    """

    with get_db() as conn:
        result = conn.execute(query, {
            'int_id': float(intersection_id),
            'start': start_date,
            'end': end_date
        })
        # Transform to IntersectionHistory...
```

### 5.2 New Spatial Endpoints

```python
from fastapi import APIRouter, Query
from geoalchemy2.functions import ST_DWithin, ST_MakePoint

router = APIRouter(prefix="/api/v1/intersections", tags=["Intersections"])

@router.get("/nearby")
def get_nearby_intersections(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(5000, description="Radius in meters", ge=100, le=50000)
):
    """
    Find intersections within radius of a point.

    Example: GET /api/v1/intersections/nearby?lat=38.86&lon=-77.05&radius=5000
    """
    query = """
        SELECT
            id,
            name,
            latitude,
            longitude,
            ST_Distance(
                geometry,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) as distance_meters
        FROM intersections
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius
        )
        ORDER BY distance_meters
    """

    with get_db() as conn:
        result = conn.execute(query, {'lat': lat, 'lon': lon, 'radius': radius})
        return [dict(row) for row in result.mappings()]

@router.get("/route")
def get_intersections_along_route(
    waypoints: List[Tuple[float, float]] = Query(..., description="[(lat,lon),...]"),
    buffer: int = Query(500, description="Buffer in meters", ge=10, le=5000)
):
    """
    Find intersections along a route with buffer.

    Example: GET /api/v1/intersections/route?waypoints=[(38.86,-77.05),(38.87,-77.06)]&buffer=500
    """
    # Create LineString from waypoints
    linestring_wkt = f"LINESTRING({','.join([f'{lon} {lat}' for lat,lon in waypoints])})"

    query = """
        SELECT
            id,
            name,
            latitude,
            longitude,
            ST_Distance(
                geometry::geography,
                ST_GeomFromText(:route, 4326)::geography
            ) as distance_meters
        FROM intersections
        WHERE ST_DWithin(
            geometry::geography,
            ST_GeomFromText(:route, 4326)::geography,
            :buffer
        )
        ORDER BY distance_meters
    """

    with get_db() as conn:
        result = conn.execute(query, {'route': linestring_wkt, 'buffer': buffer})
        return [dict(row) for row in result.mappings()]
```

---

## 6. Migration Strategy

### 6.1 Phase-by-Phase Implementation

**Phase 1: Database Setup (Week 1)**
- Create PostgreSQL instance
- Install PostGIS extension
- Create schema (tables, indexes, partitions)
- Create database users and roles
- Set up GCP service account and bucket
- Configure GCS lifecycle policies

**Phase 2: Dual-Write Implementation (Week 2)**
- Modify data collector to write to GCS (replace local Parquet)
- Add PostgreSQL write path (parallel to GCS)
- Implement retry logic and error handling
- Monitor for 48 hours to ensure stability
- Validate row counts match

**Phase 3: Historical Backfill (Week 2-3)**
- Script to read existing Parquet files
- Bulk load into PostgreSQL using COPY
- Verify data integrity (row counts, statistics)
- Create hourly/daily aggregates from raw data

**Phase 4: API Migration (Week 3)**
- Create database service layer
- Implement query routing logic
- Add spatial query endpoints
- Run A/B tests (Parquet vs PostgreSQL responses)
- Gradual rollout with feature flags

**Phase 5: Batch Jobs (Week 4)**
- Implement hourly aggregation job
- Implement daily aggregation job
- Implement retention cleanup job
- Deploy to cron/Airflow
- Monitor job execution

**Phase 6: Cutover and Monitoring (Week 4)**
- Switch all API queries to PostgreSQL
- Disable Parquet query path (keep as fallback)
- Monitor performance and errors
- Tune indexes and queries as needed

### 6.2 Rollback Plan

If issues detected:
1. Feature flag to switch API back to Parquet queries
2. Stop dual-writes to PostgreSQL (Parquet continues)
3. Diagnose issue offline
4. No data loss (Parquet archives remain)

---

## 7. Deployment Architecture

### 7.1 Production Environment

```yaml
# docker-compose.yml additions

services:
  db:
    image: postgis/postgis:15-3.3
    environment:
      POSTGRES_DB: trafficsafety
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=en_US.UTF-8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/db/init:/docker-entrypoint-initdb.d  # Schema init scripts
    ports:
      - "5433:5432"  # External port
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d trafficsafety"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - trafficsafety-network

  # PgAdmin for database management (dev only)
  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@trafficsafety.local
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
    ports:
      - "5050:80"
    networks:
      - trafficsafety-network
    profiles:
      - dev  # Only run in dev mode

volumes:
  postgres_data:
    driver: local
```

### 7.2 GCP Configuration

**Service Account Permissions:**
```json
{
  "roles": [
    "roles/storage.objectCreator",  // Write to GCS
    "roles/storage.objectViewer"     // Read from GCS
  ]
}
```

**Environment Variables:**
```bash
# Database
DB_HOST=trafficsafety-db
DB_PORT=5432
DB_NAME=trafficsafety
DB_USER=api_user
DB_PASSWORD=<secret>
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# GCP Cloud Storage
GCS_BUCKET=trafficsafety-prod-parquet
GCS_PROJECT_ID=trafficsafety-prod
GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-service-account.json

# Feature Flags
USE_POSTGRESQL=true
ENABLE_GCS_UPLOAD=true
FALLBACK_TO_PARQUET=true
```

---

## 8. Performance Optimization

### 8.1 Database Tuning

```sql
-- PostgreSQL Configuration (postgresql.conf)

# Memory Settings (for 8GB RAM server)
shared_buffers = 2GB                  # 25% of RAM
effective_cache_size = 6GB            # 75% of RAM
maintenance_work_mem = 512MB
work_mem = 32MB

# Query Planning
random_page_cost = 1.1                # For SSD storage
effective_io_concurrency = 200

# Connections
max_connections = 100
max_parallel_workers_per_gather = 2
max_parallel_workers = 4

# WAL Settings
wal_buffers = 16MB
checkpoint_completion_target = 0.9
checkpoint_timeout = 15min

# Logging (for performance analysis)
log_min_duration_statement = 1000     # Log slow queries (>1s)
log_line_prefix = '%t [%p]: '
log_checkpoints = on
log_connections = on
log_disconnections = on
```

### 8.2 Index Strategy

```sql
-- Composite indexes for common queries

-- Latest safety index for each intersection
CREATE INDEX idx_sir_latest
    ON safety_indices_realtime (intersection_id, timestamp DESC)
    WHERE timestamp > NOW() - INTERVAL '48 hours';

-- High-risk intervals
CREATE INDEX idx_sir_high_risk
    ON safety_indices_realtime (combined_index_eb)
    WHERE combined_index_eb > 75;

-- Spatial queries
CREATE INDEX idx_intersections_geom_covering
    ON intersections USING GIST (geometry)
    INCLUDE (id, name);  -- Covering index
```

### 8.3 Query Optimization

```sql
-- Use prepared statements
PREPARE get_latest_si (int) AS
    SELECT * FROM safety_indices_realtime
    WHERE intersection_id = $1
    ORDER BY timestamp DESC
    LIMIT 1;

-- Materialized views for dashboards
CREATE MATERIALIZED VIEW mv_current_safety_status AS
    SELECT DISTINCT ON (intersection_id)
        intersection_id,
        combined_index_eb as safety_index,
        traffic_volume,
        timestamp as last_updated
    FROM safety_indices_realtime
    WHERE timestamp > NOW() - INTERVAL '5 minutes'
    ORDER BY intersection_id, timestamp DESC;

-- Refresh every minute via cron
CREATE INDEX ON mv_current_safety_status (intersection_id);
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_current_safety_status;
```

---

## 9. Monitoring and Observability

### 9.1 Key Metrics

**Database Metrics:**
- Query latency (p50, p95, p99)
- Connection pool utilization
- Table sizes and growth rate
- Index hit ratio (should be >99%)
- Cache hit ratio
- Dead tuples (for vacuum monitoring)

**Application Metrics:**
- API response time per endpoint
- GCS upload success rate
- Database write success rate
- Dual-write consistency check

**Business Metrics:**
- Intersections tracked
- Data completeness (% of expected records)
- Safety index distribution
- High-risk intersection count

### 9.2 Monitoring Stack

```yaml
# Prometheus exporters
services:
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/trafficsafety?sslmode=disable"
    ports:
      - "9187:9187"
    networks:
      - trafficsafety-network

  # Grafana dashboard
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
    networks:
      - trafficsafety-network
```

**Dashboard Panels:**
1. Real-time write throughput
2. API query latency heatmap
3. Database connection pool
4. Table size growth
5. GCS upload success rate
6. Top 10 slowest queries

---

## 10. Security

### 10.1 Database Access Control

```sql
-- Create read-only user for reporting
CREATE ROLE reporting_user WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE trafficsafety TO reporting_user;
GRANT USAGE ON SCHEMA public TO reporting_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting_user;

-- Create API user with limited permissions
CREATE ROLE api_user WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE trafficsafety TO api_user;
GRANT USAGE ON SCHEMA public TO api_user;
GRANT SELECT, INSERT ON safety_indices_realtime TO api_user;
GRANT SELECT ON intersections TO api_user;
GRANT SELECT ON safety_indices_hourly, safety_indices_daily TO api_user;
GRANT INSERT ON data_quality_log TO api_user;

-- Restrict superuser access
REVOKE ALL ON DATABASE trafficsafety FROM PUBLIC;
```

### 10.2 Network Security

- Database not exposed to public internet
- Access via private Docker network only
- TLS/SSL for database connections
- GCS access via service account (no API keys)

### 10.3 Data Encryption

- At-rest: PostgreSQL transparent data encryption (TDE)
- In-transit: TLS 1.3 for all connections
- GCS: Google-managed encryption keys
- Secrets: Environment variables (Docker secrets in production)

---

## 11. Appendices

### A. SQL Queries Library

See `backend/db/queries/` for production-ready SQL queries:
- `latest_safety_index.sql`
- `historical_time_series.sql`
- `spatial_nearby.sql`
- `aggregation_hourly.sql`
- `retention_cleanup.sql`

### B. GCS Client Library

```python
# backend/app/services/gcs_storage.py
from google.cloud import storage
from pathlib import Path

class GCSStorage:
    def __init__(self, bucket_name: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def upload_parquet(self, local_path: Path, gcs_path: str):
        """Upload Parquet file to GCS."""
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_filename(str(local_path))
        return f"gs://{self.bucket.name}/{gcs_path}"

    def download_parquet(self, gcs_path: str, local_path: Path):
        """Download Parquet file from GCS."""
        blob = self.bucket.blob(gcs_path)
        blob.download_to_filename(str(local_path))
```

### C. Database Connection Pool

```python
# backend/app/db/connection.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=False           # Set True for SQL logging
)

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

---

**End of Design Document**
