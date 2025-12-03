# Traffic Camera Integration Requirements

**Status:** Draft
**Branch:** feature/intersection-cameras
**Created:** 2025-12-03
**Author:** Specification Builder

---

## Executive Summary

Add traffic camera viewing capability to intersection details, allowing users to visually verify traffic conditions through links to live camera feeds from VDOT and other sources.

**Core Value Proposition:** Enable visual verification of intersection conditions to supplement quantitative safety indices with real-time visual data.

---

## Problem Statement

Users cannot access live traffic camera feeds for intersections to visually verify current traffic conditions and safety concerns. Engineers investigating safety events need quick access to visual data to validate safety index readings and understand real-world conditions.

---

## Solution Architecture

### Three-Tier Progressive Enhancement System

1. **Primary: Database Storage**
   Store known camera URLs directly in intersection records as JSON arrays

2. **Secondary: VDOT API Integration**
   Query VDOT 511 API for nearest cameras based on intersection coordinates

3. **Tertiary: Fallback Map Link**
   Provide general VDOT 511 map centered on intersection location

### UI Integration Points

- **Intersection Details Card:** Camera buttons below metrics, above "View Historical Data" button
- **Folium Map Popups:** Camera links embedded in draggable intersection popups
- **Responsive Design:** Display up to 3 camera sources when space permits

---

## Technical Specifications

### Database Schema Changes

**New Field:** `camera_urls` (JSONB, nullable)

```json
{
  "camera_urls": [
    {
      "source": "VDOT",
      "url": "https://511virginia.org/camera/CAM123",
      "label": "VDOT Camera - Main St & Elm"
    },
    {
      "source": "511",
      "url": "https://511.vdot.virginia.gov/map?lat=37.5&lon=-77.4",
      "label": "511 Map View"
    }
  ]
}
```

**Field Schema:**
- `source` (string, required): Camera provider identifier
- `url` (string, required): Full URL to camera feed or map
- `label` (string, required): User-friendly display name

### Backend Components

#### 1. Data Model Extension
**File:** `backend/app/models/intersection.py`

```python
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, validator

class CameraLink(BaseModel):
    """Individual camera link definition"""
    source: str = Field(..., min_length=1, max_length=50)
    url: str = Field(..., regex=r'^https?://')
    label: str = Field(..., min_length=1, max_length=100)

class Intersection(BaseModel):
    # ... existing fields ...
    camera_urls: Optional[List[Dict]] = Field(
        default=None,
        description="Array of camera links for this intersection"
    )

    @validator('camera_urls')
    def validate_camera_structure(cls, v):
        """Ensure camera_urls conform to CameraLink schema"""
        if v is None:
            return v
        return [CameraLink(**cam).dict() for cam in v]
```

#### 2. VDOT Camera Service
**File:** `backend/app/services/vdot_camera_service.py` (NEW)

```python
import os
import requests
from typing import List, Dict, Tuple
from math import radians, cos, sin, asin, sqrt
from functools import lru_cache

class VDOTCameraService:
    """Service for fetching VDOT traffic camera data"""

    def __init__(self):
        self.api_key = os.getenv("VDOT_API_KEY")
        self.base_url = "https://api.vdot.virginia.gov/511"
        self.cache_ttl = 300  # 5 minutes

    @lru_cache(maxsize=1000)
    def find_nearest_cameras(
        self,
        lat: float,
        lon: float,
        radius_miles: float = 0.5,
        max_results: int = 3
    ) -> List[Dict]:
        """
        Find cameras within radius of intersection coordinates

        Args:
            lat: Intersection latitude
            lon: Intersection longitude
            radius_miles: Search radius in miles (default 0.5)
            max_results: Maximum cameras to return (default 3)

        Returns:
            List of camera link dictionaries
        """
        try:
            cameras = self._fetch_vdot_cameras()
            nearby = self._filter_by_distance(cameras, lat, lon, radius_miles)

            return [
                {
                    "source": "VDOT",
                    "url": f"https://511virginia.org/camera/{cam['id']}",
                    "label": f"VDOT {cam['name']}"
                }
                for cam in nearby[:max_results]
            ]
        except Exception as e:
            # Log error but don't fail - return empty list
            print(f"VDOT API error: {e}")
            return []

    def _fetch_vdot_cameras(self) -> List[Dict]:
        """Fetch all cameras from VDOT API"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(
            f"{self.base_url}/cameras",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("cameras", [])

    def _filter_by_distance(
        self,
        cameras: List[Dict],
        lat: float,
        lon: float,
        max_distance: float
    ) -> List[Dict]:
        """Filter cameras within max_distance miles"""
        nearby = []
        for cam in cameras:
            distance = self._haversine_distance(
                lat, lon,
                cam['latitude'], cam['longitude']
            )
            if distance <= max_distance:
                nearby.append({**cam, 'distance': distance})

        # Sort by distance, closest first
        return sorted(nearby, key=lambda x: x['distance'])

    def _haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Calculate great circle distance in miles between two points

        Formula: Haversine distance
        Returns: Distance in miles
        """
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))

        # Radius of earth in miles
        miles = 3956 * c
        return miles
```

