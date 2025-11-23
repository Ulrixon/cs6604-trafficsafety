# Operational Guide - Traffic Safety Index System

## System Status: ✅ FULLY OPERATIONAL

Last Updated: 2025-11-20

---

## Architecture Overview

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
    ├── indices/        - Computed safety indices
    └── constants/      - Normalization constants
    ↓
Historical Processing (batch)
    ↓
Real-time Processing (1-min intervals)
    ↓
FastAPI (http://localhost:8001)
    └── /api/v1/safety/index/
```

---

## Quick Commands

### Monitoring

**View Data Collection Logs:**

```bash
docker-compose logs -f data-collector
```

**View API Logs:**

```bash
docker-compose logs -f api
```

**Check All Services:**

```bash
docker-compose ps
```

### Data Operations

**View Collected BSM Files:**

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -lh /app/data/parquet/raw/bsm/
```

**Count Total BSM Messages:**

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector find /app/data/parquet/raw/bsm/ -name "*.parquet" | wc -l
```

**View Normalization Constants:**

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -lh /app/data/parquet/constants/
```

**View Safety Indices:**

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -lh /app/data/parquet/indices/
```

### Processing

**Run Historical Processing (1 day lookback):**

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 1 --storage-path /app/data/parquet
```

**Run Historical Processing (7 days lookback):**

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 7 --storage-path /app/data/parquet
```

**Run Historical Processing (specific intersection):**

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 7 --intersection "0.0" --storage-path /app/data/parquet
```

### API Testing

**Health Check:**

```bash
curl http://localhost:8001/health
```

**Get All Safety Indices (formatted):**

```bash
curl -s http://localhost:8001/api/v1/safety/index/ | python -m json.tool
```

**Get Specific Intersection:**

```bash
curl http://localhost:8001/api/v1/safety/index/0
```

**Run Sensitivity Analysis:**

```bash
curl -X POST "http://localhost:8001/api/v1/analysis/sensitivity" \
     -H "Content-Type: application/json" \
     -d '{"intersection_id": "0.0", "start_date": "2025-11-01", "end_date": "2025-11-07", "perturbation_range": 0.25, "steps": 10}'
```

**View API Documentation:**
Open in browser: http://localhost:8001/docs

### Frontend Dashboard

**Access Dashboard:**
Open in browser: http://localhost:8501

**Pages:**

1. **Real-time Dashboard**: Live safety indices and map.
2. **Trend Analysis**: Historical trends and statistics.
3. **Sensitivity Analysis**:
   - Select date range (Start/End Date).
   - Adjust perturbation range (e.g., ±25%).
   - View Stability Gauge, Heatmaps, and Trajectory plots.
   - _Note: Calculations for long ranges (e.g., 30 days) are optimized to run in <2 seconds._

### Container Management

**Restart Data Collector:**

```bash
docker-compose restart data-collector
```

**Rebuild and Restart All Services:**

```bash
docker-compose up -d --build
```

**Stop All Services:**

```bash
docker-compose down
```

**Stop and Remove Data (CAUTION):**

```bash
docker-compose down -v
```

---

## Current System Metrics

### Data Collection (as of last run)

- **Total BSM Messages**: 1,678+
- **Total PSM Messages**: 21
- **MapData Messages**: 4
- **Intersections Covered**: 4 (from MapData)
- **Collection Interval**: 60 seconds
- **Data Format**: Parquet (Snappy compression)

### Safety Indices (Example)

- **Intersection 0.0**:
  - Safety Index: 33.44
  - Range: 33.44 - 52.43
  - Traffic Volume: 29 vehicles
  - Time Intervals: 4 (15-minute aggregation)

### Normalization Constants (Latest)

- **I_max**: 1.0 (Maximum incident rate)
- **V_max**: 182.0 (Maximum vehicle volume)
- **σ_max**: 8.3 (Maximum speed variance)
- **S_ref**: 10.4 (Reference speed)

---

## Service Endpoints

### API Service (Port 8001)

- **Base URL**: http://localhost:8001
- **Health**: `GET /health`
- **List Intersections**: `GET /api/v1/safety/index/`
- **Get Intersection**: `GET /api/v1/safety/index/{id}`
- **API Docs**: `GET /docs`

### Database (Port 5433)

- **Type**: PostgreSQL 15
- **Host**: localhost:5433
- **Database**: trafficsafety
- **User**: trafficsafety
- **Password**: trafficsafety_dev

### Redis Cache (Port 6380)

- **Host**: localhost:6380
- **Use**: API response caching

---

## Data Pipeline Workflow

### 1. Initial Setup (One-time)

```bash
# Start all services
docker-compose up -d

# Wait for data collection (5-10 minutes to get sufficient data)
# Monitor progress
docker-compose logs -f data-collector

# Run historical processing to compute normalization constants
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 1 --storage-path /app/data/parquet
```

### 2. Continuous Operation

Once set up, the system runs automatically:

1. **Data Collector**: Polls VCC API every 60 seconds
2. **Raw Storage**: Saves BSM/PSM/MapData to Parquet
3. **Real-time Processing**: Computes indices every collection cycle
4. **API**: Serves latest indices via REST endpoints

### 3. Periodic Maintenance

**Daily**: Check data collection status

```bash
docker-compose logs --tail=50 data-collector
```

**Weekly**: Run historical processing to update normalization constants

```bash
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 7 --storage-path /app/data/parquet
```

**Monthly**: Review and archive old Parquet files if needed

---

## Configuration

### Environment Variables (.env)

**VCC API Credentials:**

```bash
VCC_CLIENT_ID=course-cs6604-student-djjay
VCC_CLIENT_SECRET=wHqQjvksKE6rYLYedkuIqewrFtEOpjHH
VCC_BASE_URL=https://vcc.vtti.vt.edu
```

**Collection Settings:**

```bash
COLLECTION_INTERVAL=60              # Seconds between collections
DEFAULT_LOOKBACK_DAYS=7             # Historical processing window
EMPIRICAL_BAYES_K=50               # EB tuning parameter
```

**Storage:**

```bash
PARQUET_STORAGE_PATH=/app/data/parquet
DATA_SOURCE=vcc                     # Use VCC data source
REALTIME_ENABLED=true              # Enable real-time processing
```

### Adjusting Collection Frequency

Edit `backend/.env`:

```bash
COLLECTION_INTERVAL=30   # Collect every 30 seconds
```

Then restart:

```bash
docker-compose restart data-collector
```

---

## Performance Characteristics

### Data Collection

- **Throughput**: ~20-50 BSM messages per minute
- **Latency**: < 5 seconds per collection cycle
- **Storage**: ~15KB per BSM batch (compressed Parquet)

### Historical Processing

- **Processing Time**: ~2-3 seconds for 1 day of data (1,600 messages)
- **Memory Usage**: < 200MB
- **Output**: Features, Indices, Normalization Constants

### API Response Times

- **List Intersections**: < 200ms (cached)
- **Get Intersection**: < 100ms (cached)
- **Health Check**: < 10ms

---

## Storage Management

### Disk Usage Estimates

- **Raw BSM Data**: ~15KB per batch × 1,440 batches/day = ~21MB/day
- **Raw PSM Data**: Minimal (few pedestrians)
- **MapData**: ~5KB per batch (mostly static)
- **Features/Indices**: ~10MB/day (aggregated)

### Cleanup Strategy

Parquet files are organized by date. To archive old data:

```bash
# Archive data older than 30 days
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector find /app/data/parquet/raw/bsm/ -name "*.parquet" -mtime +30 -exec rm {} \;
```

---

## Windows-Specific Notes

### Git Bash Path Conversion

Git Bash on Windows automatically converts Unix paths to Windows paths. This breaks Docker commands.

**Solution**: Prefix commands with `MSYS_NO_PATHCONV=1`

**Example:**

```bash
# ❌ Broken
docker exec trafficsafety-collector ls /app/data/parquet

# ✅ Fixed
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls /app/data/parquet
```

### Volume Mounting

Docker volumes persist data between container restarts:

```yaml
volumes:
  - parquet_data:/app/data/parquet # Named volume (persistent)
```

To view volume location:

```bash
docker volume inspect cs6604-trafficsafety_parquet_data
```

---

## Backup and Recovery

### Backup Parquet Data

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Copy volume data (Windows)
docker run --rm -v cs6604-trafficsafety_parquet_data:/data -v $(pwd)/backups/$(date +%Y%m%d):/backup alpine tar czf /backup/parquet-data.tar.gz -C /data .
```

### Restore from Backup

```bash
# Stop services
docker-compose down

# Restore data
docker run --rm -v cs6604-trafficsafety_parquet_data:/data -v $(pwd)/backups/20251120:/backup alpine tar xzf /backup/parquet-data.tar.gz -C /data

# Restart services
docker-compose up -d
```

---

## Integration Points

### Adding New Data Sources

Currently supports VCC API. To add Trino:

1. Set `DATA_SOURCE=both` in `.env`
2. Configure Trino credentials
3. Modify `intersection_service.py` to merge sources

### WebSocket Streaming (Future)

Real-time updates can be added via:

```python
# In main.py
from fastapi import WebSocket

@app.websocket("/ws/safety-indices")
async def websocket_endpoint(websocket: WebSocket):
    # Stream real-time indices
    pass
```

### External Dashboards

API supports CORS for external dashboards:

```python
# Already configured in main.py
allow_origins=["*"]  # Adjust for production
```

---

## Support and Resources

### Documentation

- **API Docs**: http://localhost:8001/docs
- **VCC API Spec**: `files/VCC_Public_API_v3.1.pdf`
- **Sprint Plan**: `construction/sprint-plan.md`
- **Troubleshooting**: `memory-bank/troubleshooting.md`

### Key Files

- **Data Collector**: `backend/data_collector.py`
- **Historical Processor**: `backend/process_historical.py`
- **Feature Engineering**: `backend/app/services/vcc_feature_engineering.py`
- **Index Computation**: `backend/app/services/index_computation.py`
- **Storage Service**: `backend/app/services/parquet_storage.py`

### Logs Location

```bash
# Container logs
docker-compose logs [service-name]

# Inside container
MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -lh /app/
```

---

## Quick Reference Card

| Action            | Command                                                                                                                         |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Start System      | `docker-compose up -d`                                                                                                          |
| Stop System       | `docker-compose down`                                                                                                           |
| View Logs         | `docker-compose logs -f data-collector`                                                                                         |
| Process History   | `MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector python process_historical.py --days 1 --storage-path /app/data/parquet` |
| Test API          | `curl http://localhost:8001/api/v1/safety/index/`                                                                               |
| Check Data        | `MSYS_NO_PATHCONV=1 docker exec trafficsafety-collector ls -lh /app/data/parquet/raw/bsm/`                                      |
| Restart Collector | `docker-compose restart data-collector`                                                                                         |
| Rebuild All       | `docker-compose up -d --build`                                                                                                  |

---

**Last Updated**: 2025-11-20
**System Version**: 0.1.0
**Status**: Production-Ready ✅
