# Intersection History Feature - Technical Design

**Feature Name**: Intersection Historical Safety Index Analysis
**Version**: 1.0
**Date**: 2025-11-20
**Status**: Draft

---

## 1. Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (Streamlit)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Intersection Details Panel                              │   │
│  │    ├─ Current Stats Display                              │   │
│  │    └─ [📊 View History Button] ─┐                        │   │
│  │                                  │                        │   │
│  │  Historical View (Expandable) <──┘                       │   │
│  │    ├─ Date Range Selector                                │   │
│  │    ├─ Plotly Time Series Chart                           │   │
│  │    ├─ Statistics Cards                                   │   │
│  │    └─ CSV Export Button                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              │ HTTP/JSON                         │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend API (FastAPI)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  New Endpoints: /api/v1/safety/history/                 │   │
│  │    ├─ GET /{id}        → Time series data               │   │
│  │    ├─ GET /{id}/stats  → Aggregate statistics           │   │
│  │    └─ GET /            → All intersections (limited)     │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │  Service Layer: history_service.py                       │   │
│  │    ├─ get_intersection_history()                         │   │
│  │    ├─ get_aggregate_stats()                              │   │
│  │    ├─ _aggregate_time_series()                           │   │
│  │    └─ _apply_smart_defaults()                            │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │  Existing: parquet_storage.py                            │   │
│  │    └─ load_indices(start_date, end_date, intersection)   │   │
│  └─────────────────────────┬───────────────────────────────┘   │
└────────────────────────────┼───────────────────────────────────┘
                             │
                             ▼
                  ┌─────────────────────────┐
                  │  Parquet Storage         │
                  │  backend/data/parquet/   │
                  │    indices/              │
                  │      indices_2025-11-*.parquet│
                  │      (1-minute intervals)│
                  └─────────────────────────┘
```

### 1.2 Component Interaction Flow

**Typical User Flow**:
1. User clicks intersection on map → Detail panel opens
2. User clicks "📊 View History" button
3. Frontend calls `GET /api/v1/safety/history/{id}?days=7`
4. Backend service:
   - Queries Parquet storage (7 days of files)
   - Applies smart default (7 days → hourly aggregation)
   - Transforms to Pydantic models
   - Returns JSON
5. Frontend receives data, renders Plotly chart
6. User adjusts date range → Repeat from step 3

---

## 2. Data Models & Schemas

### 2.1 Backend Pydantic Schemas

**File**: `backend/app/schemas/intersection.py` (add to existing file)

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class IntersectionHistoryPoint(BaseModel):
    """
    Single data point in time series.

    Represents one time interval (1-min, hourly, or daily depending on aggregation).
    """
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp for this interval"
    )
    safety_index: float = Field(
        ...,
        ge=0,
        le=100,
        description="Combined safety index (EB-adjusted if available)"
    )
    vru_index: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Vulnerable road user safety index"
    )
    vehicle_index: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Vehicle safety index"
    )
    traffic_volume: int = Field(
        ...,
        ge=0,
        description="Vehicle count for this interval"
    )
    hour_of_day: int = Field(
        ...,
        ge=0,
        le=23,
        description="Hour (0-23) for temporal pattern analysis"
    )
    day_of_week: int = Field(
        ...,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-11-20T14:30:00Z",
                "safety_index": 44.6,
                "vru_index": 42.1,
                "vehicle_index": 48.9,
                "traffic_volume": 94,
                "hour_of_day": 14,
                "day_of_week": 2
            }
        }


class IntersectionHistory(BaseModel):
    """
    Complete time series data for one intersection.
    """
    intersection_id: str = Field(
        ...,
        description="Unique intersection identifier"
    )
    intersection_name: str = Field(
        ...,
        description="Human-readable intersection name"
    )
    data_points: List[IntersectionHistoryPoint] = Field(
        ...,
        description="Array of time series data points"
    )
    start_date: datetime = Field(
        ...,
        description="Start of queried time range"
    )
    end_date: datetime = Field(
        ...,
        description="End of queried time range"
    )
    total_points: int = Field(
        ...,
        ge=0,
        description="Number of data points returned"
    )
    aggregation: str = Field(
        ...,
        description="Time aggregation level applied (1min, 1hour, 1day, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intersection_id": "0.0",
                "intersection_name": "Intersection 0.0",
                "start_date": "2025-11-13T00:00:00Z",
                "end_date": "2025-11-20T23:59:59Z",
                "total_points": 168,
                "aggregation": "1hour",
                "data_points": [{"...": "..."}]
            }
        }


class IntersectionAggregateStats(BaseModel):
    """
    Aggregated statistics over a time period.
    """
    intersection_id: str
    intersection_name: str
    period_start: datetime
    period_end: datetime

    # Safety Index Statistics
    avg_safety_index: float = Field(..., description="Mean safety index")
    min_safety_index: float = Field(..., description="Minimum observed SI")
    max_safety_index: float = Field(..., description="Maximum observed SI")
    std_safety_index: float = Field(..., description="Standard deviation of SI")

    # Traffic Statistics
    total_traffic_volume: int = Field(..., description="Sum of all vehicle counts")
    avg_traffic_volume: float = Field(..., description="Mean vehicle count per interval")

    # Risk Metrics
    high_risk_intervals: int = Field(
        ...,
        description="Count of intervals where SI > 75"
    )
    high_risk_percentage: float = Field(
        ...,
        description="Percentage of high-risk intervals"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intersection_id": "0.0",
                "intersection_name": "Intersection 0.0",
                "period_start": "2025-11-13T00:00:00Z",
                "period_end": "2025-11-20T23:59:59Z",
                "avg_safety_index": 44.6,
                "min_safety_index": 18.2,
                "max_safety_index": 78.9,
                "std_safety_index": 12.3,
                "total_traffic_volume": 947280,
                "avg_traffic_volume": 94.0,
                "high_risk_intervals": 12,
                "high_risk_percentage": 7.1
            }
        }
```

