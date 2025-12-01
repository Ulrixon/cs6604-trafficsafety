-- Migration: Create separate schema for analytics features
-- This keeps crash validation data separate from real-time safety indices

-- Create analytics schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- Grant permissions
GRANT USAGE ON SCHEMA analytics TO jason;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO jason;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA analytics TO jason;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL PRIVILEGES ON TABLES TO jason;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL PRIVILEGES ON SEQUENCES TO jason;

-- Create table for crash correlation cache (optional - for performance)
CREATE TABLE IF NOT EXISTS analytics.crash_correlation_cache (
    id SERIAL PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    threshold FLOAT NOT NULL,
    proximity_radius FLOAT NOT NULL,
    total_crashes INT NOT NULL,
    total_intervals INT NOT NULL,
    crash_rate FLOAT NOT NULL,
    true_positives INT NOT NULL,
    false_positives INT NOT NULL,
    true_negatives INT NOT NULL,
    false_negatives INT NOT NULL,
    precision FLOAT NOT NULL,
    recall FLOAT NOT NULL,
    f1_score FLOAT NOT NULL,
    accuracy FLOAT NOT NULL,
    pearson_correlation FLOAT NOT NULL,
    spearman_correlation FLOAT NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(start_date, end_date, threshold, proximity_radius)
);

CREATE INDEX idx_crash_cache_dates ON analytics.crash_correlation_cache(start_date, end_date);

-- Create view for monitored intersections (if needed)
CREATE OR REPLACE VIEW analytics.monitored_intersections AS
SELECT
    id as intersection_id,
    name,
    latitude,
    longitude,
    created_at,
    updated_at
FROM public.intersections
ORDER BY id;

COMMENT ON SCHEMA analytics IS 'Analytics and validation features for crash correlation analysis';
COMMENT ON TABLE analytics.crash_correlation_cache IS 'Cached correlation metrics to improve query performance';
COMMENT ON VIEW analytics.monitored_intersections IS 'View of intersections being monitored for safety indices';
