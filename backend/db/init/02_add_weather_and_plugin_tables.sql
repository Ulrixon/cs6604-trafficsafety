-- Traffic Safety Index System - Weather Data & Plugin System Schema
-- Version: 2.0
-- Description: Schema for weather data integration and plugin system
--
-- This migration adds:
-- - weather_observations table for NOAA/NWS data
-- - data_source_plugins table for plugin configuration
-- - feature_weight_history table for audit trail
-- - Extensions to safety_indices_realtime for weather features
--
-- Usage:
--   psql -U trafficsafety -d trafficsafety -f backend/db/init/02_add_weather_and_plugin_tables.sql

-- =============================================================================
-- 1. WEATHER OBSERVATIONS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS weather_observations (
    id BIGSERIAL PRIMARY KEY,
    station_id VARCHAR(10) NOT NULL,
    observation_time TIMESTAMPTZ NOT NULL,

    -- Raw measurements from NOAA API
    temperature_c FLOAT,
    precipitation_mm FLOAT,
    visibility_m FLOAT,
    wind_speed_ms FLOAT,
    wind_direction_deg INT CHECK (wind_direction_deg >= 0 AND wind_direction_deg < 360),
    weather_condition VARCHAR(100),

    -- Normalized features for safety index (0-1 scale)
    -- Higher value = higher risk
    temperature_normalized FLOAT CHECK (temperature_normalized >= 0 AND temperature_normalized <= 1),
    precipitation_normalized FLOAT CHECK (precipitation_normalized >= 0 AND precipitation_normalized <= 1),
    visibility_normalized FLOAT CHECK (visibility_normalized >= 0 AND visibility_normalized <= 1),
    wind_speed_normalized FLOAT CHECK (wind_speed_normalized >= 0 AND wind_speed_normalized <= 1),

    -- Raw API response for debugging and audit
    raw_json JSONB,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure unique observations (idempotency)
    UNIQUE(station_id, observation_time)
);

-- Indexes for efficient time-range queries
CREATE INDEX IF NOT EXISTS idx_weather_obs_time
    ON weather_observations(observation_time DESC);

CREATE INDEX IF NOT EXISTS idx_weather_obs_station
    ON weather_observations(station_id);

CREATE INDEX IF NOT EXISTS idx_weather_obs_created
    ON weather_observations(created_at DESC);

-- Composite index for common queries (station + time range)
CREATE INDEX IF NOT EXISTS idx_weather_obs_station_time
    ON weather_observations(station_id, observation_time DESC);

-- GIN index for JSONB queries (useful for debugging)
CREATE INDEX IF NOT EXISTS idx_weather_obs_raw_json
    ON weather_observations USING GIN(raw_json);

COMMENT ON TABLE weather_observations IS
    'Weather observations from NOAA/NWS API for safety index calculation';
COMMENT ON COLUMN weather_observations.station_id IS
    'NOAA weather station identifier (e.g., KRIC for Richmond Intl Airport)';
COMMENT ON COLUMN weather_observations.observation_time IS
    'Timestamp of weather observation (UTC)';
COMMENT ON COLUMN weather_observations.temperature_normalized IS
    'Temperature risk score: 0=optimal (20°C), 1=extreme (<0°C or >35°C)';
COMMENT ON COLUMN weather_observations.precipitation_normalized IS
    'Precipitation risk score: 0=none, 1=heavy rain (>20mm/hr)';
COMMENT ON COLUMN weather_observations.visibility_normalized IS
    'Visibility risk score: 0=good (>10km), 1=zero visibility';
COMMENT ON COLUMN weather_observations.wind_speed_normalized IS
    'Wind speed risk score: 0=calm, 1=high wind (>25m/s)';

