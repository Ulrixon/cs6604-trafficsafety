# Traffic Safety Backend API Documentation

## Base URL
```
http://localhost:8000/api/v1
```

## Endpoints

### 1. List All Intersections with Latest Safety Scores
```
GET /safety/index/
```

**Response:**
```json
[
  {
    "id": 1,
    "intersection_name": "glebe-potomac",
    "safety_index": 50.82,
    "traffic_volume": 184,
    "last_updated": "2025-11-09T23:45:00"
  }
]
```

---

### 2. Get Single Intersection by ID
```
GET /safety/index/{intersection_id}
```

**Parameters:**
- `intersection_id` (path): Integer ID of intersection

**Response:**
```json
{
  "id": 1,
  "intersection_name": "glebe-potomac",
  "safety_index": 50.82,
  "traffic_volume": 184,
  "last_updated": "2025-11-09T23:45:00"
}
```

---

### 3. List Available Intersections
```
GET /safety/index/intersections/list
```

**Response:**
```json
{
  "intersections": ["glebe-potomac"]
}
```

---

### 4. Get Safety Score at Specific Time
```
GET /safety/index/time/specific
```

**Query Parameters:**
- `intersection` (required): Intersection name (e.g., "glebe-potomac")
- `time` (required): ISO 8601 datetime (e.g., "2025-11-09T10:00:00")
- `bin_minutes` (optional): Time bin size in minutes (default: 15, range: 1-60)

**Example:**
```bash
curl "http://localhost:8000/api/v1/safety/index/time/specific?intersection=glebe-potomac&time=2025-11-09T10:00:00&bin_minutes=15"
```

**Response:**
```json
{
  "intersection": "glebe-potomac",
  "time_bin": "2025-11-09T10:00:00",
  "safety_score": 39.76,
  "mcdm_index": 39.76,
  "vehicle_count": 7,
  "vru_count": 0,
  "avg_speed": 16.59,
  "speed_variance": 159.74,
  "incident_count": 0,
  "saw_score": 44.39,
  "edas_score": 17.74,
  "codas_score": 65.82
}
```

**Fields:**
- `safety_score`: Overall safety score (0-100, higher is safer)
- `mcdm_index`: Multi-Criteria Decision Making index (same as safety_score)
- `vehicle_count`: Number of vehicles detected in time bin
- `vru_count`: Number of vulnerable road users (pedestrians, cyclists)
- `avg_speed`: Average vehicle speed (mph)
- `speed_variance`: Variance in speed distribution
- `incident_count`: Number of safety events/incidents
- `saw_score`: Simple Additive Weighting method score
- `edas_score`: EDAS (Evaluation based on Distance from Average Solution) score
- `codas_score`: CODAS (Combinative Distance-based Assessment) score

---

### 5. Get Safety Score Trend Over Time Range
```
GET /safety/index/time/range
```

**Query Parameters:**
- `intersection` (required): Intersection name (e.g., "glebe-potomac")
- `start_time` (required): ISO 8601 datetime (e.g., "2025-11-09T08:00:00")
- `end_time` (required): ISO 8601 datetime (e.g., "2025-11-09T18:00:00")
- `bin_minutes` (optional): Time bin size in minutes (default: 15, range: 1-60)

**Constraints:**
- `end_time` must be after `start_time`
- Time range cannot exceed 7 days

**Example:**
```bash
curl "http://localhost:8000/api/v1/safety/index/time/range?intersection=glebe-potomac&start_time=2025-11-09T08:00:00&end_time=2025-11-09T10:00:00&bin_minutes=15"
```

**Response:**
```json
[
  {
    "intersection": "glebe-potomac",
    "time_bin": "2025-11-09T08:00:00",
    "safety_score": 54.66,
    "mcdm_index": 54.66,
    "vehicle_count": 12,
    "vru_count": 0,
    "avg_speed": 16.39,
    "speed_variance": 168.02,
    "incident_count": 1,
    "saw_score": 56.92,
    "edas_score": 42.11,
    "codas_score": 71.10
  },
  {
    "intersection": "glebe-potomac",
    "time_bin": "2025-11-09T09:00:00",
    "safety_score": 43.66,
    "mcdm_index": 43.66,
    "vehicle_count": 9,
    "vru_count": 0,
    "avg_speed": 15.96,
    "speed_variance": 197.65,
    "incident_count": 0,
    "saw_score": 49.55,
    "edas_score": 19.46,
    "codas_score": 74.18
  }
]
```

---

## MCDM Methodology

The safety scores are calculated using a hybrid Multi-Criteria Decision Making (MCDM) approach:

1. **Data Collection**: Gathers data from multiple tables:
   - BSM (Basic Safety Messages)
   - PSM (Personal Safety Messages)
   - Vehicle count
   - VRU (Vulnerable Road User) count
   - Speed distribution
   - Safety events

2. **Criteria Weighting**: Uses CRITIC method to determine weights for:
   - Vehicle count
   - VRU count
   - Average speed
   - Speed variance
   - Incident count

3. **Scoring Methods**: Combines three MCDM methods:
   - **SAW** (Simple Additive Weighting): Weighted sum of normalized criteria
   - **EDAS** (Evaluation based on Distance from Average Solution): Distance from average performance
   - **CODAS** (Combinative Distance-based Assessment): Euclidean and Taxicab distances

4. **Final Score**: Average of SAW, EDAS, and CODAS scores, scaled to 0-100

5. **Historical Context**: Uses 24-hour lookback window for CRITIC weight calculation

---

## Data Availability

Currently available data:
- **Intersection**: glebe-potomac
- **Date Range**: Up to November 9, 2025
- **Time Resolution**: 15-minute bins (configurable)

---

## Error Responses

### 404 Not Found
```json
{
  "detail": "No data available for intersection 'xyz' at time 2025-11-09T10:00:00"
}
```

### 400 Bad Request
```json
{
  "detail": "end_time must be after start_time"
}
```

```json
{
  "detail": "Time range cannot exceed 7 days"
}
```

---

## Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "ok"
}
```
