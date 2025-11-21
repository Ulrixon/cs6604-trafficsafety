# Intersection History Feature - Requirements Specification

**Feature Name**: Intersection Historical Safety Index Analysis
**Version**: 1.0
**Date**: 2025-11-20
**Status**: Draft

---

## 1. Executive Summary

### Problem Statement
Users need the ability to view and analyze historical safety index data for intersections over time. Currently, the dashboard only displays the current/latest safety index, preventing users from understanding temporal patterns, identifying trends, validating system accuracy, or investigating specific safety events.

### Solution
Implement a historical data visualization feature that allows users to:
- View safety index trends over configurable time periods
- Analyze data at multiple time granularities (1-minute, hourly, daily, weekly, monthly)
- Export historical data for further analysis
- Identify patterns and anomalies in intersection safety

### Success Criteria
- Users can access historical data within 2 clicks from the main dashboard
- Historical charts load in <2 seconds for 24-hour periods
- Data accurately reflects stored values in Parquet files
- Users can export historical data as CSV
- System supports indefinite data retention

---

## 2. User Stories

### Primary User Stories (MVP)

**US-1: View Historical Trend**
```
As a traffic engineer
I want to see a time series chart of safety index for a specific intersection
So that I can understand how safety conditions change over time
```
**Acceptance Criteria**:
- Chart displays safety index on Y-axis, time on X-axis
- User can select time range (24hr, 7day, 30day presets)
- Chart includes visual threshold line at safety index 75 (high-risk)
- Loading time <2 seconds for 24-hour period

**US-2: Analyze at Different Time Scales**
```
As a transportation researcher
I want to view safety data at different time granularities
So that I can analyze both micro-events (1-minute) and macro-trends (monthly)
```
**Acceptance Criteria**:
- System automatically selects appropriate granularity based on date range:
  - ≤24 hours → 1-minute intervals
  - ≤7 days → hourly aggregation
  - >7 days → daily aggregation
- User can manually override auto-selected granularity
- Aggregation preserves statistical accuracy (averages, not interpolation)

**US-3: Access from Intersection Details**
```
As a dashboard user
I want to access historical data directly from the intersection detail panel
So that I can quickly investigate trends without losing context
```
**Acceptance Criteria**:
- "View History" button/link appears in intersection details panel
- Clicking opens historical view inline (expandable section or tab)
- Context (intersection ID, name) is preserved

**US-4: View Summary Statistics**
```
As a traffic analyst
I want to see aggregated statistics over the selected time period
So that I can quickly understand overall safety performance
```
**Acceptance Criteria**:
- Display cards showing: Average SI, Min SI, Max SI, Std Deviation
- Display traffic volume statistics
- Display count of high-risk intervals (SI >75)
- Statistics update when date range changes

**US-5: Export Historical Data**
```
As a researcher
I want to download historical data as CSV
So that I can perform custom analysis in external tools
```
**Acceptance Criteria**:
- CSV includes all time series data points for selected range
- File named with intersection ID and date range
- Columns: timestamp, safety_index, vru_index, vehicle_index, traffic_volume
- Export button clearly visible

**US-6: Handle Missing Data Gracefully**
```
As a dashboard user
I want to see clear indicators when historical data has gaps
So that I understand data quality and don't misinterpret results
```
**Acceptance Criteria**:
- Gaps in time series are shown as breaks in line chart (not interpolated)
- System displays warning if >20% of expected data points are missing
- No historical data case shows helpful message (not error)

### Future User Stories (Post-MVP)

**US-F1: Compare Multiple Intersections**
```
As a city planner
I want to view safety trends for multiple intersections side-by-side
So that I can identify system-wide patterns and prioritize interventions
```

**US-F2: Identify Temporal Patterns (Heatmap)**
```
As a traffic operations manager
I want to see a heatmap of safety index by hour-of-day and day-of-week
So that I can identify recurring danger periods and optimize resource allocation
```

**US-F3: Advanced Analysis Page**
```
As a power user
I want a dedicated historical analysis page with advanced features
So that I can perform deep analysis including multi-intersection comparisons and congestion correlation
```

**US-F4: Visual Validation with Camera Feeds**
```
As a traffic engineer validating system accuracy
I want to view state public camera feeds for an intersection
So that I can visually verify safety events and understand ground truth
```

---

## 3. Functional Requirements

### 3.1 MVP Requirements (Must-Have)

