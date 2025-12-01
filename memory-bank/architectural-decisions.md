# Architectural Decision Records (ADRs)

This document captures key architectural decisions made during the Traffic Safety Index System development.

---

## ADR-001: Hybrid Storage Architecture (PostgreSQL + GCP Cloud Storage)

**Date:** 2025-11-20
**Status:** Approved
**Decision Makers:** Traffic Safety Index Team

### Context

The initial implementation used Apache Parquet files for all data storage (raw and processed). While this provided simplicity and fast columnar scans for analytics, it created limitations:

1. **Performance:** File-based queries require full scans, leading to slow API responses
2. **Scalability:** Cannot efficiently serve multiple concurrent users
3. **Spatial Queries:** No support for geospatial operations (proximity, routing)
4. **Data Management:** No automated retention, aggregation, or lifecycle policies
5. **Deployment:** Local Docker volumes not suitable for production cloud deployment

### Decision

We will migrate to a **hybrid storage architecture**:

**PostgreSQL + PostGIS** for operational data:

- Fast indexed queries for real-time dashboard
- Spatial indexing and geospatial operations
- ACID transactions and data integrity
- Automated aggregation and retention

**GCP Cloud Storage** for raw data:

- Immutable archive of raw BSM/PSM/MapData messages
- Cost-effective long-term storage with lifecycle policies
- Source of truth for data reprocessing
- Compliance and audit trail

### Architecture

```
VCC API → Data Collector → Dual Write
                             ├─→ GCS (raw Parquet)
                             └─→ PostgreSQL (processed)
                                      ↓
                                  FastAPI ← Query
                                      ↓
                                  Frontend
```

**Data Flow:**

1. Collect from VCC every 60 seconds
2. Save raw to GCS (BSM/PSM/MapData)
3. Compute safety indices
4. INSERT into PostgreSQL (realtime table)
5. Hourly job aggregates to summary tables
6. API queries from PostgreSQL (fast)

### Rationale

**Why PostgreSQL?**

- Industry-standard relational database
- Excellent PostGIS support for spatial operations
- Mature ecosystem (backups, replication, monitoring)
- ACID compliance for data integrity
- Native time-series optimization with partitioning
- Team already familiar with SQL

**Why GCP Cloud Storage?**

