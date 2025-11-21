# Sprint: Intersection History Feature

**Sprint Goal**: Implement historical safety index visualization with time series charts, statistics, and export capabilities

**Sprint Duration**: 8-14 hours (estimated)
**Priority**: High
**Status**: 🛠️ Not Started

---

## Sprint Overview

### Objectives
1. Enable users to view historical safety index data for intersections
2. Provide interactive time series visualization with multiple aggregation levels
3. Display aggregate statistics (avg, min, max, high-risk count)
4. Allow CSV export of historical data
5. Implement smart defaults for time granularity selection

### Success Criteria
- ✅ User can access historical data within 2 clicks from main dashboard
- ✅ Historical chart loads in <2 seconds for 7-day period
- ✅ Data accuracy verified against Parquet storage (spot-check)
- ✅ All MVP features functional (6 must-have requirements)
- ✅ API endpoints documented in Swagger
- ✅ No regressions in existing functionality

### Out of Scope (Future Sprints)
- Multi-intersection comparison views
- Heatmap visualizations
- Separate dedicated analysis page
- Camera feed integration
- Admin validation tools

---

## Phase Breakdown

### Phase 1: Backend Core (3-4 hours)

**Goal**: Implement service layer, schemas, and API endpoints

#### Tasks

**1.1 Create Pydantic Schemas** (30 min)
- **File**: `backend/app/schemas/intersection.py` (MODIFY)
- **Add Classes**:
  - `IntersectionHistoryPoint` - Single time series data point
  - `IntersectionHistory` - Complete time series with metadata
  - `IntersectionAggregateStats` - Statistics over period
- **Fields**: timestamps, indices, traffic volume, temporal metadata
- **Validation**: Field constraints (ge=0, le=100 for SI)
- **Examples**: Add `Config.json_schema_extra` examples

**1.2 Create History Service Layer** (90 min)
- **File**: `backend/app/services/history_service.py` (NEW - ~250 lines)
- **Functions**:
  - `get_intersection_history()` - Query time series from Parquet
  - `get_aggregate_stats()` - Compute statistics
  - `get_all_intersections_history()` - Batch query
  - `_get_smart_default_aggregation()` - Auto-select granularity
  - `_aggregate_time_series()` - Resample to coarser intervals
  - `_dataframe_to_history_points()` - DataFrame → Pydantic
  - `_get_safety_index_column()` - Handle EB vs non-EB indices
- **Dependencies**: Leverage existing `parquet_storage.load_indices()`
- **Aggregation Logic**:
  - ≤1 day → 1-minute intervals
  - ≤7 days → Hourly aggregation
  - ≤30 days → Daily aggregation
  - >30 days → Weekly/monthly
- **Error Handling**: ValueError for no data, handle gaps gracefully

**1.3 Create History API Endpoints** (60 min)
- **File**: `backend/app/api/history.py` (NEW - ~200 lines)
- **Endpoints**:
  - `GET /safety/history/{id}` - Time series data
    - Query params: start_date, end_date, days, aggregation
    - Response: IntersectionHistory JSON
  - `GET /safety/history/{id}/stats` - Aggregate statistics
    - Query params: start_date, end_date, days
    - Response: IntersectionAggregateStats JSON
  - `GET /safety/history/` - All intersections (limited to 30 days)
    - Response: List[IntersectionHistory]
- **Validation**: FastAPI Query parameter validation
- **Error Codes**: 404 (no data), 400 (invalid params), 500 (server error)
- **Documentation**: Docstrings for OpenAPI/Swagger

**1.4 Register Router** (5 min)
- **File**: `backend/app/main.py` (MODIFY)
- **Change**: Import and register history router
```python
from app.api import intersection, vcc, history  # ADD history
app.include_router(history.router, prefix="/api/v1")  # ADD line
```

**1.5 Test Backend Endpoints** (30 min)
- **Tools**: curl, Postman, or pytest
- **Tests**:
  - Query existing intersection with known data
  - Test smart defaults (verify correct aggregation selected)
  - Test invalid intersection ID (expect 404)
  - Test date range validation
  - Verify response schema matches Pydantic models

