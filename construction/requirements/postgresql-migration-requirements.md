# PostgreSQL + PostGIS Migration Requirements

**Feature Name:** PostgreSQL Database Migration
**Type:** Infrastructure / Data Layer Refactoring
**Priority:** High
**Status:** Planning
**Created:** 2025-11-20
**Owner:** Traffic Safety Index Team

---

## 1. Executive Summary

This document outlines requirements for migrating from Parquet-only storage to a hybrid architecture using PostgreSQL + PostGIS for operational data and Parquet for raw data archival. This change aligns with the original system design proposal and enables spatial queries, faster API responses, and better data management.

### Business Value
- **Performance:** 10-100x faster API queries through indexed lookups
- **Scalability:** Support for multiple concurrent intersections and users
- **Spatial Capabilities:** Enable geofencing, proximity analysis, route planning
- **Data Integrity:** ACID compliance and referential integrity
- **Operational Excellence:** Automated retention policies and data lifecycle management

---

## 2. Problem Statement

### Current Architecture Limitations
1. **Poor Query Performance:** Parquet requires full file scans for point queries
2. **No Spatial Indexing:** Cannot efficiently query "intersections within radius"
3. **Limited Concurrency:** File-based storage has locking issues
4. **No Transaction Support:** Cannot ensure data consistency across related tables
5. **Manual Data Management:** No automated aggregation or retention policies

### Impact
- Dashboard becomes slow with >1 intersection
- Cannot implement planned features (heatmaps, multi-intersection analysis)
- Difficult to maintain data quality and consistency

---

## 3. User Stories

### US-1: Fast Dashboard Loading
**As a** traffic operator
**I want** the dashboard to load in under 2 seconds
**So that** I can quickly assess current traffic safety conditions

**Acceptance Criteria:**
- Dashboard loads current safety indices for all intersections in <2s
- Map renders with all markers in <1s
- Time to interactive (TTI) < 3s

---

### US-2: Historical Data Queries
**As a** traffic analyst
**I want** to query historical data for any date range efficiently
**So that** I can analyze trends without waiting

**Acceptance Criteria:**
- 7-day history query returns in <3s
- 30-day query returns in <5s
- 90-day query returns in <10s
- Query response time scales linearly with date range

---

### US-3: Spatial Queries
**As a** city planner
**I want** to find all high-risk intersections within 5 miles of a location
**So that** I can plan targeted safety interventions

**Acceptance Criteria:**
- Can query intersections within radius
- Can query intersections along a route
- Can query intersections in a polygon (neighborhood)
- Spatial queries return in <2s

---

### US-4: Multi-Intersection Comparison
**As a** traffic researcher
**I want** to compare safety indices across multiple intersections
**So that** I can identify systemic patterns

**Acceptance Criteria:**
- Can query aggregated statistics for N intersections in one request
- Can filter intersections by safety index threshold
- Can rank intersections by various metrics
- Comparison queries return in <5s

---

### US-5: Data Retention Management
**As a** system administrator
**I want** automated data retention policies
**So that** the database doesn't grow unbounded

**Acceptance Criteria:**
- Real-time data retained for 48 hours
- Hourly aggregates retained for 90 days
- Daily aggregates retained indefinitely
- Automated cleanup runs without manual intervention

---

### US-6: Data Reprocessing
**As a** data engineer
**I want** to reprocess historical data when algorithms improve
**So that** we can apply better models to past data

**Acceptance Criteria:**
- Can read raw Parquet archives
- Can bulk-load processed data into PostgreSQL
- Can replace existing data for a date range
- Reprocessing doesn't impact live system

---

## 4. Functional Requirements

### FR-1: Database Schema
**Requirement:** Define PostgreSQL schema with PostGIS support

**Tables:**
1. **intersections** - Intersection metadata
   - Columns: id, name, latitude, longitude, geometry (PostGIS POINT), lane_count, revision, created_at, updated_at
   - Indexes: Spatial index on geometry, B-tree on id