-- =============================================================================
-- 2. DATA SOURCE PLUGINS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS data_source_plugins (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    class_name VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',

    -- Configuration
    enabled BOOLEAN DEFAULT true,
    weight FLOAT DEFAULT 0.0 CHECK (weight >= 0.0 AND weight <= 1.0),
    config JSONB,  -- Plugin-specific configuration

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Audit
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Index for active plugins
CREATE INDEX IF NOT EXISTS idx_plugins_enabled
    ON data_source_plugins(enabled)
    WHERE enabled = true;

COMMENT ON TABLE data_source_plugins IS
    'Configuration for data source plugins (VCC, weather, etc.)';
COMMENT ON COLUMN data_source_plugins.name IS
    'Unique plugin identifier (e.g., "vcc", "noaa_weather")';
COMMENT ON COLUMN data_source_plugins.class_name IS
    'Python class name implementing DataSourcePlugin';
COMMENT ON COLUMN data_source_plugins.weight IS
    'Feature weight in safety index (must sum to 1.0 across enabled plugins)';
COMMENT ON COLUMN data_source_plugins.config IS
    'Plugin-specific configuration (JSON format)';

-- Insert default plugins
INSERT INTO data_source_plugins (name, class_name, description, enabled, weight, config)
VALUES
    ('vcc', 'VCCPlugin', 'Virginia Connected Corridors traffic data source', true, 0.70, '{}'::jsonb),
    ('noaa_weather', 'NOAAWeatherPlugin', 'NOAA/NWS weather observation data source', false, 0.15, '{"station_id": "KRIC"}'::jsonb)
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 3. FEATURE WEIGHT HISTORY TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS feature_weight_history (
    id BIGSERIAL PRIMARY KEY,
    plugin_name VARCHAR(50) NOT NULL,
    feature_name VARCHAR(100),

    -- Weight change
    old_weight FLOAT,
    new_weight FLOAT NOT NULL CHECK (new_weight >= 0.0 AND new_weight <= 1.0),

    -- Audit trail
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    changed_by VARCHAR(100) NOT NULL,
    reason TEXT,

    -- Impact tracking (populated after recalculation)
    affected_indices_count INT,
    average_score_change FLOAT
);

-- Indexes for querying weight changes
CREATE INDEX IF NOT EXISTS idx_feature_weight_history_time
    ON feature_weight_history(changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_feature_weight_history_plugin
    ON feature_weight_history(plugin_name);

COMMENT ON TABLE feature_weight_history IS
    'Audit trail for feature weight changes';
COMMENT ON COLUMN feature_weight_history.changed_by IS
    'User or system that changed the weight';
COMMENT ON COLUMN feature_weight_history.reason IS
    'Explanation for the weight change (e.g., "Based on crash correlation analysis")';
COMMENT ON COLUMN feature_weight_history.affected_indices_count IS
    'Number of safety indices recalculated after weight change';

-- =============================================================================
-- 4. EXTEND SAFETY_INDICES_REALTIME FOR WEATHER FEATURES
-- =============================================================================

-- Add weather feature columns to existing safety_indices_realtime table
DO $$
BEGIN
    -- Add weather feature columns if they don't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'safety_indices_realtime'
        AND column_name = 'weather_precipitation_normalized'
    ) THEN
        ALTER TABLE safety_indices_realtime
            ADD COLUMN weather_precipitation_normalized FLOAT
                CHECK (weather_precipitation_normalized >= 0 AND weather_precipitation_normalized <= 1),
            ADD COLUMN weather_visibility_normalized FLOAT
                CHECK (weather_visibility_normalized >= 0 AND weather_visibility_normalized <= 1),
            ADD COLUMN weather_wind_speed_normalized FLOAT
                CHECK (weather_wind_speed_normalized >= 0 AND weather_wind_speed_normalized <= 1),
            ADD COLUMN weather_temperature_normalized FLOAT
                CHECK (weather_temperature_normalized >= 0 AND weather_temperature_normalized <= 1);

        RAISE NOTICE 'Added weather feature columns to safety_indices_realtime';
    ELSE
        RAISE NOTICE 'Weather feature columns already exist in safety_indices_realtime';
    END IF;

    -- Add plugin contribution tracking columns if they don't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'safety_indices_realtime'
        AND column_name = 'vcc_contribution'
    ) THEN
        ALTER TABLE safety_indices_realtime
            ADD COLUMN vcc_contribution FLOAT,
            ADD COLUMN weather_contribution FLOAT,
            ADD COLUMN formula_version VARCHAR(20) DEFAULT 'v2.0';

        RAISE NOTICE 'Added plugin contribution columns to safety_indices_realtime';
    ELSE
        RAISE NOTICE 'Plugin contribution columns already exist in safety_indices_realtime';
    END IF;
END $$;

COMMENT ON COLUMN safety_indices_realtime.weather_precipitation_normalized IS
    'Precipitation risk score from weather plugin (0=none, 1=heavy)';
COMMENT ON COLUMN safety_indices_realtime.weather_visibility_normalized IS
    'Visibility risk score from weather plugin (0=good, 1=zero)';
COMMENT ON COLUMN safety_indices_realtime.weather_wind_speed_normalized IS
    'Wind speed risk score from weather plugin (0=calm, 1=high)';
COMMENT ON COLUMN safety_indices_realtime.weather_temperature_normalized IS
    'Temperature risk score from weather plugin (0=optimal, 1=extreme)';
COMMENT ON COLUMN safety_indices_realtime.vcc_contribution IS
    'Portion of safety_index contributed by VCC plugin (safety_index * VCC_weight)';
COMMENT ON COLUMN safety_indices_realtime.weather_contribution IS
    'Portion of safety_index contributed by weather plugin (safety_index * weather_weight)';
COMMENT ON COLUMN safety_indices_realtime.formula_version IS
    'Safety index formula version (v1.0=VCC only, v2.0=VCC+weather)';