**Phase 1 Deliverables**:
- ✅ `backend/app/schemas/intersection.py` (+80 lines)
- ✅ `backend/app/services/history_service.py` (NEW, ~250 lines)
- ✅ `backend/app/api/history.py` (NEW, ~200 lines)
- ✅ `backend/app/main.py` (+2 lines)
- ✅ API endpoints accessible at `/api/v1/safety/history/*`
- ✅ Swagger docs updated at `/docs`

---

### Phase 2: Frontend Foundation (2-3 hours)

**Goal**: Create UI components for historical visualization

#### Tasks

**2.1 Add Plotly Dependency** (5 min)
- **File**: `frontend/requirements.txt` (MODIFY)
- **Add Line**: `plotly>=5.18`
- **Action**: Rebuild frontend Docker container to install
```bash
docker-compose build frontend
docker-compose restart frontend
```

**2.2 Create API Client Methods** (30 min)
- **File**: `frontend/app/services/api_client.py` (MODIFY - +80 lines)
- **Add Functions**:
  - `fetch_intersection_history(intersection_id, days, aggregation)`
    - Returns: Tuple[Optional[Dict], Optional[str]]
    - Caching: @st.cache_data(ttl=300)
  - `fetch_intersection_stats(intersection_id, days)`
    - Returns: Tuple[Optional[Dict], Optional[str]]
    - Caching: @st.cache_data(ttl=300)
  - `clear_history_cache()` - Force refresh
- **Error Handling**: Timeout, connection errors, 404 responses
- **URL Construction**: Adjust base URL for history endpoints

**2.3 Create History Components** (90 min)
- **File**: `frontend/app/views/history_components.py` (NEW - ~300 lines)
- **Components**:
  - `render_time_series_chart(history_data)`
    - Plotly dual-axis chart (SI + traffic volume)
    - High-risk threshold line at SI=75
    - Interactive hover, zoom, pan
  - `render_statistics_cards(stats_data)`
    - 4 metric cards: Avg SI, Peak Risk, High-Risk Count, Avg Traffic
    - Color-coded risk levels
  - `render_date_range_selector()`
    - Preset buttons: 24hr, 7d, 30d, 90d, Custom
    - Granularity selector: Auto, 1-Min, Hourly, Daily, Weekly
    - Returns: (days, aggregation)
  - `render_historical_section(intersection_id, name)` [MAIN]
    - Combines all sub-components
    - Fetches data via API client
    - Handles loading/error states
    - CSV export button

**2.4 Test Components in Isolation** (15 min)
- **Method**: Create temporary test page or use Jupyter notebook
- **Tests**:
  - Verify chart renders with sample data
  - Check date range selector returns correct values
  - Verify statistics cards display correctly
  - Test with empty/missing data scenarios

**Phase 2 Deliverables**:
- ✅ `frontend/requirements.txt` (+1 line)
- ✅ `frontend/app/services/api_client.py` (+80 lines)
- ✅ `frontend/app/views/history_components.py` (NEW, ~300 lines)
- ✅ All components render without errors
- ✅ Plotly installed in frontend container

---

### Phase 3: Integration (1-2 hours)

**Goal**: Wire up history feature to main dashboard

#### Tasks

**3.1 Modify Details Card Component** (30 min)
- **File**: `frontend/app/views/components.py` (MODIFY)
- **Function**: `render_details_card(row)`
- **Changes**:
  - Add "📊 View Historical Data" button after existing details
  - Button triggers session state change
  - Conditionally render historical section when button clicked
```python
if st.button("📊 View Historical Data", ...):
    st.session_state['show_history'] = True
    st.session_state['history_intersection_id'] = str(row['intersection_id'])

if st.session_state.get('show_history'):
    from app.views.history_components import render_historical_section
    render_historical_section(...)
```

**3.2 Test End-to-End Flow** (30 min)
- **Actions**:
  1. Start Docker containers
  2. Open dashboard at `http://localhost:8501`
  3. Click intersection on map
  4. Click "View Historical Data" button
  5. Verify chart loads with real data
  6. Change time period → verify chart updates
  7. Download CSV → verify file contents
- **Edge Cases**:
  - Intersection with no historical data
  - Very recent intersection (minimal data)
  - Large date range (30+ days)