#### FR-1: Historical Data API Endpoints
**Priority**: P0 (Critical)
- **FR-1.1**: Endpoint to retrieve time series data for single intersection
  - Path: `GET /api/v1/safety/history/{intersection_id}`
  - Query params: `start_date`, `end_date`, `days` (lookback), `aggregation`
  - Response: JSON with array of data points (timestamp, indices, volume)
- **FR-1.2**: Endpoint to retrieve aggregated statistics
  - Path: `GET /api/v1/safety/history/{intersection_id}/stats`
  - Query params: `start_date`, `end_date`, `days`
  - Response: JSON with avg, min, max, std, high-risk count
- **FR-1.3**: Endpoint to retrieve all intersections' history (limited range)
  - Path: `GET /api/v1/safety/history/`
  - Query params: `start_date`, `end_date`, `days` (max 30)
  - Response: JSON array of intersection histories

#### FR-2: Time Series Service Layer
**Priority**: P0 (Critical)
- **FR-2.1**: Service to query Parquet storage by date range
- **FR-2.2**: Service to perform time-based aggregation (1min→hourly, 1min→daily)
- **FR-2.3**: Service to compute statistics over time periods
- **FR-2.4**: Service to handle missing data (gaps, no data scenarios)

#### FR-3: Data Models/Schemas
**Priority**: P0 (Critical)
- **FR-3.1**: Pydantic schema for historical data point (timestamp, indices, volume, metadata)
- **FR-3.2**: Pydantic schema for time series response (intersection info + data points array)
- **FR-3.3**: Pydantic schema for aggregate statistics

#### FR-4: UI Components - Time Series Chart
**Priority**: P0 (Critical)
- **FR-4.1**: Interactive line chart using Plotly
- **FR-4.2**: Dual Y-axis (safety index left, traffic volume right)
- **FR-4.3**: High-risk threshold line at SI=75
- **FR-4.4**: Hover tooltips showing exact values
- **FR-4.5**: Zoom and pan capabilities

#### FR-5: UI Components - Date Range Selection
**Priority**: P0 (Critical)
- **FR-5.1**: Preset buttons: "Last 24 Hours", "Last 7 Days", "Last 30 Days"
- **FR-5.2**: Custom date range picker (start/end date)
- **FR-5.3**: Granularity selector with smart defaults:
  - Auto-select based on range OR manual override
  - Options: 1-minute, Hourly, Daily, Weekly, Monthly

#### FR-6: UI Components - Statistics Display
**Priority**: P0 (Critical)
- **FR-6.1**: Metric cards showing: Avg SI, Peak Risk SI, High-Risk Intervals, Avg Traffic Volume
- **FR-6.2**: Delta indicators showing comparison to baseline if available
- **FR-6.3**: Color-coded risk levels (green/orange/red)

#### FR-7: UI Integration
**Priority**: P0 (Critical)
- **FR-7.1**: Add "📊 View History" button to intersection details panel
- **FR-7.2**: Expandable history section appears inline when button clicked
- **FR-7.3**: History section includes: date selector, chart, statistics, export button
- **FR-7.4**: Collapsible to return to details view

#### FR-8: Data Export
**Priority**: P0 (Critical)
- **FR-8.1**: CSV export button in history view
- **FR-8.2**: File naming: `history_{intersection_id}_{start_date}_{end_date}.csv`
- **FR-8.3**: CSV columns: timestamp, safety_index, vru_index, vehicle_index, traffic_volume, hour_of_day, day_of_week

### 3.2 Future Requirements (Nice-to-Have)

#### FR-F1: Advanced Visualizations
- **FR-F1.1**: Heatmap (hour-of-day × day-of-week) showing average safety index
- **FR-F1.2**: Comparison view for multiple intersections side-by-side
- **FR-F1.3**: Overlay of traffic volume as area chart under safety index line

#### FR-F2: Dedicated Historical Analysis Page
- **FR-F2.1**: Separate navigation tab "📊 Historical Analysis"
- **FR-F2.2**: Multi-intersection selector
- **FR-F2.3**: Advanced filtering and correlation tools
- **FR-F2.4**: System-wide pattern analysis (hot times across all intersections)

#### FR-F3: Anomaly Detection
- **FR-F3.1**: Highlight unusual safety index spikes (>2 std dev from mean)
- **FR-F3.2**: Flag rapid changes (>10 point increase in <5 minutes)
- **FR-F3.3**: Pattern recognition for recurring issues

