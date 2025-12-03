# Camera Management Guide

Complete guide for managing traffic camera URLs in the Traffic Safety Index system.

## Table of Contents
- [Overview](#overview)
- [Admin Script Usage](#admin-script-usage)
- [Database Operations](#database-operations)
- [VDOT API Integration](#vdot-api-integration)
- [Troubleshooting](#troubleshooting)

---

## Overview

The camera integration feature allows you to link traffic cameras to intersections, providing visual verification of traffic conditions. Cameras can be:
- **Automatically discovered** via VDOT API (requires API key)
- **Manually added** via admin script or SQL
- **Managed** through command-line tools

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Streamlit)                         │
│  - Camera buttons in details card                               │
│  - Camera links in map popups                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend API (FastAPI)                        │
│  - Returns camera_urls with intersection data                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                PostgreSQL Database                               │
│  - intersections.camera_urls (JSONB)                            │
│  - Stores: [{"source": "VDOT", "url": "...", "label": "..."}]  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               VDOT Camera Service (Optional)                     │
│  - Finds nearest cameras by coordinates                         │
│  - Returns camera URLs for display                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Admin Script Usage

The `populate_camera_urls.py` script provides comprehensive camera management utilities.

### Installation & Setup

```bash
# Navigate to backend directory
cd backend

# Ensure database connection is configured
export DATABASE_URL="postgresql://user:password@host:port/database"

# Optional: Configure VDOT API key for auto-population
export VDOT_API_KEY="your-api-key-here"
```

### Basic Commands

#### 1. List All Intersections

View all intersections with their camera status:

```bash
python scripts/populate_camera_urls.py --list
```

Output:
```
📍 Intersections (5 total)
================================================================================
📹 ID 0: Test Intersection - Blacksburg, VA
   Location: (37.2296, -80.4139)
   Cameras: 2
      - VDOT: VDOT Sample Camera
      - 511: View on 511 Map

⚫ ID 1: Main St & Elm Ave
   Location: (37.5407, -77.4360)
   Cameras: 0
```

#### 2. List Only Intersections with Cameras

```bash
python scripts/populate_camera_urls.py --list-cameras
```

#### 3. Auto-Populate All Intersections

Automatically find and add cameras for all intersections (requires VDOT API key):

```bash
python scripts/populate_camera_urls.py --auto-all
```

With custom parameters:
```bash
python scripts/populate_camera_urls.py --auto-all \
    --radius 1.0 \
    --max-cameras 5
```

Parameters:
- `--radius`: Search radius in miles (default: 0.5)
- `--max-cameras`: Maximum cameras to add per intersection (default: 3)

#### 4. Auto-Populate Specific Intersection

```bash
python scripts/populate_camera_urls.py --auto --intersection-id 0
```

With custom radius:
```bash
python scripts/populate_camera_urls.py --auto \
    --intersection-id 0 \
    --radius 2.0 \
    --max-cameras 5
```

#### 5. Manually Add Camera

Add a specific camera to an intersection:

```bash
python scripts/populate_camera_urls.py --add \
    --intersection-id 0 \
    --source "VDOT" \
    --url "https://511virginia.org/camera/CAM123" \
    --label "VDOT Camera - I-95 @ Exit 74"
```

#### 6. Clear Cameras for Intersection

Remove all cameras from an intersection:

```bash
python scripts/populate_camera_urls.py --clear --intersection-id 0
```

---

## Database Operations

### Direct SQL Access

#### View All Intersections with Cameras

```sql
SELECT
    id,
    name,
    latitude,
    longitude,
    camera_urls,
    jsonb_array_length(camera_urls) as camera_count
FROM intersections
WHERE camera_urls IS NOT NULL
ORDER BY id;
```

#### Add Camera to Intersection

Using the provided database function:

```sql
SELECT add_camera_url(
    0,                                              -- intersection_id
    'VDOT',                                         -- source
    'https://511virginia.org/camera/CAM456',        -- url
    'VDOT Camera - US-460 @ Main St'               -- label
);
```

#### Update Cameras (Replace All)

```sql
UPDATE intersections
SET camera_urls = '[
    {
        "source": "VDOT",
        "url": "https://511virginia.org/camera/CAM123",
        "label": "VDOT Camera - North View"
    },
    {
        "source": "VDOT",
        "url": "https://511virginia.org/camera/CAM456",
        "label": "VDOT Camera - South View"
    },
    {
        "source": "511",
        "url": "https://511.vdot.virginia.gov/map?lat=37.5&lon=-77.4",
        "label": "View on 511 Map"
    }
]'::jsonb,
    updated_at = NOW()
WHERE id = 0;
```

#### Clear Cameras

```sql
UPDATE intersections
SET camera_urls = NULL,
    updated_at = NOW()
WHERE id = 0;
```

#### Query Intersections by Camera Source

```sql
SELECT
    id,
    name,
    camera_urls
FROM intersections
WHERE camera_urls @> '[{"source": "VDOT"}]'::jsonb;
```

#### Get Statistics

```sql
SELECT
    COUNT(*) as total_intersections,
    COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) as with_cameras,
    SUM(jsonb_array_length(COALESCE(camera_urls, '[]'::jsonb))) as total_cameras,
    ROUND(
        COUNT(*) FILTER (WHERE camera_urls IS NOT NULL)::numeric / COUNT(*)::numeric * 100,
        1
    ) as percentage_with_cameras
FROM intersections;
```

---

## VDOT API Integration

### How Auto-Population Works

1. **Get Intersection Coordinates**: Retrieve lat/lon from database
2. **Query VDOT API**: Request cameras within radius
3. **Calculate Distances**: Use Haversine formula to find nearest cameras
4. **Build Camera Links**: Format camera URLs and labels
5. **Add Fallback**: Always include 511 map link
6. **Update Database**: Store as JSONB array

### Search Algorithm

```python
# Pseudocode for auto-population
def auto_populate(intersection_id, radius_miles=0.5, max_cameras=3):
    intersection = get_intersection(intersection_id)

    # 1. Find cameras via API
    vdot_cameras = vdot_api.get_cameras()

    # 2. Filter by distance
    nearby = []
    for camera in vdot_cameras:
        distance = haversine_distance(
            intersection.lat, intersection.lon,
            camera.lat, camera.lon
        )
        if distance <= radius_miles:
            nearby.append((camera, distance))

    # 3. Sort by distance (closest first)
    nearby.sort(key=lambda x: x[1])

    # 4. Take top N cameras
    cameras = [
        {
            "source": "VDOT",
            "url": f"https://511virginia.org/camera/{cam.id}",
            "label": f"VDOT {cam.name}"
        }
        for cam, dist in nearby[:max_cameras]
    ]

    # 5. Add fallback
    cameras.append({
        "source": "511",
        "url": f"https://511.vdot.virginia.gov/map?lat={lat}&lon={lon}",
        "label": "View on 511 Map"
    })

    # 6. Update database
    update_camera_urls(intersection_id, cameras)
```

### Distance Calculation

The Haversine formula calculates great-circle distance between two points:

```
a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
c = 2 × atan2(√a, √(1−a))
d = R × c
```

Where:
- R = Earth's radius (3956 miles)
- lat1, lon1 = Intersection coordinates
- lat2, lon2 = Camera coordinates

**Example:**
- Richmond (37.5407, -77.4360) to Blacksburg (37.2296, -80.4139)
- Distance ≈ 165 miles

### API Response Format

Expected VDOT API response:

```json
{
  "cameras": [
    {
      "id": "CAM123",
      "name": "I-95 @ Exit 74",
      "latitude": 37.5407,
      "longitude": -77.4360,
      "description": "Interstate 95 Northbound at Exit 74"
    }
  ]
}
```

---

## Troubleshooting

### Common Issues

#### 1. No Cameras Found

**Symptom:** Auto-population returns "No cameras found within X miles"

**Solutions:**
- Increase search radius: `--radius 2.0`
- Check VDOT API key is set: `echo $VDOT_API_KEY`
- Verify intersection has valid coordinates
- Manually add cameras as fallback

#### 2. VDOT API Key Not Set

**Symptom:** Warning "VDOT_API_KEY not set. Camera lookups will return empty results."

**Solution:**
```bash
export VDOT_API_KEY="your-api-key-here"
# OR add to .env file
echo "VDOT_API_KEY=your-key" >> .env
```

**Request API Access:**
Email: 511_videosubscription@iteris.com (see [VDOT API Access Guide](vdot-api-access-request.md))

#### 3. Database Connection Error

**Symptom:** "Error: could not connect to database"

**Solutions:**
```bash
# Check DATABASE_URL is set
echo $DATABASE_URL

# Verify database is running
psql $DATABASE_URL -c "SELECT version();"

# Test connection
python -c "from app.db.connection import get_db_session; next(get_db_session()); print('✓ Connected')"
```

#### 4. Invalid Camera URLs

**Symptom:** Cameras appear but links don't work

**Solutions:**
- Verify URL format: Must start with `http://` or `https://`
- Check camera ID is correct in VDOT system
- Test URL manually in browser
- Update with correct URL:
  ```bash
  python scripts/populate_camera_urls.py --clear --intersection-id 0
  python scripts/populate_camera_urls.py --add --intersection-id 0 \
      --source "VDOT" --url "https://corrected-url" --label "Fixed Camera"
  ```

#### 5. Cameras Don't Appear in UI

**Checklist:**
1. ✓ Check database has camera_urls:
   ```sql
   SELECT camera_urls FROM intersections WHERE id = 0;
   ```

2. ✓ Verify API returns camera_urls:
   ```bash
   curl http://localhost:8000/api/v1/safety/index/ | jq '.[0].camera_urls'
   ```

3. ✓ Check frontend logs for errors:
   ```bash
   streamlit run pages/0_🏠_Dashboard.py
   ```

4. ✓ Verify camera_urls is not null or empty array

#### 6. Script Permission Denied

**Symptom:** `-bash: ./populate_camera_urls.py: Permission denied`

**Solution:**
```bash
chmod +x backend/scripts/populate_camera_urls.py
# OR run with python explicitly
python backend/scripts/populate_camera_urls.py --list
```

---

## Best Practices

### 1. Start with Manual Population

Before running auto-population on all intersections:
1. Test with one intersection first
2. Verify cameras work in UI
3. Adjust radius if needed
4. Then run batch operation

### 2. Regular Maintenance

- **Weekly:** Check for broken camera links
- **Monthly:** Verify camera accuracy (coordinates may change)
- **Quarterly:** Re-run auto-population to catch new cameras

### 3. Quality Control

After adding cameras:
```bash
# 1. List cameras
python scripts/populate_camera_urls.py --list-cameras

# 2. Test in UI (open dashboard and click intersection)

# 3. Click camera links to verify they work

# 4. Check logs for errors
```

### 4. Backup Before Bulk Updates

```sql
-- Create backup table
CREATE TABLE intersections_camera_backup AS
SELECT id, camera_urls, updated_at
FROM intersections
WHERE camera_urls IS NOT NULL;

-- Run bulk update
-- ...

-- Restore if needed
UPDATE intersections i
SET camera_urls = b.camera_urls
FROM intersections_camera_backup b
WHERE i.id = b.id;
```

---

## Advanced Usage

### Batch Import from CSV

Create CSV file `cameras.csv`:
```csv
intersection_id,source,url,label
0,VDOT,https://511virginia.org/camera/CAM123,VDOT Camera - I-95
1,VDOT,https://511virginia.org/camera/CAM456,VDOT Camera - US-460
```

Import script:
```python
import csv

populator = CameraURLPopulator()

with open('cameras.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        populator.add_camera_url(
            int(row['intersection_id']),
            row['source'],
            row['url'],
            row['label']
        )
```

### Custom Radius by Location

Urban areas: Smaller radius (0.25 miles)
Rural areas: Larger radius (2.0 miles)

```bash
# Urban
python scripts/populate_camera_urls.py --auto --intersection-id 0 --radius 0.25

# Rural
python scripts/populate_camera_urls.py --auto --intersection-id 1 --radius 2.0
```

---

## API Reference

### Database Functions

```sql
-- Add camera
SELECT add_camera_url(intersection_id, source, url, label);

-- Get intersections with cameras
SELECT * FROM get_intersections_with_cameras();

-- Validate camera structure
SELECT validate_camera_url_structure(camera_json);
```

### Python Classes

```python
from backend.scripts.populate_camera_urls import CameraURLPopulator

populator = CameraURLPopulator()

# Methods:
populator.list_intersections()
populator.get_intersection(id)
populator.auto_populate_intersection(id, radius_miles, max_cameras)
populator.update_camera_urls(id, cameras)
populator.add_camera_url(id, source, url, label)
populator.clear_camera_urls(id)
populator.auto_populate_all(radius_miles, max_cameras)
populator.display_intersections(with_cameras_only)
```

---

## Support

### Getting Help

1. Check logs: `backend/logs/` (if configured)
2. Database queries: See [Database Operations](#database-operations)
3. Test VDOT service:
   ```python
   from app.services.vdot_camera_service import VDOTCameraService
   service = VDOTCameraService()
   cameras = service.find_nearest_cameras(37.5, -77.4)
   print(cameras)
   ```

### Reporting Issues

Include in bug reports:
- Command used
- Error message (full traceback)
- Intersection ID
- Database query results for that intersection
- VDOT API key status (set/unset, don't include actual key)

---

**Last Updated:** 2025-12-03
**Version:** 1.0
