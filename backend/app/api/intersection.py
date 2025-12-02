from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional
import logging

from ..schemas.intersection import IntersectionRead
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
from ..core.intersection_mapping import (
    normalize_intersection_name,
    validate_intersection_in_tables,
    reverse_lookup_intersection,
)

router = APIRouter(prefix="/safety/index", tags=["Safety Index"])
logger = logging.getLogger(__name__)


def find_crash_intersection_for_bsm(bsm_intersection: str, db_client) -> list:
    """
    Find intersections for a BSM intersection by querying BOTH hiresdata AND PSM tables.

    Process:
    1. Query hiresdata table: Get avg lat/lon, apply name mapping for safety-event queries
    2. Query PSM table: Get avg lat/lon, use BSM name as-is (no mapping)
    3. For each result, validate existence in required tables and find nearest crash intersection
    4. Combine results from both sources into a single list

    Returns:
        List of dictionaries with:
        - intersection_name: Name to use for most tables
        - short_name: Mapped short name for safety-event queries (only for hiresdata)
        - lat: Average latitude
        - lon: Average longitude
        - crash_intersection_id: Nearest crash intersection ID (if found)
        - source: 'hiresdata' or 'psm'
        - valid_in_tables: Dict showing which tables have data
    """
    all_results = []
    bsm_intersection = bsm_intersection.strip()
    logger.info(
        f"Querying intersection_details_view for intersection: '{bsm_intersection}' (repr: {repr(bsm_intersection)})"
    )
    # Query the view for all matching intersection_name (case-insensitive)
    query = """
        SELECT intersection_name,short_name, lat, lon, source
        FROM public.intersection_details_view
        WHERE LOWER(intersection_name) = LOWER(%(int_id)s) OR LOWER(short_name) = LOWER(%(int_id)s);
    """
    results = db_client.execute_query(query, {"int_id": bsm_intersection})

    for row in results:
        full_name = row["intersection_name"]
        lat = float(row["lat"]) if row["lat"] is not None else None
        lon = float(row["lon"]) if row["lon"] is not None else None
        source = row["source"]
        if lat is None or lon is None:
            continue
        short_name = normalize_intersection_name(full_name)
        table_validity = validate_intersection_in_tables(
            full_name, short_name, db_client
        )
        # Find crash_intersection_id using the normalized short name only.
        crash_id = _find_nearest_crash_intersection(short_name, db_client)
        all_results.append(
            {
                "intersection_name": full_name,
                "short_name": short_name,
                "lat": lat,
                "lon": lon,
                "crash_intersection_id": crash_id,
                "source": source,
                "valid_in_tables": table_validity,
            }
        )

    if not all_results:
        logger.warning(
            f"No valid intersections found for '{bsm_intersection}' in intersection_details_view"
        )
    else:
        logger.info(
            f"Total: Found {len(all_results)} valid intersection(s) for '{bsm_intersection}' in intersection_details_view"
        )
    return all_results


def _find_nearest_crash_intersection(short_name: str, db_client) -> Optional[int]:
    """
    Helper function to find a crash intersection ID by exact `short_name` match.

    This helper only accepts `short_name` and `db_client` and will not perform
    any coordinate-based fallbacks. It returns the first matching
    `crash_intersection_id` or `None`.
    """
    try:
        if not short_name:
            return None

        query_sn = """
            SELECT crash_intersection_id
            FROM public.crash_intersection_id_with_coord
            WHERE LOWER(short_name) = LOWER(%(short_name)s)
            LIMIT 1;
        """
        results = db_client.execute_query(query_sn, {"short_name": short_name})
        if results:
            logger.info(f"Found crash_intersection_id by short_name='{short_name}'")
            return results[0]["crash_intersection_id"]

        logger.info(f"No crash_intersection_id found for short_name='{short_name}'")
        return None
    except Exception as e:
        logger.error(
            f"Error finding crash intersection by short_name='{short_name}': {e}"
        )
        return None


