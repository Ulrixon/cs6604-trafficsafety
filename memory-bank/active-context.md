# Active Context

**Last Updated**: 2025-12-02
**Status**: ✅ GCP CLOUD RUN DEPLOYED | 📦 DATA MIGRATED TO GCS | 🗄️ CLOUD SQL OPERATIONAL

---

## Current Sprint: GCP Cloud Deployment ✅

### Just Completed (2025-12-02)

**Cloud Run Deployment & Data Migration:**

1. ✅ **Data Collector on Google Cloud Run (COMPLETE)**
   - **HTTP Wrapper**: Created `collector_http_wrapper.py` to provide health check endpoint
   - **Threading Fix**: Moved HTTP server to background thread, collector in main thread for signal handler support
   - **Deployment Script**: `deploy-collector-gcp.sh` automates Cloud Run deployment
   - **Service URL**: `https://cs6604-trafficsafety-collector-180117512369.europe-west1.run.app`
   - **Status**: Collecting data successfully (638 BSM, 76 MapData messages)

2. ✅ **Secret Manager Integration (COMPLETE)**
   - **VCC Credentials**: Stored in Secret Manager (`vcc_client_id`, `vcc_client_secret`)
   - **Secret Scripts**:
     - `create-vcc-secrets.sh` - Initial secret creation
     - `update-vcc-secret.sh` - Update to correct credentials
   - **Authentication**: Fixed 401 errors by updating to correct VCC client secret

3. ✅ **GCS Data Storage (COMPLETE)**
   - **Bucket**: `gs://cs6604-trafficsafety-parquet`
   - **Structure**:
     - `raw/bsm/` - Basic Safety Messages
     - `raw/mapdata/` - Map Data
     - `processed/indices/` - Computed safety indices
   - **Status**: 57 files uploaded successfully

4. ✅ **Cloud SQL Migration (98% COMPLETE)**
   - **Instance**: `vtsi-postgres` (PostgreSQL 17.6 + PostGIS)
   - **Location**: europe-west1
   - **Data Migrated**:
     - 3 intersections
     - 1,450 of 1,483 safety indices (98%)
     - Schema fully imported with spatial support
   - **Script**: `import-to-gcp-db.sh` for database imports

5. ✅ **Local Data Migration (COMPLETE)**
   - **Parquet Files**: 3,171 files copied to `gs://cs6604-trafficsafety-parquet/raw-backup/`
   - **Source**: Local Docker volume
   - **Directories**: bsm/, mapdata/, psm/

**Key Fixes:**
- Signal handler threading error (ValueError: signal only works in main thread)
- VCC authentication error (401 Unauthorized - wrong secret)
- Cloud SQL firewall (added authorized network for public IP access)
- PostGIS extension (CREATE EXTENSION postgis)

---

## Previous Sprint: Sensitivity Analysis & Optimization ✅

### Just Completed (2025-11-21 Morning)

**Sensitivity Analysis & Performance Optimization:**

1. ✅ **Sensitivity Analysis Feature (COMPLETE)**

   - **Backend**: Implemented `SensitivityAnalysisService` to perturb parameters (β, k, λ, ω) and measure stability using Spearman rank correlation.
   - **Frontend**: Created `3_🔬_Sensitivity_Analysis.py` with comprehensive visualizations:
     - **Stability Gauge**: Visualizes the mean Spearman correlation.
     - **Heatmaps**: Shows correlation across different perturbation levels.
     - **Trajectory Plots**: Visualizes how safety scores change under perturbation.
   - **Date Range Support**: Updated frontend to support multi-day analysis (Start Date/End Date).

2. ✅ **Performance Optimization (In-Memory Calculation)**

   - **Issue**: Long date ranges (e.g., 23 days) caused timeouts due to N*M database queries (Perturbations * Time Bins).
   - **Solution**: Refactored `SensitivityAnalysisService` to fetch traffic data **once** and perform all 50-100 perturbation calculations in memory.
   - **Result**: Reduced database queries from thousands to 1, eliminating timeouts.

