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

*TimescaleDB alone:*
- Vendor lock-in
- Still need separate archival storage
- Higher costs for long-term retention

*AWS S3 instead of GCS:*
- GCP chosen for future integration with BigQuery
- Closer to VCC servers (latency)
- Consistent GCP ecosystem

*NoSQL (MongoDB, Cassandra):*
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

| Time Range | Data Source | Aggregation | Points Returned |
|------------|-------------|-------------|-----------------|
| ≤ 1 day | Realtime table | 1-minute | 1,440 |
| ≤ 7 days | Realtime table | Hourly | 168 |
| ≤ 30 days | Hourly table | Daily | 30 |
| ≤ 90 days | Hourly table | Weekly | 12-13 |
| > 90 days | Daily table | Monthly | Varies |

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

| Age | Storage Class | Cost (per GB/month) | Access Time |
|-----|---------------|---------------------|-------------|
| 0-30 days | Standard | $0.020 | Immediate |
| 31-365 days | Nearline | $0.010 | ~1 second |
| 366-730 days | Coldline | $0.004 | ~1-2 seconds |
| >730 days | Delete | $0 | N/A |

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

## Decision Review Schedule

These decisions will be reviewed:
- **Quarterly:** Check if assumptions still valid
- **Annually:** Major architecture review
- **As-Needed:** When requirements change

---

**Document Maintainers:** Traffic Safety Index Team
**Last Updated:** 2025-11-20
