"""
Camera Service - Manages intersection camera URL lookups.

Provides camera URLs for intersections independent of safety index system.
Uses intersection_cameras table keyed by intersection name.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CameraService:
    """Service for managing intersection camera lookups."""

    def __init__(self, db_client):
        """Initialize camera service with database client."""
        self.db_client = db_client

    def get_cameras_by_name(self, intersection_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Look up camera URLs for an intersection by name.

        Args:
            intersection_name: Name of the intersection (case-insensitive)

        Returns:
            List of camera link dictionaries, or None if no cameras found
            Example: [{"source": "VDOT", "url": "https://...", "label": "Camera 1"}]
        """
        try:
            query = """
                SELECT camera_urls
                FROM intersection_cameras
                WHERE LOWER(intersection_name) = LOWER(%s)
                  AND camera_urls IS NOT NULL;
            """

            results = self.db_client.execute_query(query, (intersection_name,))

            if results and len(results) > 0:
                camera_urls = results[0].get("camera_urls")
                if camera_urls:
                    logger.debug(f"Found {len(camera_urls)} cameras for '{intersection_name}'")
                    return camera_urls

            logger.debug(f"No cameras found for '{intersection_name}'")
            return None

        except Exception as e:
            logger.error(f"Error looking up cameras for '{intersection_name}': {e}")
            return None

    def get_cameras_by_location(
        self, latitude: float, longitude: float, radius_km: float = 0.5
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Look up camera URLs for an intersection by geographic location.

        Args:
            latitude: Intersection latitude
            longitude: Intersection longitude
            radius_km: Search radius in kilometers (default: 0.5 km)

        Returns:
            List of camera link dictionaries, or None if no cameras found
        """
        try:
            # Use Haversine formula for distance calculation
            query = """
                SELECT camera_urls,
                       (6371 * acos(
                           cos(radians(%s)) * cos(radians(latitude)) *
                           cos(radians(longitude) - radians(%s)) +
                           sin(radians(%s)) * sin(radians(latitude))
                       )) AS distance_km
                FROM intersection_cameras
                WHERE camera_urls IS NOT NULL
                  AND latitude IS NOT NULL
                  AND longitude IS NOT NULL
                HAVING distance_km < %s
                ORDER BY distance_km
                LIMIT 1;
            """

            results = self.db_client.execute_query(
                query, (latitude, longitude, latitude, radius_km)
            )

            if results and len(results) > 0:
                camera_urls = results[0].get("camera_urls")
                if camera_urls:
                    distance = results[0].get("distance_km", 0)
                    logger.debug(
                        f"Found {len(camera_urls)} cameras within {distance:.2f}km of ({latitude}, {longitude})"
                    )
                    return camera_urls

            logger.debug(f"No cameras found within {radius_km}km of ({latitude}, {longitude})")
            return None

        except Exception as e:
            logger.error(
                f"Error looking up cameras by location ({latitude}, {longitude}): {e}"
            )
            return None

    def add_or_update_cameras(
        self,
        intersection_name: str,
        camera_urls: List[Dict[str, Any]],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> bool:
        """
        Add or update camera URLs for an intersection.

        Args:
            intersection_name: Name of the intersection
            camera_urls: List of camera link dictionaries
            latitude: Optional intersection latitude
            longitude: Optional intersection longitude

        Returns:
            True if successful, False otherwise
        """
        try:
            import json

            query = """
                INSERT INTO intersection_cameras (intersection_name, camera_urls, latitude, longitude)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (intersection_name) DO UPDATE SET
                    camera_urls = EXCLUDED.camera_urls,
                    latitude = COALESCE(EXCLUDED.latitude, intersection_cameras.latitude),
                    longitude = COALESCE(EXCLUDED.longitude, intersection_cameras.longitude),
                    updated_at = CURRENT_TIMESTAMP;
            """

            with self.db_client.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (intersection_name, json.dumps(camera_urls), latitude, longitude),
                )
                conn.commit()
                cursor.close()

            logger.info(f"Updated cameras for '{intersection_name}': {len(camera_urls)} cameras")
            return True

        except Exception as e:
            logger.error(f"Error updating cameras for '{intersection_name}': {e}")
            return False