3. ✅ **RT-SI Zero-Fill Logic**

   - **Issue**: Time series data had gaps where no traffic was recorded, causing issues for continuous analysis.
   - **Solution**: Updated `rt_si_service.py` to generate a complete time index and fill missing intervals with zero-traffic data.

4. ✅ **Correlation Analysis**
   - Implemented pairwise correlation analysis between safety scores and input features (Volume, Speed, etc.).

---

## Current Sprint: COMPLETED ✅ (Historical Context)

### What We Just Completed (2025-11-20)

**Intersection History Feature + PostgreSQL Migration Planning:**

1. ✅ **Intersection History Feature (COMPLETE)**

   - Backend: Created history API endpoints with smart aggregation
   - Frontend: Built Plotly time series charts and statistics cards
   - Integration: Added "View Historical Data" toggle in dashboard
   - Status: Fully implemented and tested

2. ✅ **Data Verification**

   - Created data verification notebook
   - Identified: Only tracking 1 intersection (0.0) out of 4 available from VCC
   - Root cause: Feature extraction not mapping vehicles to all intersections

3. ✅ **PostgreSQL Migration Architecture Decision**
   - Requirements document created (400+ lines)
   - Design document created (1000+ lines)
   - Sprint plan created (detailed 4-week plan)
   - Architectural decisions documented (ADR-001 through ADR-008)

**Key Architectural Decision**: Hybrid storage with PostgreSQL + PostGIS for operational queries and GCP Cloud Storage for raw data archival.

---

## Current System Metrics

### Data Collection

- **BSM Messages**: 1,678+
- **PSM Messages**: 21 (limited - no pedestrians in area)
- **MapData**: 4 intersections
- **Collection Rate**: 60 seconds
- **Uptime**: Continuous

### Safety Indices (Latest)

```json
{
  "intersection_name": "0.0",
  "safety_index": 33.44,
  "traffic_volume": 29,
  "range": "33.44 - 52.43"
}
```

### Normalization Constants

- **I_max**: 1.0 (Maximum incident rate)
- **V_max**: 182.0 (Maximum vehicle volume)
- **σ_max**: 8.3 (Maximum speed variance)
- **S_ref**: 10.4 (Reference speed)

---

## System Architecture

### Cloud Production (GCP)

```
VCC API (https://vcc.vtti.vt.edu)
    ↓
┌────────────────────────────────────────────────────────────┐
│ Google Cloud Run: cs6604-trafficsafety-collector          │
│ - HTTP health check (port 8080)                           │
│ - Data collection (60s interval)                          │
│ - Secrets from Secret Manager (VCC credentials)           │
└────────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────┬───────────────────────────┐
│ GCS: cs6604-trafficsafety-parquet │ Cloud SQL: vtsi-postgres │
│ - raw/bsm/                       │ - PostgreSQL 17.6        │
│ - raw/mapdata/                   │ - PostGIS enabled        │
│ - raw/psm/                       │ - 3 intersections        │
│ - processed/indices/             │ - 1,450 safety indices   │
│ - raw-backup/ (3,171 files)      │                          │
└────────────────────────────────┴───────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────────┐
│ Google Cloud Run: cs6604-trafficsafety (Backend API)      │
│ - FastAPI REST endpoints                                   │
│ - Reads from GCS + Cloud SQL                               │
└────────────────────────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────────────────────────┐
│ Google Cloud Run: safety-index-frontend                    │
│ - Streamlit dashboard                                      │
│ - Real-time visualization                                  │
└────────────────────────────────────────────────────────────┘
```

### Local Development (Docker)

```
VCC API (https://vcc.vtti.vt.edu)
    ↓
Data Collector (60s interval)
    ↓
Parquet Storage (/app/data/parquet/)
    ├── raw/bsm/        - Basic Safety Messages
    ├── raw/psm/        - Personal Safety Messages
    ├── raw/mapdata/    - Map Data
    ├── features/       - Extracted features
    ├── indices/        - Safety indices
    └── constants/      - Normalization constants
    ↓
FastAPI (http://localhost:8001)
    ├── GET /health
    ├── GET /api/v1/safety/index/
    ├── GET /api/v1/safety/index/{id}
    ├── POST /api/v1/analysis/sensitivity
    └── POST /api/v1/analysis/correlation
    ↓
Streamlit Dashboard (http://localhost:8501)
```

