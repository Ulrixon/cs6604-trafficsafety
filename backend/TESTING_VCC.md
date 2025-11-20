# Testing VCC API Integration

This guide covers testing the VCC API integration both locally and in Docker.

## Prerequisites

1. **VCC API Credentials**: You need valid VCC API credentials
   - `VCC_CLIENT_ID`: OAuth2 client ID from VCC API
   - `VCC_CLIENT_SECRET`: OAuth2 client secret from VCC API
   
2. **Python Environment**: Python 3.11+ with dependencies installed

3. **Network Access**: Access to `https://vcc.vtti.vt.edu` from your network

## Quick Start

### Option 1: Local Testing (Recommended First)

1. **Set up environment variables**:
   ```bash
   # Copy example environment file
   cp backend/.env.example backend/.env
   
   # Edit .env and add your VCC credentials
   VCC_CLIENT_ID=your_client_id_here
   VCC_CLIENT_SECRET=your_client_secret_here
   DATA_SOURCE=vcc  # or 'trino' or 'both'
   ```

2. **Install dependencies** (if not already done):
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Start the server locally**:
   ```bash
   # From backend/ directory
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   
   # Or from project root
   uvicorn backend.app.main:app --reload
   ```

4. **Run the test script**:
   ```bash
   # From backend/ directory
   python test_vcc_api.py
   
   # Or from project root
   python backend/test_vcc_api.py
   ```

5. **Verify in browser**:
   - API docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/health
   - VCC status: http://localhost:8000/api/v1/vcc/status

### Option 2: Docker Testing

1. **Set up environment file**:
   ```bash
   # Create .env file in backend/ directory
   cp backend/.env.example backend/.env
   
   # Edit .env and add your VCC credentials
   ```

2. **Build and run with Docker Compose**:
   ```bash
   cd backend
   docker-compose up --build
   ```

3. **In another terminal, run tests**:
   ```bash
   # Make sure test script can access the API
   python backend/test_vcc_api.py
   ```

4. **Check Docker logs**:
   ```bash
   docker-compose logs -f api
   ```

## Test Script Overview

The `test_vcc_api.py` script tests:

1. **Status Check**: Verify VCC API connection status
2. **Connection Test**: Test authentication and API endpoints
3. **MapData Retrieval**: Test MapData endpoint
4. **Historical Collection**: Test starting historical data collection
5. **Real-Time Status**: Check real-time streaming status

## Manual Testing

### 1. Test Connection

```bash
# Check status
curl http://localhost:8000/api/v1/vcc/status

# Test connection
curl http://localhost:8000/api/v1/vcc/test/connection
```

### 2. Test MapData

```bash
# Get all MapData
curl http://localhost:8000/api/v1/vcc/mapdata

# Get MapData for specific intersection
curl http://localhost:8000/api/v1/vcc/mapdata?intersection_id=12345
```

### 3. Test Historical Collection

```bash
# Start historical data collection (last 7 days)
curl -X POST http://localhost:8000/api/v1/vcc/historical/collect \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01T00:00:00",
    "end_date": "2024-01-07T23:59:59",
    "save_to_parquet": true
  }'
```

**Note**: This starts a background job. Check server logs for progress:
- Local: Check terminal output
- Docker: `docker-compose logs -f api`

### 4. Test Real-Time Streaming

```bash
# Check real-time status
curl http://localhost:8000/api/v1/vcc/realtime/status

# Start real-time streaming (requires REALTIME_ENABLED=true)
curl -X POST http://localhost:8000/api/v1/vcc/realtime/start \
  -H "Content-Type: application/json" \
  -d '{"intersection_id": "all", "enable": true}'

# Stop real-time streaming
curl -X POST http://localhost:8000/api/v1/vcc/realtime/stop
```

**Warning**: Real-time streaming runs continuously until stopped.

### 5. Test Safety Index Endpoints

```bash
# Get all intersections (uses VCC data if DATA_SOURCE=vcc)
curl http://localhost:8000/api/v1/safety/index/

# Get specific intersection
curl http://localhost:8000/api/v1/safety/index/101
```

## Verification Checklist

