-- Create separate table for intersection cameras
-- Decouples camera URLs from safety index intersection IDs
-- Maps cameras by intersection name/location rather than generated IDs

CREATE TABLE IF NOT EXISTS intersection_cameras (
    id SERIAL PRIMARY KEY,
    intersection_name VARCHAR(255) NOT NULL UNIQUE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    camera_urls JSONB DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Validation constraint
    CONSTRAINT valid_camera_urls CHECK (
        camera_urls IS NULL OR validate_camera_url_structure(camera_urls)
    )
);

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_intersection_cameras_name ON intersection_cameras(intersection_name);
CREATE INDEX IF NOT EXISTS idx_intersection_cameras_location ON intersection_cameras(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_intersection_cameras_urls ON intersection_cameras USING GIN (camera_urls);

-- Add comment
COMMENT ON TABLE intersection_cameras IS 'Camera URLs mapped to intersection names/locations, independent of safety index system';
COMMENT ON COLUMN intersection_cameras.intersection_name IS 'Intersection name used for lookup (matches BSM/PSM intersection names)';
COMMENT ON COLUMN intersection_cameras.latitude IS 'Intersection latitude for geospatial lookups';
COMMENT ON COLUMN intersection_cameras.longitude IS 'Intersection longitude for geospatial lookups';
COMMENT ON COLUMN intersection_cameras.camera_urls IS 'JSONB array of camera links {source, url, label}';