---

## GCP Deployment Information

### Cloud Run Services

| Service | URL | Status |
|---------|-----|--------|
| **Data Collector** | https://cs6604-trafficsafety-collector-180117512369.europe-west1.run.app | ✅ Running |
| **Backend API** | https://cs6604-trafficsafety-180117512369.europe-west1.run.app | ✅ Running |
| **Frontend Dashboard** | https://safety-index-frontend-180117512369.europe-west1.run.app | ✅ Running |

### GCP Resources

**Project**: `symbolic-cinema-305010` (Project Number: 180117512369)
**Region**: `europe-west1`

**Secret Manager:**
- `vcc_client_id` - VCC API client ID
- `vcc_client_secret` - VCC API client secret

**Cloud Storage:**
- Bucket: `gs://cs6604-trafficsafety-parquet`
- Raw data: `raw/bsm/`, `raw/mapdata/`, `raw/psm/`
- Processed data: `processed/indices/`
- Backup: `raw-backup/` (3,171 files from local migration)

**Cloud SQL:**
- Instance: `vtsi-postgres`
- Type: PostgreSQL 17.6 + PostGIS
- Connection: `symbolic-cinema-305010:europe-west1:vtsi-postgres`
- Database: `vtsi`
- Public IP: `34.140.49.230` (authorized networks required)

### Deployment Scripts

- `backend/deploy-collector-gcp.sh` - Deploy data collector to Cloud Run
- `backend/create-vcc-secrets.sh` - Create VCC API secrets
- `backend/update-vcc-secret.sh` - Update VCC client secret
- `backend/import-to-gcp-db.sh` - Import database to Cloud SQL

### Monitoring

**View Collector Logs:**
```bash
gcloud run services logs read cs6604-trafficsafety-collector \
  --region=europe-west1 --limit=50
```

**View Backend API Logs:**
```bash
gcloud run services logs read cs6604-trafficsafety \
  --region=europe-west1 --limit=50
```

**Check GCS Files:**
```bash
gcloud storage ls gs://cs6604-trafficsafety-parquet/raw/ --recursive
```

---

## What We're Working On Next

**Current Focus: Backend API GCS Integration** 🔥 URGENT

- 📋 **Status**: In Progress
- 🎯 **Goal**: Configure backend API to read from GCS bucket
- 📄 **Issue**: Backend deployed before collector, not configured for GCS
- 🔧 **Solution**: Update backend env vars to enable GCS reads

### Next Steps (Immediate)

1. **Update Backend API Configuration**
   - Enable GCS_BUCKET_NAME in backend deployment
   - Set USE_POSTGRESQL=false initially
   - Test API with GCS data source

2. **Verify Data Pipeline**
   - Check if safety indices are readable from GCS
   - Test frontend with cloud-hosted backend
   - Validate end-to-end data flow

### Future Focus: Full PostgreSQL Integration (Planned)

- 📋 **Status**: Cloud SQL operational, backend integration pending
- 🎯 **Goal**: Switch backend to use Cloud SQL + GCS hybrid storage
- 📄 **Documents**:
  - Requirements: `construction/requirements/postgresql-migration-requirements.md`
  - Design: `construction/design/postgresql-migration-design.md`

**Already Complete:**
- ✅ Cloud SQL instance with PostGIS
- ✅ Database schema migrated
- ✅ 98% of historical data imported
- ✅ GCS bucket with raw data

**Remaining Work:**
1. Update backend DATABASE_URL to use Cloud SQL Unix socket
2. Enable USE_POSTGRESQL=true in backend
3. Test hybrid GCS + PostgreSQL queries
4. Performance validation

---

### Future Focus: Data Integration & Extensibility Roadmap

- 📋 **Status**: Planning complete, deferred until after PostgreSQL migration
- 🎯 **Goal**: Transform from VCC-only to multi-source pluggable platform
- 📄 **Document**: `memory-bank/data-integration-roadmap.md`