@router.get("/")
def list_intersections(
    include_mcdm: bool = Query(
        True,
        description="Include MCDM scores for comparison (default: true)",
    ),
    bin_minutes: int = Query(
        15, description="Time bin size in minutes for RT-SI", ge=1, le=60
    ),
):
    """
    Retrieve a list of all intersections with their latest safety index data.

    **NEW BEHAVIOR (2025-12-02):** RT-SI is now the primary safety index.

    Parameters:
    - include_mcdm: If True, includes MCDM scores for comparison (default: true)
    - bin_minutes: Time window for RT-SI calculation (default: 15 minutes)

    Returns:
    - List[IntersectionRead] with RT-SI as primary safety_index
    - MCDM included as secondary comparison metric (if include_mcdm=true)
    - index_type field indicates calculation method used

    Examples:
    - GET /api/v1/safety/index/ - RT-SI with MCDM comparison
    - GET /api/v1/safety/index/?include_mcdm=false - RT-SI only (faster)
    """

    db_client = get_db_client()
    rt_si_service = RTSIService(db_client)
    mcdm_service = MCDMSafetyIndexService(db_client)

    # Get available BSM intersections
    bsm_intersections = mcdm_service.get_available_intersections()

    # Build mapping_results for all intersections
    mapping_results = {}
    for intersection in bsm_intersections:
        mapping_list = find_crash_intersection_for_bsm(intersection, db_client)
        if mapping_list:
            # Use the first valid mapping for each intersection
            mapping_results[intersection] = mapping_list[0]

    # Get base intersection data (coordinates, traffic volume, etc.)
    base_intersections = get_all(mapping_results)

    # Calculate RT-SI and MCDM for each intersection
    current_time = datetime.now()
    results = []

    for intersection in base_intersections:
        # Initialize result with base intersection data
        result_data = {
            "intersection_id": intersection.intersection_id,
            "intersection_name": intersection.intersection_name,
            "traffic_volume": intersection.traffic_volume,
            "longitude": intersection.longitude,
            "latitude": intersection.latitude,
            "safety_index": None,  # Will be set to RT-SI below
            "index_type": None,    # Will be set based on calculation
            "mcdm_index": None,    # Will be set if include_mcdm=True
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

        # Calculate RT-SI (primary safety index)
        rt_si_calculated = False
        if bsm_intersection_name:
            # Use find_crash_intersection_for_bsm to get the proper crash intersection ID
            crash_intersection_list = find_crash_intersection_for_bsm(
                bsm_intersection_name, db_client
            )
            # Use first valid result with crash_intersection_id
            valid_crash = next(
                (
                    item
                    for item in crash_intersection_list
                    if item["crash_intersection_id"] is not None
                ),
                crash_intersection_list[0] if crash_intersection_list else None,
            )
            if valid_crash and valid_crash["crash_intersection_id"]:
                crash_intersection_id = valid_crash["crash_intersection_id"]
                logger.info(
                    f"Calculating RT-SI (Full) for {intersection.intersection_name} (Crash ID: {crash_intersection_id})"
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
                        result_data["safety_index"] = rt_si_result["RT_SI"]
                        result_data["index_type"] = "RT-SI-Full"
                        rt_si_calculated = True
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
                logger.info(
                    f"No crash data for '{bsm_intersection_name}', will use RT-SI-Realtime"
                )

        # If RT-SI with crash data failed, fall back to MCDM as primary
        if not rt_si_calculated:
            logger.info(f"Using MCDM as primary index for {intersection.intersection_name}")
            result_data["safety_index"] = intersection.safety_index
            result_data["index_type"] = "MCDM"

        # Calculate MCDM as comparison metric if requested
        if include_mcdm and rt_si_calculated:
            result_data["mcdm_index"] = intersection.safety_index

        results.append(IntersectionRead(**result_data))

    if not results:
        logger.warning("No intersections returned")
    else:
        logger.info(f"Returning {len(results)} intersections with RT-SI as primary index")

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


@router.get("/debug/rt-si")
def debug_rt_si(
    intersection: str = Query(
        ..., description="Intersection name (e.g., 'glebe-potomac')"
    ),
    start_time: datetime = Query(..., description="Start datetime (ISO 8601 format)"),
    end_time: datetime = Query(..., description="End datetime (ISO 8601 format)"),
    bin_minutes: int = Query(15, description="Time bin size in minutes", ge=1, le=60),
):
    """
    Debug endpoint that returns per-bin traffic and uplift components (for diagnosis).

    Returns a JSON list of time bins with the following fields:
    - timestamp
    - vehicle_count, turning_count, vru_count
    - avg_speed, speed_variance, free_flow_speed
    - F_speed, F_variance, F_conflict, uplift_factor

    Example:
    GET /api/v1/safety/index/debug/rt-si?intersection=glebe-potomac&start_time=2025-11-01T00:00:00&end_time=2025-11-02T00:00:00&bin_minutes=15
    """
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    db_client = get_db_client()
    rt_si_service = RTSIService(db_client)

    # Find crash intersection mapping for the provided BSM intersection name
    intersection_list = find_crash_intersection_for_bsm(intersection, db_client)
    if not intersection_list:
        raise HTTPException(
            status_code=404,
            detail=f"No mapping found for intersection '{intersection}'",
        )

    # Prefer a mapping with a crash_intersection_id
    valid_intersection = next(
        (
            item
            for item in intersection_list
            if item.get("crash_intersection_id") is not None
        ),
        intersection_list[0],
    )

    if not valid_intersection or not valid_intersection.get("crash_intersection_id"):
        raise HTTPException(
            status_code=404,
            detail=f"No crash_intersection_id found for '{intersection}'",
        )

    crash_id = valid_intersection["crash_intersection_id"]
    realtime_name = valid_intersection["intersection_name"]

    try:
        rt_si_results = rt_si_service.calculate_rt_si_trend(
            crash_id,
            start_time,
            end_time,
            bin_minutes=bin_minutes,
            realtime_intersection=realtime_name,
        )

        return {
            "status": "ok",
            "intersection": intersection,
            "crash_intersection_id": crash_id,
            "realtime_name": realtime_name,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "bin_minutes": bin_minutes,
            "data_points": len(rt_si_results),
            "results": rt_si_results,
        }
    except Exception as e:
        logger.error(f"Error in debug_rt_si: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error computing RT-SI debug data: {e}"
        )


@router.get("/intersections/list", response_model=IntersectionList)
def list_available_intersections():
    """
    Get list of all available intersections in the database.
    """
    db_client = get_db_client()
    mcdm_service = MCDMSafetyIndexService(db_client)
    intersections = mcdm_service.get_available_intersections()
    return {"intersections": intersections}


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

    # Attempt multiple intersection name forms when querying MCDM
    # 1) Try as-provided
    result = mcdm_service.calculate_safety_score_for_time(
        intersection=intersection, target_time=time, bin_minutes=bin_minutes
    )

    # 2) If not found, try reverse lookup (short -> full) if caller provided a short name
    if result is None:
        try:
            full_name = reverse_lookup_intersection(intersection, db_client)
            if full_name:
                logger.info(
                    f"Reverse lookup found full name '{full_name}' for '{intersection}'"
                )
                result = mcdm_service.calculate_safety_score_for_time(
                    intersection=full_name, target_time=time, bin_minutes=bin_minutes
                )
        except Exception:
            # If reverse lookup fails, keep going
            pass

    # 3) If still not found, try normalized short name (in case caller passed full and service expects short)
    if result is None:
        try:
            normalized_intersection = normalize_intersection_name(intersection)
            if normalized_intersection and normalized_intersection != intersection:
                result = mcdm_service.calculate_safety_score_for_time(
                    intersection=normalized_intersection,
                    target_time=time,
                    bin_minutes=bin_minutes,
                )
        except Exception:
            pass

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for intersection '{intersection}' at time {time}",
        )

    # Find corresponding crash intersections for RT-SI
    intersection_list = find_crash_intersection_for_bsm(intersection, db_client)

    if intersection_list:
        # Use first valid result with crash_intersection_id
        valid_intersection = next(
            (
                item
                for item in intersection_list
                if item["crash_intersection_id"] is not None
            ),
            intersection_list[0] if intersection_list else None,
        )

        if valid_intersection and valid_intersection["crash_intersection_id"]:
            crash_id = valid_intersection["crash_intersection_id"]
            realtime_name = valid_intersection["intersection_name"]

            # Calculate RT-SI
            try:
                rt_si_result = rt_si_service.calculate_rt_si(
                    crash_id,
                    time,
                    bin_minutes=bin_minutes,
                    realtime_intersection=realtime_name,
                )

                if rt_si_result is not None:
                    result["rt_si_score"] = rt_si_result["RT_SI"]
                    result["vru_index"] = rt_si_result["VRU_index"]
                    result["vehicle_index"] = rt_si_result["VEH_index"]

                    logger.info(
                        f"Safety scores for {intersection} at {time}: "
                        f"RT-SI={rt_si_result['RT_SI']:.2f}, MCDM={result['mcdm_index']:.2f} "
                        f"(Source: {valid_intersection['source']}, blending to be done in frontend)"
                    )
                else:
                    logger.warning(f"No RT-SI data for {intersection} at {time}")
            except Exception as e:
                logger.error(f"Error calculating RT-SI: {e}", exc_info=True)
        else:
            logger.warning(f"No valid crash intersection found for '{intersection}'")
    else:
        logger.warning(f"No intersections found for '{intersection}'")

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
            intersection=normalize_intersection_name(intersection),
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

    # Find corresponding crash intersections for RT-SI
    intersection_list = find_crash_intersection_for_bsm(intersection, db_client)

    if intersection_list:
        # Use first valid result with crash_intersection_id
        valid_intersection = next(
            (
                item
                for item in intersection_list
                if item["crash_intersection_id"] is not None
            ),
            intersection_list[0] if intersection_list else None,
        )

        if valid_intersection and valid_intersection["crash_intersection_id"]:
            crash_id = valid_intersection["crash_intersection_id"]
            realtime_name = valid_intersection["intersection_name"]

            try:
                # Calculate RT-SI trend using optimized method
                logger.info(
                    f"Calculating RT-SI trend for {intersection} "
                    f"(crash ID: {crash_id}, Source: {valid_intersection['source']}) from {start_time} to {end_time}"
                )

                rt_si_results = rt_si_service.calculate_rt_si_trend(
                    crash_id,
                    start_time,
                    end_time,
                    bin_minutes=bin_minutes,
                    realtime_intersection=realtime_name,
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
            logger.warning(f"No valid crash intersection found for '{intersection}'")
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
