# Sprint Plan - Traffic Safety Index System

## Sprint Overview

**Sprint Goal**: Implement a complete end-to-end pipeline for collecting VCC data, computing safety indices, and serving them via API.

**Sprint Duration**: Current sprint
**Last Updated**: 2025-11-20

---

## Completed Work

### 1. Infrastructure Setup ✅
- **Status**: COMPLETED
- **Description**: Set up Docker containerization for all services
- **Deliverables**:
  - PostgreSQL database (port 5433)
  - Redis cache (port 6380)
  - Backend API (port 8001)
  - Data collector service
  - Docker Compose orchestration with health checks
- **Files Created/Modified**:
  - `docker-compose.yml`
  - `backend/Dockerfile`
  - `backend/Dockerfile.collector`
  - `.env` (root level)
  - `backend/.env`

### 2. Data Collection Service ✅
- **Status**: COMPLETED
- **Description**: Continuous VCC API data collection service
- **Deliverables**:
  - Standalone data collector running every 60 seconds
  - VCC API authentication (OAuth2 JWT)
  - Raw data storage to Parquet files
  - Collection statistics and monitoring
- **Files Created/Modified**:
  - `backend/data_collector.py` - Main collection service
  - `backend/app/services/parquet_storage.py` - Added batch save methods:
    - `save_bsm_batch()`
    - `save_psm_batch()`
    - `save_mapdata_batch()`
- **Current Collection Status**:
  - ~12 BSM messages per cycle
  - 4 MapData messages (4 intersections)
  - 0 PSM messages (no pedestrians detected yet)
  - Running successfully with VCC credentials

### 3. Historical Batch Processing ✅
- **Status**: COMPLETED
- **Description**: Script to process all accumulated historical data
- **Deliverables**:
  - Complete processing pipeline:
    1. Load raw data from Parquet files
    2. Extract features at 15-minute intervals
    3. Detect VRU-vehicle and vehicle-vehicle conflicts
    4. Create master feature table
    5. Compute normalization constants
    6. Compute safety indices
    7. Apply Empirical Bayes adjustment
  - Save processed data and indices to Parquet
- **Files Created**:
  - `backend/process_historical.py` - Batch processing script
- **Usage**:
  ```bash
  python process_historical.py --days 7 --storage-path data/parquet
  ```

### 4. Real-time Processing ✅
- **Status**: COMPLETED
- **Description**: Add real-time safety index computation to data collector
- **Deliverables**:
  - Real-time feature extraction at 1-minute intervals
  - Real-time conflict detection
  - Real-time safety index computation using pre-computed normalization constants
  - Graceful degradation when normalization constants don't exist yet
- **Files Modified**:
  - `backend/data_collector.py` - Added real-time processing after data collection
- **Workflow**:
  1. Collect VCC data
  2. Save raw data to Parquet
  3. Load normalization constants (if available)
  4. Extract features and detect conflicts
  5. Compute safety indices
  6. Save indices to Parquet

---

## Current Work

### 5. API Endpoint for On-Demand Processing 🔄
- **Status**: IN PROGRESS
- **Description**: Create FastAPI endpoint to trigger processing and retrieve safety indices
- **Planned Deliverables**:
  - GET endpoint to retrieve latest safety indices for all intersections
  - GET endpoint to retrieve safety indices for specific intersection
  - GET endpoint with time range filtering
  - POST endpoint to trigger on-demand processing
  - Response caching with Redis
- **Planned Files to Modify**:
  - `backend/app/api/v1/endpoints/intersections.py`
  - `backend/app/services/safety_index_service.py` (new file)
- **Acceptance Criteria**:
  - API returns safety indices from Parquet storage
  - Time range filtering works correctly
  - Response times < 500ms with caching
  - Proper error handling when no data available

---

## Upcoming Work

### 6. Integration Testing 📋
- **Status**: PENDING
- **Description**: Test the complete end-to-end pipeline
- **Test Scenarios**:
  1. **Cold Start Test**:
     - Clear all data
     - Start data collector
     - Wait for 5 collection cycles
     - Run historical processing
     - Verify indices are computed

  2. **Historical Processing Test**:
     - Run `process_historical.py` with existing data
     - Verify normalization constants are saved
     - Verify safety indices are saved
     - Check data quality and completeness

  3. **Real-time Processing Test**:
     - Ensure normalization constants exist
     - Restart data collector
     - Verify real-time indices are computed each cycle
     - Compare with batch-processed indices for consistency

  4. **API Test**:
     - Query safety indices via API
     - Test time range filtering
     - Test intersection-specific queries
     - Verify response format and data quality

  5. **Error Handling Test**:
     - Test with missing normalization constants
     - Test with corrupted Parquet files
     - Test with VCC API unavailability
     - Verify graceful error handling

- **Success Criteria**:
  - All test scenarios pass
  - No data loss
  - Error handling works as expected
  - Performance meets requirements

---

## Backlog / Future Enhancements

### 7. Empirical Bayes Adjustment Integration
- **Status**: BACKLOG
- **Description**: Integrate Empirical Bayes adjustment into real-time processing
- **Current State**:
  - Implemented in historical processing
  - Not yet in real-time processing
