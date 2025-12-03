# Camera Integration - Test Plan

**Feature:** Traffic Camera Integration
**Branch:** `feature/intersection-cameras`
**Date:** 2025-12-03

---

## Pre-Test Setup

### 1. Database Migration

```bash
# Apply migration
psql $DATABASE_URL -f backend/db/init/03_add_camera_urls.sql

# Verify column exists
psql $DATABASE_URL -c "
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name='intersections' AND column_name='camera_urls';
"
```

**Expected Output:**
```
 column_name  | data_type
--------------+-----------
 camera_urls  | jsonb
```

✅ **Pass** | ❌ **Fail**

---

### 2. Environment Configuration

```bash
# Optional: Set VDOT API key
export VDOT_API_KEY="your-key-here"

# Verify environment
echo "DATABASE_URL: ${DATABASE_URL:0:20}..."
echo "VDOT_API_KEY: ${VDOT_API_KEY:+SET}${VDOT_API_KEY:-NOT SET}"
```

✅ **Pass** | ❌ **Fail**

---

## Test Suite 1: Backend Unit Tests

### Test 1.1: Camera URL Validation

```bash
cd backend
python -c "
from app.schemas.intersection import CameraLink, IntersectionRead

# Test 1: Valid camera link
cam = CameraLink(source='VDOT', url='https://test.com', label='Test')
print('✓ Valid camera link accepted')

# Test 2: Invalid URL (should fail)
try:
    CameraLink(source='VDOT', url='ftp://invalid.com', label='Test')
    print('✗ Invalid URL accepted (FAIL)')
except:
    print('✓ Invalid URL rejected')

# Test 3: Intersection with camera_urls
data = {
    'intersection_id': 1,
    'intersection_name': 'Test',
    'safety_index': 65.0,
    'index_type': 'RT-SI',
    'traffic_volume': 250,
    'longitude': -77.0,
    'latitude': 38.8,
    'camera_urls': [{'source': 'VDOT', 'url': 'https://test.com', 'label': 'Cam1'}]
}
intersection = IntersectionRead(**data)
print(f'✓ Intersection with {len(intersection.camera_urls)} camera(s)')
"
```

**Expected Output:**
```
✓ Valid camera link accepted
✓ Invalid URL rejected
✓ Intersection with 1 camera(s)
```

✅ **Pass** | ❌ **Fail**

---

### Test 1.2: VDOT Service

```bash
cd backend
python -c "
from app.services.vdot_camera_service import VDOTCameraService

service = VDOTCameraService()

# Test distance calculation
distance = service._haversine_distance(37.5407, -77.4360, 37.2296, -80.4139)
print(f'Distance Richmond-Blacksburg: {distance:.1f} miles')
assert 160 < distance < 170, f'Distance calculation off: {distance}'
print('✓ Haversine distance accurate')

# Test fallback
fallback = service.get_fallback_map_link(37.5, -77.4)
assert fallback['source'] == '511', 'Fallback source incorrect'
assert 'lat=37.5' in fallback['url'], 'Fallback URL incorrect'
print('✓ Fallback map link generated')

print('\\nAll backend tests passed!')
"
```

**Expected Output:**
```
Distance Richmond-Blacksburg: 164.8 miles
✓ Haversine distance accurate
✓ Fallback map link generated

All backend tests passed!
```

✅ **Pass** | ❌ **Fail**

---

## Test Suite 2: Database Operations

### Test 2.1: Insert Camera Data

```bash
psql $DATABASE_URL << 'EOF'
-- Add test camera to intersection 0
UPDATE intersections
SET camera_urls = '[
    {
        "source": "VDOT",
        "url": "https://511virginia.org/camera/TEST123",
        "label": "Test VDOT Camera"
    },
    {
        "source": "511",
        "url": "https://511.vdot.virginia.gov/map?lat=37.2296&lon=-80.4139",
        "label": "View on 511 Map"
    }
]'::jsonb
WHERE id = 0;

-- Verify
SELECT id, name, jsonb_array_length(camera_urls) as camera_count
FROM intersections
WHERE id = 0;
EOF
```

**Expected Output:**
```
 id |              name               | camera_count
----+---------------------------------+--------------
  0 | Test Intersection - Blacksburg  |            2
```

✅ **Pass** | ❌ **Fail**

---

### Test 2.2: Query Validation Function

```bash
psql $DATABASE_URL << 'EOF'
-- Test valid structure
SELECT validate_camera_url_structure('[
    {"source": "VDOT", "url": "https://test.com", "label": "Test"}
]'::jsonb) as is_valid;

-- Test invalid structure (missing label)
SELECT validate_camera_url_structure('[
    {"source": "VDOT", "url": "https://test.com"}
]'::jsonb) as is_valid;
EOF
```

