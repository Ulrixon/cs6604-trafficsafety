# Dual-Write Migration Guide

This guide explains how to enable and test the dual-write feature for migrating from Parquet-only storage to PostgreSQL + PostGIS + Parquet.

---

## Overview

The **dual-write** feature writes safety index data to both storage systems simultaneously:
- **PostgreSQL + PostGIS**: Operational database for fast queries
- **Local Parquet files**: Archive and fallback

This enables:
1. Zero-downtime migration from Parquet to PostgreSQL
2. Data validation before full cutover
3. Easy rollback if issues occur

---

## Prerequisites

✅ **Completed:**
- PostgreSQL + PostGIS 3.3 running in Docker
- Database schema deployed ([backend/db/init/01_init_schema.sql](../backend/db/init/01_init_schema.sql))
- Database service layer implemented ([backend/app/services/db_service.py](../backend/app/services/db_service.py))
- Data collector updated for dual-write ([backend/data_collector.py](../backend/data_collector.py))

---

## Phase 1: Enable Dual-Write (Testing)

### Step 1: Enable the Feature Flag

Edit [.env](../backend/.env) or set environment variables:

```bash
# Enable dual-write (writes to both Parquet and PostgreSQL)
ENABLE_DUAL_WRITE=true

# Keep fallback enabled for safety
FALLBACK_TO_PARQUET=true

# PostgreSQL disabled for queries (still using Parquet)
USE_POSTGRESQL=false
```

### Step 2: Restart the Data Collector

```bash
docker-compose restart data-collector
```

### Step 3: Monitor Logs

```bash
docker logs trafficsafety-collector --tail 100 -f
```

You should see:
```
VCC DATA COLLECTOR SERVICE
================================================================================
PostgreSQL Dual-Write: ✓ ENABLED
  Database URL: postgresql://trafficsafety:trafficsafety_dev@db:5432/trafficsafety
  Fallback to Parquet: True
================================================================================

Saving 5 computed safety indices...
  ✓ Parquet: Saved 5 records
  ✓ PostgreSQL: Saved 5/5 records
✓ Dual-write successful (Parquet + PostgreSQL)
```

---

## Phase 2: Validate Data Consistency

### Step 1: Check PostgreSQL Has Data

```bash
docker exec trafficsafety-db psql -U trafficsafety -d trafficsafety -c "
    SELECT COUNT(*) as total_records,
           COUNT(DISTINCT intersection_id) as intersections,
           MIN(timestamp) as oldest,
           MAX(timestamp) as latest
    FROM safety_indices_realtime;
"
```

Expected output:
```
 total_records | intersections |         oldest          |         latest
---------------+---------------+-------------------------+-------------------------
           120 |             1 | 2025-11-21 04:00:00+00  | 2025-11-21 05:59:00+00
```

### Step 2: Compare Sample Data

Run the validation script (created in Phase 3.3):
```bash
docker exec trafficsafety-collector python scripts/validate_dual_write.py
```

### Step 3: Verify Spatial Data

```bash
docker exec trafficsafety-db psql -U trafficsafety -d trafficsafety -c "
    SELECT id, name, ST_AsText(geometry) as location
    FROM intersections;
"
```

---

## Phase 3: Enable PostgreSQL Queries (Gradual Cutover)

**⚠️ Only proceed after validating Phase 2!**

### Step 1: Switch 10% of API Queries to PostgreSQL

Edit [.env](../backend/.env):
```bash
# Enable PostgreSQL for queries (10% rollout)
USE_POSTGRESQL=true
FALLBACK_TO_PARQUET=true  # Keep fallback enabled
ENABLE_DUAL_WRITE=true     # Keep dual-write enabled
```

### Step 2: Restart API

```bash
docker-compose restart api
```

### Step 3: Monitor API Health

```bash
curl http://localhost:8001/health | jq
```

Expected response:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": {
    "enabled": true,
    "status": "healthy",
    "name": "trafficsafety",
    "postgis_version": "3.3 USE_GEOS=1 USE_PROJ=1 USE_STATS=1",
    "connection_pool": {
      "size": 5,
      "checked_in": 4,
      "checked_out": 1,
      "overflow": 0
    }
  }
}
```

### Step 4: Test Query Performance

```bash
# Query from PostgreSQL
time curl -s http://localhost:8001/api/v1/safety/index/ > /dev/null

