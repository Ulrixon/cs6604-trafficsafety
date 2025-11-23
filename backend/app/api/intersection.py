from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional
import logging

from ..schemas.intersection import IntersectionRead, IntersectionWithRTSI
from ..schemas.safety_score import (
    SafetyScoreTimePoint,
    IntersectionList,
    SafetyScoreTrendWithCorrelations,
    TrendMetadata,
)
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
        WITH distances AS (
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
        )
        SELECT intersection_id, distance_km
        FROM distances
        WHERE distance_km < 0.5
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


@router.get("/")
def list_intersections(
    include_rtsi: bool = Query(
        False,
        description="Include RT-SI scores for real-time blending (slower)",
    ),
    bin_minutes: int = Query(
        15, description="Time bin size in minutes for RT-SI", ge=1, le=60
    ),
):
    """
    Retrieve a list of all intersections with their latest safety index data.

    Parameters:
    - include_rtsi: If True, includes RT-SI scores (requires real-time data query)
    - bin_minutes: Time window for RT-SI calculation (default: 15 minutes)

    Returns:
    - If include_rtsi=false: List[IntersectionRead] with MCDM only
    - If include_rtsi=true: List[IntersectionWithRTSI] with both MCDM and RT-SI

    Examples:
    - GET /api/v1/safety/index/ - Fast MCDM-only response
    - GET /api/v1/safety/index/?include_rtsi=true - Includes RT-SI for blending in frontend
    """
    if not include_rtsi:
        # Fast path: just return MCDM indices
        intersections = get_all()
        if not intersections:
            logger.warning("No intersections returned from get_all()")
        else:
            logger.info(f"Returning {len(intersections)} intersections (MCDM only)")
        return intersections

    # Slow path: calculate RT-SI for each intersection
    db_client = get_db_client()
    rt_si_service = RTSIService(db_client)
    mcdm_service = MCDMSafetyIndexService(db_client)

    # Get base MCDM data
    base_intersections = get_all()

    # Get available BSM intersections
    bsm_intersections = mcdm_service.get_available_intersections()

    # Calculate RT-SI for each intersection
    current_time = datetime.now()
    results = []

    for intersection in base_intersections:
        result_data = {
            "intersection_id": intersection.intersection_id,
            "intersection_name": intersection.intersection_name,
            "safety_index": intersection.safety_index,
            "mcdm_index": intersection.safety_index,  # MCDM is the base safety_index
            "traffic_volume": intersection.traffic_volume,
            "longitude": intersection.longitude,
            "latitude": intersection.latitude,
            "rt_si_score": None,
            "vru_index": None,
            "vehicle_index": None,
            "timestamp": current_time,
        }

        # Try to find matching BSM intersection and calculate RT-SI
        # First, find corresponding BSM intersection name
        bsm_intersection_name = None
        for bsm_name in bsm_intersections:
            # Normalize both names for comparison: remove hyphens and spaces
            normalized_bsm = bsm_name.lower().replace("-", "").replace(" ", "")
            normalized_intersection = (
                intersection.intersection_name.lower().replace("-", "").replace(" ", "")
            )

            # Check if names match (exact or contains)
            if (
                normalized_bsm == normalized_intersection
                or normalized_bsm in normalized_intersection
            ):
                bsm_intersection_name = bsm_name
                logger.info(
                    f"Matched BSM intersection '{bsm_name}' to '{intersection.intersection_name}'"
                )
                break

        if bsm_intersection_name:
            # Use find_crash_intersection_for_bsm to get the proper crash intersection ID
            crash_intersection_id = find_crash_intersection_for_bsm(
                bsm_intersection_name, db_client
            )

            if crash_intersection_id:
                logger.info(
                    f"Calculating RT-SI for {intersection.intersection_name} (Crash ID: {crash_intersection_id}, BSM: {bsm_intersection_name})"
                )
                try:
                    rt_si_result = rt_si_service.calculate_rt_si(
                        crash_intersection_id,
                        current_time,
                        bin_minutes=bin_minutes,
                        realtime_intersection=bsm_intersection_name,
                        lookback_hours=168,  # Look back up to 1 week for latest available data
                    )

                    if rt_si_result is not None:
                        result_data["rt_si_score"] = rt_si_result["RT_SI"]
                        result_data["vru_index"] = rt_si_result["VRU_index"]
                        result_data["vehicle_index"] = rt_si_result["VEH_index"]
                        logger.info(
                            f"RT-SI calculated successfully: {rt_si_result['RT_SI']:.2f}"
                        )
                    else:
                        logger.warning(
                            f"RT-SI calculation returned None for {intersection.intersection_name}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not calculate RT-SI for {intersection.intersection_name}: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    f"Could not find crash intersection ID for BSM '{bsm_intersection_name}'"
                )

        results.append(IntersectionWithRTSI(**result_data))

    return results


