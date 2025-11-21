-- Traffic Safety Index System - PostgreSQL + PostGIS Schema
-- Version: 1.0
-- Description: Complete database schema for storing safety indices with spatial capabilities
--
-- This schema implements:
-- - PostGIS extension for geospatial operations
-- - Intersections table with spatial indexing
-- - Time-partitioned realtime safety indices (1-minute granularity)
-- - Pre-aggregated hourly and daily tables for efficient querying
-- - Automated partition management functions
-- - Retention policies via partition dropping

-- =============================================================================
-- 1. EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Verify PostGIS is installed
DO $$
BEGIN
    RAISE NOTICE 'PostGIS version: %', PostGIS_Version();
END $$;

-- =============================================================================
-- 2. INTERSECTIONS TABLE
-- =============================================================================

CREATE TABLE intersections (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    geometry GEOMETRY(POINT, 4326),  -- WGS84 spatial reference system
    lane_count INTEGER CHECK (lane_count > 0),
    revision INTEGER,
    metadata JSONB,  -- Store flexible metadata (signal timing, road types, etc.)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Spatial index for geometry-based queries (proximity, routing)
CREATE INDEX idx_intersections_geometry ON intersections USING GIST (geometry);

-- Index for lookup by name
CREATE INDEX idx_intersections_name ON intersections (name);

-- Trigger to auto-update geometry from lat/lon
CREATE OR REPLACE FUNCTION update_intersection_geometry()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geometry = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_intersection_geometry
BEFORE INSERT OR UPDATE ON intersections
FOR EACH ROW
EXECUTE FUNCTION update_intersection_geometry();

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_intersections_updated_at
BEFORE UPDATE ON intersections
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- 3. SAFETY INDICES - REALTIME (1-MINUTE GRANULARITY, PARTITIONED)
-- =============================================================================

-- Main table (partitioned by day)
CREATE TABLE safety_indices_realtime (
    id BIGSERIAL,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Safety indices (0-100 scale)
    combined_index DOUBLE PRECISION NOT NULL CHECK (combined_index BETWEEN 0 AND 100),
    combined_index_eb DOUBLE PRECISION CHECK (combined_index_eb BETWEEN 0 AND 100),  -- Empirical Bayes adjusted
    vru_index DOUBLE PRECISION CHECK (vru_index BETWEEN 0 AND 100),  -- Vulnerable road users
    vehicle_index DOUBLE PRECISION CHECK (vehicle_index BETWEEN 0 AND 100),

    -- Traffic volume metrics
    traffic_volume INTEGER NOT NULL CHECK (traffic_volume >= 0),
    vru_count INTEGER NOT NULL DEFAULT 0 CHECK (vru_count >= 0),

    -- Time features (for aggregation and ML)
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),  -- 0=Monday, 6=Sunday

    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create indexes on parent table (inherited by partitions)
CREATE INDEX idx_safety_realtime_intersection_time ON safety_indices_realtime (intersection_id, timestamp DESC);
CREATE INDEX idx_safety_realtime_timestamp ON safety_indices_realtime (timestamp DESC);
CREATE INDEX idx_safety_realtime_high_risk ON safety_indices_realtime (intersection_id, timestamp DESC)
    WHERE combined_index > 75;  -- Partial index for high-risk queries

-- =============================================================================
-- 4. PARTITION MANAGEMENT FUNCTIONS
-- =============================================================================

-- Function to create a partition for a specific date
CREATE OR REPLACE FUNCTION create_realtime_partition(partition_date DATE)
RETURNS TEXT AS $$
DECLARE
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    partition_name := 'safety_indices_realtime_' || TO_CHAR(partition_date, 'YYYY_MM_DD');
    start_date := partition_date::TEXT;
    end_date := (partition_date + INTERVAL '1 day')::TEXT;

    -- Check if partition already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = partition_name
    ) THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF safety_indices_realtime
             FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
        RAISE NOTICE 'Created partition: %', partition_name;
        RETURN partition_name;
    ELSE
        RAISE NOTICE 'Partition already exists: %', partition_name;
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to create partitions for next N days
CREATE OR REPLACE FUNCTION create_future_partitions(days_ahead INTEGER DEFAULT 7)
RETURNS VOID AS $$
DECLARE
    i INTEGER;