#### 3. API Endpoint Enhancement
**File:** `backend/app/api/endpoints/intersections.py`

```python
from app.services.vdot_camera_service import VDOTCameraService

camera_service = VDOTCameraService()

@router.get("/intersections/{intersection_id}")
async def get_intersection(intersection_id: int):
    """Get intersection with camera data enrichment"""
    intersection = await db.fetch_intersection(intersection_id)

    # If no camera URLs in database, try VDOT API lookup
    if not intersection.camera_urls:
        vdot_cameras = camera_service.find_nearest_cameras(
            intersection.latitude,
            intersection.longitude
        )

        # Add fallback map link
        fallback = {
            "source": "511",
            "url": f"https://511.vdot.virginia.gov/map?lat={intersection.latitude}&lon={intersection.longitude}",
            "label": "View on 511 Map"
        }

        intersection.camera_urls = vdot_cameras + [fallback]

    return intersection
```

### Frontend Components

#### 1. Camera Button Renderer
**File:** `frontend/app/views/components.py`

```python
import streamlit as st
from typing import List, Dict, Optional

def render_camera_buttons(
    camera_urls: Optional[List[Dict]],
    intersection_id: int,
    max_buttons: int = 3
):
    """
    Render camera access buttons for intersection

    Args:
        camera_urls: List of camera link dictionaries
        intersection_id: Intersection ID for unique keys
        max_buttons: Maximum buttons to display
    """
    if not camera_urls:
        return  # No cameras available

    st.markdown("#### 📹 Traffic Cameras")

    # Display up to max_buttons cameras
    for idx, camera in enumerate(camera_urls[:max_buttons]):
        # Validate required fields
        if not all(k in camera for k in ['source', 'url', 'label']):
            continue

        # Icon selection based on source
        icon = {
            'VDOT': '📹',
            '511': '🗺️',
            'TrafficLand': '📹',
        }.get(camera['source'], '🔗')

        # Styled link button
        button_html = f"""
        <a href="{camera['url']}"
           target="_blank"
           rel="noopener noreferrer"
           style="
               display: inline-block;
               padding: 10px 20px;
               margin: 5px 5px 5px 0;
               background-color: #0066cc;
               color: white;
               border-radius: 5px;
               text-decoration: none;
               font-weight: 500;
               transition: background-color 0.2s;
           "
           onmouseover="this.style.backgroundColor='#0052a3'"
           onmouseout="this.style.backgroundColor='#0066cc'">
            {icon} {camera['label']}
        </a>
        """
        st.markdown(button_html, unsafe_allow_html=True)

    # Show count if more cameras available
    if len(camera_urls) > max_buttons:
        st.caption(f"+ {len(camera_urls) - max_buttons} more camera(s) available")
```

#### 2. Details Card Integration
**File:** `frontend/app/views/components.py` (modify existing)

```python
def render_details_card(row: pd.Series):
    """Render intersection details card with camera buttons"""
    # ... existing code for name, risk badge, metrics ...

    # Add camera buttons section (NEW)
    if row.get('camera_urls'):
        st.markdown("---")  # Separator
        render_camera_buttons(
            camera_urls=row['camera_urls'],
            intersection_id=row['intersection_id'],
            max_buttons=3
        )

    # Existing historical data button
    st.markdown("---")
    if st.button(
        "📊 View Historical Data",
        key=f"history_toggle_{row['intersection_id']}",
        use_container_width=True
    ):
        # ... existing logic ...
```

