"""
Intersection service - Provides safety index using MCDM methodology
"""

from typing import List, Optional, Dict
import logging

from ..models.intersection import Intersection
from ..core.config import settings
from .db_client import get_db_client
from .mcdm_service import MCDMSafetyIndexService

logger = logging.getLogger(__name__)


def get_intersection_coordinates() -> Dict[str, Dict[str, float]]:
    """
    Fetch intersection coordinates from PSM table.

    PSM (Personal Safety Messages) contains latitude/longitude data for each intersection.
    Calculates average coordinates from all PSM records per intersection.

    Returns:
        Dictionary mapping intersection names to their coordinates
        Example: {"glebe-potomac": {"latitude": 38.8608, "longitude": -77.0530}}
    """
    try:
        db_client = get_db_client()

        # Fetch average lat/lon from PSM table for each intersection
        query_psm = """
        SELECT 
            intersection,
            AVG(lat) as avg_latitude,
            AVG(lon) as avg_longitude,
            COUNT(*) as sample_count
        FROM psm
        WHERE lat IS NOT NULL 
          AND lon IS NOT NULL
          AND lat BETWEEN -90 AND 90
          AND lon BETWEEN -180 AND 180
        GROUP BY intersection
        """
        results_psm = db_client.execute_query(query_psm)

        coords_map = {}
        for row in results_psm:
            coords_map[row["intersection"]] = {
                "latitude": float(row["avg_latitude"]),
                "longitude": float(row["avg_longitude"]),
            }
            logger.info(
                f"Loaded coordinates for {row['intersection']}: "
                f"({row['avg_latitude']:.6f}, {row['avg_longitude']:.6f}) "
                f"from {row['sample_count']} PSM records"
            )

        # Now fetch from hiresdata for any intersection not already in coords_map
        query_hires = """
        SELECT 
            intersection,
            AVG(intersection_lat) as avg_latitude,
            AVG(intersection_long) as avg_longitude,
            COUNT(*) as sample_count
        FROM hiresdata
        WHERE intersection_lat IS NOT NULL 
          AND intersection_long IS NOT NULL
          AND intersection_lat BETWEEN -90 AND 90
          AND intersection_long BETWEEN -180 AND 180
        GROUP BY intersection
        """
        results_hires = db_client.execute_query(query_hires)
        for row in results_hires:
            if row["intersection"] not in coords_map:
                coords_map[row["intersection"]] = {
                    "latitude": float(row["avg_latitude"]),
                    "longitude": float(row["avg_longitude"]),
                }
                logger.info(
                    f"Loaded coordinates for {row['intersection']} from hiresdata: "
                    f"({row['avg_latitude']:.6f}, {row['avg_longitude']:.6f}) "
                    f"from {row['sample_count']} hiresdata records"
                )

        # Add a reverse map for short_name if not present
        # This will be filled in compute_current_indices
        if hasattr(get_intersection_coordinates, "short_name_map"):
            for (
                short_name,
                coords,
            ) in get_intersection_coordinates.short_name_map.items():
                if short_name not in coords_map:
                    coords_map[short_name] = coords

        return coords_map

    except Exception as e:
        logger.error(
            f"Error fetching intersection coordinates from PSM/hiresdata: {e}",
            exc_info=True,
        )
        return {}


from typing import Optional