@router.get("/debug/status")
def debug_status():
    """
    Debug endpoint to check database connectivity and data availability.
    """
    try:
        db_client = get_db_client()
        mcdm_service = MCDMSafetyIndexService(db_client)

        # Check available intersections
        available_intersections = mcdm_service.get_available_intersections()

        # Try to calculate latest scores
        safety_scores = mcdm_service.calculate_latest_safety_scores(
            bin_minutes=15,
            lookback_hours=24,
        )

        return {
            "status": "ok",
            "database_connected": True,
            "available_intersections_count": len(available_intersections),
            "available_intersections": available_intersections[:5],  # First 5
            "safety_scores_count": len(safety_scores) if safety_scores else 0,
            "sample_score": safety_scores[0] if safety_scores else None,
        }
    except Exception as e:
        logger.error(f"Debug status check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "database_connected": False,
        }


@router.get("/intersections/list", response_model=IntersectionList)
def list_available_intersections():
    """
    Get list of all available intersections in the database.
    """
    db_client = get_db_client()
    mcdm_service = MCDMSafetyIndexService(db_client)
    intersections = mcdm_service.get_available_intersections()
    return {"intersections": intersections}


@router.get("/{intersection_id}", response_model=IntersectionRead)
def get_intersection(intersection_id: int):
    """
    Retrieve details for a single intersection by its ID.
    """
    intersection = get_by_id(intersection_id)
    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    return intersection


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

    Returns both MCDM and RT-SI scores separately for client-side blending:
    - mcdm_index: Long-term prioritization score (0-100)
    - rt_si_score: Real-time safety index (0-100)
    - vru_index: VRU sub-index (0-100)
    - vehicle_index: Vehicle sub-index (0-100)

    Frontend should blend: Final = α*RT-SI + (1-α)*MCDM

    Example:
    ```
    GET /api/v1/safety/index/time/specific?intersection=glebe-potomac&time=2025-11-09T10:00:00&bin_minutes=15
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

            if rt_si_result is not None:
                result["rt_si_score"] = rt_si_result["RT_SI"]
                result["vru_index"] = rt_si_result["VRU_index"]
                result["vehicle_index"] = rt_si_result["VEH_index"]

                logger.info(
                    f"Safety scores for {intersection} at {time}: "
                    f"RT-SI={rt_si_result['RT_SI']:.2f}, MCDM={result['mcdm_index']:.2f} "
                    f"(blending to be done in frontend)"
                )
            else:
                logger.warning(f"No RT-SI data for {intersection} at {time}")
        except Exception as e:
            logger.error(f"Error calculating RT-SI: {e}", exc_info=True)
    else:
        logger.warning(f"No crash intersection found for '{intersection}'")

    return result


@router.get("/time/range", response_model=SafetyScoreTrendWithCorrelations)
def get_safety_score_trend(
    intersection: str = Query(
        ..., description="Intersection name (e.g., 'glebe-potomac')"
    ),
    start_time: datetime = Query(..., description="Start datetime (ISO 8601 format)"),
    end_time: datetime = Query(..., description="End datetime (ISO 8601 format)"),
    bin_minutes: int = Query(15, description="Time bin size in minutes", ge=1, le=60),
    include_correlations: bool = Query(
        True, description="Include correlation analysis in response"
    ),
):
    """
    Get safety score trend with correlation analysis for a specific intersection over a time range.

    Returns:
    - time_series: Time series data with both MCDM and RT-SI scores
      - mcdm_index: Long-term prioritization score (0-100)
      - rt_si_score: Real-time safety index (0-100)
      - vru_index: VRU sub-index (0-100)
      - vehicle_index: Vehicle sub-index (0-100)
      - RT-SI uplift factors: F_speed, F_variance, F_conflict
      - Historical crash rates: raw_crash_rate, eb_crash_rate

    - correlation_analysis: Statistical validation of safety mechanisms
      - Pearson/Spearman correlations between variables and safety indices
      - Monotonic trend analysis (e.g., "higher speed variance → higher incidents")
      - Partial correlations showing independent contributions of each factor

    - metadata: Query information and statistics

    This response validates that each component corresponds to a real safety mechanism.

    Example:
    ```
    GET /api/v1/safety/index/time/range?intersection=glebe-potomac&start_time=2025-11-09T08:00:00&end_time=2025-11-09T18:00:00&bin_minutes=15&include_correlations=true
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
            # Calculate RT-SI trend using optimized method
            # This calculates RT-SI for each time bin with data (no lookback)
            logger.info(
                f"Calculating RT-SI trend for {intersection} "
                f"(crash ID: {crash_intersection_id}) from {start_time} to {end_time}"
            )

            rt_si_results = rt_si_service.calculate_rt_si_trend(
                crash_intersection_id,
                start_time,
                end_time,
                bin_minutes=bin_minutes,
                realtime_intersection=intersection,
            )

            # Create a map of timestamp -> RT-SI result for quick lookup
            rt_si_map = {
                datetime.fromisoformat(r["timestamp"]): r for r in rt_si_results
            }

            # Add RT-SI data to matching MCDM time points
            for result in results:
                time_bin = result["time_bin"]
                if time_bin in rt_si_map:
                    rt_si_data = rt_si_map[time_bin]
                    result["rt_si_score"] = rt_si_data["RT_SI"]
                    result["vru_index"] = rt_si_data["VRU_index"]
                    result["vehicle_index"] = rt_si_data["VEH_index"]
                    result["raw_crash_rate"] = rt_si_data["raw_crash_rate"]
                    result["eb_crash_rate"] = rt_si_data["eb_crash_rate"]
                else:
                    # No RT-SI data for this time bin - leave as None
                    logger.debug(f"No RT-SI data for time bin {time_bin}")

            # Add RT-SI component data for correlation analysis
            for result in results:
                time_bin = result["time_bin"]
                if time_bin in rt_si_map:
                    rt_si_data = rt_si_map[time_bin]
                    # Add uplift factors for correlation analysis
                    result["F_speed"] = rt_si_data.get("F_speed")
                    result["F_variance"] = rt_si_data.get("F_variance")
                    result["F_conflict"] = rt_si_data.get("F_conflict")
                    result["uplift_factor"] = rt_si_data.get("uplift_factor")

            logger.info(
                f"Successfully calculated safety scores: {len(results)} MCDM points, "
                f"{len(rt_si_results)} RT-SI points (blending to be done in frontend)"
            )

        except Exception as e:
            logger.error(f"Error calculating RT-SI trend: {e}", exc_info=True)
    else:
        logger.warning(f"No crash intersection found for '{intersection}'")

    # Compute correlation analysis if requested and we have enough data
    correlation_analysis = None
    if include_correlations and len(results) >= 3:
        try:
            from app.services.correlation_service import CorrelationAnalysisService

            correlation_service = CorrelationAnalysisService()
            correlation_analysis = correlation_service.compute_correlations(results)
            logger.info("Correlation analysis completed successfully")
        except Exception as e:
            logger.error(f"Error computing correlations: {e}", exc_info=True)
            # Don't fail the request if correlation analysis fails
            correlation_analysis = {"error": str(e)}

    # Return results with correlation analysis
    return {
        "time_series": results,
        "correlation_analysis": correlation_analysis,
        "metadata": {
            "intersection": intersection,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "bin_minutes": bin_minutes,
            "data_points": len(results),
        },
    }