2. **safety_indices_realtime** - 1-minute safety indices (hot data)
   - Columns: id, intersection_id, timestamp, combined_index, combined_index_eb, vru_index, vru_index_eb, vehicle_index, vehicle_index_eb, traffic_volume, vru_count, vehicle_event_count, vru_event_count, hour_of_day, day_of_week
   - Indexes: (intersection_id, timestamp), (timestamp), (combined_index_eb)
   - Partitioning: Range partition by timestamp (daily partitions)
   - Retention: 48 hours

3. **safety_indices_hourly** - Hourly aggregates (warm data)
   - Columns: id, intersection_id, hour_timestamp, avg_si, min_si, max_si, std_si, total_volume, avg_volume, high_risk_minutes, data_quality_score
   - Indexes: (intersection_id, hour_timestamp), (hour_timestamp)
   - Partitioning: Range partition by hour_timestamp (monthly partitions)
   - Retention: 90 days

4. **safety_indices_daily** - Daily aggregates (cold data)
   - Columns: id, intersection_id, date, avg_si, min_si, max_si, std_si, total_volume, avg_volume, high_risk_hours, peak_hour, peak_si
   - Indexes: (intersection_id, date), (date)
   - Retention: Indefinite

5. **normalization_constants** - System-wide normalization parameters
   - Columns: id, computed_at, constants (JSONB), valid_from, valid_until
   - Indexes: (computed_at), (valid_from, valid_until)

6. **data_quality_log** - Track data collection issues
   - Columns: id, timestamp, intersection_id, issue_type, severity, message, metadata (JSONB)
   - Indexes: (timestamp), (intersection_id, timestamp)

**Validation:**
- Schema matches design document
- All indexes created successfully
- PostGIS extension enabled
- TimescaleDB extension enabled (optional, for better time-series performance)

---

### FR-2: Data Ingestion Pipeline
**Requirement:** Dual-write to Parquet (raw) and PostgreSQL (processed)

**Flow:**
1. Collect data from VCC API
2. Save raw BSM/PSM/MapData → Parquet (immutable archive)
3. Extract features and compute safety indices
4. INSERT INTO PostgreSQL (realtime table)
5. Handle duplicate detection (upsert on conflict)

**Validation:**
- Both storage layers receive data within same collection cycle
- No data loss compared to current Parquet-only approach
- Failed database writes don't block Parquet writes
- Retry logic for transient database errors

---

### FR-3: API Query Migration
**Requirement:** Migrate all API queries from Parquet to PostgreSQL

**Endpoints to Migrate:**
1. `GET /api/v1/safety/index/` - Current safety indices
   - Query: `SELECT * FROM intersections JOIN (SELECT DISTINCT ON (intersection_id) * FROM safety_indices_realtime ORDER BY intersection_id, timestamp DESC) latest USING (intersection_id)`

2. `GET /api/v1/safety/history/{id}` - Time series data
   - Query: Use realtime table for <48h, hourly for 2-90 days, daily for >90 days
   - Implement smart query routing based on date range

3. `GET /api/v1/safety/history/{id}/stats` - Aggregated statistics
   - Query: Pre-computed from hourly/daily tables when possible

**Validation:**
- API response format unchanged (backward compatibility)
- Query performance improved by >10x
- Support same date ranges as before
- Graceful degradation if database unavailable (fallback to Parquet)

---

### FR-4: Data Aggregation Jobs
**Requirement:** Automated batch jobs for data aggregation and retention

**Jobs:**

**Job 1: Hourly Aggregation**
- Schedule: Every hour at :05 (5 min after hour end)
- Logic:
  ```sql
  INSERT INTO safety_indices_hourly
  SELECT
    intersection_id,
    date_trunc('hour', timestamp) as hour_timestamp,
    AVG(combined_index_eb) as avg_si,
    MIN(combined_index_eb) as min_si,
    MAX(combined_index_eb) as max_si,
    STDDEV(combined_index_eb) as std_si,
    SUM(traffic_volume) as total_volume,
    AVG(traffic_volume) as avg_volume,
    COUNT(*) FILTER (WHERE combined_index_eb > 75) as high_risk_minutes,
    (COUNT(*) / 60.0) as data_quality_score  -- % of expected 60 points
  FROM safety_indices_realtime
  WHERE timestamp >= (current_hour - interval '1 hour')
    AND timestamp < current_hour
  GROUP BY intersection_id, hour_timestamp
  ```