#### 3. Draggable Map Popup
**File:** `frontend/app/controllers/map_controller.py`

```python
import folium
from typing import Dict, List, Optional

def create_intersection_popup(intersection: Dict) -> folium.Popup:
    """
    Create draggable popup with camera links

    Args:
        intersection: Intersection data dict with camera_urls

    Returns:
        Folium Popup object configured as draggable
    """
    # Build camera links HTML
    camera_html = ""
    if intersection.get('camera_urls'):
        camera_html = "<div style='margin-top: 10px; border-top: 1px solid #ddd; padding-top: 8px;'>"
        camera_html += "<strong>📹 Cameras:</strong><br>"

        # Show max 2 cameras in popup (space constraint)
        for cam in intersection['camera_urls'][:2]:
            icon = '📹' if cam['source'] == 'VDOT' else '🗺️'
            camera_html += f"""
            <a href='{cam['url']}'
               target='_blank'
               rel='noopener noreferrer'
               style='color: #0066cc; text-decoration: none; display: block; margin: 3px 0;'>
                {icon} {cam['label']}
            </a>
            """
        camera_html += "</div>"

    # Complete popup HTML
    popup_html = f"""
    <div style="width: 220px; font-family: Arial, sans-serif;">
        <h4 style="margin: 0 0 10px 0;">{intersection['intersection_name']}</h4>
        <table style="width: 100%; font-size: 13px;">
            <tr>
                <td><strong>Safety Index:</strong></td>
                <td style="color: {intersection['risk_color']}; font-weight: bold;">
                    {intersection['safety_index']:.1f}
                </td>
            </tr>
            <tr>
                <td><strong>Risk Level:</strong></td>
                <td>{intersection['risk_level']}</td>
            </tr>
            <tr>
                <td><strong>Traffic:</strong></td>
                <td>{intersection['traffic_volume']:.0f}</td>
            </tr>
        </table>
        {camera_html}
    </div>
    """

    # Create draggable popup
    popup = folium.Popup(
        popup_html,
        max_width=250,
        draggable=True  # Enable drag functionality
    )

    return popup
```

---

## Implementation Phases

### Phase 1: Database & Backend API (3-4 days)

**Tasks:**
1. Create Alembic migration adding `camera_urls` JSONB column
2. Update Intersection Pydantic model with validation
3. Modify API endpoints to return camera_urls field
4. Write unit tests for model validation
5. Test migration on staging database

**Deliverables:**
- Migration script: `alembic/versions/xxx_add_camera_urls.py`
- Updated model: `backend/app/models/intersection.py`
- Unit tests: `backend/tests/test_intersection_model.py`

**Success Criteria:**
- Migration runs without errors
- API returns camera_urls as null for existing intersections
- Pydantic validation rejects malformed camera data

---

### Phase 2: VDOT API Integration (3-4 days)

**Tasks:**
1. Request VDOT API access from Iteris (email: 511_videosubscription@iteris.com)
2. Implement `VDOTCameraService` class
3. Add coordinate-based camera matching with Haversine distance
4. Implement LRU caching layer (5-minute TTL)
5. Write integration tests with mocked API responses
6. Add configuration for API credentials (environment variables)

**Deliverables:**
- Service class: `backend/app/services/vdot_camera_service.py`
- Configuration: Environment variable `VDOT_API_KEY`
- Integration tests: `backend/tests/integration/test_vdot_service.py`
- Documentation: API access setup guide

**Success Criteria:**
- Service returns cameras within 0.5 mile radius
- Haversine distance calculation accuracy within 1%
- Graceful degradation when API unavailable
- Cache reduces API calls by 80%+

---

### Phase 3: Frontend UI - Details Card (2 days)

**Tasks:**
1. Implement `render_camera_buttons()` component
2. Integrate into `render_details_card()`
3. Style buttons to match existing design system
4. Test responsive layout on mobile/tablet
5. Add empty state handling (no cameras)

**Deliverables:**
- Updated: `frontend/app/views/components.py`
- CSS styling for camera buttons
- Mobile responsive testing report

**Success Criteria:**
- Buttons appear when camera_urls exists
- No buttons shown when camera_urls is null/empty
- Links open in new tab with proper rel attributes
- Mobile buttons are touch-friendly (min 44px height)

