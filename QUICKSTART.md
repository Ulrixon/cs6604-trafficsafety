# Quick Start Guide - Traffic Safety Index System

## Current Status

✅ **Docker Stack is Running!**

The following services are now running on your local machine:

- **PostgreSQL Database** - Port 5433 (healthy)
- **Redis Cache** - Port 6380 (healthy)
- **Backend API** - Port 8001 (healthy) - http://localhost:8001
- **Data Collector** - Waiting for VCC credentials

## Next Steps

### 1. Add VCC API Credentials

To start collecting data, you need to add your VCC API credentials:

1. Open `backend/.env`
2. Replace the placeholder values:
   ```bash
   VCC_CLIENT_ID=your_actual_client_id
   VCC_CLIENT_SECRET=your_actual_client_secret
   ```
3. Restart the data collector:
   ```bash
   docker-compose restart data-collector
   ```

### 2. Verify Data Collection

Once you've added credentials, check that data collection is working:

```bash
# View collector logs
docker-compose logs -f data-collector

# You should see output like:
# ================================================================================
# COLLECTION CYCLE #1
# ================================================================================
# [1/2] Collecting VCC data...
# ✓ Retrieved 12 MapData messages
# ✓ Collected 145 BSM messages
# ...
```

### 3. Test the API

The API is accessible at http://localhost:8001

```bash
# Health check
curl http://localhost:8001/health

# API documentation (open in browser)
http://localhost:8001/docs

# Get safety indices (once data is collected)
curl http://localhost:8001/api/v1/intersections/safety-indices
```

## What's Running

### Services

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| PostgreSQL | 5433 | ✅ Running | Store safety indices and processed data |
| Redis | 6380 | ✅ Running | Caching layer for improved performance |
| Backend API | 8001 | ✅ Running | REST API for safety index queries |
| Data Collector | - | ⏸️ Waiting | Collects VCC data every 60 seconds |

### Data Flow

1. **Data Collector** → Polls VCC API every 60 seconds
2. **Raw Data** → Saved to Parquet files (`/app/data/parquet`)
3. **API Request** → Processes raw data on-demand
4. **Safety Indices** → Computed and returned via API

## Configuration

### Environment Variables

Key settings in `backend/.env`:

```bash
# VCC API Credentials (REQUIRED)
VCC_CLIENT_ID=your_client_id_here
VCC_CLIENT_SECRET=your_client_secret_here

# Collection Settings
COLLECTION_INTERVAL=60  # Seconds between collection cycles

# Safety Index Parameters
EMPIRICAL_BAYES_K=50  # Tuning parameter for EB adjustment
DEFAULT_LOOKBACK_DAYS=7  # Days of historical data to analyze
```

### Adjusting Collection Interval

To collect data more or less frequently:

1. Edit `backend/.env`
2. Change `COLLECTION_INTERVAL` (in seconds)
3. Restart: `docker-compose restart data-collector`

Examples:
- Every 5 minutes: `COLLECTION_INTERVAL=300`
- Every 30 seconds: `COLLECTION_INTERVAL=30`

## Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f data-collector
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 data-collector
```

### Check Container Status

```bash
docker-compose ps
```

### View Collected Data

```bash
# List Parquet files
ls -lh backend/data/parquet/

# Or on Windows
dir backend\data\parquet\
```

## Troubleshooting

### Data Collector Won't Start

**Problem**: Collector shows "Authentication error"

**Solution**:
1. Ensure VCC credentials are set in `backend/.env`
2. Credentials should NOT be in quotes
3. Restart: `docker-compose restart data-collector`

### No Data Being Collected

**Problem**: Collector runs but no data appears

**Possible causes**:
- VCC API may be temporarily unavailable
- Credentials may be invalid
- Network connectivity issues

**Check logs**:
```bash
docker-compose logs data-collector | grep "✗"
```

### API Not Responding

**Problem**: Can't access http://localhost:8001

**Check status**:
```bash
docker-compose ps api

# If not healthy, check logs
docker-compose logs api
```

### Port Conflicts

**Problem**: Port already in use

**Solution**: Edit `docker-compose.yml` ports:
```yaml
ports:
  - "8002:8000"  # Change 8001 to 8002
```

Then: `docker-compose up -d`

## Stopping the System

```bash
# Stop all services (preserves data)
docker-compose stop

# Stop and remove containers (preserves data volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

## Restarting the System

```bash
# Start all services
docker-compose up -d

# Rebuild and start (after code changes)
docker-compose up -d --build
```

## Getting VCC API Credentials

If you don't have VCC API credentials:

1. Contact the Virginia Tech Transportation Institute (VTTI)
2. Request access to the VCC Public API
3. You'll receive a `client_id` and `client_secret`

VCC Website: https://vcc.vtti.vt.edu

## Directory Structure

```
cs6604-trafficsafety/
├── docker-compose.yml          # Main orchestration file
├── backend/
│   ├── .env                    # Configuration (ADD YOUR CREDENTIALS HERE)
│   ├── Dockerfile              # API container
│   ├── Dockerfile.collector    # Data collector container
│   ├── data_collector.py       # Data collection service
│   ├── requirements.txt        # Python dependencies
│   ├── app/                    # API application code
│   └── data/
│       └── parquet/            # Collected data storage
├── data/
│   └── vcc-api-exploration.ipynb  # Jupyter notebook for exploration
└── DOCKER_README.md            # Detailed Docker documentation
```

## API Endpoints

Once running, visit http://localhost:8001/docs for full API documentation.

Key endpoints:
- `GET /health` - Health check
- `GET /api/v1/intersections` - List intersections
- `GET /api/v1/intersections/safety-indices` - Get safety scores
- `GET /api/v1/intersections/{id}` - Get specific intersection data

## Resources

- **Docker Setup Guide**: [DOCKER_README.md](DOCKER_README.md)
- **VCC API Documentation**: `files/VCC_Public_API_v3.1.pdf`
- **Data Exploration Notebook**: `data/vcc-api-exploration.ipynb`
- **Project Brief**: `memory-bank/project-brief.md`

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Review troubleshooting section above
3. Check project documentation
4. Review active context: `memory-bank/active-context.md`

---

**Status**: ✅ Docker Stack Running | ⏸️ Waiting for VCC Credentials

**Next Action**: Add your VCC API credentials to `backend/.env`