**Job 2: Daily Aggregation**
- Schedule: Daily at 00:05
- Logic: Aggregate previous day from hourly table

**Job 3: Retention Cleanup**
- Schedule: Daily at 02:00
- Logic:
  - Delete realtime data older than 48 hours
  - Delete hourly data older than 90 days
  - Vacuum tables

**Validation:**
- Jobs run on schedule without manual intervention
- Aggregations mathematically correct
- No data loss during cleanup
- Logs success/failure

---

### FR-5: Spatial Query API
**Requirement:** New API endpoints for spatial queries

**New Endpoints:**

1. `GET /api/v1/intersections/nearby?lat={lat}&lon={lon}&radius={meters}`
   - Returns intersections within radius
   - Uses PostGIS ST_DWithin for performance

2. `GET /api/v1/intersections/route?waypoints=[{lat,lon},...]&buffer={meters}`
   - Returns intersections along route
   - Uses PostGIS ST_Buffer and ST_Intersects

3. `GET /api/v1/intersections/area?polygon=[{lat,lon},...]`
   - Returns intersections within polygon
   - Uses PostGIS ST_Within

**Validation:**
- Spatial queries return correct results
- Performance <2s for typical queries
- Handles edge cases (antimeridian, poles)

---

### FR-6: Historical Data Backfill
**Requirement:** One-time migration of existing Parquet data to PostgreSQL

**Process:**
1. Read all Parquet indices files
2. Transform to PostgreSQL schema
3. Bulk load using COPY command
4. Create appropriate aggregates (hourly, daily)
5. Validate row counts and statistics match

**Validation:**
- All historical data accessible via API
- No data loss or corruption
- Statistics match pre-migration values
- Process can be re-run if needed

---

## 5. Non-Functional Requirements

### NFR-1: Performance
- API response time: <2s for 95th percentile
- Database query time: <500ms for 95th percentile
- Write throughput: >1000 rows/second
- Concurrent users: Support 50+ simultaneous dashboard users

### NFR-2: Scalability
- Handle up to 100 intersections initially
- Scale to 1000 intersections without architecture changes
- Database size: Plan for 500GB over 1 year

### NFR-3: Reliability
- Database uptime: 99.9% (allowing ~8 hours downtime/year)
- Automated backups: Daily, retained for 30 days
- Point-in-time recovery: Last 7 days
- Replication: Read replicas for scaling (future)

### NFR-4: Data Integrity
- ACID compliance for all transactions
- Foreign key constraints enforced
- Null constraints on critical fields
- Check constraints on value ranges (SI: 0-100)

### NFR-5: Security
- Connection encryption (TLS)
- Principle of least privilege for database users
- No raw passwords in config (use environment variables)
- Audit logging for schema changes

### NFR-6: Observability
- Database metrics exported to monitoring
- Query performance tracking
- Table size monitoring
- Partition health checks

---

## 6. Data Model Requirements

### DM-1: Intersection Model
```python
class Intersection(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    geometry: str  # PostGIS POINT (WKT format)
    lane_count: Optional[int]
    revision: Optional[int]
    metadata: Optional[Dict]  # JSONB for flexible attributes
    created_at: datetime
    updated_at: datetime
```

### DM-2: Safety Index Model (Realtime)
```python
class SafetyIndexRealtime(BaseModel):
    id: int
    intersection_id: int
    timestamp: datetime
    combined_index: float = Field(ge=0, le=100)
    combined_index_eb: Optional[float] = Field(ge=0, le=100)
    vru_index: Optional[float] = Field(ge=0, le=100)
    vru_index_eb: Optional[float] = Field(ge=0, le=100)
    vehicle_index: Optional[float] = Field(ge=0, le=100)
    vehicle_index_eb: Optional[float] = Field(ge=0, le=100)
    traffic_volume: int = Field(ge=0)
    vru_count: int = Field(ge=0)
    vehicle_event_count: int = Field(ge=0)
    vru_event_count: int = Field(ge=0)
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
```

