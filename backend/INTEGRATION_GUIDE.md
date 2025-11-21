# Safety Index Integration Guide

This document outlines the complete integration of the Jupyter notebook safety index computation logic into the FastAPI backend.

## File Structure

```
backend/app/
├── services/
│   ├── trino_client.py          ✅ DONE - Trino connection singleton
│   ├── data_collection.py       📝 TODO - Phase 2: Baseline & exposure metrics
│   ├── feature_engineering.py   📝 TODO - Phase 3: BSM/PSM/events aggregation
│   ├── index_computation.py     📝 TODO - Phases 5-7: Compute indices
│   └── intersection_service.py  📝 TODO - Replace mock data
├── api/
│   └── intersection.py          📝 TODO - Add new endpoints
├── schemas/
│   └── intersection.py          📝 TODO - Add time series models
└── core/
    └── config.py                ✅ DONE - Added Trino & safety settings
```

---

## Summary of All Functions to Port

### Phase 2: Data Collection (data_collection.py)
- `collect_baseline_events()` - Query safety-event table, apply severity weights
- `collect_exposure_metrics()` - Query vehicle-count and vru-count tables

### Phase 3: Feature Engineering (feature_engineering.py)
- `collect_bsm_features()` - BSM vehicle features (speed, variance, braking)
- `collect_psm_features()` - PSM VRU features (pedestrian/cyclist counts)
- `aggregate_safety_events()` - Group events by 15-min intervals
- `create_master_feature_table()` - Join all data sources

### Phase 5-7: Index Computation (index_computation.py)
- `compute_normalization_constants()` - Calculate I_max, V_max, etc.
- `compute_safety_indices()` - Apply VRU/Vehicle/Combined formulas
- `apply_empirical_bayes()` - Stabilize with historical baseline

---

## MVP Implementation (Option C)

**Goal:** Get API returning real data ASAP, skip advanced features

### Step 1: Simplified data_collection.py
```python
# Just enough to get baseline events
def collect_baseline_events_simple(start_date, end_date):
    query = f"""
    SELECT intersection, event_type,
           from_unixtime(time_at_site / 1000000) as event_time
    FROM alexandria."safety-event"
    WHERE time_at_site >= {start_micros} AND time_at_site <= {end_micros}
    """
    return trino_client.execute_query(query)
```

### Step 2: Simplified feature_engineering.py
```python
# Just BSM vehicle counts and speed
def collect_bsm_features_simple(start_date, end_date):
    query = f"""
    SELECT intersection,
           from_unixtime(publish_timestamp / 1000000) as time,
           speed
    FROM alexandria.bsm
    WHERE publish_timestamp >= {start_micros} AND publish_timestamp <= {end_micros}
    """
    df = trino_client.execute_query(query)
    df['time_15min'] = pd.to_datetime(df['time']).dt.floor('15min')

    return df.groupby(['intersection', 'time_15min']).agg({
        'time': 'count',  # vehicle_count
        'speed': 'mean'   # avg_speed
    }).rename(columns={'time': 'vehicle_count', 'speed': 'avg_speed'}).reset_index()
```

### Step 3: Simplified index_computation.py
```python
# Basic formula without EB adjustment
def compute_safety_indices_simple(features_df):
    # Simple score: higher vehicle count + events = higher index
    features_df['safety_index'] = (
        (features_df['vehicle_count'] / features_df['vehicle_count'].max() * 50) +
        (features_df.get('event_count', 0) / max(features_df.get('event_count', 1).max(), 1) * 50)
    ).clip(0, 100)

    return features_df
```

### Step 4: Update intersection_service.py
Replace `get_all()` with:
```python
def get_all():
    from datetime import datetime, timedelta
    from .data_collection import collect_baseline_events_simple
    from .feature_engineering import collect_bsm_features_simple
    from .index_computation import compute_safety_indices_simple

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(hours=24)

    # Simplified pipeline
    features = collect_bsm_features_simple(start_dt, end_dt)
    indices = compute_safety_indices_simple(features)

    # Get latest per intersection
    latest = indices.sort_values('time_15min').groupby('intersection').last()

    return [
        Intersection(
            intersection_id=i,
            intersection_name=row.name,
            safety_index=row['safety_index'],
            traffic_volume=int(row['vehicle_count']),
            latitude=38.856, longitude=-77.053
        )
        for i, (_, row) in enumerate(latest.iterrows(), 101)
    ]
```

**Result:** API returns REAL data within 30 minutes of work!

---

## Full Implementation (Option A) - Using Guide Above

Once MVP proves concept, implement complete versions:

1. **data_collection.py** - Full Phase 2 logic with severity weights
2. **feature_engineering.py** - All Phase 3 functions with proper aggregation
3. **index_computation.py** - Exact formulas from notebook with EB adjustment
4. **Add new endpoints** - /compute and /timeseries
5. **Update schemas** - Time series models

---

## Key Technical Details

### Timestamp Conversion (CRITICAL)
Database stores **microseconds** (16 digits):
- SQL: `from_unixtime(publish_timestamp / 1000000)`
- Python: `int(datetime.timestamp() * 1000000)`

### Safety Index Formulas
```
VRU Index = 100 × [0.4×(I_VRU/I_max) + 0.2×(V/V_max) + 0.2×(S/S_ref) + 0.2×(σ_S/σ_max)]
Vehicle Index = 100 × [0.3×(I_vehicle/I_max) + 0.3×(V/V_max) + 0.2×(σ_S/σ_max) + 0.2×(hard_braking)]
Combined = 0.6×VRU + 0.4×Vehicle
```

### Empirical Bayes
```
λ = N / (N + k)  where k=50
Adjusted = λ × Raw + (1-λ) × Baseline
```

---

## Next Steps

1. ✅ Read this guide
2. 🚀 Implement MVP (Option C) - ~30 min
3. ✅ Test API returns real data
4. 🔄 Circle back to implement full version (Option A) - ~90 min