**Expected Output:**
```
 is_valid
----------
 t        <- First query (valid)

 is_valid
----------
 f        <- Second query (invalid)
```

✅ **Pass** | ❌ **Fail**

---

## Test Suite 3: Admin Script

### Test 3.1: List Intersections

```bash
cd backend
python scripts/populate_camera_urls.py --list
```

**Expected Output:**
```
📍 Intersections (X total)
================================================================================
📹 ID 0: Test Intersection - Blacksburg, VA
   Location: (37.2296, -80.4139)
   Cameras: 2
      - VDOT: Test VDOT Camera
      - 511: View on 511 Map

⚫ ID 1: ...
   Location: (...)
   Cameras: 0
```

✅ **Pass** | ❌ **Fail**

---

### Test 3.2: Manual Camera Addition

```bash
cd backend
python scripts/populate_camera_urls.py --add \
    --intersection-id 0 \
    --source "TrafficLand" \
    --url "https://trafficland.com/camera/test456" \
    --label "TrafficLand Test Camera"
```

**Expected Output:**
```
✅ Updated intersection 0 with 3 camera(s)
   - VDOT: Test VDOT Camera
   - 511: View on 511 Map
   - TrafficLand: TrafficLand Test Camera
```

✅ **Pass** | ❌ **Fail**

---

### Test 3.3: Clear Cameras

```bash
cd backend
python scripts/populate_camera_urls.py --clear --intersection-id 0

# Verify
python scripts/populate_camera_urls.py --list | grep "ID 0:" -A 3
```

**Expected Output:**
```
✅ Cleared camera URLs for intersection 0

⚫ ID 0: Test Intersection - Blacksburg, VA
   Location: (37.2296, -80.4139)
   Cameras: 0
```

✅ **Pass** | ❌ **Fail**

---

## Test Suite 4: Frontend Integration

### Test 4.1: Camera Buttons in Details Card

**Setup:**
```bash
# Re-add test cameras
cd backend
python scripts/populate_camera_urls.py --add \
    --intersection-id 0 \
    --source "VDOT" \
    --url "https://511virginia.org/camera/TEST" \
    --label "Test Camera"

# Start frontend
cd ../frontend
streamlit run pages/0_🏠_Dashboard.py
```

**Manual Steps:**
1. Open dashboard in browser
2. Click on intersection marker (ID 0)
3. Scroll to bottom of details card

**Expected:**
- [ ] "📹 Traffic Cameras:" section appears
- [ ] Blue button labeled "📹 Test Camera"
- [ ] Button has hover effect (darkens on mouse over)
- [ ] Button is full-width
- [ ] Clicking button opens new tab to camera URL

✅ **Pass** | ❌ **Fail**

---

### Test 4.2: Map Popup Cameras

**Manual Steps:**
1. Refresh dashboard
2. Click on intersection marker (ID 0) on map
3. Check popup content

**Expected:**
- [ ] Popup contains camera section
- [ ] "📹 Cameras:" label appears
- [ ] "📹 Test Camera" link appears
- [ ] Link is clickable
- [ ] Clicking link opens new tab
- [ ] Popup is draggable (can be moved on map)

✅ **Pass** | ❌ **Fail**

---

### Test 4.3: Multiple Cameras

**Setup:**
```bash
cd backend
python scripts/populate_camera_urls.py --add \
    --intersection-id 0 \
    --source "VDOT" \
    --url "https://511virginia.org/camera/CAM2" \
    --label "Second Camera"

python scripts/populate_camera_urls.py --add \
    --intersection-id 0 \
    --source "511" \
    --url "https://511.vdot.virginia.gov/map?lat=37.2&lon=-80.4" \
    --label "511 Map View"
```

**Manual Steps:**
1. Refresh dashboard
2. Click intersection 0

**Expected - Details Card:**
- [ ] Shows "3 camera(s)" or displays 3 buttons
- [ ] All 3 cameras visible
- [ ] Buttons stack vertically

**Expected - Map Popup:**
- [ ] Shows 2 cameras (max for popup)
- [ ] First 2 cameras from list displayed

✅ **Pass** | ❌ **Fail**

---

### Test 4.4: No Cameras

**Setup:**
```bash
cd backend
python scripts/populate_camera_urls.py --clear --intersection-id 0
```

**Manual Steps:**
1. Refresh dashboard
2. Click intersection 0

**Expected:**
- [ ] NO "Traffic Cameras" section appears
- [ ] Details card shows normal metrics only
- [ ] Map popup has no camera section
- [ ] No errors in browser console