---

### Phase 4: Frontend UI - Map Popups (2 days)

**Tasks:**
1. Update popup HTML generation with camera links
2. Enable `draggable=True` on Folium popups
3. Test popup functionality across browsers (Chrome, Firefox, Safari)
4. Adjust popup sizing for camera content
5. Test on mobile devices

**Deliverables:**
- Updated: `frontend/app/controllers/map_controller.py`
- Browser compatibility test results
- Mobile testing report (iOS/Android)

**Success Criteria:**
- Popups are draggable on desktop browsers
- Camera links work correctly from popup
- Popup size accommodates 2 camera links
- Mobile popups remain functional (may not be draggable)

---

### Phase 5: Data Population (3-4 days)

**Tasks:**
1. Create admin script to populate camera URLs
2. Run VDOT API matching for Virginia intersections
3. Manual verification of camera accuracy (sample 20 intersections)
4. Document process for adding/updating cameras
5. Create CSV template for bulk camera imports

**Deliverables:**
- Admin script: `backend/scripts/populate_camera_urls.py`
- Documentation: `docs/camera-management.md`
- CSV template: `data/camera_urls_template.csv`
- Populated data for 50+ intersections

**Success Criteria:**
- 50+ intersections have camera_urls populated
- 90%+ camera links are valid (manually verified)
- Process documented for future updates
- Bulk import tested successfully

---

### Phase 6: Testing & Documentation (2-3 days)

**Tasks:**
1. Execute comprehensive test plan (see below)
2. Fix bugs discovered during testing
3. Write user documentation for camera features
4. Create admin guide for camera management
5. Performance testing (page load times)

**Deliverables:**
- Test results report
- Bug fix commits
- User guide: `docs/user-guide-cameras.md`
- Admin guide: `docs/admin-camera-management.md`
- Performance test results

**Success Criteria:**
- All test scenarios pass
- Page load time < 2 seconds with camera data
- Documentation reviewed and approved
- Zero high-priority bugs

---

## Comprehensive Test Plan

### A. Manual Testing

#### A1. Intersection Details Card
- [ ] **Test 1.1:** Intersection with camera_urls displays buttons
- [ ] **Test 1.2:** Intersection without camera_urls shows no camera section
- [ ] **Test 1.3:** Clicking camera button opens new tab
- [ ] **Test 1.4:** Multiple cameras display correctly (up to 3)
- [ ] **Test 1.5:** More than 3 cameras shows count indicator
- [ ] **Test 1.6:** Button hover effects work
- [ ] **Test 1.7:** Camera section appears below metrics, above historical data button

#### A2. Map Popup Testing
- [ ] **Test 2.1:** Popup displays camera links when available
- [ ] **Test 2.2:** Popup is draggable on desktop
- [ ] **Test 2.3:** Camera links work from popup
- [ ] **Test 2.4:** Popup max shows 2 cameras (space constraint)
- [ ] **Test 2.5:** Popup renders correctly on mobile (draggable may fail)

#### A3. VDOT API Integration
- [ ] **Test 3.1:** Intersection with no DB cameras triggers API lookup
- [ ] **Test 3.2:** API returns cameras within 0.5 mile radius
- [ ] **Test 3.3:** Fallback map link always included
- [ ] **Test 3.4:** API timeout/error shows fallback map link only
- [ ] **Test 3.5:** Cache reduces repeated API calls

---

### B. Test with Data Scenarios

#### B1. Database Camera Data
- [ ] **Test DB.1:** Intersection with 1 camera in database
- [ ] **Test DB.2:** Intersection with 3 cameras in database
- [ ] **Test DB.3:** Intersection with 5 cameras (should show 3 + count)
- [ ] **Test DB.4:** Intersection with empty camera_urls array
- [ ] **Test DB.5:** Intersection with null camera_urls

#### B2. API Fallback Scenarios
- [ ] **Test API.1:** No DB cameras, API returns 2 nearby cameras
- [ ] **Test API.2:** No DB cameras, API returns 0 cameras (shows map only)
- [ ] **Test API.3:** No DB cameras, API timeout (shows map only)
- [ ] **Test API.4:** No DB cameras, API error (shows map only)

---