def compute_current_indices(
    mapping_results: Optional[dict] = None,
) -> List[Intersection]:
    """
    Compute current safety indices for all intersections using MCDM methodology.

    Uses Multi-Criteria Decision Making (MCDM) approach with:
    - CRITIC method for weight calculation
    - Hybrid scoring combining SAW, EDAS, and CODAS methods
    - Real-time data from PostgreSQL database

    Returns:
        List of Intersection objects with computed safety scores
    """
    try:
        logger.info("Computing MCDM safety indices for intersections...")

        # Get database client
        db_client = get_db_client()

        # Initialize MCDM service
        mcdm_service = MCDMSafetyIndexService(db_client)

        # Calculate latest safety scores
        # Use extended lookback to capture older data (30 days = 720 hours)
        safety_scores = mcdm_service.calculate_latest_safety_scores(
            bin_minutes=settings.MCDM_BIN_MINUTES,
            lookback_hours=720,  # 30 days lookback for older datasets
        )

        # Build a dict mapping intersection names to their safety scores
        # Key by both original and normalized names for flexible lookup
        from ..core.intersection_mapping import normalize_intersection_name

        safety_scores_dict = {}
        if safety_scores:
            for score_data in safety_scores:
                intersection_name = score_data["intersection"]
                # Store by original name
                safety_scores_dict[intersection_name] = score_data
                # Also store by normalized version for flexible lookup
                normalized = normalize_intersection_name(intersection_name)
                if normalized != intersection_name:
                    safety_scores_dict[normalized] = score_data
        else:
            logger.warning("No safety scores computed - no data available")

        intersections = []
        db_client = get_db_client()
        from ..api.intersection import find_crash_intersection_for_bsm

        # Process all intersections from mapping_results, not just those with safety scores
        intersections_to_process = []
        if mapping_results:
            # Use all mapped intersections
            intersections_to_process = list(mapping_results.keys())
            logger.info(
                f"Processing {len(intersections_to_process)} mapped intersections"
            )
        elif safety_scores:
            # Fallback to only intersections with safety scores
            intersections_to_process = [s["intersection"] for s in safety_scores]
            logger.info(
                f"Processing {len(intersections_to_process)} intersections with safety scores"
            )

        for idx, intersection_name in enumerate(intersections_to_process):
            score_data = safety_scores_dict.get(intersection_name)
            # Try normalized name if direct lookup fails
            if score_data is None:
                normalized = normalize_intersection_name(intersection_name)
                score_data = safety_scores_dict.get(normalized)
                if score_data:
                    logger.debug(
                        f"Found safety data for '{intersection_name}' using normalized name '{normalized}'"
                    )
            # Debug: log intersection being processed
            logger.debug(
                f"Processing intersection: {intersection_name}, has_safety_data={score_data is not None}"
            )
            # Always use mapping_results if provided and has lat/lon
            mapping = None
            normalized = None
            if mapping_results:
                # Debug: show available mapping keys (sample)
                try:
                    sample_keys = list(mapping_results.keys())[:50]
                    logger.debug(f"Mapping results keys sample: {sample_keys}")
                except Exception:
                    pass
                # Try direct key
                mapping = mapping_results.get(intersection_name)
                # If not found, try normalized key (case-insensitive)
                if mapping is None:
                    from ..core.intersection_mapping import normalize_intersection_name

                    normalized = normalize_intersection_name(intersection_name)
                    mapping = mapping_results.get(normalized)
                # If still not found, try lower-case match
                if mapping is None:
                    lower_keys = {k.lower(): v for k, v in mapping_results.items()}
                    mapping = lower_keys.get(intersection_name.lower())
                    if mapping is None and normalized is not None:
                        mapping = lower_keys.get(normalized.lower())
                # If still not found, try matching against short_name in mapping_results
                if mapping is None:
                    for v in mapping_results.values():
                        if v.get("short_name") == intersection_name:
                            mapping = v
                            break
                # Try lower-case short_name match
                if mapping is None:
                    for v in mapping_results.values():
                        if v.get("short_name", "").lower() == intersection_name.lower():
                            mapping = v
                            break
            if mapping:
                lat = mapping.get("lat")
                lon = mapping.get("lon")
                if lat is not None and lon is not None:
                    longitude = lon
                    latitude = lat
                else:
                    logger.warning(
                        f"Mapping results for {intersection_name} missing lat/lon"
                    )
                    longitude = 0.0
                    latitude = 0.0
            else:
                logger.warning(
                    f"No mapping results for {intersection_name} in provided mapping_results"
                )
                # Attempt to resolve mapping on-the-fly using API helper
                try:
                    logger.info(
                        f"Attempting on-the-fly lookup for '{intersection_name}'"
                    )
                    lookup = find_crash_intersection_for_bsm(
                        intersection_name, db_client
                    )
                    if lookup:
                        mapping = lookup[0]
                        logger.info(
                            f"On-the-fly mapping found for '{intersection_name}': {mapping}"
                        )
                    else:
                        logger.warning(
                            f"On-the-fly lookup found no mapping for '{intersection_name}'"
                        )
                except Exception as e:
                    logger.error(
                        f"Error during on-the-fly lookup for '{intersection_name}': {e}"
                    )

                if not mapping:
                    continue
                longitude = mapping.get("lon", 0.0)
                latitude = mapping.get("lat", 0.0)

            # Use safety score data if available, otherwise use default/null values
            if score_data:
                safety_index = score_data["safety_score"]
                traffic_volume = score_data["vehicle_count"]
            else:
                # No safety data available, use null/default values
                safety_index = None
                traffic_volume = 0
                logger.info(
                    f"Including intersection '{intersection_name}' without safety data"
                )

            intersections.append(
                Intersection(
                    intersection_id=100 + idx + 1,  # Generate sequential IDs
                    intersection_name=intersection_name,
                    safety_index=safety_index,
                    traffic_volume=traffic_volume,
                    longitude=longitude,
                    latitude=latitude,
                )
            )
        logger.info(f"✓ Computed MCDM indices for {len(intersections)} intersections")
        return intersections

    except Exception as e:
        logger.error(f"Error computing MCDM safety indices: {e}", exc_info=True)
        return []


def get_all(mapping_results: Optional[dict] = None) -> List[Intersection]:

    # Fallback to computing indices from MCDM database
    return compute_current_indices(mapping_results)


def get_by_id(intersection_id: int) -> Optional[Intersection]:
    """Return a single intersection matching the given ID, or None."""
    all_intersections = get_all()

    for item in all_intersections:
        if item.intersection_id == intersection_id:
            return item

    return None