✅ **Pass** | ❌ **Fail**

---

## Test Suite 5: Regression Tests

### Test 5.1: Existing Functionality

**Manual Steps:**
1. Open dashboard
2. Verify all existing features work:

- [ ] KPI cards display correctly
- [ ] Map renders with markers
- [ ] Marker colors based on safety index
- [ ] Marker size based on traffic volume
- [ ] Clicking marker shows details
- [ ] "View Historical Data" button works
- [ ] Historical charts render
- [ ] Filters work (search, safety index, traffic volume)
- [ ] Data table displays
- [ ] CSV download works

✅ **Pass** | ❌ **Fail**

---

### Test 5.2: API Response Format

```bash
# Test API endpoint
curl http://localhost:8000/api/v1/safety/index/ | jq '.[0]' | head -20
```

**Expected:**
```json
{
  "intersection_id": 101,
  "intersection_name": "...",
  "safety_index": 63.0,
  "traffic_volume": 253,
  "latitude": 38.856,
  "longitude": -77.053,
  "camera_urls": null  # or array if cameras exist
}
```

- [ ] API returns without errors
- [ ] camera_urls field present (can be null)
- [ ] Other fields unchanged

✅ **Pass** | ❌ **Fail**

---

## Test Suite 6: Performance Tests

### Test 6.1: Page Load Time

**Manual Steps:**
1. Open browser developer tools (F12)
2. Go to Network tab
3. Refresh dashboard
4. Check "DOMContentLoaded" time

**Expected:**
- [ ] Page loads in < 3 seconds
- [ ] No significant slowdown vs. before camera integration

✅ **Pass** | ❌ **Fail**

---

### Test 6.2: API Response Time

```bash
# Time API request
time curl -s http://localhost:8000/api/v1/safety/index/ > /dev/null
```

**Expected:**
- Response time < 2 seconds

✅ **Pass** | ❌ **Fail**

---

## Test Suite 7: Edge Cases

### Test 7.1: Invalid Camera URL Data

```bash
# Insert malformed JSON
psql $DATABASE_URL << 'EOF'
UPDATE intersections
SET camera_urls = 'invalid json'::jsonb
WHERE id = 0;
EOF
```

**Expected:**
- Database rejects invalid JSON (error thrown)

✅ **Pass** | ❌ **Fail**

---

### Test 7.2: Missing Required Fields

```bash
psql $DATABASE_URL << 'EOF'
UPDATE intersections
SET camera_urls = '[{"source": "VDOT"}]'::jsonb  -- Missing url and label
WHERE id = 0;
EOF
```

**Expected:**
- [ ] Frontend loads without crashing
- [ ] Details card renders (may hide camera section or skip invalid camera)
- [ ] No JavaScript errors in console

✅ **Pass** | ❌ **Fail**

---

## Test Suite 8: Mobile Testing

### Test 8.1: Mobile Responsiveness

**Manual Steps:**
1. Open dashboard on mobile device or Chrome DevTools mobile view
2. Click intersection
3. Check camera buttons

**Expected:**
- [ ] Camera buttons full-width
- [ ] Buttons easily tappable (min 44px height)
- [ ] Text doesn't overflow
- [ ] Links open in new tab
- [ ] Map popup functional (drag may not work on mobile)

✅ **Pass** | ❌ **Fail**

---

## Test Summary

### Results

| Test Suite | Tests | Pass | Fail | Notes |
|-----------|-------|------|------|-------|
| 1. Backend Unit Tests | 2 | | | |
| 2. Database Operations | 2 | | | |
| 3. Admin Script | 3 | | | |
| 4. Frontend Integration | 4 | | | |
| 5. Regression Tests | 2 | | | |
| 6. Performance Tests | 2 | | | |
| 7. Edge Cases | 2 | | | |
| 8. Mobile Testing | 1 | | | |
| **TOTAL** | **18** | | | |

---

## Known Issues

Document any issues found during testing:

1. **Issue:** [Description]
   - **Severity:** High/Medium/Low
   - **Steps to Reproduce:** [...]
   - **Expected:** [...]
   - **Actual:** [...]

---

## Sign-Off

- [ ] All critical tests passing
- [ ] No high-severity bugs
- [ ] Medium/low bugs documented
- [ ] Feature ready for production

**Tester:** ________________
**Date:** ________________
**Signature:** ________________

---

## Cleanup (After Testing)

```bash
# Optional: Remove test cameras
cd backend
python scripts/populate_camera_urls.py --clear --intersection-id 0

# Optional: Restore production data
# (Run your production data restoration process)
```

---

**Test Plan Version:** 1.0
**Last Updated:** 2025-12-03