### C. External Link Validation

#### C1. Click-Through Testing
- [ ] **Test C.1:** VDOT camera link opens correct camera feed
- [ ] **Test C.2:** 511 map link opens centered on intersection
- [ ] **Test C.3:** Links open in new tab (not replacing app)
- [ ] **Test C.4:** Links have proper `rel="noopener noreferrer"` attributes
- [ ] **Test C.5:** Dead/broken camera links return 404 (user sees VDOT error page)

---

### D. VDOT API Integration Tests

#### D1. API Connectivity
- [ ] **Test D.1:** Valid API key authenticates successfully
- [ ] **Test D.2:** Invalid API key returns 401 error (graceful fallback)
- [ ] **Test D.3:** API rate limit hit (graceful degradation)
- [ ] **Test D.4:** API returns unexpected JSON structure (error handling)

#### D2. Coordinate Matching
- [ ] **Test D.2.1:** Camera 0.1 miles away is included
- [ ] **Test D.2.2:** Camera 0.6 miles away is excluded (radius = 0.5)
- [ ] **Test D.2.3:** Multiple cameras sorted by distance (closest first)
- [ ] **Test D.2.4:** Edge case: Intersection on state border

---

### E. Coordinate-Based Fallback Matching

#### E1. Distance Calculation
- [ ] **Test E.1:** Haversine distance calculation accuracy (± 1%)
- [ ] **Test E.2:** Edge case: Intersection at North/South pole
- [ ] **Test E.3:** Edge case: Intersection crossing 180° longitude

#### E2. Radius Filtering
- [ ] **Test E.4:** Cameras within 0.5 miles included
- [ ] **Test E.5:** Cameras beyond 0.5 miles excluded
- [ ] **Test E.6:** Zero cameras within radius shows map fallback only

---

### F. Draggable Popup Functionality

#### F1. Desktop Browsers
- [ ] **Test F.1:** Chrome - popup draggable
- [ ] **Test F.2:** Firefox - popup draggable
- [ ] **Test F.3:** Safari - popup draggable
- [ ] **Test F.4:** Edge - popup draggable

#### F2. Mobile Devices
- [ ] **Test F.5:** iOS Safari - popup displays correctly
- [ ] **Test F.6:** Android Chrome - popup displays correctly
- [ ] **Test F.7:** Mobile - camera links functional (drag may not work)

---

### G. Mobile Device Testing

#### G1. Responsive Layout
- [ ] **Test G.1:** Buttons stack properly on mobile
- [ ] **Test G.2:** Button text doesn't overflow
- [ ] **Test G.3:** Touch targets minimum 44px height
- [ ] **Test G.4:** Camera section doesn't break details card layout

#### G2. External Links on Mobile
- [ ] **Test G.5:** Camera links open in mobile browser
- [ ] **Test G.6:** 511 map link works on mobile
- [ ] **Test G.7:** Multiple cameras accessible on mobile

---

### H. Automated Tests

#### H1. Unit Tests
```python
# backend/tests/test_intersection_model.py
def test_camera_urls_validation():
    """Valid camera_urls accepted"""

def test_camera_urls_invalid_structure():
    """Invalid camera_urls rejected"""

def test_camera_urls_null():
    """Null camera_urls allowed"""

# backend/tests/test_vdot_service.py
def test_haversine_distance():
    """Distance calculation accuracy"""

def test_find_nearest_cameras():
    """API returns nearest cameras"""

def test_api_error_handling():
    """Graceful degradation on API failure"""
```

#### H2. Integration Tests
```python
# backend/tests/integration/test_camera_endpoint.py
def test_intersection_with_camera_urls():
    """API returns camera_urls from database"""

def test_intersection_without_camera_urls():
    """API triggers VDOT lookup"""

def test_vdot_api_fallback():
    """API failure returns map link"""
```

#### H3. End-to-End Tests
- [ ] **Test E2E.1:** Full user flow: select intersection → see cameras → click link
- [ ] **Test E2E.2:** Intersection without cameras shows no camera section
- [ ] **Test E2E.3:** Map popup interaction with camera links

---

### I. Performance Testing

#### I1. Page Load Performance
- [ ] **Test P.1:** Dashboard load time < 2 seconds with camera data
- [ ] **Test P.2:** Details card render time < 500ms
- [ ] **Test P.3:** Map popup creation < 100ms