-- =============================================================================
-- 5. WEATHER DATA PARTITIONING (Future Enhancement)
-- =============================================================================

-- Note: For now, weather_observations is a single table.
-- If data volume grows significantly, we can implement partitioning
-- similar to safety_indices_realtime (monthly partitions).
--
-- Partition strategy would be:
-- - Monthly partitions by observation_time
-- - Retention: 2 years of raw observations
-- - Automated partition creation/dropping
--
-- Example:
-- CREATE TABLE weather_observations_2024_11 PARTITION OF weather_observations
--     FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

-- =============================================================================
-- 6. VALIDATION FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_plugin_weights()
RETURNS TABLE(
    total_weight FLOAT,
    is_valid BOOLEAN,
    message TEXT
) AS $$
DECLARE
    weight_sum FLOAT;
BEGIN
    SELECT SUM(weight) INTO weight_sum
    FROM data_source_plugins
    WHERE enabled = true;

    RETURN QUERY
    SELECT
        weight_sum,
        ABS(weight_sum - 1.0) < 0.01 AS is_valid,
        CASE
            WHEN ABS(weight_sum - 1.0) < 0.01 THEN
                'Plugin weights are valid (sum = ' || ROUND(weight_sum::numeric, 3) || ')'
            ELSE
                'Warning: Plugin weights sum to ' || ROUND(weight_sum::numeric, 3) || ', expected 1.0'
        END AS message;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION validate_plugin_weights() IS
    'Validate that enabled plugin weights sum to approximately 1.0';

-- =============================================================================
-- 7. HELPER VIEWS
-- =============================================================================

-- View for active plugins with their configurations
CREATE OR REPLACE VIEW v_active_plugins AS
SELECT
    name,
    description,
    version,
    weight,
    enabled,
    config,
    updated_at
FROM data_source_plugins
WHERE enabled = true
ORDER BY weight DESC;

COMMENT ON VIEW v_active_plugins IS
    'Active data source plugins with configuration';

-- View for recent weight changes
CREATE OR REPLACE VIEW v_recent_weight_changes AS
SELECT
    plugin_name,
    feature_name,
    old_weight,
    new_weight,
    new_weight - old_weight AS weight_delta,
    changed_at,
    changed_by,
    reason
FROM feature_weight_history
ORDER BY changed_at DESC
LIMIT 100;

COMMENT ON VIEW v_recent_weight_changes IS
    'Last 100 feature weight changes for audit';

-- =============================================================================
-- 8. GRANTS (Adjust as needed for your user roles)
-- =============================================================================

-- Grant access to application user
-- Note: Adjust the username based on your setup
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'trafficsafety') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON weather_observations TO trafficsafety;
        GRANT SELECT, INSERT, UPDATE, DELETE ON data_source_plugins TO trafficsafety;
        GRANT SELECT, INSERT, UPDATE, DELETE ON feature_weight_history TO trafficsafety;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO trafficsafety;
        GRANT SELECT ON v_active_plugins TO trafficsafety;
        GRANT SELECT ON v_recent_weight_changes TO trafficsafety;
        GRANT EXECUTE ON FUNCTION validate_plugin_weights() TO trafficsafety;

        RAISE NOTICE 'Granted permissions to trafficsafety user';
    ELSE
        RAISE NOTICE 'User trafficsafety does not exist, skipping grants';
    END IF;
END $$;

-- =============================================================================
-- 9. VERIFICATION
-- =============================================================================

-- Verify tables were created
DO $$
DECLARE
    table_count INT;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('weather_observations', 'data_source_plugins', 'feature_weight_history');

    IF table_count = 3 THEN
        RAISE NOTICE '✓ All 3 new tables created successfully';
    ELSE
        RAISE WARNING '⚠ Expected 3 tables, found %', table_count;
    END IF;
END $$;

-- Verify weather columns added to safety_indices_realtime
DO $$
DECLARE
    column_count INT;
BEGIN
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'safety_indices_realtime'
    AND column_name IN (
        'weather_precipitation_normalized',
        'weather_visibility_normalized',
        'weather_wind_speed_normalized',
        'weather_temperature_normalized',
        'vcc_contribution',
        'weather_contribution',
        'formula_version'
    );

    IF column_count = 7 THEN
        RAISE NOTICE '✓ All 7 weather columns added to safety_indices_realtime';
    ELSE
        RAISE WARNING '⚠ Expected 7 columns, found %', column_count;
    END IF;
END $$;

-- Show summary
SELECT '=== Plugin Weight Validation ===' AS status;
SELECT * FROM validate_plugin_weights();

SELECT '=== Active Plugins ===' AS status;
SELECT name, weight, enabled FROM data_source_plugins ORDER BY weight DESC;

-- Migration complete
SELECT '✓ Migration 02_add_weather_and_plugin_tables.sql completed successfully' AS status;