#### FR-F4: Validation & Camera Integration
- **FR-F4.1**: Link to state public camera feed for intersection (future spec)
- **FR-F4.2**: Admin tools for data validation (future spec)
- **FR-F4.3**: Raw data viewer/downloader (future spec)

---

## 4. Non-Functional Requirements

### 4.1 Performance
- **NFR-1**: Historical API endpoints respond in <500ms for 7-day queries (P0)
- **NFR-2**: Historical API endpoints respond in <2s for 30-day queries (P0)
- **NFR-3**: UI chart renders in <1s after data received (P0)
- **NFR-4**: CSV export generates in <3s for 30-day periods (P1)

### 4.2 Scalability
- **NFR-5**: System handles concurrent queries from 10+ users without degradation (P1)
- **NFR-6**: Parquet storage efficiently queries across date partitions (P0)
- **NFR-7**: API implements caching for frequently requested date ranges (P1)

### 4.3 Data Integrity
- **NFR-8**: Historical data matches raw Parquet files (100% accuracy) (P0)
- **NFR-9**: Aggregations preserve statistical properties (P0)
- **NFR-10**: No data interpolation across gaps (P0)

### 4.4 Reliability
- **NFR-11**: Historical endpoints return 404 with helpful message for non-existent data (P0)
- **NFR-12**: UI gracefully handles API failures (show cached data or error message) (P0)
- **NFR-13**: System maintains data retention indefinitely (no automatic deletion) (P0)

### 4.5 Usability
- **NFR-14**: History feature discoverable within 2 clicks from main dashboard (P0)
- **NFR-15**: Smart defaults require no user configuration for common use cases (P0)
- **NFR-16**: UI responsive on desktop and tablet (1024px+ width) (P1)

### 4.6 Maintainability
- **NFR-17**: Code follows existing project patterns (service layer, Pydantic schemas, Streamlit components) (P0)
- **NFR-18**: API documented with OpenAPI/Swagger (P0)
- **NFR-19**: Component functions have docstrings and type hints (P0)

---

## 5. Technical Specifications

### 5.1 Data Storage
**Current State**:
- Parquet files in `backend/data/parquet/indices/` directory
- File naming: `indices_YYYY-MM-DD.parquet`
- Columns include: `time_15min` (datetime), `intersection`, `Combined_Index_EB`, `VRU_Index_EB`, `Vehicle_Index_EB`, `vehicle_count`, `hour_of_day`, `day_of_week`
- **IMPORTANT**: System now operates at 1-minute intervals, not 15-minute

**Note**: Code references may show `time_15min` as column name - this is historical naming, actual data is 1-minute granularity.

### 5.2 API Endpoint Specifications

#### Endpoint 1: Get Intersection History
```
GET /api/v1/safety/history/{intersection_id}

Query Parameters:
  - start_date: string (YYYY-MM-DD) [optional]
  - end_date: string (YYYY-MM-DD) [optional]
  - days: integer (1-365) [default: 7]
  - aggregation: enum("1min", "1hour", "1day", "1week", "1month") [default: auto]

Response: 200 OK
{
  "intersection_id": "0.0",
  "intersection_name": "Intersection 0.0",
  "start_date": "2025-11-13T00:00:00Z",
  "end_date": "2025-11-20T23:59:59Z",
  "total_points": 10080,
  "data_points": [
    {
      "timestamp": "2025-11-13T00:00:00Z",
      "safety_index": 45.2,
      "vru_index": 42.1,
      "vehicle_index": 48.9,
      "traffic_volume": 94,
      "hour_of_day": 0,
      "day_of_week": 2
    },
    ...
  ]
}

Errors:
  - 404: Intersection not found or no data for period
  - 400: Invalid date format or parameter
  - 500: Server error
```

#### Endpoint 2: Get Aggregate Statistics
```
GET /api/v1/safety/history/{intersection_id}/stats

Query Parameters:
  - start_date, end_date, days (same as above)

Response: 200 OK
{
  "intersection_id": "0.0",
  "intersection_name": "Intersection 0.0",
  "period_start": "2025-11-13T00:00:00Z",
  "period_end": "2025-11-20T23:59:59Z",
  "avg_safety_index": 44.6,
  "min_safety_index": 18.2,
  "max_safety_index": 78.9,
  "std_safety_index": 12.3,
  "total_traffic_volume": 947280,
  "avg_traffic_volume": 94,
  "high_risk_intervals": 124
}
```