- **Reason**: Need baseline event rates which require historical data

### 8. WebSocket Real-time Streaming
- **Status**: BACKLOG
- **Description**: Implement WebSocket streaming for real-time safety index updates
- **Use Case**: Dashboard real-time updates
- **Technical Approach**:
  - FastAPI WebSocket endpoint
  - Publish-subscribe pattern with Redis
  - Client receives updates as new indices are computed

### 9. SPAT Data Integration
- **Status**: BACKLOG
- **Description**: Integrate Signal Phase And Timing (SPAT) data into features
- **Current State**: VCC API supports SPAT but not yet collected
- **Benefits**: Better conflict detection with signal phase awareness

### 10. Advanced Conflict Detection
- **Status**: BACKLOG
- **Description**: Enhance conflict detection algorithms
- **Potential Improvements**:
  - Trajectory prediction
  - Near-miss detection with configurable thresholds
  - Red-light violation detection
  - Speed violation detection

### 11. Dashboard/Visualization
- **Status**: BACKLOG
- **Description**: Build web dashboard for visualizing safety indices
- **Features**:
  - Real-time intersection safety map
  - Historical trends
  - Alert notifications for dangerous intersections
  - Admin controls

### 12. Data Quality Monitoring
- **Status**: BACKLOG
- **Description**: Monitor data collection quality and completeness
- **Metrics**:
  - Collection success rate
  - Data completeness (missing fields)
  - API latency
  - Index computation failures
- **Alerting**: Notify when quality degrades

---

## Technical Debt

### 1. PSM Data Collection
- **Issue**: Currently collecting 0 PSM messages
- **Impact**: No VRU conflict detection
- **Investigation Needed**:
  - Are there actually no pedestrians in the area?
  - Is PSM broadcasting working correctly?
  - Do we need to adjust collection parameters?

### 2. Error Handling Improvements
- **Issue**: Some error cases may not be handled gracefully
- **Examples**:
  - Network timeouts during VCC API calls
  - Corrupted Parquet files
  - Disk space exhaustion
- **Action**: Add comprehensive error handling and retry logic

### 3. Performance Optimization
- **Issue**: Feature extraction may be slow with large datasets
- **Potential Solutions**:
  - Parallelize processing
  - Incremental processing (only process new data)
  - Pre-aggregate frequently queried data

### 4. Configuration Management
- **Issue**: Some parameters are hardcoded
- **Action**: Move all tunable parameters to configuration
- **Examples**:
  - Conflict detection thresholds
  - Time aggregation intervals
  - Empirical Bayes K parameter

---

## Dependencies

### External Dependencies
- **VCC API**: Connected Corridor Public API v3.1
  - Base URL: https://vcc.vtti.vt.edu
  - Credentials: Configured in `.env`
  - Status: ✅ WORKING

### Data Dependencies
- **Normalization Constants**: Required for real-time index computation
  - Source: Historical batch processing
  - Status: ⚠️ MUST RUN `process_historical.py` FIRST

### Service Dependencies
- **PostgreSQL**: Data storage (currently not used, future enhancement)
- **Redis**: Caching (configured but not yet used in endpoints)

---

## Known Issues

1. **PSM Data Not Being Collected**
   - **Impact**: Medium (no VRU conflict detection)
   - **Workaround**: System still works with BSM data only
   - **Status**: Under investigation

2. **Normalization Constants Bootstrap Problem**
   - **Issue**: Real-time processing needs constants that come from historical processing
   - **Impact**: Low (documented in workflow)
   - **Solution**: Run `process_historical.py` once after sufficient data collection
   - **Status**: Working as designed

---

## Success Metrics

### Data Collection
- ✅ VCC API authentication successful
- ✅ Collecting data every 60 seconds
- ✅ ~12 BSM messages per cycle
- ✅ 4 intersections covered (MapData)
- ⚠️ 0 PSM messages (investigating)

### Processing Pipeline
- ✅ Historical processing script complete
- ✅ Real-time processing integrated
- ⏸️ API endpoints pending
- ⏸️ End-to-end testing pending

### Quality Metrics (Target)
- API response time: < 500ms (with caching)
- Data collection uptime: > 99%
- Index computation accuracy: Verified against baseline
- API error rate: < 1%

---

## Next Actions

1. **Immediate (Current Sprint)**:
   - ✅ Complete real-time processing integration
   - 🔄 Create API endpoints for safety index retrieval
   - 📋 Run end-to-end integration tests
   - 📋 Document API usage

2. **Short-term (Next Sprint)**:
   - Investigate PSM data collection issue
   - Implement WebSocket streaming
   - Build basic dashboard prototype
   - Set up monitoring/alerting

3. **Long-term**:
   - Advanced conflict detection algorithms
   - SPAT data integration
   - Production deployment
   - Performance optimization

---

## Notes

- Docker stack is running successfully on localhost
- VCC API credentials are configured and working
- Data is being stored in `backend/data/parquet/`
- All services are healthy and operational
- System is ready for API endpoint implementation and testing

---

**Last Updated**: 2025-11-20
**Sprint Status**: ON TRACK
**Blockers**: None
**Next Milestone**: Complete API endpoints and integration testing