---

## 7. Migration Requirements

### MR-1: Zero-Downtime Migration
- System remains operational during migration
- Dual-write mode: Both Parquet and PostgreSQL receive data
- Gradual API cutover with feature flags
- Rollback plan if issues detected

### MR-2: Data Validation
- Compare row counts: Parquet vs PostgreSQL
- Compare statistics: Mean, min, max for each intersection
- Spot-check random samples for correctness
- Automated validation reports

### MR-3: Backward Compatibility
- API responses maintain same JSON structure
- Frontend requires zero changes
- Parquet files still readable for audits
- Old queries continue to work during transition

---

## 8. Testing Requirements

### TR-1: Unit Tests
- Database model validations
- Service layer CRUD operations
- Constraint enforcement
- Data type conversions

### TR-2: Integration Tests
- End-to-end data flow: VCC → DB → API → Frontend
- Aggregation job correctness
- Spatial query accuracy
- Concurrent write handling

### TR-3: Performance Tests
- Load testing: 1000 req/second
- Query performance under load
- Database connection pool sizing
- Index effectiveness

### TR-4: Migration Tests
- Backfill process validation
- Data integrity checks
- Rollback procedures
- Disaster recovery

---

## 9. Acceptance Criteria

### Overall Success Criteria
- [ ] All API endpoints respond faster than Parquet baseline
- [ ] Historical data accessible for all past dates
- [ ] Spatial queries return correct results
- [ ] No data loss during migration
- [ ] Automated jobs run reliably
- [ ] Documentation complete
- [ ] Team trained on new architecture

### Phase Gates
**Phase 1 Complete:**
- [ ] PostgreSQL schema created
- [ ] PostGIS enabled and tested
- [ ] Connection from API verified

**Phase 2 Complete:**
- [ ] Data collector writing to both Parquet and PostgreSQL
- [ ] No errors in dual-write mode for 48 hours
- [ ] Row counts match between storage layers

**Phase 3 Complete:**
- [ ] All API endpoints migrated
- [ ] Performance benchmarks met
- [ ] Frontend works without changes

**Phase 4 Complete:**
- [ ] Historical data backfilled
- [ ] Aggregation jobs deployed
- [ ] Monitoring in place

---

## 10. Out of Scope

The following are explicitly **not** included in this migration:

- [ ] Multi-master replication
- [ ] Real-time streaming (WebSockets) to clients
- [ ] Machine learning model deployment
- [ ] Advanced analytics (anomaly detection, forecasting)
- [ ] Camera feed integration
- [ ] SPAT (signal timing) data storage
- [ ] User authentication and authorization
- [ ] Role-based access control

These may be addressed in future sprints.

---

## 11. Dependencies

### External Dependencies
- PostgreSQL 15+ with PostGIS 3.3+
- Docker Compose for local development
- pgAdmin or similar for database management
- Existing Parquet storage remains operational

### Internal Dependencies
- Existing data collector must continue running
- API endpoints must maintain backward compatibility
- Frontend should work without modification

---

## 12. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Data loss during migration | High | Low | Parquet archives remain; dual-write; validation |
| Performance worse than expected | Medium | Medium | Benchmarking before cutover; index tuning |
| Database downtime affects collection | High | Low | Parquet writes continue; queue for DB when available |
| Schema changes needed post-migration | Medium | Medium | Use migrations tool (Alembic); version control |
| Team unfamiliar with PostgreSQL | Low | High | Training; documentation; pair programming |

---

## 13. References

- Original Proposal: `docs/proposal.md`
- System Architecture: `construction/design/postgresql-migration-design.md`
- Sprint Plan: `construction/sprints/sprint-postgresql-migration.md`
- PostGIS Documentation: https://postgis.net/documentation/
- PostgreSQL Performance: https://www.postgresql.org/docs/current/performance-tips.html
