-- Traffic Safety Index System - Camera Integration Schema
-- Version: 3.0
-- Description: Schema for traffic camera URL integration
--
-- This migration adds:
-- - camera_urls JSONB column to intersections table for flexible camera link storage
--
-- Usage:
--   psql -U trafficsafety -d trafficsafety -f backend/db/init/03_add_camera_urls.sql

-- =============================================================================
-- 1. ADD CAMERA_URLS COLUMN TO INTERSECTIONS TABLE
-- =============================================================================

DO $$
BEGIN
    -- Add camera_urls column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'intersections'
        AND column_name = 'camera_urls'
    ) THEN
        ALTER TABLE intersections
            ADD COLUMN camera_urls JSONB DEFAULT NULL;

        RAISE NOTICE 'Added camera_urls column to intersections table';
    ELSE
        RAISE NOTICE 'camera_urls column already exists in intersections table';
    END IF;
END $$;

COMMENT ON COLUMN intersections.camera_urls IS
    'Array of traffic camera links: [{"source": "VDOT", "url": "https://...", "label": "Camera Name"}]';

-- =============================================================================
-- 2. CREATE INDEX FOR CAMERA AVAILABILITY QUERIES
-- =============================================================================

-- GIN index for efficient JSONB queries
CREATE INDEX IF NOT EXISTS idx_intersections_camera_urls
    ON intersections USING GIN(camera_urls);

-- Partial index for intersections with cameras
CREATE INDEX IF NOT EXISTS idx_intersections_has_cameras
    ON intersections (id)
    WHERE camera_urls IS NOT NULL;

COMMENT ON INDEX idx_intersections_camera_urls IS
    'GIN index for efficient JSONB queries on camera_urls';
COMMENT ON INDEX idx_intersections_has_cameras IS
    'Partial index for quickly finding intersections with camera data';

-- =============================================================================
-- 3. VALIDATION FUNCTION FOR CAMERA URL STRUCTURE
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_camera_url_structure(camera_data JSONB)
RETURNS BOOLEAN AS $$
DECLARE
    cam JSONB;
BEGIN
    -- Null is valid (no cameras)
    IF camera_data IS NULL THEN
        RETURN TRUE;
    END IF;

    -- Must be an array
    IF jsonb_typeof(camera_data) != 'array' THEN
        RETURN FALSE;
    END IF;

    -- Validate each camera object
    FOR cam IN SELECT * FROM jsonb_array_elements(camera_data)
    LOOP
        -- Each camera must have required fields
        IF NOT (
            cam ? 'source' AND
            cam ? 'url' AND
            cam ? 'label' AND
            jsonb_typeof(cam->'source') = 'string' AND
            jsonb_typeof(cam->'url') = 'string' AND
            jsonb_typeof(cam->'label') = 'string'
        ) THEN
            RETURN FALSE;
        END IF;

        -- URL must start with http:// or https://
        IF NOT ((cam->>'url') ~* '^https?://') THEN
            RETURN FALSE;
        END IF;
    END LOOP;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION validate_camera_url_structure(JSONB) IS
    'Validates camera_urls JSONB structure: must be array with objects containing source, url, label';

-- =============================================================================
-- 4. ADD CHECK CONSTRAINT FOR CAMERA URL VALIDATION
-- =============================================================================

-- Add constraint to ensure camera_urls follows expected structure
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'check_camera_urls_structure'
    ) THEN
        ALTER TABLE intersections
            ADD CONSTRAINT check_camera_urls_structure
            CHECK (validate_camera_url_structure(camera_urls));

        RAISE NOTICE 'Added check constraint for camera_urls structure validation';
    ELSE
        RAISE NOTICE 'Camera URLs structure constraint already exists';
    END IF;
END $$;

-- =============================================================================
-- 5. HELPER FUNCTIONS
-- =============================================================================

