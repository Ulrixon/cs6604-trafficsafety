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
        query = """
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

        results = db_client.execute_query(query)

        coords_map = {}
        for row in results:
            coords_map[row["intersection"]] = {
                "latitude": float(row["avg_latitude"]),
                "longitude": float(row["avg_longitude"]),
            }
            logger.info(
                f"Loaded coordinates for {row['intersection']}: "
                f"({row['avg_latitude']:.6f}, {row['avg_longitude']:.6f}) "
                f"from {row['sample_count']} PSM records"
            )

        return coords_map

    except Exception as e:
        logger.error(
            f"Error fetching intersection coordinates from PSM: {e}", exc_info=True
        )
        return {}


def compute_current_indices() -> List[Intersection]:
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
        safety_scores = mcdm_service.calculate_latest_safety_scores(
            bin_minutes=settings.MCDM_BIN_MINUTES,
            lookback_hours=settings.MCDM_LOOKBACK_HOURS,
        )

        if not safety_scores:
            logger.warning("No safety scores computed - no data available")
            return []

        # Fetch intersection coordinates from BSM table
        intersection_coords = get_intersection_coordinates()

        # Default fallback coordinates (center of Arlington, VA)
        DEFAULT_COORDS = {"latitude": 38.8816, "longitude": -77.1945}

        # Convert to Intersection objects
        intersections = []
        for idx, score_data in enumerate(safety_scores):
            intersection_name = score_data["intersection"]

            # Use coordinates from BSM data, or fallback to default
            coords = intersection_coords.get(intersection_name, DEFAULT_COORDS)

            if intersection_name not in intersection_coords:
                logger.warning(
                    f"No coordinates found in BSM for '{intersection_name}', "
                    f"using default: ({DEFAULT_COORDS['latitude']}, {DEFAULT_COORDS['longitude']})"
                )

            intersections.append(
                Intersection(
                    intersection_id=100 + idx + 1,  # Generate sequential IDs
                    intersection_name=intersection_name,
                    safety_index=score_data["safety_score"],
                    traffic_volume=score_data["vehicle_count"],
                    longitude=coords["longitude"],
                    latitude=coords["latitude"],
                )
            )

        logger.info(f"✓ Computed MCDM indices for {len(intersections)} intersections")
        return intersections

    except Exception as e:
        logger.error(f"Error computing MCDM safety indices: {e}", exc_info=True)
        return []


def get_all() -> List[Intersection]:
    """Return a list of all intersections with current safety indices."""
    return compute_current_indices()


def get_by_id(intersection_id: int) -> Optional[Intersection]:
    """Return a single intersection matching the given ID, or None."""
    all_intersections = get_all()

    for item in all_intersections:
        if item.intersection_id == intersection_id:
            return item

    return None