### 2.2 Frontend Data Models

**File**: `frontend/app/models/history.py` (NEW)

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

# Frontend uses same schemas as backend (reuse via API)
# Import from API response and validate

class HistoryDataPoint(BaseModel):
    """Frontend representation of time series point"""
    timestamp: datetime
    safety_index: float
    vru_index: Optional[float]
    vehicle_index: Optional[float]
    traffic_volume: int
    hour_of_day: int
    day_of_week: int

class HistoryData(BaseModel):
    """Frontend representation of intersection history"""
    intersection_id: str
    intersection_name: str
    data_points: List[HistoryDataPoint]
    start_date: datetime
    end_date: datetime
    total_points: int
    aggregation: str
```

---

## 3. Backend Implementation Design

### 3.1 Service Layer

**File**: `backend/app/services/history_service.py` (NEW - ~250 lines)

```python
"""
Service layer for historical intersection safety data.

This service provides time series queries and aggregation over
stored Parquet files with 1-minute interval safety indices.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
import pandas as pd
import logging

from ..models.intersection import Intersection
from .parquet_storage import parquet_storage
from ..schemas.intersection import (
    IntersectionHistory,
    IntersectionHistoryPoint,
    IntersectionAggregateStats
)

logger = logging.getLogger(__name__)

# Aggregation constants
AGGREGATION_LEVELS = ["1min", "1hour", "1day", "1week", "1month"]
MAX_POINTS_THRESHOLD = 10000  # Warn if query would return >10k points


def get_intersection_history(
    intersection_id: str,
    start_date: date,
    end_date: date,
    aggregation: Optional[str] = None
) -> IntersectionHistory:
    """
    Retrieve historical time series data for an intersection.

    Args:
        intersection_id: Unique intersection identifier
        start_date: Start date for query (inclusive)
        end_date: End date for query (inclusive)
        aggregation: Time aggregation level or None for auto-select

    Returns:
        IntersectionHistory object with time series data

    Raises:
        ValueError: If no data found or invalid parameters
    """
    # Validate dates
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    # Apply smart defaults if aggregation not specified
    if aggregation is None:
        aggregation = _get_smart_default_aggregation(start_date, end_date)
    elif aggregation not in AGGREGATION_LEVELS:
        raise ValueError(f"Invalid aggregation. Must be one of {AGGREGATION_LEVELS}")

    logger.info(f"Querying history for {intersection_id}: {start_date} to {end_date}, agg={aggregation}")

    # Load raw data from Parquet storage
    try:
        indices_df = parquet_storage.load_indices(
            start_date=start_date,
            end_date=end_date,
            intersection_id=intersection_id
        )
    except Exception as e:
        logger.error(f"Failed to load indices: {e}")
        raise ValueError(f"Unable to load data for intersection {intersection_id}")

    if len(indices_df) == 0:
        raise ValueError(
            f"No data found for intersection {intersection_id} "
            f"between {start_date} and {end_date}"
        )

    # Apply aggregation if needed
    if aggregation != "1min":
        indices_df = _aggregate_time_series(indices_df, aggregation)

    # Convert DataFrame to Pydantic models
    data_points = _dataframe_to_history_points(indices_df)

    # Get intersection name (with fallback)
    intersection_name = _get_intersection_name(intersection_id)

    return IntersectionHistory(
        intersection_id=intersection_id,
        intersection_name=intersection_name,
        data_points=data_points,
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.max.time()),
        total_points=len(data_points),
        aggregation=aggregation
    )


def get_aggregate_stats(
    intersection_id: str,
    start_date: date,
    end_date: date
) -> IntersectionAggregateStats:
    """
    Compute aggregated statistics over a time period.

    Args:
        intersection_id: Unique intersection identifier
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        IntersectionAggregateStats with computed metrics
    """
    # Load data
    indices_df = parquet_storage.load_indices(
        start_date=start_date,
        end_date=end_date,
        intersection_id=intersection_id
    )

    if len(indices_df) == 0:
        raise ValueError(f"No data found for intersection {intersection_id}")

    # Determine which safety index column to use (prefer EB-adjusted)
    safety_col = _get_safety_index_column(indices_df)

    # Compute statistics
    high_risk_count = int((indices_df[safety_col] > 75).sum())
    total_intervals = len(indices_df)

    return IntersectionAggregateStats(
        intersection_id=intersection_id,
        intersection_name=_get_intersection_name(intersection_id),
        period_start=indices_df['time_15min'].min(),
        period_end=indices_df['time_15min'].max(),
        avg_safety_index=float(indices_df[safety_col].mean()),
        min_safety_index=float(indices_df[safety_col].min()),
        max_safety_index=float(indices_df[safety_col].max()),
        std_safety_index=float(indices_df[safety_col].std()),
        total_traffic_volume=int(indices_df['vehicle_count'].sum()),
        avg_traffic_volume=float(indices_df['vehicle_count'].mean()),
        high_risk_intervals=high_risk_count,
        high_risk_percentage=round((high_risk_count / total_intervals) * 100, 2) if total_intervals > 0 else 0.0
    )


def get_all_intersections_history(
    start_date: date,
    end_date: date,
    aggregation: Optional[str] = None
) -> List[IntersectionHistory]:
    """
    Get history for all intersections.

    Note: May return large dataset. Consider limiting date range.
    """
    # Load all indices (no intersection filter)
    indices_df = parquet_storage.load_indices(
        start_date=start_date,
        end_date=end_date,
        intersection_id=None
    )

    if len(indices_df) == 0:
        return []

    # Group by intersection
    histories = []
    for intersection_id in indices_df['intersection'].unique():
        try:
            history = get_intersection_history(
                str(intersection_id),
                start_date,
                end_date,
                aggregation
            )
            histories.append(history)
        except Exception as e:
            logger.warning(f"Failed to load history for {intersection_id}: {e}")
            continue

    return histories


# ============================================================================
# INTERNAL HELPER FUNCTIONS
# ============================================================================

def _get_smart_default_aggregation(start_date: date, end_date: date) -> str:
    """
    Determine appropriate aggregation level based on date range.

    Rules:
    - ≤1 day: 1-minute intervals
    - ≤7 days: Hourly aggregation
    - ≤30 days: Daily aggregation
    - ≤90 days: Weekly aggregation
    - >90 days: Monthly aggregation
    """
    days = (end_date - start_date).days + 1  # Inclusive

    if days <= 1:
        return "1min"
    elif days <= 7:
        return "1hour"
    elif days <= 30:
        return "1day"
    elif days <= 90:
        return "1week"
    else:
        return "1month"


def _aggregate_time_series(df: pd.DataFrame, aggregation: str) -> pd.DataFrame:
    """
    Resample time series to coarser granularity.

    Aggregation rules:
    - Safety indices: Mean
    - Traffic volume: Sum
    - Hour/day: First value in period
    """
    df = df.copy()
    df['time_15min'] = pd.to_datetime(df['time_15min'])
    df = df.set_index('time_15min')

    # Map aggregation string to pandas resample rule
    resample_rule = {
        "1min": "1min",
        "1hour": "1h",
        "1day": "1D",
        "1week": "1W",
        "1month": "1ME"  # Month end
    }.get(aggregation, "1h")

    # Define aggregation functions
    agg_dict = {
        'Combined_Index': 'mean',
        'Combined_Index_EB': 'mean',
        'VRU_Index': 'mean',
        'VRU_Index_EB': 'mean',
        'Vehicle_Index': 'mean',
        'Vehicle_Index_EB': 'mean',
        'vehicle_count': 'sum',  # Traffic volume should be summed
        'hour_of_day': 'first',
        'day_of_week': 'first'
    }

    # Only aggregate columns that exist
    agg_dict_filtered = {k: v for k, v in agg_dict.items() if k in df.columns}

    # Resample
    resampled = df.groupby('intersection').resample(resample_rule).agg(
        agg_dict_filtered
    ).reset_index()

    return resampled


def _dataframe_to_history_points(df: pd.DataFrame) -> List[IntersectionHistoryPoint]:
    """
    Convert DataFrame to list of IntersectionHistoryPoint objects.
    """
    points = []
    safety_col = _get_safety_index_column(df)

    for _, row in df.iterrows():
        point = IntersectionHistoryPoint(
            timestamp=pd.to_datetime(row['time_15min']),
            safety_index=float(row[safety_col]),
            vru_index=float(row.get('VRU_Index_EB', row.get('VRU_Index', None))) if 'VRU_Index' in row else None,
            vehicle_index=float(row.get('Vehicle_Index_EB', row.get('Vehicle_Index', None))) if 'Vehicle_Index' in row else None,
            traffic_volume=int(row['vehicle_count']),
            hour_of_day=int(row['hour_of_day']),
            day_of_week=int(row['day_of_week'])
        )
        points.append(point)

    return points


def _get_safety_index_column(df: pd.DataFrame) -> str:
    """
    Determine which safety index column to use.
    Prefer Empirical Bayes adjusted (_EB suffix) if available.
    """
    if 'Combined_Index_EB' in df.columns:
        return 'Combined_Index_EB'
    elif 'Combined_Index' in df.columns:
        return 'Combined_Index'
    else:
        raise ValueError("No safety index column found in data")


def _get_intersection_name(intersection_id: str) -> str:
    """
    Lookup human-readable intersection name.

    TODO: Implement proper lookup from MapData cache or database.
    For now, return formatted ID.
    """
    return f"Intersection {intersection_id}"


def _estimate_point_count(start_date: date, end_date: date, aggregation: str) -> int:
    """
    Estimate number of data points for a query.
    Used for warnings about large datasets.
    """
    days = (end_date - start_date).days + 1

    points_per_day = {
        "1min": 1440,  # 60 min/hr * 24 hr
        "1hour": 24,
        "1day": 1,
        "1week": 1/7,
        "1month": 1/30
    }

    return int(days * points_per_day.get(aggregation, 24))
```

### 3.2 API Endpoints

**File**: `backend/app/api/history.py` (NEW - ~200 lines)

```python
"""
Historical safety index API endpoints.

