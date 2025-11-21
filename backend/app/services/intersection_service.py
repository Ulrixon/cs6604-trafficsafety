"""
Intersection service - Provides safety index using MCDM methodology
"""

from typing import List, Optional
import logging

from ..models.intersection import Intersection
from ..core.config import settings
from .db_client import get_db_client
from .mcdm_service import MCDMSafetyIndexService

logger = logging.getLogger(__name__)


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

        # Convert to Intersection objects
        intersections = []
        for idx, score_data in enumerate(safety_scores):
            intersections.append(
                Intersection(
                    intersection_id=100 + idx + 1,  # Generate sequential IDs
                    intersection_name=score_data["intersection"],
                    safety_index=score_data["safety_score"],
                    traffic_volume=score_data["vehicle_count"],
                    longitude=-77.053,  # Default coordinates (TODO: lookup from metadata)
                    latitude=38.856,
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