#### I2. API Performance
- [ ] **Test P.4:** VDOT API response time < 1 second
- [ ] **Test P.5:** Cached API responses < 10ms
- [ ] **Test P.6:** Concurrent API calls (10 intersections) < 3 seconds

---

### Regression Testing Checklist

**CRITICAL: Do NOT break existing functionality**

#### R1. Intersection Display
- [ ] **Regression R.1:** Intersection name displays correctly
- [ ] **Regression R.2:** Risk badge shows correct level
- [ ] **Regression R.3:** Safety index formatted correctly
- [ ] **Regression R.4:** Latitude/longitude display unchanged

#### R2. Historical Data Button
- [ ] **Regression R.5:** "View Historical Data" button works
- [ ] **Regression R.6:** Historical charts render correctly
- [ ] **Regression R.7:** Toggle state persists correctly

#### R3. Map Display
- [ ] **Regression R.8:** Map markers appear correctly
- [ ] **Regression R.9:** Marker colors based on safety index
- [ ] **Regression R.10:** Marker size based on traffic volume
- [ ] **Regression R.11:** Legend displays correctly

#### R4. Filters & Search
- [ ] **Regression R.12:** Text search works
- [ ] **Regression R.13:** Safety index slider filters
- [ ] **Regression R.14:** Traffic volume slider filters
- [ ] **Regression R.15:** Filters update map correctly

#### R5. Data Table
- [ ] **Regression R.16:** Table displays all columns
- [ ] **Regression R.17:** Sorting works correctly
- [ ] **Regression R.18:** CSV download works
- [ ] **Regression R.19:** Data accuracy unchanged

---

## Critical Questions from Technical Review

### Skeptical Technical Lead Questions

1. **Business Value: What's the 20% that gives 80% value?**
   - Why integrate static camera URLs instead of focusing on safety prediction accuracy?
   - If crash correlation (Phase 7) validates the safety index at 85%+ AUC, do engineers need camera verification?
   - Should we defer this until Phase 7 crash analysis is complete?

2. **Technical Risk: Hidden VDOT API dependency**
   - Which VDOT API specifically? Public or private?
   - Rate limits and SLA guarantees?
   - What happens when API is down?
   - Fallback behavior for intersections without cameras?

3. **Maintenance: Who owns this long-term?**
   - Who maintains camera URL mappings when intersections change?
   - Where does camera metadata live (config file, database, env vars)?
   - Who updates `available` flags when cameras go offline?
   - What's the operational overhead?

4. **Alternatives: Why not existing solutions?**
   - Google Street View API already has intersection imagery
   - Third-party aggregators (ClearFlow, Waze) maintain camera databases
   - Could users just open VDOT in separate browser tab?
   - Why not QR codes linking to VDOT (zero integration)?

5. **Complexity vs. ROI: Is progressive enhancement justified?**
   - Tier 1 (direct URLs): 1-2 days, 80% value
   - Tier 2 (API lookup): 3-5 days, 15% additional value
   - Tier 3 (fallback): 2-3 days, 5% edge cases
   - Why not ship Tier 1, measure usage, then decide on Tier 2/3?

6. **Data Quality: Sync with reality**
   - Does VDOT change camera IDs/URLs without notice?
   - How to keep camera mappings in sync with intersection renames?
   - How often is `available` flag updated?
   - At 100+ intersections, this becomes a support burden

7. **Validation Workflow: Real problem?**
   - How often do engineers actually need camera validation?
   - Is this solving a model validation problem with a UI band-aid?
   - Would improving Phase 7 correlation eliminate need for cameras?

---

### Quality/Operations Engineer Questions

1. **Testing: Fallback chain validation**
   - How to test transitions between database → API → fallback?
   - Test scenario when VDOT API unavailable?
   - How to verify draggable popups in automated tests?
   - Catch JavaScript errors preventing drag functionality?

2. **Monitoring: Production failure detection**
   - Key metrics: VDOT API response times, camera URL resolution rates, fallback frequency?
   - Alert thresholds for API failures?
   - Distinguish legitimate "no cameras" from failed API calls?
   - How to detect corrupt camera_urls JSON in database?
   - Log fallback activations without excessive overhead?