Provides time series queries and statistics for intersection safety data.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import date, datetime, timedelta
from typing import List, Optional
import logging

from ..schemas.intersection import (
    IntersectionHistory,
    IntersectionAggregateStats
)
from ..services.history_service import (
    get_intersection_history,
    get_aggregate_stats,
    get_all_intersections_history
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/safety/history",
    tags=["Safety Index History"]
)


@router.get("/{intersection_id}", response_model=IntersectionHistory)
def get_history(
    intersection_id: str,
    start_date: Optional[date] = Query(
        None,
        description="Start date (YYYY-MM-DD). If not provided, calculated from 'days' parameter."
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date (YYYY-MM-DD). Defaults to today if not provided."
    ),
    days: Optional[int] = Query(
        7,
        ge=1,
        le=365,
        description="Days of history to retrieve (if start_date not provided). Default: 7"
    ),
    aggregation: Optional[str] = Query(
        None,
        regex="^(1min|1hour|1day|1week|1month)$",
        description="Time aggregation level. If not provided, smart default based on range is used."
    )
):
    """
    Retrieve historical time series data for a specific intersection.

    **Query Parameters:**
    - `start_date` & `end_date`: Explicit date range (YYYY-MM-DD)
    - `days`: Number of days back from today (ignored if start_date provided)
    - `aggregation`: Time granularity (1min, 1hour, 1day, 1week, 1month)

    **Smart Defaults** (when aggregation not specified):
    - ≤1 day → 1-minute intervals
    - ≤7 days → Hourly aggregation
    - ≤30 days → Daily aggregation
    - >30 days → Weekly or monthly

    **Returns:**
    - Time series data with timestamps, safety indices, traffic volumes
    - Metadata about date range and aggregation level

    **Example:**
    ```
    GET /api/v1/safety/history/0.0?days=7
    ```
    """
    # Determine date range
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=days-1)  # -1 to make end_date inclusive

    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date"
        )

    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 365 days"
        )

    try:
        history = get_intersection_history(
            intersection_id=intersection_id,
            start_date=start_date,
            end_date=end_date,
            aggregation=aggregation
        )
        return history

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error retrieving history: {str(e)}"
        )


