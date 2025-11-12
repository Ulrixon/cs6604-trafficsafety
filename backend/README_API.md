# Safety Index FastAPI Backend

## Overview

This FastAPI backend computes real-time safety indices for traffic intersections using data from the smart-cities Trino database.

**Status:** ✅ MVP Complete - Returns real computed safety indices (not mock data)

---

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Start the Server

```bash
# From project root
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or run directly:
```bash
python -m uvicorn app.main:app --reload
```

### 3. Test the API

Open your browser to:
- **Health Check:** http://localhost:8000/health
- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **List Intersections:** http://localhost:8000/api/v1/safety/index/

Or run the test script:
```bash
python test_api_manual.py
```

---

## API Endpoints

### `GET /health`
Health check endpoint

**Response:**
```json
{"status": "ok"}
```

### `GET /api/v1/safety/index/`
List all intersections with current safety indices

**Response:**
```json
[
  {
    "intersection_id": 101,
    "intersection_name": "glebe-potomac",
    "safety_index": 45.2,
    "traffic_volume": 253,
    "latitude": 38.856,
    "longitude": -77.053
  },
  ...
]
```

**Note:** This endpoint:
- Queries Trino for last 24 hours of data
- Computes safety indices in real-time
- May take 10-30 seconds on first request
- Returns computed indices (0-100 scale)

### `GET /api/v1/safety/index/{intersection_id}`
Get a single intersection by ID

**Response:**
```json
{
  "intersection_id": 101,
  "intersection_name": "glebe-potomac",
  "safety_index": 45.2,
  "traffic_volume": 253,
  "latitude": 38.856,
  "longitude": -77.053
}
```

---

## How It Works

### Data Pipeline

1. **Data Collection** (`services/data_collection.py`)
   - Queries Trino `alexandria.safety-event` table
   - Queries Trino `alexandria.bsm` table
   - Handles microsecond timestamp conversion

2. **Feature Engineering** (`services/feature_engineering.py`)
   - Aggregates BSM data to 15-minute intervals
   - Computes vehicle counts, average speed, speed variance

3. **Index Computation** (`services/index_computation.py`)
   - Applies safety index formulas
   - Normalizes to 0-100 scale
   - Higher index = more dangerous

4. **API Service** (`services/intersection_service.py`)
   - Orchestrates the pipeline
   - Returns latest index per intersection

### Safety Index Formula (Simplified MVP)

```
safety_index = 
  (vehicle_count / max_vehicles × 30) +
  (event_count / max_events × 50) +
  (speed_variance / max_variance × 20)
  
Clamped to [0, 100]
```

**Risk Levels:**
- **0-30:** Low risk (green)
- **30-50:** Medium risk (yellow)
- **50-70:** High risk (orange)
- **70-100:** Critical risk (red)

---

## Configuration

Configuration is loaded from environment variables (or defaults in `app/core/config.py`):

```python
# Trino Database
TRINO_HOST = "smart-cities-trino.pre-prod.cloud.vtti.vt.edu"
TRINO_PORT = 443
TRINO_CATALOG = "smartcities_iceberg"

# Computation Settings
DEFAULT_LOOKBACK_DAYS = 7  # Not used in MVP (uses 24 hours)
EMPIRICAL_BAYES_K = 50     # Not used in MVP
```

Create a `.env` file in `backend/` to override:
```bash
cp .env.example .env
# Edit .env with your settings
```

---

## MVP vs Full Implementation

### ✅ Current MVP Features
- Real-time data from Trino database
- BSM vehicle feature extraction
- Safety event collection
- Basic safety index formula
- 15-minute interval aggregation
- Last 24 hours of data

### 📋 Full Implementation (See INTEGRATION_GUIDE.md)
- [ ] PSM VRU features (pedestrian/cyclist data)
- [ ] Complete safety index formulas from notebook
- [ ] Empirical Bayes stabilization
- [ ] Normalization constants (I_max, V_max, etc.)
- [ ] Time series endpoint (custom date ranges)
- [ ] POST /compute endpoint (trigger computation)
- [ ] Database caching (PostgreSQL)
- [ ] Background task scheduling

---

## Troubleshooting

### Issue: API returns empty list `[]`

**Possible causes:**
1. No data in Trino for last 24 hours
2. Trino connection failed (check OAuth2 authentication)
3. Query timeout

**Solution:**
- Check server logs for error messages
- Verify Trino credentials work in notebook
- Try reducing time window in `intersection_service.py`

### Issue: Slow response (>30 seconds)

**Expected behavior:**
- First request may take 15-30 seconds (Trino query + computation)
- Subsequent requests will be cached (future enhancement)

**Solution:**
- Add database caching (PostgreSQL)
- Pre-compute indices every 15 minutes (background task)

### Issue: Import errors

**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: Trino authentication fails

**Solution:**
- Trino uses OAuth2 - browser authentication required
- When you start the server, you may need to authenticate in browser
- Check that you can connect in the Jupyter notebook first

---

## Next Steps

### 1. Test the MVP
```bash
# Terminal 1: Start server
uvicorn app.main:app --reload

# Terminal 2: Test
python test_api_manual.py
```

### 2. Verify Real Data
- API should return actual intersection names (e.g., "glebe-potomac")
- Safety indices should vary (not all the same)
- Traffic volumes should be realistic

### 3. Full Implementation
See `INTEGRATION_GUIDE.md` for complete implementation plan:
- Port remaining notebook functions
- Add advanced features
- Implement caching
- Add scheduler

---

## Files Created

```
backend/
├── app/
│   ├── services/
│   │   ├── trino_client.py           ✅ Trino OAuth2 connection
│   │   ├── data_collection.py        ✅ Query safety events & BSM
│   │   ├── feature_engineering.py    ✅ Aggregate to 15-min intervals
│   │   ├── index_computation.py      ✅ Compute safety indices
│   │   └── intersection_service.py   ✅ Orchestrate pipeline (replaced mock data)
│   └── core/
│       └── config.py                 ✅ Added Trino settings
├── INTEGRATION_GUIDE.md              ✅ Full implementation plan
├── README_API.md                     ✅ This file
└── test_api_manual.py                ✅ Manual test script
```

---

## Support

**Documentation:**
- Full implementation guide: `INTEGRATION_GUIDE.md`
- Notebook reference: `../data/smart-cities-vtti-test.ipynb`

**Questions:**
- Check logs in terminal where server is running
- Review Trino queries in service files
- Compare to notebook cell outputs