# Check logs for errors
docker logs trafficsafety-api --tail 50
```

---

## Phase 4: Full Cutover

**⚠️ Only after 48 hours of stable dual-write with no errors!**

### Step 1: Switch 100% of Queries to PostgreSQL

Edit [.env](../backend/.env):
```bash
USE_POSTGRESQL=true
FALLBACK_TO_PARQUET=true   # Still keep fallback for safety
ENABLE_DUAL_WRITE=true
```

### Step 2: Monitor for 24 Hours

- Check API response times
- Monitor database connection pool
- Watch for fallback usage in logs

### Step 3: Disable Fallback (Optional)

After 7 days of stable operation:
```bash
USE_POSTGRESQL=true
FALLBACK_TO_PARQUET=false  # No longer needed
ENABLE_DUAL_WRITE=true      # Keep for archival
```

---

## Rollback Procedure

If issues occur at any phase:

### Immediate Rollback

```bash
# Revert to Parquet-only mode
docker-compose exec api sh -c 'export USE_POSTGRESQL=false && kill -HUP 1'
```

Or restart with updated .env:
```bash
USE_POSTGRESQL=false
FALLBACK_TO_PARQUET=true
ENABLE_DUAL_WRITE=false
```

```bash
docker-compose restart api data-collector
```

### Verify Rollback

```bash
curl http://localhost:8001/health | jq '.database.enabled'
# Should return: false
```

---

## Monitoring Dual-Write Status

### Data Collector Statistics

View statistics in collector logs:
```
COLLECTION STATISTICS
================================================================================
Total Collections: 15
Total BSM Messages: 1,250
Total PSM Messages: 340
Total MapData: 4
Errors: 0

Dual-Write Statistics:
  Parquet Writes: 15
  PostgreSQL Writes: 15
  Dual-Write Errors: 0

Last Collection: 2025-11-21 05:30:00
================================================================================
```

### Database Growth

```bash
docker exec trafficsafety-db psql -U trafficsafety -d trafficsafety -c "
    SELECT * FROM v_table_sizes ORDER BY size_bytes DESC LIMIT 5;
"
```

### Connection Pool Status

```bash
curl -s http://localhost:8001/health | jq '.database.connection_pool'
```

---

## Troubleshooting

### Dual-Write Errors

**Symptom:** `Dual-Write Errors: 5` in statistics

**Diagnosis:**
```bash
docker logs trafficsafety-collector --tail 200 | grep "PostgreSQL write failed"
```

**Solutions:**
1. Check database connectivity: `docker ps | grep trafficsafety-db`
2. Verify schema: `docker exec trafficsafety-db psql -U trafficsafety -d trafficsafety -c "\dt"`
3. Check disk space: `docker exec trafficsafety-db df -h`

### Connection Pool Exhaustion

**Symptom:** `checked_out` == `size` + `overflow`

**Solutions:**
1. Increase pool size in [.env](../backend/.env):
   ```bash
   DB_POOL_SIZE=10
   DB_MAX_OVERFLOW=20
   ```
2. Restart API: `docker-compose restart api`

### Data Mismatch

**Symptom:** Parquet and PostgreSQL have different row counts

**Diagnosis:**
```bash
docker exec trafficsafety-collector python scripts/validate_dual_write.py --detailed
```

**Solutions:**
1. Review validation report
2. Check for data collector restarts during migration
3. Run backfill script (Phase 6)

---

## Success Criteria

Before declaring migration complete:

- [ ] **48 hours** of dual-write with zero errors
- [ ] **Row counts match** between Parquet and PostgreSQL
- [ ] **Sample data matches** (within 0.1% tolerance)
- [ ] **API response time improved** (10-100x faster)
- [ ] **No fallback usage** in logs for 24 hours
- [ ] **Connection pool healthy** (checked_out < 80% of size)

---

## Next Phase: GCP Cloud Storage

After successful dual-write migration, proceed to:
- **Phase 2:** GCP Cloud Storage setup
- **Phase 5:** Batch aggregation jobs (hourly, daily)
- **Phase 6:** Historical data backfill

See: [construction/sprints/sprint-postgresql-migration.md](../construction/sprints/sprint-postgresql-migration.md)

---

**Last Updated:** 2025-11-21
**Maintainer:** Traffic Safety Index Team