@router.get("/{intersection_id}/stats", response_model=IntersectionAggregateStats)
def get_statistics(
    intersection_id: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    days: Optional[int] = Query(7, ge=1, le=365)
):
    """
    Get aggregated statistics for an intersection over a time period.

    **Returns:**
    - Average, min, max, standard deviation of safety index
    - Total and average traffic volume
    - Count and percentage of high-risk intervals (SI >75)

    **Example:**
    ```
    GET /api/v1/safety/history/0.0/stats?days=30
    ```
    """
    # Determine date range (same logic as get_history)
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=days-1)

    try:
        stats = get_aggregate_stats(
            intersection_id=intersection_id,
            start_date=start_date,
            end_date=end_date
        )
        return stats

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error computing statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error computing statistics: {str(e)}"
        )


@router.get("/", response_model=List[IntersectionHistory])
def get_all_histories(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    days: Optional[int] = Query(7, ge=1, le=30),
    aggregation: Optional[str] = Query(None, regex="^(1min|1hour|1day|1week|1month)$")
):
    """
    Get historical data for all intersections.

    **Note:** Limited to 30 days max to prevent large responses.
    Use single-intersection endpoints for longer periods.

    **Example:**
    ```
    GET /api/v1/safety/history/?days=7&aggregation=1hour
    ```
    """
    # Determine date range
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=days-1)

    # Enforce 30-day limit for all-intersections query
    if (end_date - start_date).days > 30:
        raise HTTPException(
            status_code=400,
            detail="All-intersections query limited to 30 days. Use single-intersection endpoint for longer periods."
        )

    try:
        histories = get_all_intersections_history(
            start_date=start_date,
            end_date=end_date,
            aggregation=aggregation
        )
        return histories

    except Exception as e:
        logger.error(f"Error retrieving all histories: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error retrieving histories: {str(e)}"
        )
