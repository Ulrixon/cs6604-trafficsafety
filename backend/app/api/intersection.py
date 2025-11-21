from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional

from ..schemas.intersection import IntersectionRead
from ..schemas.safety_score import SafetyScoreTimePoint, IntersectionList
from ..services.intersection_service import get_all, get_by_id
from ..services.db_client import get_db_client
from ..services.mcdm_service import MCDMSafetyIndexService
from ..core.config import settings

router = APIRouter(prefix="/safety/index", tags=["Safety Index"])


@router.get("/", response_model=list[IntersectionRead])
def list_intersections():
    """
    Retrieve a list of all intersections with their latest safety index data.
    """
    return get_all()


@router.get("/{intersection_id}", response_model=IntersectionRead)
def get_intersection(intersection_id: int):
    """
    Retrieve details for a single intersection by its ID.
    """
    intersection = get_by_id(intersection_id)
    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return intersection


@router.get("/intersections/list", response_model=IntersectionList)
def list_available_intersections():
    """
    Get list of all available intersections in the database.
    """
    db_client = get_db_client()
    mcdm_service = MCDMSafetyIndexService(db_client)
    intersections = mcdm_service.get_available_intersections()
    return {"intersections": intersections}


@router.get("/time/specific", response_model=SafetyScoreTimePoint)
def get_safety_score_at_time(
    intersection: str = Query(
        ..., description="Intersection name (e.g., 'glebe-potomac')"
    ),
    time: datetime = Query(..., description="Target datetime (ISO 8601 format)"),
    bin_minutes: int = Query(15, description="Time bin size in minutes", ge=1, le=60),
):
    """
    Get safety score for a specific intersection at a specific time.

    Example:
    ```
    GET /api/v1/safety/index/time/specific?intersection=glebe-potomac&time=2025-11-09T10:00:00&bin_minutes=15
    ```
    """
    db_client = get_db_client()
    mcdm_service = MCDMSafetyIndexService(db_client)

    result = mcdm_service.calculate_safety_score_for_time(
        intersection=intersection, target_time=time, bin_minutes=bin_minutes
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for intersection '{intersection}' at time {time}",
        )

    return result


@router.get("/time/range", response_model=list[SafetyScoreTimePoint])
def get_safety_score_trend(
    intersection: str = Query(
        ..., description="Intersection name (e.g., 'glebe-potomac')"
    ),
    start_time: datetime = Query(..., description="Start datetime (ISO 8601 format)"),
    end_time: datetime = Query(..., description="End datetime (ISO 8601 format)"),
    bin_minutes: int = Query(15, description="Time bin size in minutes", ge=1, le=60),
):
    """
    Get safety score trend for a specific intersection over a time range.

    Returns time series data for creating trend charts.

    Example:
    ```
    GET /api/v1/safety/index/time/range?intersection=glebe-potomac&start_time=2025-11-09T08:00:00&end_time=2025-11-09T18:00:00&bin_minutes=15
    ```
    """
    # Validate time range
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    db_client = get_db_client()
    mcdm_service = MCDMSafetyIndexService(db_client)

    results = mcdm_service.calculate_safety_score_trend(
        intersection=intersection,
        start_time=start_time,
        end_time=end_time,
        bin_minutes=bin_minutes,
    )

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for intersection '{intersection}' in the specified time range",
        )

    return results