**3.3 Handle Session State** (15 min)
- **Issue**: Streamlit reruns can lose state
- **Solution**: Initialize session state in main.py if needed
```python
if 'show_history' not in st.session_state:
    st.session_state['show_history'] = False
```
- **Collapse History**: Add "Hide History" button to close section

**Phase 3 Deliverables**:
- ✅ `frontend/app/views/components.py` (+30 lines)
- ✅ `frontend/app/views/main.py` (+10 lines for session state init)
- ✅ End-to-end user flow functional
- ✅ History section accessible from details panel

---

### Phase 4: Enhancements & Polish (2-3 hours)

**Goal**: Refine UI/UX, optimize performance, add polish

#### Tasks

**4.1 UI Polish** (45 min)
- **Improvements**:
  - Add loading spinners with descriptive messages
  - Improve error messages (user-friendly, actionable)
  - Add help text tooltips to date selectors
  - Format chart axes labels (dates, numbers)
  - Consistent color scheme across components
  - Responsive layout (handle narrow screens gracefully)
- **Visual Refinements**:
  - Adjust chart height (400-500px optimal)
  - Add dividers between sections
  - Use st.expander for CSV export section
  - Add data preview (first 10 rows) in export expander

**4.2 Performance Optimization** (30 min)
- **Caching**:
  - Verify @st.cache_data is applied to API calls
  - Test cache invalidation (change date range)
  - Add "Refresh Data" button to clear cache if needed
- **Query Optimization**:
  - Ensure Parquet column projection (only read needed columns)
  - Verify date partition pruning (only load relevant files)
  - Test query time for 7-day, 30-day, 90-day periods
- **Target**: <2 seconds for 7-day, <5 seconds for 30-day

**4.3 CSV Export Enhancement** (15 min)
- **Features**:
  - Include all relevant columns in export
  - Add metadata header (intersection name, date range)
  - Descriptive filename: `history_{intersection_id}_{start}_{end}.csv`
  - Test opening in Excel/Google Sheets

**4.4 Accessibility** (15 min)
- **Color Contrast**: Ensure SI line visible for colorblind users
- **Alt Text**: Add chart descriptions for screen readers
- **Keyboard Navigation**: Verify button focus states

**Phase 4 Deliverables**:
- ✅ Polished UI with consistent styling
- ✅ Performance targets met (<2s for 7-day queries)
- ✅ Export functionality fully tested
- ✅ Accessibility considerations addressed

---

### Phase 5: Documentation & Testing (1-2 hours)

**Goal**: Document feature, write tests, update guides

#### Tasks

**5.1 Update API Documentation** (15 min)
- **File**: `backend/app/api/history.py`
- **Action**: Verify docstrings are comprehensive
- **Test**: Open Swagger UI at `http://localhost:8001/docs`
- **Verify**:
  - All endpoints listed under "Safety Index History" tag
  - Request/response schemas documented
  - Example requests visible
  - Error codes explained

**5.2 Write Unit Tests** (45 min)
- **File**: `backend/tests/test_history_service.py` (NEW)
- **Tests**:
  - `test_smart_default_aggregation()` - Verify date range logic
  - `test_aggregate_time_series()` - Verify aggregation math
  - `test_dataframe_to_history_points()` - Verify conversion
  - `test_handle_missing_data()` - Verify gap handling
- **File**: `backend/tests/test_history_api.py` (NEW)
- **Tests**:
  - `test_get_history_endpoint()` - 200 response with data
  - `test_get_stats_endpoint()` - Statistics calculated correctly
  - `test_invalid_intersection()` - 404 error handling
  - `test_date_validation()` - 400 for invalid dates

**5.3 Manual Testing Checklist** (30 min)
- [ ] Click intersection → detail panel opens
- [ ] Click "View Historical Data" → section expands
- [ ] Default shows 7 days of data
- [ ] Chart displays safety index line and traffic volume bars
- [ ] High-risk threshold line visible at SI=75
- [ ] Statistics cards show correct values
- [ ] Change time period to "Last 24 Hours" → chart updates to 1-min data
- [ ] Change time period to "Last 30 Days" → chart updates to daily data
- [ ] Manual aggregation override works (select "Hourly" for 30-day period)
- [ ] Export CSV button downloads file
- [ ] CSV opens in Excel with correct data
- [ ] Click different intersection → history updates
- [ ] Error handling: query intersection with no data → shows helpful message
- [ ] Performance: 7-day query completes in <2 seconds

