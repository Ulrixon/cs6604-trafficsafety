# Camera Integration - Local Testing Guide

Complete guide for testing the camera integration feature locally before deploying to production.

---

## Prerequisites

- Python 3.11+ installed
- PostgreSQL database running (local or remote)
- VDOT API key (optional - will use fallback if not set)
- Git repository cloned

---

## Step 1: Environment Setup

### 1.1 Set Environment Variables

**Windows (PowerShell):**
```powershell
# Navigate to project
cd C:\Code\Git\cs6604-trafficsafety

# Set database connection
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/trafficsafety"

# Optional: Set VDOT API key (if you have one)
$env:VDOT_API_KEY = "your-vdot-api-key-here"

# Verify
echo $env:DATABASE_URL
```

**Windows (Command Prompt):**
```cmd
cd C:\Code\Git\cs6604-trafficsafety
set DATABASE_URL=postgresql://user:password@localhost:5432/trafficsafety
set VDOT_API_KEY=your-vdot-api-key-here
```

**Linux/Mac:**
```bash
cd ~/Code/cs6604-trafficsafety
export DATABASE_URL="postgresql://user:password@localhost:5432/trafficsafety"
export VDOT_API_KEY="your-vdot-api-key-here"  # Optional
```

### 1.2 Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

## Step 2: Database Migration

### 2.1 Apply Migration

Connect to your database and run the migration:

**Using psql:**
```bash
# Windows
psql %DATABASE_URL% -f backend/db/init/03_add_camera_urls.sql

# Linux/Mac
psql $DATABASE_URL -f backend/db/init/03_add_camera_urls.sql
```

**Expected Output:**
```
ALTER TABLE
CREATE INDEX
CREATE INDEX
CREATE FUNCTION
CREATE VIEW
CREATE FUNCTION
```

### 2.2 Verify Migration

```bash
# Check that camera_urls column exists
psql $DATABASE_URL -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='intersections' AND column_name='camera_urls';"
```

**Expected Output:**
```
 column_name  | data_type
--------------+-----------
 camera_urls  | jsonb
```

---

## Step 3: Test Admin Script

### 3.1 List All Intersections

```bash
cd backend
python scripts/populate_camera_urls.py --list
```

**Expected Output:**
```
📍 Intersections (X total)
================================================================================
⚫ ID 0: Test Intersection - Blacksburg, VA
   Location: (37.2296, -80.4139)
   Cameras: 0

⚫ ID 1: Intersection Name
   Location: (lat, lon)
   Cameras: 0
...
```

### 3.2 Test Manual Camera Addition

Add a test camera to intersection 0:

```bash
python scripts/populate_camera_urls.py --add \
    --intersection-id 0 \
    --source "511" \
    --url "https://511.vdot.virginia.gov/map?lat=37.2296&lon=-80.4139" \
    --label "511 Map - Test Location"
```

**Expected Output:**
```
✅ Updated intersection 0 with 1 camera(s)
   - 511: 511 Map - Test Location
```

### 3.3 Verify Camera Was Added

```bash
python scripts/populate_camera_urls.py --list | head -20
```

**Expected Output:**
```
📍 Intersections (X total)
================================================================================
📹 ID 0: Test Intersection - Blacksburg, VA
   Location: (37.2296, -80.4139)
   Cameras: 1
      - 511: 511 Map - Test Location
...
```

Or query directly in SQL:
```bash
psql $DATABASE_URL -c "SELECT id, name, camera_urls FROM intersections WHERE id = 0;"
```

---

## Step 4: Test VDOT API Integration (Optional)

**Note:** This requires a VDOT API key. If you don't have one, the script will use fallback (511 map links).

### 4.1 Test VDOT Service

```bash
cd backend
python -c "
from app.services.vdot_camera_service import VDOTCameraService

service = VDOTCameraService()

# Test Richmond, VA (should have cameras nearby)
cameras = service.get_cameras_with_fallback(37.5407, -77.4360, radius_miles=1.0)

print(f'Found {len(cameras)} camera(s):')
for cam in cameras:
    print(f'  - {cam[\"source\"]}: {cam[\"label\"]}')
"
```