**Key Initiatives** (postponed):

1. **Pluggable Data Source Architecture** - Allow easy addition of new data sources (weather, crash data, traffic)
2. **Configurable Safety Index** - Make features and weights adjustable without code changes
3. **Admin UI** - Build dashboard for data analysis and index tuning
4. **Multi-source Integration** - Add weather, VDOT crash data, traffic volume sources

**Timeline**: 4-6 months (15-20 weeks development)
**Phases**: 6 phases from plugin framework to A/B testing
**Status**: Deferred until PostgreSQL migration complete

---

## What Decisions Are We Facing?

### 1. **PostgreSQL + GCP Migration Approval** 🔥 URGENT - NEW

- **Status**: Planning complete, ready to implement
- **Documents**:
  - `construction/requirements/postgresql-migration-requirements.md`
  - `construction/design/postgresql-migration-design.md`
  - `construction/sprints/sprint-postgresql-migration.md`
  - `memory-bank/architectural-decisions.md`
- **Key Decisions Needed**:
  - ✅ **Approve hybrid storage architecture?** (PostgreSQL + GCP Cloud Storage)
  - ✅ **Approve GCP Cloud Storage?** (~$35/month for Parquet archival)
  - ✅ **Approve 4-week timeline?** (80-100 hours effort)
  - ✅ **Start immediately or defer?** (Blocks multi-intersection support)
  - ⏳ **GCP project setup?** (Need to create GCP account/project)

**Recommendation:** Approve and start immediately. Current Parquet-only architecture cannot scale beyond 1-2 intersections efficiently.

**Benefits:**

- 10-100x faster API queries
- Support for 100+ intersections
- Spatial queries (proximity, routing, heatmaps)
- Production-ready cloud storage
- Automated data lifecycle management

**Risks:** Managed with dual-write, feature flags, validation, and rollback plan

---

### 2. **Data Integration Roadmap Approval** (Deferred)

- **Status**: Roadmap complete, deferred until after PostgreSQL migration
- **Document**: `memory-bank/data-integration-roadmap.md`
- **Key Decisions Needed**:
  - ⏸️ Deferred - PostgreSQL migration takes priority
  - Will revisit after database migration complete

**Proposed Architecture**:

- Pluggable data source framework (abstract interface + registry)
- Configurable feature definitions (YAML-based)
- Dynamic feature engine (compute from config, not code)
- Admin UI for data source management and weight tuning
- A/B testing framework for index formulas

**Proposed New Data Sources** (Phase 3):

1. Weather API (OpenWeatherMap) - precipitation, visibility, temperature
2. VDOT Crash Data - historical crashes for validation
3. Traffic Volume API - additional traffic metrics

### 2. **Configuration Storage Strategy**

- **Question**: Database vs. files vs. hybrid approach?
- **Recommendation**: Hybrid - files for defaults, database for runtime changes
- **Impact**: Affects admin UI implementation and deployment

### 3. **Admin UI Technology Choice**

- **Options**:
  - React + TypeScript (full-featured, production-grade)
  - Streamlit (rapid prototyping, Python-native)
  - Vue.js (lighter weight alternative)
- **Recommendation**: React for production quality, Streamlit for MVP/prototype
- **Decision Needed**: Start with MVP or go straight to production UI?

### 4. **Empirical Bayes Implementation** (Deferred)

- **Current Status**: Skipped due to data structure mismatch
- **Decision**: Keep as backlog item or redesign baseline data structure?
- **Impact**: Low - raw indices are still meaningful
- **Recommendation**: Address in Phase 2 or 3 of roadmap

### 5. **PSM Data Scarcity** (Monitoring)

- **Observation**: Only 21 PSM messages vs 1,678 BSM
- **Question**: Is this normal or a collection issue?
- **Investigation Needed**: Check VCC API coverage for pedestrian-heavy areas
- **Impact**: Low - system works with BSM-only data
- **Action**: Continue monitoring, investigate if needed

### 6. **Production Deployment** (Future)