BEGIN
    FOR i IN 0..days_ahead LOOP
        PERFORM create_realtime_partition(CURRENT_DATE + i);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to drop old partitions (data retention)
CREATE OR REPLACE FUNCTION drop_old_realtime_partitions(retention_days INTEGER DEFAULT 2)
RETURNS VOID AS $$
DECLARE
    partition_record RECORD;
    partition_date DATE;
BEGIN
    FOR partition_record IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE 'safety_indices_realtime_%'
    LOOP
        -- Extract date from partition name (format: safety_indices_realtime_YYYY_MM_DD)
        BEGIN
            partition_date := TO_DATE(
                SUBSTRING(partition_record.tablename FROM 'safety_indices_realtime_(.*)'),
                'YYYY_MM_DD'
            );

            -- Drop if older than retention period
            IF partition_date < CURRENT_DATE - retention_days THEN
                EXECUTE format('DROP TABLE IF EXISTS %I', partition_record.tablename);
                RAISE NOTICE 'Dropped old partition: %', partition_record.tablename;
            END IF;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE NOTICE 'Could not process partition: %', partition_record.tablename;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create initial partitions (today + 7 days ahead)
SELECT create_future_partitions(7);

-- =============================================================================
-- 5. SAFETY INDICES - HOURLY AGGREGATES
-- =============================================================================

CREATE TABLE safety_indices_hourly (
    id BIGSERIAL PRIMARY KEY,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    hour_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,  -- Rounded to hour

    -- Aggregated statistics
    avg_si DOUBLE PRECISION NOT NULL CHECK (avg_si BETWEEN 0 AND 100),
    min_si DOUBLE PRECISION NOT NULL CHECK (min_si BETWEEN 0 AND 100),
    max_si DOUBLE PRECISION NOT NULL CHECK (max_si BETWEEN 0 AND 100),
    std_si DOUBLE PRECISION CHECK (std_si >= 0),

    -- Traffic aggregates
    total_volume BIGINT NOT NULL CHECK (total_volume >= 0),
    avg_volume DOUBLE PRECISION CHECK (avg_volume >= 0),

    -- Risk metrics
    high_risk_minutes INTEGER NOT NULL DEFAULT 0 CHECK (high_risk_minutes BETWEEN 0 AND 60),

    -- Metadata
    data_points INTEGER NOT NULL CHECK (data_points > 0),  -- Number of 1-min intervals aggregated

    UNIQUE (intersection_id, hour_timestamp)
);

-- Indexes for efficient querying
CREATE INDEX idx_safety_hourly_intersection_time ON safety_indices_hourly (intersection_id, hour_timestamp DESC);
CREATE INDEX idx_safety_hourly_timestamp ON safety_indices_hourly (hour_timestamp DESC);

-- =============================================================================
-- 6. SAFETY INDICES - DAILY AGGREGATES
-- =============================================================================

CREATE TABLE safety_indices_daily (
    id BIGSERIAL PRIMARY KEY,
    intersection_id INTEGER NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
    date DATE NOT NULL,

    -- Aggregated statistics
    avg_si DOUBLE PRECISION NOT NULL CHECK (avg_si BETWEEN 0 AND 100),
    min_si DOUBLE PRECISION NOT NULL CHECK (min_si BETWEEN 0 AND 100),
    max_si DOUBLE PRECISION NOT NULL CHECK (max_si BETWEEN 0 AND 100),
    std_si DOUBLE PRECISION CHECK (std_si >= 0),

    -- Traffic aggregates
    total_volume BIGINT NOT NULL CHECK (total_volume >= 0),
    avg_volume DOUBLE PRECISION CHECK (avg_volume >= 0),

    -- Risk metrics
    high_risk_hours INTEGER NOT NULL DEFAULT 0 CHECK (high_risk_hours BETWEEN 0 AND 24),
    high_risk_percentage DOUBLE PRECISION CHECK (high_risk_percentage BETWEEN 0 AND 100),

    -- Peak metrics
    peak_hour INTEGER CHECK (peak_hour BETWEEN 0 AND 23),
    peak_si DOUBLE PRECISION CHECK (peak_si BETWEEN 0 AND 100),

    -- Metadata
    data_points INTEGER NOT NULL CHECK (data_points > 0),  -- Number of 1-min intervals aggregated

    UNIQUE (intersection_id, date)
);