**5.4 Update User Documentation** (15 min)
- **File**: `memory-bank/operational-guide.md` (MODIFY)
- **Add Section**: "Viewing Historical Safety Data"
  - How to access history feature
  - Explanation of time granularities
  - How to export data
  - Interpreting the chart

**5.5 Update Project Documentation** (15 min)
- **File**: `README.md` or appropriate doc
- **Update**: List of features (add "Historical analysis")
- **File**: `construction/sprint-plan.md`
- **Update**: Mark this sprint as completed

**Phase 5 Deliverables**:
- ✅ Unit tests passing (90%+ coverage for new code)
- ✅ API documentation complete in Swagger
- ✅ Manual testing checklist 100% passed
- ✅ User documentation updated
- ✅ Project documentation reflects new feature

---

## Dependencies & Blockers

### Prerequisites
- ✅ Parquet storage with 1-minute interval data (EXISTS)
- ✅ Existing API framework (FastAPI) (EXISTS)
- ✅ Existing frontend framework (Streamlit) (EXISTS)
- ✅ Docker compose setup (EXISTS)

### External Dependencies
- Plotly library (will be added to requirements.txt)
- No new external APIs or services required

### Potential Blockers
1. **Data Availability**: Need at least 7 days of historical data for meaningful demo
   - **Mitigation**: Use existing data from November 13-20, 2025
2. **Performance**: Large date ranges (90+ days) may be slow
   - **Mitigation**: Implement smart defaults, add warnings for large queries
3. **Container Rebuild**: Adding Plotly requires frontend container rebuild
   - **Mitigation**: Document rebuild command, test locally first

---

## Testing Strategy

### Unit Tests (Backend)
- **Framework**: pytest
- **Coverage Target**: >80% for new service code
- **Files**:
  - `backend/tests/test_history_service.py`
  - `backend/tests/test_history_api.py`
- **Key Tests**:
  - Aggregation logic correctness
  - Date range calculations
  - Schema validation
  - Error handling paths

### Integration Tests (Backend)
- **Method**: FastAPI TestClient
- **Tests**:
  - Full endpoint request/response cycle
  - Database/Parquet interaction
  - Error scenarios (404, 400, 500)

### Component Tests (Frontend)
- **Method**: Manual testing + screenshots
- **Tests**:
  - Component rendering with various data inputs
  - Loading states
  - Error states
  - Edge cases (no data, gaps)

### End-to-End Tests
- **Method**: Manual user flow testing
- **Tests**: See Phase 5.3 checklist (15 test scenarios)

### Performance Tests
- **Metrics**:
  - API response time (7-day query: <500ms, 30-day: <2s)
  - Frontend render time (<1s after data received)
  - CSV export generation (<3s for 30 days)
- **Tools**: Chrome DevTools, API timing logs

### Data Validation Tests
- **Method**: Spot-check against Parquet files
- **Tests**:
  - Random sample of 10 data points → verify match
  - Aggregation math → verify SUM/MEAN correct
  - No interpolation → verify gaps preserved

---

## Success Metrics

### Functional Metrics
- ✅ All 6 MVP user stories completed
- ✅ 100% of manual test checklist passed
- ✅ No P0/P1 bugs in production

### Performance Metrics
- ✅ 7-day query: <2 seconds (target: <500ms)
- ✅ 30-day query: <5 seconds (target: <2s)
- ✅ Chart render: <1 second after data load

### Quality Metrics
- ✅ Unit test coverage: >80% for new code
- ✅ No regression in existing features
- ✅ API documentation 100% complete (Swagger)

### User Experience Metrics
- ✅ Feature discoverable within 2 clicks
- ✅ Zero configuration required for common use cases
- ✅ Error messages are user-friendly and actionable

---

## Rollback Plan

If critical issues discovered post-deployment:

### Level 1: Feature Flag (Fastest)
1. Add feature flag in frontend config
2. Hide "View Historical Data" button if flag=False
3. API endpoints remain but unused

### Level 2: Remove Frontend Integration
1. Revert changes to `components.py`
2. Remove history button from UI
3. Keep backend endpoints for future use

### Level 3: Full Rollback
1. Remove history router registration from main.py
2. Delete history API endpoints file
3. Rebuild and redeploy containers

---

## Post-Sprint Actions

### Immediate (Within 1 Day)
- [ ] Monitor error logs for unexpected issues
- [ ] Track API response times in production
- [ ] Gather user feedback on discoverability

### Short-Term (Within 1 Week)
- [ ] Analyze usage patterns (which aggregation levels most used)
- [ ] Identify most common date ranges queried
- [ ] Document any technical debt or improvements needed

### Long-Term (Next Sprint Planning)
- [ ] Evaluate user demand for heatmap visualization
- [ ] Consider separate dedicated analysis page
- [ ] Plan camera feed integration (validation feature)
- [ ] Plan admin validation tools (next spec)

---

## Risk Assessment

### High Risk
- **Data Quality**: Historical data may have gaps or inconsistencies
  - **Mitigation**: Implement robust error handling, show warnings
  - **Impact**: Medium (degrades UX but doesn't break)

### Medium Risk
- **Performance**: Large queries could timeout or be slow
  - **Mitigation**: Smart defaults, query limits, caching
  - **Impact**: Medium (frustrates users but workaround available)

### Low Risk
- **Browser Compatibility**: Plotly may not work in older browsers
  - **Mitigation**: Document minimum browser requirements
  - **Impact**: Low (target audience uses modern browsers)

---

## Sprint Retrospective Template

### What Went Well
- [ ] TBD after sprint completion

### What Could Be Improved
- [ ] TBD after sprint completion

### Lessons Learned
- [ ] TBD after sprint completion

### Action Items
- [ ] TBD after sprint completion

---

## Appendix: File Inventory

### New Files Created
1. `backend/app/services/history_service.py` (~250 lines)
2. `backend/app/api/history.py` (~200 lines)
3. `frontend/app/views/history_components.py` (~300 lines)
4. `backend/tests/test_history_service.py` (~100 lines)
5. `backend/tests/test_history_api.py` (~80 lines)

### Files Modified
1. `backend/app/schemas/intersection.py` (+80 lines)
2. `backend/app/main.py` (+2 lines)
3. `frontend/app/services/api_client.py` (+80 lines)
4. `frontend/app/views/components.py` (+30 lines)
5. `frontend/requirements.txt` (+1 line)
6. `memory-bank/operational-guide.md` (+30 lines)

### Total Code Impact
- **New Code**: ~930 lines
- **Modified Code**: ~223 lines
- **Total Files Affected**: 11 files
- **New Files**: 5 files

---

## Sprint Timeline (Estimated)

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| Phase 1: Backend Core | 3-4 hours | Day 1 AM | Day 1 PM |
| Phase 2: Frontend Foundation | 2-3 hours | Day 1 PM | Day 2 AM |
| Phase 3: Integration | 1-2 hours | Day 2 AM | Day 2 AM |
| Phase 4: Enhancement & Polish | 2-3 hours | Day 2 PM | Day 2 PM |
| Phase 5: Documentation & Testing | 1-2 hours | Day 3 AM | Day 3 AM |
| **Total** | **9-14 hours** | | |

*Note: Timeline assumes dedicated work periods. Adjust for interruptions and context switching.*

---

## References

### Requirements Document
- [intersection-history-requirements.md](../requirements/intersection-history-requirements.md)

### Design Document
- [intersection-history-design.md](../design/intersection-history-design.md)

### Future Features
- [intersection-validation-future.md](../requirements/intersection-validation-future.md)

### Related Documentation
- [memory-bank/operational-guide.md](../../memory-bank/operational-guide.md)
- [QUICKSTART.md](../../QUICKSTART.md)
- [DOCKER_README.md](../../DOCKER_README.md)

---

**Sprint Status**: 🛠️ Ready to Start
**Last Updated**: 2025-11-20
**Sprint Owner**: TBD
**Reviewers**: TBD