**With VDOT API Key:**
```
Found 3 camera(s):
  - VDOT: VDOT Camera - I-95 @ Broad St
  - VDOT: VDOT Camera - I-64 @ 5th St
  - 511: View on 511 Map
```

**Without VDOT API Key:**
```
Found 1 camera(s):
  - 511: View on 511 Map
```

### 4.2 Test Auto-Population

Auto-populate cameras for intersection 0:

```bash
python scripts/populate_camera_urls.py --auto --intersection-id 0 --radius 1.0
```

**Expected Output:**
```
📍 Processing: Test Intersection - Blacksburg, VA (ID: 0)
   Location: (37.2296, -80.4139)
✅ Updated intersection 0 with 2 camera(s)
   - VDOT: VDOT Camera - US-460 @ Main St  # If VDOT API key set
   - 511: View on 511 Map
```

---

## Step 5: Test Backend API

### 5.1 Start Backend Server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 5.2 Test API Endpoint

Open a new terminal and test the API:

```bash
# Get all intersections
curl http://localhost:8000/api/v1/safety/index/ | python -m json.tool | head -30
```

**Expected Output:**
```json
[
  {
    "intersection_id": 0,
    "intersection_name": "Test Intersection - Blacksburg, VA",
    "safety_index": 65.0,
    "traffic_volume": 250,
    "latitude": 37.2296,
    "longitude": -80.4139,
    "camera_urls": [
      {
        "source": "511",
        "url": "https://511.vdot.virginia.gov/map?lat=37.2296&lon=-80.4139",
        "label": "511 Map - Test Location"
      }
    ]
  },
  ...
]
```

### 5.3 Verify Camera URLs Field

Check that camera_urls appears in response:

```bash
curl -s http://localhost:8000/api/v1/safety/index/ | python -c "import sys, json; data = json.load(sys.stdin); print('camera_urls field present:', 'camera_urls' in data[0])"
```

**Expected Output:**
```
camera_urls field present: True
```

---

## Step 6: Test Frontend UI

### 6.1 Start Frontend

Open a new terminal:

```bash
cd frontend
streamlit run pages/0_🏠_Dashboard.py
```

**Expected Output:**
```
You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

### 6.2 Visual Testing Checklist

Open browser to http://localhost:8501

**Test 1: Map Popup**
- [ ] Click on intersection marker (ID 0)
- [ ] Popup appears with intersection details
- [ ] "📹 Cameras:" section appears at bottom
- [ ] Camera link is visible: "🗺️ 511 Map - Test Location"
- [ ] Clicking link opens new tab to 511 map
- [ ] Popup is draggable (can move it around)

**Test 2: Details Card**
- [ ] Click on intersection marker
- [ ] Details card appears on left side
- [ ] Scroll to bottom of details card
- [ ] "📹 Traffic Cameras:" section appears
- [ ] Blue button with camera label appears
- [ ] Button has hover effect (darkens on mouse over)
- [ ] Clicking button opens new tab
- [ ] Link opens correct URL

**Test 3: No Cameras**
- [ ] Clear cameras: `python scripts/populate_camera_urls.py --clear --intersection-id 0`
- [ ] Refresh frontend
- [ ] Click on intersection 0
- [ ] NO camera section appears (graceful degradation)
- [ ] No errors in browser console (F12)

**Test 4: Multiple Cameras**
- [ ] Add 3 cameras to intersection 0:
  ```bash
  python scripts/populate_camera_urls.py --add \
      --intersection-id 0 --source "VDOT" \
      --url "https://example.com/cam1" --label "Camera 1"

  python scripts/populate_camera_urls.py --add \
      --intersection-id 0 --source "VDOT" \
      --url "https://example.com/cam2" --label "Camera 2"

  python scripts/populate_camera_urls.py --add \
      --intersection-id 0 --source "511" \
      --url "https://511.vdot.virginia.gov" --label "511 Map"
  ```
- [ ] Refresh frontend
- [ ] Click intersection 0
- [ ] Details card shows all 3 cameras (or "and X more")
- [ ] Map popup shows max 2 cameras
- [ ] All camera links work

---

## Step 7: Test Schema Validation

### 7.1 Test Valid Camera Structure

```bash
cd backend
python -c "
from app.schemas.intersection import CameraLink