-- Function to get intersections with cameras
CREATE OR REPLACE FUNCTION get_intersections_with_cameras()
RETURNS TABLE (
    intersection_id INTEGER,
    intersection_name VARCHAR,
    camera_count INT,
    camera_sources TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.id,
        i.name,
        jsonb_array_length(i.camera_urls) AS camera_count,
        ARRAY(
            SELECT jsonb_array_elements(i.camera_urls)->>'source'
        ) AS camera_sources
    FROM intersections i
    WHERE i.camera_urls IS NOT NULL
    AND jsonb_array_length(i.camera_urls) > 0
    ORDER BY jsonb_array_length(i.camera_urls) DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_intersections_with_cameras() IS
    'Returns all intersections that have camera URLs with camera count and sources';

-- Function to add camera URL to intersection
CREATE OR REPLACE FUNCTION add_camera_url(
    p_intersection_id INTEGER,
    p_source VARCHAR,
    p_url VARCHAR,
    p_label VARCHAR
)
RETURNS JSONB AS $$
DECLARE
    current_cameras JSONB;
    new_camera JSONB;
    updated_cameras JSONB;
BEGIN
    -- Get current camera URLs
    SELECT camera_urls INTO current_cameras
    FROM intersections
    WHERE id = p_intersection_id;

    -- Create new camera object
    new_camera := jsonb_build_object(
        'source', p_source,
        'url', p_url,
        'label', p_label
    );

    -- Initialize or append to array
    IF current_cameras IS NULL THEN
        updated_cameras := jsonb_build_array(new_camera);
    ELSE
        updated_cameras := current_cameras || new_camera;
    END IF;

    -- Update intersection
    UPDATE intersections
    SET camera_urls = updated_cameras,
        updated_at = NOW()
    WHERE id = p_intersection_id;

    RETURN updated_cameras;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION add_camera_url(INTEGER, VARCHAR, VARCHAR, VARCHAR) IS
    'Add a camera URL to an intersection. Parameters: intersection_id, source, url, label';

-- =============================================================================
-- 6. HELPER VIEWS
-- =============================================================================

-- View: Intersections with camera information
CREATE OR REPLACE VIEW v_intersections_with_cameras AS
SELECT
    i.id AS intersection_id,
    i.name AS intersection_name,
    i.latitude,
    i.longitude,
    i.camera_urls,
    jsonb_array_length(COALESCE(i.camera_urls, '[]'::jsonb)) AS camera_count,
    CASE
        WHEN i.camera_urls IS NOT NULL AND jsonb_array_length(i.camera_urls) > 0
        THEN true
        ELSE false
    END AS has_cameras
FROM intersections i;

COMMENT ON VIEW v_intersections_with_cameras IS
    'All intersections with camera URL information and camera count';

-- =============================================================================
-- 7. SEED DATA FOR TESTING
-- =============================================================================

-- Add sample camera URLs to test intersection (ID 0)
UPDATE intersections
SET camera_urls = '[
    {
        "source": "VDOT",
        "url": "https://511virginia.org/camera/sample",
        "label": "VDOT Sample Camera"
    },
    {
        "source": "511",
        "url": "https://511.vdot.virginia.gov/map?lat=37.2296&lon=-80.4139",
        "label": "View on 511 Map"
    }
]'::jsonb
WHERE id = 0
AND camera_urls IS NULL;

-- =============================================================================
-- 8. GRANTS (Adjust as needed for your user roles)
-- =============================================================================

-- Grant access to application user
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'trafficsafety') THEN
        GRANT SELECT ON v_intersections_with_cameras TO trafficsafety;
        GRANT EXECUTE ON FUNCTION validate_camera_url_structure(JSONB) TO trafficsafety;
        GRANT EXECUTE ON FUNCTION get_intersections_with_cameras() TO trafficsafety;
        GRANT EXECUTE ON FUNCTION add_camera_url(INTEGER, VARCHAR, VARCHAR, VARCHAR) TO trafficsafety;

        RAISE NOTICE 'Granted camera-related permissions to trafficsafety user';
    ELSE
        RAISE NOTICE 'User trafficsafety does not exist, skipping grants';
    END IF;
END $$;

-- =============================================================================
-- 9. VERIFICATION
-- =============================================================================

-- Verify camera_urls column was added
DO $$
DECLARE
    column_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'intersections'
        AND column_name = 'camera_urls'
    ) INTO column_exists;

    IF column_exists THEN
        RAISE NOTICE '✓ camera_urls column added to intersections table';
    ELSE
        RAISE WARNING '⚠ camera_urls column not found in intersections table';
    END IF;
END $$;

-- Verify indexes were created
DO $$
DECLARE
    index_count INT;
BEGIN
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'intersections'
    AND indexname IN ('idx_intersections_camera_urls', 'idx_intersections_has_cameras');

    IF index_count = 2 THEN
        RAISE NOTICE '✓ Camera URL indexes created successfully';
    ELSE
        RAISE WARNING '⚠ Expected 2 camera URL indexes, found %', index_count;
    END IF;
END $$;

-- Test validation function with sample data
DO $$
DECLARE
    valid_test BOOLEAN;
    invalid_test BOOLEAN;
BEGIN
    -- Test valid structure
    valid_test := validate_camera_url_structure('[
        {"source": "VDOT", "url": "https://example.com", "label": "Test"}
    ]'::jsonb);

    -- Test invalid structure (missing label)
    invalid_test := validate_camera_url_structure('[
        {"source": "VDOT", "url": "https://example.com"}
    ]'::jsonb);

    IF valid_test = TRUE AND invalid_test = FALSE THEN
        RAISE NOTICE '✓ Camera URL validation function working correctly';
    ELSE
        RAISE WARNING '⚠ Camera URL validation function may have issues';
    END IF;
END $$;

-- Show summary
SELECT '=== Camera URL Statistics ===' AS status;
SELECT
    COUNT(*) AS total_intersections,
    COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) AS intersections_with_cameras,
    SUM(jsonb_array_length(COALESCE(camera_urls, '[]'::jsonb))) AS total_cameras
FROM intersections;

SELECT '=== Sample Intersection with Cameras ===' AS status;
SELECT * FROM v_intersections_with_cameras WHERE has_cameras = true LIMIT 3;

-- Migration complete
SELECT '✓ Migration 03_add_camera_urls.sql completed successfully' AS status;