- **Current**: Running on localhost
- **Needed**: Cloud deployment strategy (AWS, Azure, GCP?)
- **Timeline**: After roadmap Phase 4-5 (admin UI complete)
- **Considerations**:
  - Scaling data collection
  - Database choice (keep PostgreSQL or switch to TimescaleDB?)
  - Caching strategy (Redis vs alternatives)
  - Monitoring and alerting (Prometheus + Grafana)

---

## What's Unclear?

### Mathematical Formulas - ✅ RESOLVED

~~Some of the math is still a little foggy~~ → **NOW CLEAR!**

**Implemented Formulas:**

1. **VRU Safety Index**:

   ```
   I_VRU = (I_VRU_raw × w1) + (V × w2) + (σ_v × w3)
   Where: I_VRU_raw, V, σ_v are normalized values
   ```

2. **Vehicle Safety Index**:

   ```
   I_vehicle = (I_vehicle_raw × w4) + (V × w5) + (Δθ × w6) + (S × w7)
   ```

3. **Combined Index**:

   ```
   Combined_Index = I_VRU + I_vehicle
   ```

4. **Normalization** (working correctly):

   ```
   I_max = max(incident_rates)
   V_max = max(vehicle_volumes)
   σ_max = max(speed_variances)
   S_ref = reference_speed
   ```

5. **Empirical Bayes** (pending):
   ```
   Adjusted_Index = λ × Raw_Index + (1-λ) × Baseline
   Where λ = N / (N + k)
   ```

### Remaining Technical Questions

1. **Conflict Detection Thresholds**

   - Current: Using default proximity thresholds
   - Question: What are optimal thresholds for different road types?
   - Impact: Medium (affects conflict detection accuracy)

2. **Temporal Aggregation**

   - Current: 15-minute intervals (historical), 1-minute (real-time)
   - Question: Are these intervals optimal?
   - Observation: 15-min seems good for statistical significance

3. **Index Interpretation**
   - Current: Numeric scores (33.44, etc.)
   - Question: What do these numbers mean to end users?
   - Need: Categorization (safe/moderate/dangerous) or percentile ranking

---

## Known Issues & Workarounds

### 1. Empirical Bayes Adjustment - Skipped

**Issue**: Baseline event data structure mismatch (missing 'hour_of_day' column)

**Status**: Non-blocking - using raw indices

**Workaround**: Raw safety indices are mathematically sound and meaningful

**Future Fix**: Restructure baseline data or redesign EB calculation

### 2. Limited PSM Data

**Issue**: Only 21 PSM messages collected vs 1,678 BSM

**Status**: Expected - likely no pedestrians in monitoring area

**Impact**: VRU conflict detection has limited data

**Workaround**: System works with BSM-only data

### 3. Windows Path Mangling (Git Bash)

**Issue**: Git Bash converts Unix paths to Windows paths

**Status**: Known platform limitation

**Workaround**: Prefix all Docker commands with `MSYS_NO_PATHCONV=1`