# Valid camera
cam = CameraLink(source='VDOT', url='https://test.com/cam', label='Test Camera')
print('✓ Valid camera accepted')
print(f'  Source: {cam.source}')
print(f'  URL: {cam.url}')
print(f'  Label: {cam.label}')
"
```

**Expected Output:**
```
✓ Valid camera accepted
  Source: VDOT
  URL: https://test.com/cam
  Label: Test Camera
```

### 7.2 Test Invalid URL Rejection

```bash
python -c "
from app.schemas.intersection import CameraLink

# Invalid URL (not http/https)
try:
    cam = CameraLink(source='VDOT', url='ftp://invalid.com', label='Test')
    print('✗ Invalid URL accepted (FAIL)')
except Exception as e:
    print('✓ Invalid URL rejected')
    print(f'  Error: {type(e).__name__}')
"
```

**Expected Output:**
```
✓ Invalid URL rejected
  Error: ValidationError
```

---

## Step 8: Test Batch Operations

### 8.1 Auto-Populate All Intersections

**Warning:** This will process ALL intersections in your database. For testing, use a small dataset.

```bash
# Check how many intersections you have
python scripts/populate_camera_urls.py --list | grep "total"

# If < 10 intersections, proceed
python scripts/populate_camera_urls.py --auto-all --radius 0.5 --max-cameras 3
```

**Expected Output:**
```
🔄 Auto-populating cameras for 5 intersections
   Radius: 0.5 miles
   Max cameras: 3

📍 Processing: Test Intersection - Blacksburg, VA (ID: 0)
   Location: (37.2296, -80.4139)
✅ Updated intersection 0 with 2 camera(s)
   - VDOT: VDOT Camera - US-460
   - 511: View on 511 Map

... (repeats for each intersection)

=============================================================
✅ Successfully populated: 5
❌ Failed: 0
```

### 8.2 Test New-Only Population

```bash
# Clear one intersection
python scripts/populate_camera_urls.py --clear --intersection-id 0

# Run new-only
python scripts/populate_camera_urls.py --auto-new-only
```

**Expected Output:**
```
🔄 Auto-populating NEW intersections only
   Total intersections: 5
   Without cameras: 1
   Radius: 0.5 miles
   Max cameras: 3

📍 Processing: Test Intersection - Blacksburg, VA (ID: 0)
   Location: (37.2296, -80.4139)
✅ Updated intersection 0 with 2 camera(s)

=============================================================
✅ Successfully populated: 1
❌ Failed: 0
📊 Coverage: 5/5 intersections have cameras
```

---

## Step 9: Test Database Queries

### 9.1 Query Intersections with Cameras

```sql
psql $DATABASE_URL -c "
SELECT
    id,
    name,
    jsonb_array_length(camera_urls) as camera_count
FROM intersections
WHERE camera_urls IS NOT NULL
ORDER BY id
LIMIT 5;
"
```

### 9.2 Test Validation Function

```sql
psql $DATABASE_URL -c "
-- Valid structure
SELECT validate_camera_url_structure('[
    {\"source\": \"VDOT\", \"url\": \"https://test.com\", \"label\": \"Test\"}
]'::jsonb) as is_valid;
"
```

**Expected Output:**
```
 is_valid
----------
 t
```

### 9.3 Get Coverage Statistics

```sql
psql $DATABASE_URL -c "
SELECT
    COUNT(*) as total_intersections,
    COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) as with_cameras,
    ROUND(100.0 * COUNT(*) FILTER (WHERE camera_urls IS NOT NULL) / COUNT(*), 1) as coverage_pct