### ✓ Basic Connectivity
- [ ] Server starts without errors
- [ ] Health endpoint returns `{"status": "ok"}`
- [ ] VCC status endpoint returns connection info

### ✓ Authentication
- [ ] VCC status shows "authenticated"
- [ ] Connection test shows authenticated: true
- [ ] No authentication errors in logs

### ✓ Data Retrieval
- [ ] MapData endpoint returns data (may be empty if no intersections)
- [ ] Connection test shows message counts > 0
- [ ] No connection errors in logs

### ✓ Data Processing
- [ ] Historical collection starts successfully
- [ ] Parquet files created in `backend/data/parquet/`
- [ ] Safety index endpoints return data (if VCC data collected)

### ✓ Real-Time (Optional)
- [ ] Real-time status endpoint works
- [ ] Can start/stop streaming (if enabled)
- [ ] Messages buffer correctly

## Troubleshooting

### Authentication Fails

**Symptom**: Status shows "failed" or "disconnected"

**Solutions**:
1. Verify `VCC_CLIENT_ID` and `VCC_CLIENT_SECRET` in `.env`
2. Check credentials are correct (no extra spaces)
3. Verify network can reach `https://vcc.vtti.vt.edu`
4. Check server logs for detailed error messages

### No Data Retrieved

**Symptom**: MapData count is 0 or endpoints return empty

**Solutions**:
1. Check if VCC API has data available
2. Test VCC API directly using `data/vcc-api-exploration.ipynb`
3. Verify your credentials have access to the data
4. Check if intersection IDs are correct

### Parquet Storage Issues

**Symptom**: Files not created or permission errors

**Solutions**:
1. Create directory: `mkdir -p backend/data/parquet/{features,indices,constants}`
2. Check write permissions on `backend/data/parquet/`
3. In Docker: Verify volume mount in `docker-compose.yml`

### Real-Time Streaming Issues

**Symptom**: Cannot start streaming or connection drops

**Solutions**:
1. Set `REALTIME_ENABLED=true` in `.env`
2. Check WebSocket connectivity: `wss://vcc.vtti.vt.edu/ws/bsm?key=...`
3. Check server logs for WebSocket errors
4. Verify network allows WebSocket connections

### Docker-Specific Issues

**Symptom**: Container won't start or can't access API

**Solutions**:
1. Check `.env` file exists and has correct values
2. Verify volume mounts in `docker-compose.yml`
3. Check port 8000 is not already in use: `netstat -an | findstr 8000`
4. View logs: `docker-compose logs api`

## Expected Test Results

### Successful Test Output

```
======================================================================
  VCC API Integration Test Suite
======================================================================

Testing API at: http://localhost:8000
VCC endpoints at: http://localhost:8000/api/v1/vcc

======================================================================
  1. Testing VCC API Status
======================================================================
Status Code: 200
✓ Connection Status: connected
  Authentication: authenticated
  Base URL: https://vcc.vtti.vt.edu
  Data Source: vcc
  Real-time Enabled: false
  MapData Available: 5
  Streaming Active: False

======================================================================
  2. Testing VCC API Connection
======================================================================
Status Code: 200
Status: success
Authenticated: True

Endpoints:
  ✓ BSM: 42 messages
  ✓ PSM: 18 messages
  ✓ MAPDATA: 5 messages

...

======================================================================
  Test Summary
======================================================================
  status              ✓ PASS
  connection          ✓ PASS
  mapdata             ✓ PASS
  historical          ✓ PASS
  realtime_status     ✓ PASS

Results: 5/5 tests passed

✓ All tests passed! VCC API integration is working.
```

## Next Steps

After successful testing:

1. **Collect Historical Data**: Run historical collection to build baseline
2. **Process Indices**: Use historical processor to compute indices
3. **Enable Real-Time**: Set `REALTIME_ENABLED=true` for live updates
4. **Frontend Integration**: Update Streamlit frontend to show VCC data
5. **Production Deployment**: Configure for production environment

## Additional Resources

- VCC API Documentation: `files/VCC_Public_API_v3.1.pdf`
- VCC Exploration Notebook: `data/vcc-api-exploration.ipynb`
- Implementation Notes: `memory-bank/vcc-api-implementation-notes.md`