### 5.3 Data Aggregation Rules

**1-Minute to Hourly**:
- Safety Index: Mean of all 1-min intervals in hour
- Traffic Volume: Sum of all 1-min counts
- VRU/Vehicle Indices: Mean

**Hourly to Daily**:
- Safety Index: Mean of all hourly values
- Traffic Volume: Sum of all hourly totals
- Min/Max: Preserve extremes

**Daily to Weekly/Monthly**:
- Safety Index: Mean
- Traffic Volume: Sum
- High-Risk: Count intervals where SI >75

### 5.4 Smart Defaults Logic
```python
def get_default_aggregation(start_date, end_date):
    days = (end_date - start_date).days

    if days <= 1:
        return "1min"  # Up to 24 hours
    elif days <= 7:
        return "1hour"  # Up to 7 days
    elif days <= 30:
        return "1day"   # Up to 30 days
    elif days <= 90:
        return "1week"  # Up to 90 days
    else:
        return "1month" # Beyond 90 days
```

### 5.5 Frontend Dependencies
**New Dependencies Required**:
- `plotly` - Interactive time series charts
- Already have: `streamlit`, `pandas`, `requests`

**Update `frontend/requirements.txt`**:
```
streamlit>=1.36
requests>=2.32
pydantic>=2.6
pandas>=2.2
folium>=0.17
streamlit-folium>=0.21
plotly>=5.18  # NEW
```

---

## 6. User Interface Requirements

### 6.1 UI Integration Points

**Existing Details Panel** (`frontend/app/views/components.py:render_details_card()`):
- Add "📊 View History" button after intersection details
- Button expands historical section inline (below details)

