# VCC API Safety Index Implementation Notes

## Overview

Implementation of VCC API data collection, historical index computation, and real-time streaming for the traffic safety index system.

## Key Design Decisions

### 1. Interval Strategy

**Historical Baseline**: 15-minute intervals (per paper requirements)
- Normalization constants computed from 15-minute aggregated historical data
- Safety index formulas designed for 15-minute intervals
- Historical index computation uses 15-minute intervals

**Real-Time Features**: 1-minute intervals for responsiveness
- Real-time WebSocket messages aggregated to 1-minute intervals
- Allows for faster response to changing conditions
- Better granularity for real-time monitoring

**Real-Time Indices**: 15-minute rolling windows
- Use 1-minute aggregated features as input
- Compute safety indices on 15-minute rolling windows
- Maintains compatibility with historical baseline while providing near-real-time updates

### 2. Timestamp Handling (CRITICAL)

**VCC API**: Uses milliseconds since epoch
- Parse: `pd.to_datetime(timestamp_ms, unit='ms')` or `datetime.fromtimestamp(timestamp_ms / 1000)`
- VCC API response field: `timestamp` or `publishTimestamp` (milliseconds)

**Trino Database**: Uses microseconds since epoch  
- SQL: `from_unixtime(publish_timestamp / 1000000)` 
- Python: `datetime.fromtimestamp(timestamp_us / 1000000)`
- Trino field: `publish_timestamp` (microseconds)

**Key Differences**:
- VCC: divide by 1000 (milliseconds → seconds)
- Trino: divide by 1000000 (microseconds → seconds)

**Common Mistakes to Avoid**:
- ❌ Using `/1000` for Trino data (will give wrong dates)
- ❌ Using `/1000000` for VCC data (will give wrong dates)
- ✅ Always verify timestamp format from source API/documentation

### 3. Data Source Integration

The system supports three modes:
- `DATA_SOURCE='trino'`: Use existing Trino database (default)
- `DATA_SOURCE='vcc'`: Use VCC API data from Parquet storage
- `DATA_SOURCE='both'`: Merge data from both sources (VCC as primary, Trino as fallback) - **Not yet implemented**

### 4. Feature Extraction Differences

**VCC API Format**:
- BSM: `bsm_message['bsmJson']['coreData']` contains vehicle data
- PSM: `psm_message['psmJson']['position']` contains VRU location
- Timestamps: milliseconds (different from Trino)
- Hard braking: `brakeAppliedStatus & 0x04` (same as Trino)

**Trino Format**:
- Direct column access: `df['lat']`, `df['lon']`, etc.
- Timestamps: microseconds
- Flat structure (no nested JSON)

### 5. Intersection Mapping

VCC API requires mapping lat/lon to intersection IDs:
- Use MapData API to get intersection reference points
- Simple proximity matching (within ~100m threshold)
- RSU name can also be used if available
- More sophisticated matching (Haversine distance) can be added later

### 6. Storage Strategy

**Parquet Files**: Date-partitioned storage
- `backend/data/parquet/features/features_YYYY-MM-DD.parquet`
- `backend/data/parquet/indices/indices_YYYY-MM-DD.parquet`
- `backend/data/parquet/constants/normalization_constants.parquet`

**Benefits**:
- Efficient columnar storage
- Fast date range queries
- Easy to append new data
- Compatible with pandas/pyarrow

### 7. Real-Time Processing

**WebSocket Streaming**:
- Connect to `wss://vcc.vtti.vt.edu/ws/bsm?key={key}` and `/ws/psm?key={key}`
- Buffer messages in 1-minute windows
- Process buffered messages when interval completes
- Update safety indices using 15-minute rolling window

**Update Frequency**:
- Features aggregated every 1 minute
- Indices recomputed every 1 minute (using 15-minute window)
- Parquet storage updated on 15-minute boundaries

## Implementation Files

### Backend Services

1. **`backend/app/services/vcc_client.py`** ✓
   - VCC API client with JWT authentication
   - Methods for all VCC endpoints (BSM, PSM, SPAT, MapData)
   - WebSocket key and URL management
   - Rate limiting to respect API limits

2. **`backend/app/services/parquet_storage.py`** ✓
   - Parquet file management
   - Date-partitioned storage
   - Load/save features and indices
   - Normalization constants storage

3. **`backend/app/services/vcc_feature_engineering.py`** ✓
   - Parse VCC API message format
   - Extract BSM features (vehicles)
   - Extract PSM features (VRUs)
   - Conflict detection algorithms
   - Timestamp handling for VCC format (milliseconds)

4. **`backend/app/services/vcc_data_collection.py`** ✓
   - Historical data collection from VCC API
   - Batch processing with pagination
   - Progress tracking and resumable collection

5. **`backend/app/services/vcc_historical_processor.py`** ✓
   - Batch processing of historical data
   - 15-minute interval aggregation
   - Normalization constant computation
   - Index computation pipeline

6. **`backend/app/services/vcc_realtime_streaming.py`** ✓
   - WebSocket connection management
   - 1-minute interval buffering
   - Message parsing and aggregation

7. **`backend/app/services/vcc_realtime_processor.py`** ✓
   - Real-time feature aggregation (1-minute)
   - 15-minute rolling window index computation
   - Parquet storage updates

### API Endpoints