-- Indexes for efficient querying
CREATE INDEX idx_safety_daily_intersection_date ON safety_indices_daily (intersection_id, date DESC);
CREATE INDEX idx_safety_daily_date ON safety_indices_daily (date DESC);

-- =============================================================================
-- 7. SEED DATA FOR TESTING
-- =============================================================================

-- Insert test intersection (ID 0 from current system)
INSERT INTO intersections (id, name, latitude, longitude, lane_count, revision, metadata)
VALUES (
    0,
    'Test Intersection - Blacksburg, VA',
    37.2296,
    -80.4139,
    4,
    1,
    '{"city": "Blacksburg", "state": "VA", "country": "USA"}'::JSONB
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 8. HELPER VIEWS
-- =============================================================================

-- View: Latest safety index for each intersection
CREATE OR REPLACE VIEW v_latest_safety_indices AS
SELECT DISTINCT ON (i.id)
    i.id AS intersection_id,
    i.name AS intersection_name,
    i.latitude,
    i.longitude,
    i.geometry,
    sr.timestamp,
    sr.combined_index AS safety_index,
    sr.combined_index_eb AS safety_index_eb,
    sr.vru_index,
    sr.vehicle_index,
    sr.traffic_volume,
    sr.vru_count,
    CASE
        WHEN sr.combined_index < 60 THEN 'Low'
        WHEN sr.combined_index <= 75 THEN 'Medium'
        ELSE 'High'
    END AS risk_level
FROM intersections i
LEFT JOIN safety_indices_realtime sr ON i.id = sr.intersection_id
ORDER BY i.id, sr.timestamp DESC NULLS LAST;

-- View: High-risk intersections (safety index > 75)
CREATE OR REPLACE VIEW v_high_risk_intersections AS
SELECT *
FROM v_latest_safety_indices
WHERE safety_index > 75;

-- =============================================================================
-- 9. UTILITY FUNCTIONS
-- =============================================================================

-- Function to get intersections within radius (in meters)
CREATE OR REPLACE FUNCTION get_intersections_within_radius(
    center_lat DOUBLE PRECISION,
    center_lon DOUBLE PRECISION,
    radius_meters DOUBLE PRECISION
)
RETURNS TABLE (
    intersection_id INTEGER,
    intersection_name VARCHAR,
    distance_meters DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.id,
        i.name,
        ST_Distance(
            i.geometry::geography,
            ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography
        ) AS distance,
        i.latitude,
        i.longitude
    FROM intersections i
    WHERE ST_DWithin(
        i.geometry::geography,
        ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography,
        radius_meters
    )
    ORDER BY distance;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 10. DATABASE STATISTICS AND MONITORING
-- =============================================================================

-- Enable query performance tracking
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View: Table sizes for monitoring
CREATE OR REPLACE VIEW v_table_sizes AS
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY size_bytes DESC;

-- =============================================================================
-- SCHEMA INITIALIZATION COMPLETE
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Traffic Safety Index Database Schema';
    RAISE NOTICE 'Initialization Complete';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'PostGIS Version: %', PostGIS_Version();
    RAISE NOTICE 'Tables Created:';
    RAISE NOTICE '  - intersections (with spatial indexing)';
    RAISE NOTICE '  - safety_indices_realtime (partitioned)';
    RAISE NOTICE '  - safety_indices_hourly';
    RAISE NOTICE '  - safety_indices_daily';
    RAISE NOTICE 'Partitions: % days created', 8;
    RAISE NOTICE 'Views: 3 helper views created';
    RAISE NOTICE 'Functions: 6 utility functions created';
    RAISE NOTICE '========================================';
END $$;