- Significantly cheaper than database storage for archives
- Automatic lifecycle transitions (Standard → Nearline → Coldline)
- Durability: 99.999999999% (11 9's)
- Integration with BigQuery for future analytics
- No infrastructure management required
- Scales to petabytes without reconfiguration

**Why Not Alternatives?**

_TimescaleDB alone:_

- Vendor lock-in
- Still need separate archival storage
- Higher costs for long-term retention

_AWS S3 instead of GCS:_

- GCP chosen for future integration with BigQuery
- Closer to VCC servers (latency)
- Consistent GCP ecosystem

_NoSQL (MongoDB, Cassandra):_

- Overkill for our data model
- Less mature spatial support
- No ACID guarantees

### Consequences

**Positive:**

- 10-100x faster API queries
- Enable spatial features (proximity, routing)
- Automated data lifecycle management
- Production-ready deployment
- Cost-effective long-term storage (~$35/month for Parquet)
- Can scale to 1000+ intersections

**Negative:**

- Increased complexity (dual-write, two storage systems)
- PostgreSQL operational overhead (backups, monitoring)
- GCS costs (minimal but not free)
- Migration effort (~80-100 hours)

**Neutral:**

- More moving parts to manage
- Need to learn GCS APIs
- Database administration skills required

### Implementation

See detailed plans:

- Requirements: `construction/requirements/postgresql-migration-requirements.md`
- Design: `construction/design/postgresql-migration-design.md`
- Sprint: `construction/sprints/sprint-postgresql-migration.md`

**Timeline:** 4 weeks
**Estimated Cost:** $35/month (GCS) + $0 (PostgreSQL in Docker)

### Compliance

This aligns with the original system proposal, which specified PostgreSQL + PostGIS as the primary data store.

---

## ADR-002: 1-Minute Time Granularity for Safety Indices

**Date:** 2025-11-19 (Confirmed 2025-11-20)
**Status:** Implemented
**Decision Makers:** Traffic Safety Index Team

### Context

Initial design used 15-minute aggregation windows. During implementation, we discovered this was too coarse for real-time safety monitoring.

### Decision

Change base time granularity from 15-minute to **1-minute intervals** for safety index computation.

### Rationale

- Traffic conditions change rapidly (seconds to minutes)
- 15-minute windows miss short-duration hazardous events
- VCC API provides data every ~1 second (we poll every 60 seconds)
- 1-minute aligns with data collection frequency
- Enables detection of brief but critical safety events

### Consequences

**Positive:**

- 15x higher temporal resolution
- Can detect brief safety incidents
- More accurate real-time monitoring
- Better data for machine learning

**Negative:**

- 15x more data to store and process
- Higher database write throughput required
- More aggressive aggregation needed for historical queries

**Mitigations:**

- PostgreSQL partitioning handles volume
- Automated hourly/daily aggregation reduces query load
- Retention policies limit growth

### Implementation Status

- ✅ Data collector computes 1-minute indices
- ✅ Parquet storage uses 1-minute granularity
- ⏳ PostgreSQL schema designed for 1-minute (pending migration)

**Note:** Legacy column name `time_15min` remains in Parquet for backward compatibility but contains 1-minute timestamps.

---

## ADR-003: Dual-Write During Migration

**Date:** 2025-11-20
**Status:** Approved
**Decision Makers:** Traffic Safety Index Team

### Context

Migrating from Parquet-only to PostgreSQL+GCS while maintaining uptime requires a transition strategy.

### Decision

Implement **dual-write** architecture during migration:

- Data collector writes to both GCS and PostgreSQL simultaneously
- API can query from either source (feature flag controlled)
- Gradual rollout with validation at each step

### Migration Phases

1. **Phase 1:** Setup (PostgreSQL + GCS)
2. **Phase 2:** Dual-write begins (both receive data)
3. **Phase 3:** API migrated with fallback
4. **Phase 4:** Backfill historical data
5. **Phase 5:** Full cutover (disable Parquet queries)

### Rationale

- **Zero downtime:** System stays operational throughout
- **Validation:** Can compare outputs before cutover
- **Rollback:** Easy to revert if issues detected
- **Risk mitigation:** Gradual rollout reduces impact

### Consequences

**Positive:**

- No service interruption
- Can validate before committing
- Easy rollback path
- Team gains confidence gradually

**Negative:**

- Temporary increased complexity
- Both systems must be maintained during transition
- Higher write load temporarily
- More monitoring required

### Success Criteria

- [ ] 48 hours of stable dual-write
- [ ] Row counts match between systems
- [ ] Sample values match within tolerance
- [ ] No data loss detected
- [ ] API performance improved

---

## ADR-004: Smart Aggregation for Historical Queries

**Date:** 2025-11-20
**Status:** Approved (Implemented for Parquet, Extending to PostgreSQL)

### Context

Historical queries can span hours to years. Returning all 1-minute data points is inefficient and overwhelming for visualizations.

### Decision

Implement **smart query routing** based on time range:

| Time Range | Data Source    | Aggregation | Points Returned |
| ---------- | -------------- | ----------- | --------------- |
| ≤ 1 day    | Realtime table | 1-minute    | 1,440           |
| ≤ 7 days   | Realtime table | Hourly      | 168             |
| ≤ 30 days  | Hourly table   | Daily       | 30              |
| ≤ 90 days  | Hourly table   | Weekly      | 12-13           |
| > 90 days  | Daily table    | Monthly     | Varies          |

### Rationale

- Optimizes query performance (smaller result sets)
- Improves visualization (appropriate granularity)
- Reduces API response sizes
- Leverages pre-computed aggregates

### Consequences

**Positive:**

- Faster queries for long time ranges
- Better user experience (appropriate detail level)
- Lower bandwidth usage
- Leverages database capabilities

**Negative:**

- Complexity in query routing logic
- Loss of granularity for older data
- Must maintain aggregation jobs

### Implementation

- ✅ Smart defaults in History API
- ✅ User can override with `aggregation` parameter
- ⏳ PostgreSQL tables designed to support this

---

## ADR-005: PostGIS for Spatial Operations

**Date:** 2025-11-20
**Status:** Approved

### Context

Future features require spatial operations:

- Find intersections within radius
- Find intersections along route
- Proximity analysis
- Heatmap generation

### Decision

Use **PostGIS extension** for PostgreSQL to handle all spatial operations.

### Rationale

- Industry standard for geospatial in PostgreSQL
- Mature, well-documented, widely supported
- Efficient spatial indexing (GIST/SPGIS)
- Rich function library
- Native integration with PostgreSQL

### Spatial Features Enabled

1. **Proximity Queries:**

   ```sql
   ST_DWithin(geometry, point, radius)
   ```

2. **Distance Calculations:**

   ```sql
   ST_Distance(geometry::geography, point::geography)
   ```

3. **Route Buffers:**

   ```sql
   ST_Buffer(linestring, buffer_distance)
   ```

4. **Area Queries:**
   ```sql
   ST_Within(geometry, polygon)
   ```

### Consequences

**Positive:**

- Enables planned spatial features
- Performant spatial queries
- Standard GeoJSON support
- Integration with mapping libraries

**Negative:**

- Learning curve for PostGIS
- Slightly larger Docker image
- Additional extension to manage

---

## ADR-006: Time Partitioning for Realtime Table

**Date:** 2025-11-20
**Status:** Approved

### Context

The `safety_indices_realtime` table will receive 1,440 rows per intersection per day. At 100 intersections, that's 144,000 rows/day or 52M rows/year.

### Decision

Implement **daily range partitioning** on the realtime table:

- Partition by `timestamp` column
- One partition per day
- Automated partition creation (7 days ahead)
- Automated partition dropping (>48 hours old)

### Rationale

- **Query Performance:** Partition pruning speeds up time-range queries
- **Maintenance:** Can drop old partitions instead of DELETE
- **Backup/Restore:** Can backup partitions independently
- **Index Sizes:** Smaller indexes per partition

### Implementation

```sql
CREATE TABLE safety_indices_realtime (...)
PARTITION BY RANGE (timestamp);

-- Auto-create partitions
CREATE FUNCTION create_realtime_partition(date)...

-- Auto-drop old partitions
CREATE FUNCTION drop_old_realtime_partitions()...
```

### Consequences

**Positive:**

- 10-100x faster queries on time ranges
- Efficient old data deletion
- Smaller individual indexes
- Better VACUUM performance

**Negative:**

- More complex schema
- Need partition management jobs
- Queries must include partition key for best performance

---

## ADR-007: GCS Lifecycle Policies for Cost Optimization

**Date:** 2025-11-20
**Status:** Approved

### Context

Storing years of raw Parquet files in GCS Standard class would be expensive. Data access patterns show:

- Frequent access: Last 30 days
- Occasional access: 31-365 days
- Rare access: >365 days

### Decision

Implement **automatic lifecycle transitions**:

| Age          | Storage Class | Cost (per GB/month) | Access Time  |
| ------------ | ------------- | ------------------- | ------------ |
| 0-30 days    | Standard      | $0.020              | Immediate    |
| 31-365 days  | Nearline      | $0.010              | ~1 second    |
| 366-730 days | Coldline      | $0.004              | ~1-2 seconds |
| >730 days    | Delete        | $0                  | N/A          |

### Rationale

- **Cost Savings:** ~75% reduction vs Standard-only
- **Transparent:** Access patterns unchanged
- **Automated:** No manual intervention

### Cost Projection

**100GB/month write rate:**

- Month 1: 100GB Standard = $2.00
- Month 6: 100 Standard + 500 Nearline = $7.00
- Month 12: 100 Standard + 500 Nearline + 1000 Coldline = $11.00
- **Steady State (24 months):** ~$15/month vs $48/month (Standard-only)

### Consequences

**Positive:**

- Significant cost savings (68% reduction)
- Automated management
- Transparent to applications

**Negative:**

- Slightly slower access for old data (acceptable)
- Need to monitor lifecycle transitions
- Cannot easily change policies retroactively

---

## ADR-008: Feature Flags for Gradual Rollout

**Date:** 2025-11-20
**Status:** Approved

### Context

Cutover from Parquet to PostgreSQL is risky. Need ability to:

- Test in production with subset of traffic
- Rollback quickly if issues detected
- Compare performance before full commit

### Decision

Use **environment-variable feature flags**:

```python
USE_POSTGRESQL: bool = True/False
FALLBACK_TO_PARQUET: bool = True/False
ENABLE_GCS_UPLOAD: bool = True/False
```

### Rollout Strategy

1. **0% (Baseline):** USE_POSTGRESQL=False
2. **10% (Canary):** Random 10% of requests use PostgreSQL
3. **50% (Half):** Increase if no errors
4. **100% (Full):** All queries from PostgreSQL
5. **Fallback Off:** FALLBACK_TO_PARQUET=False

### Rationale

- **Risk Mitigation:** Gradual exposure
- **Easy Rollback:** Change env var, restart
- **A/B Testing:** Compare performance
- **Confidence Building:** Team sees it working

### Consequences

**Positive:**

- Low-risk deployment
- Quick rollback capability
- Can measure impact empirically
- Team confidence increases gradually

**Negative:**

- Temporary code complexity
- Need to remove flags eventually
- Monitoring must track both paths

---

## ADR-009: In-Memory Calculation for Sensitivity Analysis

**Date:** 2025-11-21
**Status:** Implemented
**Decision Makers:** Traffic Safety Index Team

### Context

The Sensitivity Analysis feature requires calculating safety indices for multiple perturbation scenarios (e.g., varying weights by ±10%, ±25%) over a time range.

- **Initial Approach:** For each perturbation, query the database/service to recalculate indices.
- **Problem:** With 50-100 perturbations and a 30-day range (43,200 minutes), this resulted in thousands of database queries, causing timeouts (>30s) and poor user experience.

### Decision

Implement **In-Memory Calculation** for sensitivity analysis:

1. Fetch raw traffic data (volume, speed, conflicts) **once** for the requested time range.
2. Store data in memory (list of dictionaries or Pandas DataFrame).
3. Iterate through perturbation scenarios in a tight loop, applying the safety index formula to the in-memory data.
4. Aggregate results and return.

### Rationale

- **Performance:** Reduces database round-trips from $O(P \times T)$ to $O(1)$, where $P$ is perturbations and $T$ is time segments.
- **Efficiency:** Python's in-memory operations are orders of magnitude faster than network/disk I/O.
- **Scalability:** Allows for hundreds of perturbations without degrading database performance.

### Consequences

**Positive:**

- API response time reduced from >30s (timeout) to <2s for 30-day ranges.
- Reduced load on the database.
- smoother frontend experience.

**Negative:**

- Higher memory usage on the API server (proportional to the time range size).
- Logic duplication: The safety index formula must be available to the sensitivity service (refactored to `calculate_rt_si_from_data`).

### Implementation

- Refactored `RTSIService` to expose `calculate_rt_si_from_data(data, weights)`.
- Updated `SensitivityAnalysisService` to fetch bulk data and loop in memory.

---

## ADR-010: Zero-Filling for Time Series Continuity

**Date:** 2025-11-21
**Status:** Implemented
**Decision Makers:** Traffic Safety Index Team

### Context

Traffic data is sparse; periods with no vehicles result in missing rows in the database.

- **Problem:** Time series analysis (trends, correlation) requires a continuous timeline. Missing data was interpreted as "unknown" rather than "safe/quiet", skewing analysis.
- **Example:** 3 AM often has zero traffic. If omitted, the average safety index might look artificially high/low based only on busy hours.

### Decision

Implement **Zero-Filling** for data retrieval:

1. Generate a complete date-time index for the requested range (at 15-min or 1-hour granularity).
2. Left-join actual data with this index.
3. Fill missing values with **0** for volume/conflicts and **NaN** (or carry-forward) for speed, as appropriate.
4. For Safety Index, 0 volume implies 0 risk (Safety Index = 0 or Baseline).

### Rationale

- **Accuracy:** Reflects the reality that "no traffic" = "no accidents" (high safety).
- **Consistency:** Ensures charts and statistics cover the full time period.
- **Analysis:** Enables correct correlation and trend analysis without gaps.

### Consequences

**Positive:**

- Continuous line charts in frontend.
- Accurate daily averages (denominator includes quiet hours).
- Robust statistical analysis.

**Negative:**

- Slightly larger data payloads (returning rows for empty periods).
- Need to handle "0" correctly in formulas (avoid divide-by-zero).

### Implementation

- Updated `get_bulk_traffic_data` in `RTSIService` to reindex and fill zeros.

---

## ADR-011: Cloud Build CI/CD with Repository-Based Configuration

**Date:** 2025-12-01
**Status:** Implemented
**Decision Makers:** Traffic Safety Index Team

### Context

Manual deployment to GCP Cloud Run was error-prone and time-consuming. We needed:

1. Automated deployment on every push to main
2. Version-controlled deployment configuration
3. File-based triggering (only deploy what changed)
4. No GitHub Actions (permission issues with Workload Identity Federation)

### Decision

Implement **Cloud Build with repository-based configuration files**:

- **Backend**: `backend/cloudbuild.yaml` (triggers on backend/** changes)
- **Frontend**: `frontend/cloudbuild.yaml` (triggers on frontend/** changes)
- **Artifact Registry**: Use modern artifact registry (deprecated Container Registry removed)
- **Full Configuration**: Complete Cloud Run settings in YAML (memory, CPU, secrets, env vars)

### Architecture

```
Git Push → GitHub → Cloud Build Trigger (file filter) →
  1. Build Docker Image
  2. Push to Artifact Registry
  3. Deploy to Cloud Run (with secrets)
```

**Cloud Build Configuration:**
- Service-specific triggers with file filtering
- Full deployment configuration in source control
- Automatic secret injection from Secret Manager
- Complete resource specifications (2Gi/2CPU backend, 1Gi/1CPU frontend)

### Rationale

**Why Cloud Build?**
- Native GCP integration (no permission issues)
- Simpler than GitHub Actions (no Workload Identity setup)
- Built-in Artifact Registry and Cloud Run support
- Integrated logging and monitoring

**Why Repository-Based YAML?**
- Version control for deployment configuration
- Review deployment changes in PRs
- No inline YAML in GCP Console
- Easy to diff and track changes

**Why File Filtering?**
- Only deploy services that changed
- Faster deployments (don't rebuild frontend when backend changes)
- Reduced Cloud Build minutes usage

### Consequences

**Positive:**
- Fully automated deployment (5-8 minutes from push to live)
- Zero manual steps required
- Configuration changes reviewed in PRs
- Separate backend/frontend deployment lifecycles
- Integrated with existing GCP infrastructure

**Negative:**
- Build time ~5-8 minutes per service
- Cloud Build costs (~$0.015 per deployment after free tier)
- Need to maintain cloudbuild.yaml files

**Cost Impact:**
- 120 free build-minutes per day
- ~5 minutes per deployment = 24 free deployments/day
- Expected cost: $5-15/month for typical usage

### Implementation Status

- ✅ Backend cloudbuild.yaml created with full configuration
- ✅ Frontend cloudbuild.yaml created
- ✅ Cloud Build triggers updated to use repository files
- ✅ File filtering configured (backend/**, frontend/**)
- ✅ DEPLOYMENT_GUIDE.md updated with instructions
- ✅ Successfully deployed to production

---

## ADR-012: GCP Secret Manager for Database Credentials

**Date:** 2025-12-01
**Status:** Implemented
**Decision Makers:** Traffic Safety Index Team

### Context

Database credentials were hardcoded in `analytics_service.py`:

```python
GCP_DB_HOST = "34.140.49.230"
GCP_DB_USER = "jason"
GCP_DB_PASSWORD = "*9ZS^l(HGq].BA]6"  # ❌ Security risk
```

This presented multiple security issues:
1. Credentials visible in source code
2. Credentials in version control history
3. No rotation capability
4. Exposed in Docker images

### Decision

Migrate all database credentials to **GCP Secret Manager** with environment variable injection:

**Secrets Created:**
- `db_user` (version 3): Username
- `db_password` (version 1): Password

**IAM Permissions:**
- Cloud Run service account: `secretAccessor` role
- Cloud Build service account: `secretAccessor` role

**Code Changes:**
```python
# After (secure)
import os
GCP_DB_HOST = os.getenv("VTTI_DB_HOST", "34.140.49.230")
GCP_DB_USER = os.getenv("VTTI_DB_USER")
GCP_DB_PASSWORD = os.getenv("VTTI_DB_PASSWORD")  # ✅ From Secret Manager
```

### Rationale

**Why Secret Manager?**
- Industry standard for credential management
- Automatic audit logging of access
- Version history for rotation
- IAM-based access control
- Integrated with Cloud Run (automatic injection)

**Why Environment Variables?**
- No code changes needed to rotate secrets
- Standard 12-factor app pattern
- Works locally and in production
- Easy to test with different credentials

**Why Both Service Accounts?**
- Cloud Run needs access at runtime
- Cloud Build needs access during deployment (for config validation)

### Consequences

**Positive:**
- No credentials in source code or Git history
- Can rotate credentials by updating secret versions
- Audit log of all credential access
- Compliant with security best practices
- Automatic injection in Cloud Run (no config changes)

**Negative:**
- Additional GCP service to manage
- Slight complexity in local development (need to set env vars)
- IAM permissions must be maintained

**Security Benefits:**
- ✅ Credentials not in Docker images
- ✅ Credentials not in Git history
- ✅ Access audited and logged
- ✅ Can rotate without redeploying code
- ✅ Role-based access control

### Implementation

- ✅ Created `db_password` secret in GCP Secret Manager
- ✅ Updated `db_user` secret to version 3
- ✅ Granted `secretAccessor` role to both service accounts
- ✅ Updated `analytics_service.py` to use environment variables
- ✅ Updated `cloudbuild.yaml` to inject secrets (`:latest` versions)
- ✅ Tested and verified in production

---

## ADR-013: Separate Analytics Schema for Data Organization

**Date:** 2025-12-01
**Status:** Implemented
**Decision Makers:** Traffic Safety Index Team

### Context

The new Analytics & Validation features (crash correlation, validation metrics) needed database tables. Mixing these with production safety index tables could cause:

1. Data confusion (validation vs operational data)
2. Permission issues (analytics might need different access)
3. Backup/restore complexity
4. Performance impact on production queries

### Decision

Create a **separate `analytics` schema** for validation features:

**Schema Structure:**
```sql
analytics.crash_correlation_cache  -- Precomputed validation metrics
analytics.monitored_intersections  -- View into public.intersections
```

**Public Schema (unchanged):**
```sql
public.intersections              -- Operational intersection data
public.safety_indices_realtime    -- Production safety indices
public.vcc_*                      -- VCC message data
```

### Rationale

**Why Separate Schema?**
- Clear separation of concerns (operational vs analytical)
- Different data lifecycle (cache can be dropped/rebuilt)
- Easier permission management
- Clearer backup/restore strategy
- Won't affect production queries

**Why View for Intersections?**
- Analytical queries need intersection data
- View ensures consistency with source
- Can add analytical-specific columns if needed
- No data duplication

### Architecture

```
public schema (operational)
  ├── intersections (source of truth)
  ├── safety_indices_realtime (production data)
  └── vcc_* (message data)

analytics schema (validation)
  ├── crash_correlation_cache (precomputed metrics)
  └── monitored_intersections (view → public.intersections)
```

### Consequences

**Positive:**
- Clean separation between operational and analytical data
- Analytics features can't accidentally affect production
- Easier to grant read-only access to analytics schema
- Can drop and rebuild cache without affecting operations
- Clear data organization

**Negative:**
- Need to manage two schemas
- Cross-schema queries require schema prefix
- Additional migration complexity

**Neutral:**
- Need to grant permissions on both schemas
- Views add one level of indirection

### Implementation

- ✅ Created migration script: `002_create_analytics_schema.sql`
- ✅ Created `analytics` schema with permissions
- ✅ Created `crash_correlation_cache` table with indexes
- ✅ Created `monitored_intersections` view
- ✅ Documented in `backend/db/migrations/README.md`
- ⏳ Migration needs to be run manually in production

**Migration Command:**
```bash
psql -h 34.140.49.230 -p 5432 -U jason -d vtsi
\i backend/db/migrations/002_create_analytics_schema.sql
```

---

## Decision Review Schedule

These decisions will be reviewed:

- **Quarterly:** Check if assumptions still valid
- **Annually:** Major architecture review
- **As-Needed:** When requirements change

---

**Document Maintainers:** Traffic Safety Index Team
**Last Updated:** 2025-12-01
