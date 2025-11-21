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
        pattern="^(1min|1hour|1day|1week|1month)$",
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
    aggregation: Optional[str] = Query(None, pattern="^(1min|1hour|1day|1week|1month)$")
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
