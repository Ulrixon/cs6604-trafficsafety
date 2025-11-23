from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional
import logging

from ..schemas.intersection import IntersectionRead
from ..schemas.safety_score import SafetyScoreTimePoint, IntersectionList
from ..services.intersection_service import get_all, get_by_id
from ..services.db_client import get_db_client
from ..services.mcdm_service import MCDMSafetyIndexService
from ..services.rt_si_service import RTSIService
from ..core.config import settings

router = APIRouter(prefix="/safety/index", tags=["Safety Index"])
logger = logging.getLogger(__name__)


def find_crash_intersection_for_bsm(bsm_intersection: str, db_client) -> Optional[int]:
    """
    Find the crash intersection ID for a BSM intersection.
    Uses PSM table coordinates and Haversine distance to find nearest intersection.
    """
    try:
        # Get coordinates from PSM table
        psm_query = """
        SELECT 
            AVG(lat) as avg_lat,
            AVG(lon) as avg_lon
        FROM psm
        WHERE intersection = %(int_id)s
        GROUP BY intersection;
        """
        psm_results = db_client.execute_query(psm_query, {"int_id": bsm_intersection})

        if not psm_results or psm_results[0]["avg_lat"] is None:
            logger.warning(f"No PSM data found for intersection '{bsm_intersection}'")
            return None

        bsm_lat = float(psm_results[0]["avg_lat"])
        bsm_lon = float(psm_results[0]["avg_lon"])

        # Find nearest crash intersection using Haversine
        nearest_query = """
        SELECT 
            i.intersection_id,
            6371 * acos(
                cos(radians(%(bsm_lat)s)) * 
                cos(radians(i.transport_junction_latitude)) * 
                cos(radians(i.transport_junction_longitude) - radians(%(bsm_lon)s)) + 
                sin(radians(%(bsm_lat)s)) * 
                sin(radians(i.transport_junction_latitude))
            ) as distance_km
        FROM lrs_road_intersections i
        WHERE i.transport_junction_latitude IS NOT NULL
          AND i.transport_junction_longitude IS NOT NULL
        HAVING distance_km < 0.5
        ORDER BY distance_km
        LIMIT 1;
        """

        results = db_client.execute_query(
            nearest_query, {"bsm_lat": bsm_lat, "bsm_lon": bsm_lon}
        )

        if results:
            return results[0]["intersection_id"]

        logger.warning(
            f"No crash intersection found within 0.5 km of '{bsm_intersection}'"
        )
        return None

    except Exception as e:
        logger.error(
            f"Error finding crash intersection for '{bsm_intersection}': {e}",
            exc_info=True,
        )
        return None


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
    alpha: float = Query(
        0.7,
        description="Blending coefficient: α*RT-SI + (1-α)*MCDM (0=only MCDM, 1=only RT-SI)",
        ge=0.0,
        le=1.0,
    ),
):
    """
    Get safety score for a specific intersection at a specific time.

    Returns:
    - MCDM index (long-term prioritization)
    - RT-SI score (real-time safety with VRU and Vehicle sub-indices)
    - Final blended safety index: α*RT-SI + (1-α)*MCDM

    Example:
    ```
    GET /api/v1/safety/index/time/specific?intersection=glebe-potomac&time=2025-11-09T10:00:00&bin_minutes=15&alpha=0.7
    ```
    """
    db_client = get_db_client()
    mcdm_service = MCDMSafetyIndexService(db_client)
    rt_si_service = RTSIService(db_client)

    # Calculate MCDM index
    result = mcdm_service.calculate_safety_score_for_time(
        intersection=intersection, target_time=time, bin_minutes=bin_minutes
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for intersection '{intersection}' at time {time}",
        )

    # Find corresponding crash intersection for RT-SI
    crash_intersection_id = find_crash_intersection_for_bsm(intersection, db_client)

    if crash_intersection_id:
        # Calculate RT-SI
        try:
            rt_si_result = rt_si_service.calculate_rt_si(
                crash_intersection_id,
                time,
                bin_minutes=bin_minutes,
                realtime_intersection=intersection,
            )

            if rt_si_result:
                result["rt_si_score"] = rt_si_result["RT_SI"]
                result["vru_index"] = rt_si_result["VRU_index"]
                result["vehicle_index"] = rt_si_result["VEH_index"]

                # Calculate blended final safety index
                # Formula: SI_Final = α * RT-SI + (1-α) * MCDM
                result["final_safety_index"] = (
                    alpha * rt_si_result["RT_SI"] + (1 - alpha) * result["mcdm_index"]
                )

                logger.info(
                    f"Blended safety index for {intersection} at {time}: "
                    f"RT-SI={rt_si_result['RT_SI']:.2f}, MCDM={result['mcdm_index']:.2f}, "
                    f"Final={result['final_safety_index']:.2f} (α={alpha})"
                )
            else:
                logger.warning(
                    f"No RT-SI data for {intersection} at {time}, using MCDM only"
                )
                result["final_safety_index"] = result["mcdm_index"]
        except Exception as e:
            logger.error(f"Error calculating RT-SI: {e}", exc_info=True)
            result["final_safety_index"] = result["mcdm_index"]
    else:
        logger.warning(
            f"No crash intersection found for '{intersection}', using MCDM only"
        )
        result["final_safety_index"] = result["mcdm_index"]

    return result