**`backend/app/api/vcc.py`** ✓
- `GET /api/v1/vcc/status` - VCC API connection status
- `POST /api/v1/vcc/historical/collect` - Start historical data collection
- `POST /api/v1/vcc/historical/process` - Process historical data
- `POST /api/v1/vcc/realtime/start` - Start real-time streaming
- `POST /api/v1/vcc/realtime/stop` - Stop real-time streaming
- `GET /api/v1/vcc/realtime/status` - Real-time streaming status
- `GET /api/v1/vcc/mapdata` - Get MapData messages
- `GET /api/v1/vcc/test/connection` - Test VCC API connection

### Configuration

**`backend/app/core/config.py`** ✓
- `VCC_BASE_URL`: VCC API base URL (default: "https://vcc.vtti.vt.edu")
- `VCC_CLIENT_ID`: OAuth2 client ID (from env var)
- `VCC_CLIENT_SECRET`: OAuth2 client secret (from env var)
- `DATA_SOURCE`: 'trino', 'vcc', or 'both' (default: 'trino')
- `PARQUET_STORAGE_PATH`: Path to Parquet files (default: "backend/data/parquet")
- `REALTIME_ENABLED`: Enable/disable real-time streaming (default: False)

### Integration

**`backend/app/services/intersection_service.py`** ✓
- Modified to support VCC data source option
- Loads indices from Parquet storage when `DATA_SOURCE='vcc'`
- Falls back to Trino processing for 'trino' or 'both' modes

**`backend/app/main.py`** ✓
- Includes VCC API router at `/api/v1/vcc`

### Dependencies

**`backend/requirements.txt`** ✓
- `pyarrow>=14.0.0`: Parquet file support
- `websockets>=10.4`: WebSocket client support
- `aiohttp>=3.9.0`: Async HTTP client for WebSocket
- `requests>=2.28.0`: Already present, used for VCC API calls

## Usage Examples

### 1. Historical Data Collection

```python
from backend.app.services.vcc_historical_processor import process_historical_vcc_data
from datetime import datetime, timedelta

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

result = process_historical_vcc_data(
    start_date=start_date,
    end_date=end_date,
    save_to_parquet=True
)
```

### 2. Real-Time Streaming

```python
from backend.app.services.vcc_realtime_streaming import vcc_streamer
from backend.app.services.vcc_realtime_processor import vcc_realtime_processor

async def process_interval(bsm_messages, psm_messages, interval_start):
    result = await vcc_realtime_processor.process_minute_interval(
        bsm_messages,
        psm_messages,
        interval_start
    )
    print(f"Processed interval: {result}")

await vcc_streamer.start_streaming(
    callback=process_interval,
    intersection_id='all'
)
```

### 3. API Endpoints

```bash
# Test connection
curl http://localhost:8000/api/v1/vcc/test/connection

# Get status
curl http://localhost:8000/api/v1/vcc/status

# Start historical collection
curl -X POST http://localhost:8000/api/v1/vcc/historical/collect \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2024-01-01T00:00:00", "end_date": "2024-01-07T23:59:59"}'

# Start real-time streaming
curl -X POST http://localhost:8000/api/v1/vcc/realtime/start \
  -H "Content-Type: application/json" \
  -d '{"intersection_id": "all", "enable": true}'
```

## Testing Checklist

- [ ] Verify VCC API authentication works
- [ ] Test timestamp parsing (milliseconds vs microseconds)
- [ ] Verify intersection mapping from lat/lon
- [ ] Test conflict detection algorithms
- [ ] Verify Parquet storage/loading
- [ ] Test WebSocket streaming
- [ ] Verify 1-minute vs 15-minute aggregation
- [ ] Test real-time index updates
- [ ] Compare VCC indices with Trino indices (if both sources available)
- [ ] Test API endpoints

## Known Issues / Notes

1. **Timestamp Format**: VCC API uses milliseconds, Trino uses microseconds. Always verify which format you're working with.

2. **Intersection Mapping**: Simple proximity matching used initially. May need refinement based on actual data quality.

3. **Conflict Detection**: Spatial-temporal proximity algorithm is basic. May need tuning of thresholds based on data characteristics.

4. **Rate Limiting**: VCC API rate limits not explicitly documented. Using conservative 100ms interval between requests.

5. **WebSocket Reconnection**: Need to handle disconnections gracefully with automatic reconnection.

6. **Data Completeness**: VCC API may have sparse data coverage compared to Trino. Handle missing data gracefully.

7. **Historical Data Collection**: VCC API `/api/bsm/current` and `/api/psm/current` may not provide historical data directly. May need to rely on previously collected data or API-specific historical endpoints if available.

8. **'both' Mode**: Merging VCC and Trino data sources not yet implemented. Currently falls back to VCC-only when `DATA_SOURCE='both'`.

## Next Steps

1. ✅ Implement VCC API client service
2. ✅ Implement Parquet storage service
3. ✅ Implement VCC feature engineering
4. ✅ Implement historical data collection
5. ✅ Implement historical processor
6. ✅ Implement WebSocket streaming service
7. ✅ Implement real-time processor
8. ✅ Add VCC API endpoints
9. ✅ Integrate with intersection_service.py
10. ⏳ Implement frontend real-time visualization
11. ⏳ Implement 'both' mode data source merging
12. ⏳ Add comprehensive error handling and retry logic
13. ⏳ Add WebSocket reconnection logic
14. ⏳ Optimize conflict detection algorithms