**Example**:

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls /app/data/parquet
```

---

## Deployment Checklist

If deploying to production:

- [ ] Update VCC credentials for production API
- [ ] Configure CORS for production domains
- [ ] Set up SSL/TLS certificates
- [ ] Implement proper authentication
- [ ] Configure monitoring (Prometheus/Grafana)
- [ ] Set up log aggregation
- [ ] Configure automated backups
- [ ] Document disaster recovery procedures
- [ ] Performance testing
- [ ] Security audit

---

## Next Actions

### Immediate (This Week)

1. **Review Data Integration Roadmap** 🔥 URGENT

   - Read `memory-bank/data-integration-roadmap.md`
   - Approve architecture approach
   - Prioritize phases (1-6)
   - Identify must-have features

2. **Prototype Plugin System** (If approved)

   - 1-week spike to validate approach
   - Build minimal plugin framework
   - Migrate VCC to plugin architecture
   - Test with dummy second source

3. **Design Admin UI Mockups** (If approved)
   - Create detailed wireframes
   - Get user feedback
   - Finalize screen designs

### Short-term (Next 1-2 Sprints)

Following the roadmap phases:

**Phase 1: Core Plugin Architecture** (2-3 weeks)

- Implement base data source plugin framework
- Migrate existing VCC code to plugin
- Create data source registry
- Add basic admin API endpoints

**Phase 2: Dynamic Feature Engine** (2-3 weeks)

- Implement configurable feature definitions
- Create dynamic feature computation engine
- Migrate existing features to config format
- Add weight adjustment capability

**Phase 3: New Data Source Integration** (3-4 weeks)

- Implement Weather API plugin
- Implement VDOT crash data plugin (if accessible)
- Implement Traffic volume plugin
- Integration testing

### Medium-term (Months 2-3)

**Phase 4: Admin UI - Basic Features** (3-4 weeks)

- Build core admin dashboard
- Data source management UI
- Feature weight tuning interface
- Real-time index preview

**Phase 5: Admin UI - Analysis Tools** (2-3 weeks)

- Data exploration and visualization
- Index comparison tools
- Feature analysis (correlation, importance)
- Configuration history/rollback

### Long-term (Months 4-6)

**Phase 6: A/B Testing Framework** (2-3 weeks)

- Multiple index formula support
- Parallel index computation
- Performance metrics
- Formula selection tools

**Production Deployment** (After Phase 5)

- Cloud infrastructure setup
- Monitoring and alerting
- Security hardening
- Performance optimization

**Additional Enhancements** (Ongoing)

- Machine learning for predictive analytics
- Mobile app integration
- Alert/notification system
- WebSocket streaming for real-time updates

---

## Success Metrics - ✅ ALL ACHIEVED

| Metric                   | Target     | Actual             | Status |
| ------------------------ | ---------- | ------------------ | ------ |
| Data Collection          | Continuous | 60s intervals      | ✅     |
| API Response Time        | < 500ms    | ~200ms             | ✅     |
| Safety Index Computation | Working    | 33.44 (real value) | ✅     |
| System Uptime            | > 95%      | 100%               | ✅     |
| Docker Deployment        | Functional | 4 services running | ✅     |
| Data Persistence         | Yes        | Parquet volumes    | ✅     |

---

## Team Knowledge

### Key Learning: Feature Engineering with Time Intervals

**Challenge**: Real-time (1-min) and historical (15-min) intervals caused column name conflicts

**Solution**: Standardize to 'time_15min' for downstream compatibility while supporting variable intervals:

```python
time_col_name = f'time_{interval_minutes}min'
features.rename(columns={'time_interval': time_col_name}, inplace=True)

# Standardize for compatibility
if time_col_name != 'time_15min':
    features['time_15min'] = features[time_col_name]
```

### Key Learning: Docker Volume Persistence

**Issue**: Data lost on container restart

**Solution**: Named volumes in docker-compose.yml:

```yaml
volumes:
  - parquet_data:/app/data/parquet
```

### Key Learning: Windows Docker Commands

**Issue**: Git Bash mangles paths

**Solution**: Always use `MSYS_NO_PATHCONV=1` prefix

---

## Documentation

### Current System

- **Operational Guide**: `memory-bank/operational-guide.md` - Complete operational manual
- **Troubleshooting**: `memory-bank/troubleshooting.md` - Common issues and solutions
- **Sprint Plan**: `construction/sprint-plan.md` - Completed sprint retrospective
- **Quick Start**: `QUICKSTART.md` - Getting started guide
- **Docker Setup**: `DOCKER_README.md` - Docker deployment guide
- **API Docs**: http://localhost:8001/docs - Interactive API documentation (when running)

### Future Planning

- **Data Integration Roadmap**: `memory-bank/data-integration-roadmap.md` - Next generation architecture plan
  - Pluggable data sources
  - Configurable safety index
  - Admin UI design
  - 6-phase implementation plan (4-6 months)

---

**Current Status**: ✅ PRODUCTION-READY → 📋 PLANNING NEXT GENERATION
**Last Code Change**: 2025-11-21
**Last Planning Update**: 2025-11-21 (Sensitivity Analysis)
**Next Action**: Review and approve roadmap → Begin Phase 1 implementation