```

### 3.3 Router Registration

**File**: `backend/app/main.py` (MODIFY - add 2 lines)

```python
from fastapi import FastAPI
from app.api import intersection, vcc, history  # ADD: history

app = FastAPI(
    title="Traffic Safety API",
    version="0.1.0"
)

# Include routers
app.include_router(intersection.router, prefix="/api/v1")
app.include_router(vcc.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")  # ADD THIS LINE

@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

---

## 4. Frontend Implementation Design

### 4.1 API Client Methods

**File**: `frontend/app/services/api_client.py` (MODIFY - add ~80 lines)

```python
import streamlit as st
from typing import List, Optional, Dict, Tuple
import requests
from app.utils.config import API_URL, API_TIMEOUT

# Update API_URL in config.py to base URL (remove /safety/index/)
# Or define HISTORY_API_BASE = API_URL.replace('/safety/index/', '/safety/history/')

@st.cache_data(ttl=300, show_spinner=False)  # 5-minute cache
def fetch_intersection_history(
    intersection_id: str,
    days: int = 7,
    aggregation: Optional[str] = None
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Fetch historical time series for intersection.

    Args:
        intersection_id: Intersection identifier
        days: Days of history to retrieve (default 7)
        aggregation: Optional time aggregation ('1min', '1hour', etc.)

    Returns:
        Tuple of (history_data_dict, error_message)
    """
    # Construct URL (adjust base URL as needed)
    base_url = API_URL.replace('/safety/index/', '/safety/history/')
    url = f"{base_url}{intersection_id}"

    params = {"days": days}
    if aggregation:
        params["aggregation"] = aggregation

    try:
        session = _get_session_with_retries()  # Reuse existing function
        response = session.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        return data, None

    except requests.exceptions.Timeout:
        return None, f"Request timed out after {API_TIMEOUT} seconds"
    except requests.exceptions.ConnectionError:
        return None, "Could not connect to API"
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, f"No historical data found for intersection {intersection_id}"
        return None, f"API error: {e.response.status_code}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_intersection_stats(
    intersection_id: str,
    days: int = 7
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Fetch aggregated statistics for intersection.

    Args:
        intersection_id: Intersection identifier
        days: Days to compute statistics over

    Returns:
        Tuple of (stats_dict, error_message)
    """
    base_url = API_URL.replace('/safety/index/', '/safety/history/')
    url = f"{base_url}{intersection_id}/stats"

    params = {"days": days}

    try:
        session = _get_session_with_retries()
        response = session.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        return data, None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, f"No data found for intersection {intersection_id}"
        return None, f"API error: {e.response.status_code}"
    except Exception as e:
        return None, f"Error: {str(e)}"


def clear_history_cache():
    """Clear cached historical data (force refresh)."""
    fetch_intersection_history.clear()
    fetch_intersection_stats.clear()
```

### 4.2 UI Components

**File**: `frontend/app/views/history_components.py` (NEW - ~300 lines)

```python
"""
Historical visualization components.

Provides reusable UI components for displaying time series data,
statistics, and date range selectors.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# ============================================================================
# TIME SERIES CHART
# ============================================================================

def render_time_series_chart(history_data: Dict):
    """
    Render interactive Plotly time series chart.

    Shows:
    - Safety index (line, left Y-axis)
    - Traffic volume (bars, right Y-axis, semi-transparent)
    - High-risk threshold line (dashed red at SI=75)

    Args:
        history_data: Dictionary from API (IntersectionHistory schema)
    """
    if not history_data or not history_data.get('data_points'):
        st.warning("📊 No historical data available for the selected period.")
        return

    # Convert to DataFrame for easier plotting
    df = pd.DataFrame(history_data['data_points'])
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Safety Index line (primary axis)
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['safety_index'],
            name='Safety Index',
            line=dict(color='#E74C3C', width=2),
            mode='lines',
            hovertemplate='<b>%{x}</b><br>Safety Index: %{y:.1f}<extra></extra>'
        ),
        secondary_y=False
    )

    # Traffic Volume bars (secondary axis)
    fig.add_trace(
        go.Bar(
            x=df['timestamp'],
            y=df['traffic_volume'],
            name='Traffic Volume',
            marker_color='rgba(52, 152, 219, 0.3)',
            hovertemplate='<b>%{x}</b><br>Volume: %{y}<extra></extra>'
        ),
        secondary_y=True
    )

    # High-risk threshold line
    fig.add_hline(
        y=75,
        line_dash="dash",
        line_color="red",
        line_width=1,
        annotation_text="High Risk (75)",
        annotation_position="right",
        secondary_y=False
    )

    # Update layout
    fig.update_layout(
        title=f"Safety Index History: {history_data['intersection_name']}",
        xaxis_title="Time",
        hovermode='x unified',
        height=450,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Set y-axes titles
    fig.update_yaxes(title_text="Safety Index", secondary_y=False, range=[0, 100])
    fig.update_yaxes(title_text="Traffic Volume", secondary_y=True)

    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# STATISTICS CARDS
# ============================================================================

def render_statistics_cards(stats_data: Dict):
    """
    Render metric cards showing aggregated statistics.

    Args:
        stats_data: Dictionary from API (IntersectionAggregateStats schema)
    """
    if not stats_data:
        st.info("No statistics available")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_si = stats_data['avg_safety_index']
        risk_level = "🟢" if avg_si < 60 else "🟠" if avg_si < 75 else "🔴"
        st.metric(
            label="Average Safety Index",
            value=f"{avg_si:.1f}",
            delta=f"±{stats_data['std_safety_index']:.1f}",
            help="Mean safety index over period with standard deviation"
        )
        st.caption(f"{risk_level} Risk Level")

    with col2:
        max_si = stats_data['max_safety_index']
        delta_color = "inverse" if max_si > 75 else "normal"
        st.metric(
            label="Peak Risk",
            value=f"{max_si:.1f}",
            delta="High" if max_si > 75 else "Normal",
            delta_color=delta_color,
            help="Maximum safety index observed"
        )

    with col3:
        hr_count = stats_data['high_risk_intervals']
        hr_pct = stats_data['high_risk_percentage']
        st.metric(
            label="High-Risk Periods",
            value=hr_count,
            delta=f"{hr_pct:.1f}%",
            delta_color="inverse",
            help="Count of intervals where safety index exceeded 75"
        )

    with col4:
        avg_vol = stats_data['avg_traffic_volume']
        total_vol = stats_data['total_traffic_volume']
        st.metric(
            label="Avg Traffic Volume",
            value=f"{avg_vol:.0f}",
            delta=f"Total: {total_vol:,}",
            help="Mean vehicle count per interval"
        )


# ============================================================================
# DATE RANGE SELECTOR
# ============================================================================

def render_date_range_selector() -> Tuple[int, Optional[str]]:
    """
    Render date range preset selector and optional custom range.

    Returns:
        Tuple of (days_back, aggregation_override)
    """
    col1, col2 = st.columns([2, 1])

    with col1:
        period_option = st.selectbox(
            "Time Period",
            options=["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom"],
            index=1,  # Default to 7 days
            help="Select predefined period or choose 'Custom' for date picker"
        )

    with col2:
        agg_option = st.selectbox(
            "Granularity",
            options=["Auto (Smart Default)", "1-Minute", "Hourly", "Daily", "Weekly"],
            index=0,
            help="Time aggregation level. 'Auto' selects based on period length."
        )

    # Map selections to API parameters
    period_map = {
        "Last 24 Hours": 1,
        "Last 7 Days": 7,
        "Last 30 Days": 30,
        "Last 90 Days": 90
    }

    agg_map = {
        "Auto (Smart Default)": None,
        "1-Minute": "1min",
        "Hourly": "1hour",
        "Daily": "1day",
        "Weekly": "1week"
    }

    days = period_map.get(period_option, 7)
    aggregation = agg_map.get(agg_option, None)

    # Handle custom date range
    if period_option == "Custom":
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now().date() - timedelta(days=7),
                max_value=datetime.now().date()
            )
        with col_end:
            end_date = st.date_input(
                "End Date",
                value=datetime.now().date(),
                max_value=datetime.now().date()
            )
        days = (end_date - start_date).days + 1

    return days, aggregation


# ============================================================================
# HISTORICAL SECTION (MAIN COMPONENT)
# ============================================================================

def render_historical_section(intersection_id: str, intersection_name: str):
    """
    Render complete historical analysis section.

    This is the main component that combines all sub-components:
    - Date range selector
    - Time series chart
    - Statistics cards
    - Export button

    Args:
        intersection_id: Intersection identifier
        intersection_name: Human-readable name
    """
    from app.services.api_client import fetch_intersection_history, fetch_intersection_stats

    st.subheader("📊 Historical Safety Analysis")

    # Date range selector
    days, aggregation = render_date_range_selector()

    # Fetch data
    with st.spinner("Loading historical data..."):
        history_data, history_error = fetch_intersection_history(
            intersection_id, days=days, aggregation=aggregation
        )
        stats_data, stats_error = fetch_intersection_stats(
            intersection_id, days=days
        )

    # Handle errors
    if history_error:
        st.error(f"❌ {history_error}")
        return

    if not history_data:
        st.warning("No historical data available for this intersection.")
        return

    # Display statistics cards
    if stats_data:
        render_statistics_cards(stats_data)
        st.divider()

    # Display time series chart
    render_time_series_chart(history_data)

    st.divider()

    # Export section
    with st.expander("📥 Export Data"):
        st.caption(f"Download {history_data['total_points']} data points as CSV")

        # Convert to DataFrame and CSV
        df = pd.DataFrame(history_data['data_points'])
        csv = df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"history_{intersection_id}_{days}days.csv",
            mime="text/csv",
            use_container_width=True
        )

        # Show preview
        st.caption("Data Preview:")
        st.dataframe(df.head(10), use_container_width=True)
```

### 4.3 Integration with Main Dashboard

**File**: `frontend/app/views/components.py` (MODIFY - update `render_details_card()`)

```python
def render_details_card(row: Optional[pd.Series]):
    """
    Render detailed information card for a selected intersection.

    MODIFIED: Add "View History" button that expands historical section.
    """
    if row is None:
        st.info("👆 Click on a marker to view details")
        return

    # ... existing code for risk level and details ...

    # ADD: History button
    st.divider()

    if st.button("📊 View Historical Data", use_container_width=True, key=f"history_{row['intersection_id']}"):
        # Set session state to show history
        st.session_state['show_history'] = True
        st.session_state['history_intersection_id'] = str(row['intersection_id'])
        st.session_state['history_intersection_name'] = row['intersection_name']

    # Show history section if button was clicked
    if st.session_state.get('show_history') and st.session_state.get('history_intersection_id') == str(row['intersection_id']):
        st.divider()
        from app.views.history_components import render_historical_section
        render_historical_section(
            str(row['intersection_id']),
            row['intersection_name']
        )
```

---

## 5. Performance Optimization

### 5.1 Caching Strategy

**Backend Caching** (Future):
```python
# Use Redis for frequently requested date ranges
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_history(intersection_id: str, start: str, end: str, agg: str):
    """Cache frequently requested historical queries"""
    # Convert strings back to dates, call service
    pass
```

**Frontend Caching**:
- Already using `@st.cache_data(ttl=300)` for API calls
- 5-minute TTL balances freshness and performance

### 5.2 Query Optimization

**Parquet Column Projection**:
```python
# Only read needed columns from Parquet files
columns_needed = [
    'time_15min', 'intersection', 'Combined_Index_EB',
    'Combined_Index', 'vehicle_count', 'hour_of_day', 'day_of_week'
]

df = pd.read_parquet(file_path, columns=columns_needed)
```

**Date Partition Pruning**:
- Parquet files are already date-partitioned (one file per day)
- Only read files within requested date range
- Implemented in existing `parquet_storage.load_indices()`

### 5.3 Response Size Limits

- **Single Intersection**: No hard limit, but warn if >10k points
- **All Intersections**: Hard limit to 30 days max
- **Aggregation**: Auto-select to keep response <5000 points typically

---

## 6. Extension Points (Future Features)

### 6.1 Camera Feed Integration

**Data Model Addition**:
```python
class IntersectionWithCamera(IntersectionRead):
    camera_url: Optional[str] = Field(None, description="State public camera feed URL")
    camera_available: bool = Field(False, description="Whether camera feed is available")
```

**UI Integration**:
- Add camera icon to details panel if `camera_available=True`
- Link opens in new tab or embedded iframe
- Sync timestamp with selected point in historical chart

### 6.2 Multi-Intersection Comparison

**New Component** (`frontend/app/views/comparison_view.py`):
```python
def render_comparison_view(intersection_ids: List[str]):
    """
    Render side-by-side comparison of multiple intersections.

    Features:
    - Multiple line charts overlaid
    - Synchronized x-axis (time)
    - Color-coded by intersection
    - Comparative statistics table
    """
    pass
```

### 6.3 Heatmap Visualization

**Component** (in `history_components.py`):
```python
def render_safety_heatmap(history_data: Dict):
    """
    Render hour-of-day × day-of-week heatmap.

    Shows average safety index for each time slot,
    useful for identifying recurring danger periods.
    """
    import plotly.express as px

    df = pd.DataFrame(history_data['data_points'])
    pivot = df.pivot_table(
        values='safety_index',
        index='hour_of_day',
        columns='day_of_week',
        aggfunc='mean'
    )

    fig = px.imshow(
        pivot,
        labels=dict(x="Day of Week", y="Hour", color="Avg SI"),
        color_continuous_scale="RdYlGn_r"  # Red=high risk
    )
    st.plotly_chart(fig)
```

---

## 7. Error Handling & Edge Cases

### 7.1 No Data Scenarios

**Case 1**: Newly added intersection (no historical data)
```python
# API returns 404 with message
{
  "detail": "No data found for intersection X between DATE1 and DATE2"
}

# Frontend shows:
st.info("📊 This intersection was recently added. Historical data will be available once collection begins.")
```

**Case 2**: System downtime (gaps in data)
```python
# Don't interpolate gaps - show breaks in line chart
# Plotly automatically handles None/NaN values as breaks

# Add warning if >20% missing:
if missing_pct > 20:
    st.warning(f"⚠️ {missing_pct:.1f}% of expected data points are missing. Results may be incomplete.")
```

### 7.2 Performance Degradation

**Large Query Warning**:
```python
estimated_points = _estimate_point_count(start, end, agg)
if estimated_points > 10000:
    logger.warning(f"Large query: {estimated_points} points estimated")
    # Could add HTTP header: X-Warning: "Large dataset"
```

**Timeout Handling** (Frontend):
```python
try:
    response = session.get(url, timeout=API_TIMEOUT)
except requests.exceptions.Timeout:
    st.error("⏱️ Request timed out. Try a shorter date range or coarser aggregation.")
```

### 7.3 Invalid Inputs

**Invalid Aggregation**:
```python
# FastAPI regex validation in Query parameter
aggregation: str = Query(None, regex="^(1min|1hour|1day|1week|1month)$")
# Returns 422 Unprocessable Entity if invalid
```

**Future Dates**:
```python
if start_date > date.today():
    raise HTTPException(400, "Cannot query future dates")
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

**Test Service Layer** (`tests/test_history_service.py`):
```python
def test_smart_default_aggregation():
    # 1 day → 1min
    assert _get_smart_default_aggregation(date(2025,1,1), date(2025,1,1)) == "1min"
    # 7 days → 1hour
    assert _get_smart_default_aggregation(date(2025,1,1), date(2025,1,7)) == "1hour"
    # 30 days → 1day
    assert _get_smart_default_aggregation(date(2025,1,1), date(2025,1,30)) == "1day"

def test_aggregate_time_series():
    # Create sample 1-min data
    df = create_sample_df(intervals=60)  # 1 hour of 1-min data

    # Aggregate to hourly
    hourly = _aggregate_time_series(df, "1hour")

    assert len(hourly) == 1  # 1 hour
    assert hourly['vehicle_count'].iloc[0] == df['vehicle_count'].sum()  # Traffic summed
    assert abs(hourly['Combined_Index'].iloc[0] - df['Combined_Index'].mean()) < 0.1  # SI averaged
```

### 8.2 Integration Tests

**Test API Endpoints** (`tests/test_history_api.py`):
```python
def test_get_history_endpoint(client):
    response = client.get("/api/v1/safety/history/0.0?days=7")
    assert response.status_code == 200
    data = response.json()
    assert 'data_points' in data
    assert data['total_points'] > 0

def test_get_stats_endpoint(client):
    response = client.get("/api/v1/safety/history/0.0/stats?days=7")
    assert response.status_code == 200
    data = response.json()
    assert 'avg_safety_index' in data
    assert 0 <= data['avg_safety_index'] <= 100
```

### 8.3 Frontend Tests

**Component Tests** (manual/Selenium):
- Click "View History" button → Section expands
- Select different time periods → Chart updates
- Export CSV → File downloads correctly
- Handle no data → Shows helpful message

---

## 9. Deployment Considerations

### 9.1 Docker Updates

**Frontend Requirements** (`frontend/requirements.txt`):
```
streamlit>=1.36
requests>=2.32
pydantic>=2.6
pandas>=2.2
folium>=0.17
streamlit-folium>=0.21
plotly>=5.18  # ADD THIS LINE
```

**No Changes Needed**:
- Docker compose already configured
- No new environment variables required
- No database migrations (Parquet-only)

### 9.2 API Documentation

**Swagger/OpenAPI** (auto-generated by FastAPI):
- Access at `http://localhost:8001/docs`
- New endpoints automatically documented
- Pydantic schemas generate JSON Schema examples

---

## 10. Future Enhancements Roadmap

### Phase 1 (Current): MVP
- ✅ Single intersection history
- ✅ Time series chart
- ✅ Statistics cards
- ✅ CSV export
- ✅ Smart aggregation

### Phase 2 (Next): Advanced Analysis
- ❌ Heatmap visualization
- ❌ Multi-intersection comparison
- ❌ Separate analysis page

### Phase 3 (Future): Validation & Context
- ❌ Camera feed integration
- ❌ Admin data validation tools
- ❌ Anomaly detection

### Phase 4 (Future): Predictive
- ❌ Forecasting/prediction
- ❌ Pattern recognition
- ❌ Rerouting recommendations

---

## Appendix: Code File Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── intersection.py          [existing]
│   │   ├── vcc.py                   [existing]
│   │   └── history.py               [NEW - 200 lines]
│   ├── services/
│   │   ├── parquet_storage.py       [existing]
│   │   └── history_service.py       [NEW - 250 lines]
│   ├── schemas/
│   │   └── intersection.py          [MODIFY - add 3 classes]
│   └── main.py                      [MODIFY - add 1 line]

frontend/
├── app/
│   ├── views/
│   │   ├── main.py                  [existing]
│   │   ├── components.py            [MODIFY - add history button]
│   │   └── history_components.py    [NEW - 300 lines]
│   ├── services/
│   │   └── api_client.py            [MODIFY - add 2 functions]
│   └── models/
│       └── history.py               [NEW - 50 lines]
└── requirements.txt                 [MODIFY - add plotly]
```

**Total Lines of New Code**: ~800 lines
**Total Files Modified**: 5 files
**Total New Files**: 3 files