FROM intersections;
"
```

**Expected Output:**
```
 total_intersections | with_cameras | coverage_pct
---------------------+--------------+--------------
                   5 |            5 |        100.0
```

---

## Step 10: Performance Testing

### 10.1 Time API Response

```bash
# Windows PowerShell
Measure-Command { curl -s http://localhost:8000/api/v1/safety/index/ | Out-Null }

# Linux/Mac
time curl -s http://localhost:8000/api/v1/safety/index/ > /dev/null
```

**Expected:** < 2 seconds

### 10.2 Time Camera Population

```bash
# Clear all cameras first
for i in {0..4}; do
    python scripts/populate_camera_urls.py --clear --intersection-id $i
done

# Time auto-populate-all
time python scripts/populate_camera_urls.py --auto-all
```

**Expected:** ~5-10 seconds for 5 intersections

---

## Troubleshooting

### Issue: "No module named 'app'"

**Solution:**
```bash
cd backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python scripts/populate_camera_urls.py --list
```

### Issue: "database connection failed"

**Check connection:**
```bash
psql $DATABASE_URL -c "SELECT version();"
```

**Verify DATABASE_URL format:**
```
postgresql://username:password@host:port/database
```

### Issue: "VDOT_API_KEY not set" warning

**Expected behavior** - The script will use fallback (511 map links) if VDOT API key is not set.

To test with VDOT API:
1. Request API key from VDOT (see [vdot-api-access-request.md](vdot-api-access-request.md))
2. Set environment variable: `export VDOT_API_KEY="your-key"`

### Issue: Frontend not showing cameras

**Debug steps:**
1. Check API returns camera_urls:
   ```bash
   curl http://localhost:8000/api/v1/safety/index/ | python -m json.tool | grep -A 5 camera_urls
   ```

2. Check browser console (F12) for errors

3. Verify intersection has cameras:
   ```bash
   python scripts/populate_camera_urls.py --list | grep "ID 0" -A 3
   ```

4. Clear Streamlit cache:
   - Click hamburger menu (top right)
   - Click "Clear cache"
   - Refresh page

---

## Quick Test Script

Save this as `test_cameras_local.sh` for quick testing:

```bash
#!/bin/bash
set -e

echo "=== Camera Integration Local Test ==="
echo ""

# 1. Database check
echo "1. Checking database..."
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name='intersections' AND column_name='camera_urls';" | grep camera_urls
echo "✓ Database migration verified"
echo ""

# 2. List intersections
echo "2. Listing intersections..."
cd backend
python scripts/populate_camera_urls.py --list | head -10
echo ""

# 3. Add test camera
echo "3. Adding test camera to intersection 0..."
python scripts/populate_camera_urls.py --clear --intersection-id 0
python scripts/populate_camera_urls.py --add \
    --intersection-id 0 \
    --source "TEST" \
    --url "https://example.com/test" \
    --label "Test Camera"
echo ""

# 4. Verify
echo "4. Verifying camera was added..."
python scripts/populate_camera_urls.py --list | grep "ID 0" -A 3
echo ""

# 5. Test API
echo "5. Testing API endpoint..."
curl -s http://localhost:8000/api/v1/safety/index/ | python -c "import sys, json; data = json.load(sys.stdin); print(f'API returned {len(data)} intersections'); print(f'Intersection 0 has {len(data[0].get(\"camera_urls\", []))} camera(s)')"
echo ""

echo "=== All tests passed! ==="
```

Run it:
```bash
chmod +x test_cameras_local.sh
./test_cameras_local.sh
```

---

## Next Steps

After successful local testing:

1. **Review test results** - Ensure all tests passed
2. **Test with real data** - Use actual VDOT API key
3. **Performance testing** - Test with full dataset
4. **Integration testing** - Test with data collector
5. **Deploy to staging** - Test in staging environment
6. **Deploy to production** - Use GCP deployment guide

---

**Last Updated:** 2025-12-03
**Version:** 1.0
