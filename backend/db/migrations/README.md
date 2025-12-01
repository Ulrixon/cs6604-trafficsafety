# Database Migrations

This directory contains SQL migration scripts for the GCP PostgreSQL database.

## Running Migrations

Connect to the GCP database and run migrations in order:

```bash
# Connect to database
psql -h 34.140.49.230 -p 5432 -U jason -d vtsi

# Run migrations
\i backend/db/migrations/002_create_analytics_schema.sql
```

## Migration History

| # | File | Description | Date |
|---|------|-------------|------|
| 001 | 01_init_schema.sql | Initial schema for safety indices | 2025-11-21 |
| 002 | 002_create_analytics_schema.sql | Analytics schema for crash validation | 2025-12-01 |

## Schema Organization

**public schema:**
- `intersections` - Monitored intersection locations
- `safety_indices_realtime` - Real-time safety index data
- `vcc_*` tables - VCC message data (BSM, PSM, MapData)

**analytics schema:**
- `crash_correlation_cache` - Cached correlation metrics
- `monitored_intersections` (view) - View into public.intersections

**External (GCP vtsi database):**
- `vdot_crashes` - Virginia crash data (accessed via analytics_service.py)

## Notes

- The analytics schema is separate to avoid mixing validation data with production safety indices
- The `vdot_crashes` table exists in the same GCP database but is managed separately
- Cache tables are optional performance optimizations