@router.get("/time/range", response_model=list[SafetyScoreTimePoint])
def get_safety_score_trend(
    intersection: str = Query(
        ..., description="Intersection name (e.g., 'glebe-potomac')"
    ),
    start_time: datetime = Query(..., description="Start datetime (ISO 8601 format)"),
    end_time: datetime = Query(..., description="End datetime (ISO 8601 format)"),
    bin_minutes: int = Query(15, description="Time bin size in minutes", ge=1, le=60),
    alpha: float = Query(
        0.7,
        description="Blending coefficient: α*RT-SI + (1-α)*MCDM (0=only MCDM, 1=only RT-SI)",
        ge=0.0,
        le=1.0,
    ),
):
    """
    Get safety score trend for a specific intersection over a time range.

    Returns time series data for creating trend charts, including:
    - MCDM index (long-term prioritization)
    - RT-SI score (real-time safety with VRU and Vehicle sub-indices)
    - Final blended safety index: α*RT-SI + (1-α)*MCDM

    Example:
    ```
    GET /api/v1/safety/index/time/range?intersection=glebe-potomac&start_time=2025-11-09T08:00:00&end_time=2025-11-09T18:00:00&bin_minutes=15&alpha=0.7
    ```
    """
    # Validate time range
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    db_client = get_db_client()
    mcdm_service = MCDMSafetyIndexService(db_client)
    rt_si_service = RTSIService(db_client)

    try:
        # Calculate MCDM trend
        results = mcdm_service.calculate_safety_score_trend(
            intersection=intersection,
            start_time=start_time,
            end_time=end_time,
            bin_minutes=bin_minutes,
        )
    except Exception as e:
        logger.error(f"Error calculating MCDM trend: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating safety score trend: {str(e)}",
        )

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for intersection '{intersection}' in the specified time range",
        )

    # Find corresponding crash intersection for RT-SI
    crash_intersection_id = find_crash_intersection_for_bsm(intersection, db_client)

    if crash_intersection_id:
        try:
            # Calculate RT-SI trend
            logger.info(
                f"Calculating RT-SI trend for {intersection} "
                f"(crash ID: {crash_intersection_id}) from {start_time} to {end_time}"
            )

            # Add RT-SI data to each time point
            for result in results:
                try:
                    rt_si_result = rt_si_service.calculate_rt_si(
                        crash_intersection_id,
                        result["time_bin"],
                        bin_minutes=bin_minutes,
                        realtime_intersection=intersection,
                    )

                    if rt_si_result:
                        result["rt_si_score"] = rt_si_result["RT_SI"]
                        result["vru_index"] = rt_si_result["VRU_index"]
                        result["vehicle_index"] = rt_si_result["VEH_index"]

                        # Calculate blended final safety index
                        result["final_safety_index"] = (
                            alpha * rt_si_result["RT_SI"]
                            + (1 - alpha) * result["mcdm_index"]
                        )
                    else:
                        # No RT-SI data, use MCDM only
                        result["final_safety_index"] = result["mcdm_index"]

                except Exception as e:
                    logger.debug(
                        f"Error calculating RT-SI for time {result['time_bin']}: {e}"
                    )
                    result["final_safety_index"] = result["mcdm_index"]

            logger.info(
                f"Successfully calculated blended safety scores for {len(results)} time points"
            )

        except Exception as e:
            logger.error(f"Error calculating RT-SI trend: {e}", exc_info=True)
            # Fall back to MCDM only
            for result in results:
                result["final_safety_index"] = result["mcdm_index"]
    else:
        logger.warning(
            f"No crash intersection found for '{intersection}', using MCDM only"
        )
        for result in results:
            result["final_safety_index"] = result["mcdm_index"]

    return results