@router.get("/sensitivity-analysis")
def get_sensitivity_analysis(
    intersection: str = Query(
        ..., description="Intersection name (e.g., 'glebe-potomac')"
    ),
    start_time: datetime = Query(..., description="Start datetime (ISO 8601 format)"),
    end_time: datetime = Query(..., description="End datetime (ISO 8601 format)"),
    bin_minutes: int = Query(15, description="Time bin size in minutes", ge=1, le=60),
    perturbation_pct: float = Query(
        0.25,
        description="Parameter perturbation percentage (0.25 = ±25%)",
        ge=0.1,
        le=0.5,
    ),
    n_samples: int = Query(
        100, description="Number of parameter sets to test", ge=10, le=500
    ),
):
    """
    Perform sensitivity analysis on RT-SI parameters.

    Randomly perturbs parameters (β₁, β₂, β₃, k₁...k₅, λ, ω) and measures:
    - Spearman rank correlation (stability of rankings)
    - Score changes (magnitude of differences)
    - Tier changes (Low→High risk reclassifications)

    This validates that the RT-SI methodology is robust and not overly sensitive
    to parameter tuning choices.

    **Parameters analyzed:**
    - β₁, β₂, β₃: Uplift weights (speed, variance, conflict)
    - k₁...k₅: Scaling constants
    - λ: Empirical Bayes shrinkage
    - ω: VRU vs Vehicle blend

    **Returns:**
    - baseline: Original RT-SI scores
    - stability_metrics: Spearman correlations, score changes, tier changes
    - parameter_importance: Which parameters have most impact
    - perturbed_samples: Sample perturbed results for inspection

    Example:
    ```
    GET /api/v1/safety/index/sensitivity-analysis?intersection=glebe-potomac&start_time=2025-11-01T08:00:00&end_time=2025-11-01T18:00:00&bin_minutes=15&perturbation_pct=0.25&n_samples=100
    ```
    """
    # Validate time range
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    db_client = get_db_client()

    try:
        from app.services.sensitivity_analysis_service import SensitivityAnalysisService

        sensitivity_service = SensitivityAnalysisService(db_client)

        results = sensitivity_service.analyze_sensitivity(
            intersection=intersection,
            start_time=start_time,
            end_time=end_time,
            bin_minutes=bin_minutes,
            perturbation_pct=perturbation_pct,
            n_samples=n_samples,
        )

        if "error" in results:
            raise HTTPException(status_code=404, detail=results["error"])

        return results

    except Exception as e:
        logger.error(f"Error performing sensitivity analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error performing sensitivity analysis: {str(e)}",
        )