**Historical Section Structure**:
```
┌─────────────────────────────────────────┐
│ 📍 Intersection 0.0                     │
│ ✅ Low Risk (SI: 44.6)                  │
│ ┌─────────────────────────────────────┐ │
│ │ 📊 View History                      │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [EXPANDED WHEN CLICKED]                 │
│ ┌─────────────────────────────────────┐ │
│ │ Time Period: [Last 7 Days ▼]        │ │
│ │ Granularity: [Auto (Hourly)]        │ │
│ │                                      │ │
│ │ [Line Chart: Safety Index over Time]│ │
│ │                                      │ │
│ │ ┌──┬──┬──┬──┐                        │ │
│ │ │Avg│Max│Min│HR│ [Statistics Cards] │ │
│ │ └──┴──┴──┴──┘                        │ │
│ │                                      │ │
│ │ [📥 Download CSV]                    │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 6.2 Chart Specifications

**Time Series Chart** (Plotly):
- **X-Axis**: Timestamp (formatted based on granularity)
  - 1-min: "HH:MM"
  - Hourly: "MM/DD HH:00"
  - Daily: "YYYY-MM-DD"
- **Y-Axis (Primary)**: Safety Index (0-100)
- **Y-Axis (Secondary)**: Traffic Volume (right side)
- **High-Risk Line**: Horizontal dashed line at SI=75 (red)
- **Colors**: Safety Index = red (#E74C3C), Traffic Volume = blue (#3498DB, 30% opacity)
- **Interactivity**: Hover shows exact values, zoom/pan enabled
- **Height**: 400px

### 6.3 Loading States
- Display spinner with message "Loading historical data..."
- Show skeleton/placeholder chart during initial load
- Update chart smoothly when date range changes (no full page refresh)

### 6.4 Error States
- **No Data**: "No historical data available for this intersection in the selected period."
- **API Error**: "Unable to load historical data. Please try again."
- **Partial Data**: "Warning: X% of expected data points are missing. Results may be incomplete."

---

## 7. Testing & Validation

### 7.1 Functional Testing
- **Test 1**: Verify historical endpoint returns correct data for known date range
- **Test 2**: Verify smart defaults select appropriate aggregation
- **Test 3**: Verify CSV export contains all expected columns and data
- **Test 4**: Verify chart renders with correct data points
- **Test 5**: Verify statistics calculations (avg, min, max, std)

### 7.2 Performance Testing
- **Test 6**: Measure API response time for 1-day, 7-day, 30-day queries
- **Test 7**: Measure chart render time with 1000, 5000, 10000 data points
- **Test 8**: Test concurrent user queries (10 simultaneous requests)

### 7.3 Data Validation
- **Test 9**: Spot-check 10 random data points against Parquet files
- **Test 10**: Verify no data interpolation across gaps
- **Test 11**: Verify aggregations preserve statistical properties

### 7.4 Edge Cases
- **Test 12**: Intersection with no historical data
- **Test 13**: Date range with gaps (system downtime)
- **Test 14**: Very large date range (90+ days at 1-min granularity)
- **Test 15**: Invalid intersection ID
- **Test 16**: Future date ranges

### 7.5 User Acceptance Testing
- **UAT-1**: User can access history within 2 clicks
- **UAT-2**: User can understand chart without instructions
- **UAT-3**: User can export and open CSV in Excel/Sheets

---

## 8. Dependencies & Constraints

### 8.1 Dependencies
- **Backend**: Existing Parquet storage with 1-minute interval data
- **Backend**: FastAPI framework and Pydantic
- **Frontend**: Streamlit framework
- **Frontend**: New dependency: Plotly (for charts)

### 8.2 Constraints
- **Data Granularity**: Limited to 1-minute intervals (no finer resolution)
- **Storage**: Parquet files are date-partitioned (one file per day)
- **Performance**: Large queries (>30 days at 1-min) may be slow without caching
- **Browser Compatibility**: Plotly requires modern browsers (Chrome, Firefox, Safari, Edge)

### 8.3 Assumptions
- Historical data exists for at least the past 7 days
- Parquet files follow consistent naming convention
- All safety indices include Empirical Bayes adjustments (Combined_Index_EB)
- System continues indefinite data retention (no purging)

---

## 9. Out of Scope (Future Specs)

### 9.1 Admin Validation Tools (Future Spec)
- Raw data viewer with direct Parquet file access
- Data quality metrics dashboard
- Aggregation verification tools
- Manual data correction interface

### 9.2 Camera Feed Integration (Future Spec)
- Mapping intersections to state public camera URLs
- Embedding or linking to video feeds
- Synchronizing video timestamps with safety index events
- Video clip export for incidents

### 9.3 Advanced Multi-Intersection Analysis (Future Spec)
- System-wide pattern detection (hot times across all intersections)
- Correlation analysis (congestion vs safety)
- Rerouting recommendations based on safety trends
- Predictive modeling and forecasting

### 9.4 Real-Time Updates (Future Enhancement)
- Live updating charts (WebSocket or polling)
- Real-time anomaly alerts
- Streaming data visualization

---

## 10. Acceptance Criteria Summary

### MVP is considered complete when:
1. ✅ User can click intersection on map, view details, and click "View History" button
2. ✅ Historical chart loads and displays 7 days of safety index data by default
3. ✅ User can change time period (24hr, 7d, 30d presets)
4. ✅ System automatically selects appropriate granularity (1-min, hourly, daily)
5. ✅ Statistics cards show avg, max, min safety index and high-risk count
6. ✅ User can export historical data as CSV
7. ✅ Chart loads in <2 seconds for 7-day period
8. ✅ Data matches values in Parquet storage (spot-checked)
9. ✅ System handles "no data" case gracefully (helpful message, not error)
10. ✅ API endpoints documented in Swagger/OpenAPI

---

## 11. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-20 | Claude | Initial requirements specification |

---

## 12. Appendix: Research Summary

### Current System State
- **Data Collection**: 1-minute intervals (not 15-minute despite some variable naming)
- **Storage**: Parquet files in `backend/data/parquet/indices/`
- **Existing API**: Only returns latest/current safety index per intersection
- **Frontend**: Streamlit dashboard with map, no historical views
- **Indices Computed**: VRU Index, Vehicle Index, Combined Index (with EB adjustments)

### Key File Paths (from research)
- **Backend API**: `backend/app/api/intersection.py` (current endpoints)
- **Parquet Storage**: `backend/app/services/parquet_storage.py` (has load_indices with date range)
- **Frontend Components**: `frontend/app/views/components.py`
- **Frontend Main**: `frontend/app/views/main.py`
- **API Client**: `frontend/app/services/api_client.py`

### Technical Debt Notes
- Some code refers to `time_15min` column - this is legacy naming, actual data is 1-minute
- Empirical Bayes adjustment may be missing in older data (check for `_EB` suffix columns)
- Intersection names may need better lookup mechanism (currently using ID as name)