3. **Debugging: 3am production issues**
   - If camera links break, what logging exists?
   - How to diagnose JSON schema mismatches after deployment?
   - VDOT API credential rotation - how to trace root cause?
   - Client-side error logging for popup JavaScript failures?
   - How to reproduce intersection-specific failures?

4. **User Experience: Feature state communication**
   - When intersection has no cameras, hide button or show disabled state?
   - Visual feedback for draggable popups?
   - Loading spinner during slow VDOT API lookups?
   - What happens on API timeout - error or fallback?
   - Progressive enhancement delay - is there user communication?

5. **Data Quality: Invalid values**
   - Invalid JSON in camera_urls - caught when?
   - Coordinate drift causing wrong camera matches?
   - Backend serialization bug (JSON string vs. array)?

6. **Integration: Testing without false positives**
   - How to test Mode 1 without triggering Mode 2?
   - VDOT API credentials in Cloud Run - secure?
   - Test data leakage across environments?

7. **Load & Cost: API query overhead**
   - 100+ intersections on dashboard = thundering herd?
   - Cache level: frontend, backend, database?
   - VDOT rate limits - what's the fallback?
   - Does repeated panel open/close call API each time?

---

## Risk Mitigation Strategies

### High Priority Risks

**Risk 1: VDOT API Dependency**
- **Mitigation:** Implement robust caching (5-min TTL), graceful degradation to map fallback
- **Monitoring:** Track API availability, alert on >10% failure rate

**Risk 2: Data Quality (stale/invalid camera URLs)**
- **Mitigation:** JSON schema validation, weekly automated link checker
- **Process:** Quarterly camera URL audit and cleanup

**Risk 3: Performance Impact**
- **Mitigation:** LRU cache, async API calls, max 3 cameras per intersection
- **Target:** Page load time increase < 200ms

**Risk 4: Scope Creep**
- **Mitigation:** Ship Tier 1 (database URLs) first, validate usage before Tier 2/3
- **Decision Point:** If <5% click-through rate, consider deprecating

---

## Success Metrics

### Launch Criteria (Week 1)
- [ ] 50+ intersections with camera_urls populated
- [ ] Camera buttons render without errors
- [ ] External links open correctly
- [ ] Zero regression bugs in existing features

### Adoption Metrics (Month 1)
- Camera button click-through rate > 10%
- VDOT API availability > 95%
- User feedback: 80%+ positive sentiment

### Long-Term Health (Month 3)
- Camera URL accuracy > 90% (manual audit)
- API cache hit rate > 80%
- Support tickets < 2/month

---

## Rollout Plan

### Stage 1: Staging Deployment
- Deploy to staging environment
- Test with 10 sample intersections
- Validate camera links manually
- Performance testing

### Stage 2: Canary Release (10%)
- Feature flag enabled for 10% traffic
- Monitor error rates, performance
- Gather user feedback
- Fix critical bugs

### Stage 3: Gradual Rollout
- 25% traffic (Week 1)
- 50% traffic (Week 2)
- 100% traffic (Week 3)
- Monitor at each stage

### Stage 4: Post-Launch
- Weekly camera URL audits
- Monthly usage analysis
- Quarterly feature review

---

## Documentation Deliverables

1. **User Guide:** How to use camera features
2. **Admin Guide:** How to add/update camera URLs
3. **API Documentation:** VDOT service integration
4. **Runbook:** Troubleshooting camera issues
5. **Architecture Decision Record (ADR):** Why this approach

---

## Dependencies

### External
- VDOT API access approval (email Iteris)
- VDOT API key provisioning
- Camera URL data sources

### Internal
- Database migration approval
- Security review for external links
- UX review for button placement

---

## Open Questions

1. Should we require camera link disclaimers (legal/privacy)?
2. Do we need analytics tracking on camera link clicks?
3. Should admin have UI to manage camera URLs (vs. direct DB)?
4. Mobile app considerations (future)?
5. Accessibility: screen reader support for camera buttons?

---

## Approval Checklist

- [ ] Technical Lead review
- [ ] QA Engineer review
- [ ] Security review (external links, API keys)
- [ ] UX/Design review
- [ ] Product Owner approval
- [ ] Database migration approval
- [ ] Documentation complete

---

**End of Specification**
