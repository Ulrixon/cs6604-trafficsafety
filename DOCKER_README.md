# Docker Deployment Guide

This guide explains how to deploy the Traffic Safety Intersection Index system using Docker.

## Architecture

The Docker deployment includes:

1. **PostgreSQL Database** - Stores safety indices and historical data
2. **Backend API** - FastAPI service exposing safety index endpoints
3. **Data Collector** - Continuous service collecting VCC data and computing safety indices
4. **Redis** - Caching layer for improved performance (optional)

## Prerequisites

- Docker Desktop installed and running
- VCC API credentials (client_id and client_secret)
- At least 2GB of free disk space

## Quick Start

### 1. Configure VCC Credentials

Edit `backend/.env` and add your VCC API credentials:

```bash
VCC_CLIENT_ID=your_actual_client_id
VCC_CLIENT_SECRET=your_actual_client_secret
```

### 2. Launch the Stack

From the project root directory:

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f data-collector
```

### 3. Verify Services

Check that all services are healthy:

```bash
docker-compose ps
```

You should see:
- `trafficsafety-db` - Running (healthy)
- `trafficsafety-api` - Running (healthy)
- `trafficsafety-collector` - Running
- `trafficsafety-redis` - Running (healthy)

### 4. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Get safety indices (after collector runs)
curl http://localhost:8000/api/v1/intersections/safety-indices
```

## Configuration

### Environment Variables

Key variables in `backend/.env`:

- `VCC_CLIENT_ID` - Your VCC API client ID (required)
- `VCC_CLIENT_SECRET` - Your VCC API client secret (required)
- `COLLECTION_INTERVAL` - Seconds between data collection cycles (default: 60)
- `EMPIRICAL_BAYES_K` - Tuning parameter for safety index (default: 50)
- `DEFAULT_LOOKBACK_DAYS` - Days of historical data to analyze (default: 7)
- `REALTIME_ENABLED` - Enable WebSocket streaming (default: true)

### Adjusting Collection Interval

To collect data every 5 minutes instead of 1 minute:

```bash
# In backend/.env
COLLECTION_INTERVAL=300
```

Then restart:

```bash
docker-compose restart data-collector
```

## Data Storage

Data is stored in Docker volumes:

- `parquet_data` - Raw VCC data in Parquet format (shared between API and collector)
- `postgres_data` - PostgreSQL database files
- `redis_data` - Redis cache

To view volume locations:

```bash
docker volume ls
docker volume inspect cs6604-trafficsafety_parquet_data
```

## Monitoring

### View Data Collection Progress

```bash
# Follow collector logs
docker-compose logs -f data-collector
```

You'll see output like:

```
================================================================================
COLLECTION CYCLE #1
Time: 2025-11-19 16:45:32
================================================================================

[1/4] Collecting VCC data...
✓ Retrieved 12 MapData messages
✓ Collected 145 BSM messages
✓ Collected 8 PSM messages

[2/4] Saving data to Parquet storage...
✓ Saved 145 BSM messages
✓ Saved 8 PSM messages
✓ Saved 12 MapData messages

[3/4] Computing features...
✓ Computed features for 12 intersections

[4/4] Computing safety indices...
✓ Computed safety indices for 12 intersections

================================================================================
SAMPLE SAFETY INDICES
================================================================================
intersection_id  safety_score  risk_level  total_vehicles  conflict_count
            100          8.5        LOW              145               2
            101          6.2     MEDIUM               98               5
            102          4.1       HIGH               67              12
...
```

### API Metrics

```bash
# View API logs
docker-compose logs -f api
```

## Troubleshooting

### VCC Authentication Errors

If you see "Failed to get VCC access token":

1. Verify credentials in `backend/.env`
2. Ensure credentials are not quoted
3. Check VCC API status at https://vcc.vtti.vt.edu

```bash
# Test authentication manually
docker-compose exec data-collector python -c "
from app.services.vcc_client import vcc_client
token = vcc_client.get_access_token()
print('✓ Success!' if token else '✗ Failed')
"
```

### No Data Collected

Check collector logs:

```bash
docker-compose logs data-collector | grep "✗"
```

Common issues:
- VCC API may be down or rate-limiting
- Network connectivity issues
- Invalid credentials

### Database Connection Issues

```bash
# Check database health
docker-compose exec db pg_isready -U trafficsafety

# Connect to database
docker-compose exec db psql -U trafficsafety
```

## Stopping the Stack

```bash
# Stop all services (preserves data)
docker-compose stop

# Stop and remove containers (preserves data volumes)
docker-compose down

# Stop and remove everything including data
docker-compose down -v
```

## Development Mode

For development with hot-reload:

```bash
# Backend code changes will auto-reload
docker-compose up

# Rebuild after dependency changes
docker-compose up --build
```

## Production Deployment

For production:

1. Update `docker-compose.yml`:
   - Remove volume mounts for app directories
   - Set `DEBUG=false`
   - Configure proper CORS origins
   - Use secrets for credentials (not .env files)

2. Use production-grade database:
   - Use managed PostgreSQL (AWS RDS, Azure Database, etc.)
   - Configure backups
   - Enable SSL connections

3. Add reverse proxy:
   - Nginx or Traefik for SSL termination
   - Load balancing for multiple API instances

## Scaling

To run multiple data collectors:

```bash
docker-compose up --scale data-collector=3
```

Note: Each collector will operate independently. Consider adding coordination (e.g., using Redis locks) to avoid duplicate work.

## Backup and Restore

### Backup Parquet Data

```bash
# Create backup
docker run --rm -v cs6604-trafficsafety_parquet_data:/data -v $(pwd):/backup ubuntu tar czf /backup/parquet_backup.tar.gz /data

# Restore backup
docker run --rm -v cs6604-trafficsafety_parquet_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/parquet_backup.tar.gz -C /
```

### Backup PostgreSQL

```bash
# Create backup
docker-compose exec db pg_dump -U trafficsafety > backup.sql

# Restore backup
docker-compose exec -T db psql -U trafficsafety < backup.sql
```

## Resources

- VCC API Documentation: `files/VCC_Public_API_v3.1.pdf`
- Backend API Documentation: http://localhost:8000/docs (when running)
- Project Documentation: `README.md`

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review troubleshooting section above
3. Check project README and documentation
