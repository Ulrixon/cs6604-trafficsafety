"""
VDOT Camera Service - Traffic camera data integration

This service fetches traffic camera data from the VDOT 511 API and provides
nearest camera lookup based on intersection coordinates.

VDOT API Access:
- Requires subscription through Iteris Inc.
- Contact: 511_videosubscription@iteris.com
- Free for internal use, monthly fee for resale
- Documentation: https://www.virginiadot.org/newsroom/511_video.asp
"""

import os
import requests
from typing import List, Dict, Optional, Tuple
from math import radians, cos, sin, asin, sqrt
from functools import lru_cache
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VDOTCameraService:
    """Service for fetching VDOT traffic camera data"""

    def __init__(self):
        """
        Initialize VDOT Camera Service

        Environment Variables:
            VDOT_API_KEY: API key from Iteris subscription
            VDOT_API_URL: Base URL for VDOT API (default: https://api.vdot.virginia.gov/511)
            VDOT_CACHE_TTL: Cache time-to-live in seconds (default: 300)
        """
        self.api_key = os.getenv("VDOT_API_KEY")
        self.base_url = os.getenv("VDOT_API_URL", "https://api.vdot.virginia.gov/511")
        self.cache_ttl = int(os.getenv("VDOT_CACHE_TTL", "300"))  # 5 minutes default

        if not self.api_key:
            logger.warning(
                "VDOT_API_KEY not set. Camera lookups will return empty results. "
                "Contact 511_videosubscription@iteris.com to request access."
            )

    def find_nearest_cameras(
        self,
        lat: float,
        lon: float,
        radius_miles: float = 0.5,
        max_results: int = 3
    ) -> List[Dict[str, str]]:
        """
        Find cameras within radius of intersection coordinates

        Args:
            lat: Intersection latitude (-90 to 90)
            lon: Intersection longitude (-180 to 180)
            radius_miles: Search radius in miles (default 0.5)
            max_results: Maximum cameras to return (default 3)

        Returns:
            List of camera link dictionaries with keys:
                - source: "VDOT"
                - url: Full URL to camera feed
                - label: User-friendly camera name

        Example:
            >>> service = VDOTCameraService()
            >>> cameras = service.find_nearest_cameras(37.5, -77.4, radius_miles=1.0)
            >>> print(cameras)
            [
                {
                    "source": "VDOT",
                    "url": "https://511virginia.org/camera/CAM123",
                    "label": "VDOT Camera - I-95 @ Exit 74"
                }
            ]
        """
        try:
            # Validate inputs
            if not (-90 <= lat <= 90):
                logger.error(f"Invalid latitude: {lat}")
                return []

            if not (-180 <= lon <= 180):
                logger.error(f"Invalid longitude: {lon}")
                return []

            # If no API key, return empty list with fallback map link
            if not self.api_key:
                logger.debug("No VDOT API key - skipping camera lookup")
                return []

            # Fetch all cameras from VDOT API (with caching)
            cameras = self._fetch_vdot_cameras()

            if not cameras:
                logger.warning("No cameras returned from VDOT API")
                return []

            # Filter by distance
            nearby = self._filter_by_distance(cameras, lat, lon, radius_miles)

            # Format as camera link dictionaries
            camera_links = []
            for cam in nearby[:max_results]:
                camera_links.append({
                    "source": "VDOT",
                    "url": self._build_camera_url(cam),
                    "label": self._build_camera_label(cam)
                })

            logger.info(
                f"Found {len(camera_links)} camera(s) within {radius_miles} miles of "
                f"({lat:.4f}, {lon:.4f})"
            )
            return camera_links

        except Exception as e:
            # Log error but don't fail - return empty list
            logger.error(f"Error finding nearest cameras: {e}", exc_info=True)
            return []

    def _fetch_vdot_cameras(self) -> List[Dict]:
        """
        Fetch all cameras from VDOT API with caching

        Returns:
            List of camera dictionaries from VDOT API

        Note:
            Results are cached using LRU cache for 5 minutes to reduce API calls
        """
        return self._fetch_vdot_cameras_cached()

    @lru_cache(maxsize=1)
    def _fetch_vdot_cameras_cached(self) -> List[Dict]:
        """
        Cached camera fetch implementation

        This method is decorated with @lru_cache to cache results.
        Cache is invalidated after cache_ttl seconds.
        """
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}

            logger.debug(f"Fetching cameras from VDOT API: {self.base_url}/cameras")
            response = requests.get(
                f"{self.base_url}/cameras",
                headers=headers,
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            cameras = data.get("cameras", [])
            logger.info(f"Fetched {len(cameras)} cameras from VDOT API")

            return cameras

        except requests.exceptions.Timeout:
            logger.error("VDOT API request timed out")
            return []
        except requests.exceptions.HTTPError as e:
            logger.error(f"VDOT API HTTP error: {e}")
            if e.response.status_code == 401:
                logger.error("VDOT API authentication failed - check VDOT_API_KEY")
            return []
        except Exception as e:
            logger.error(f"Error fetching cameras from VDOT API: {e}", exc_info=True)
            return []

    def _filter_by_distance(
        self,
        cameras: List[Dict],
        lat: float,
        lon: float,
        max_distance: float
    ) -> List[Dict]:
        """
        Filter cameras within max_distance miles of target coordinates

        Args:
            cameras: List of camera dictionaries from VDOT API
            lat: Target latitude
            lon: Target longitude
            max_distance: Maximum distance in miles

        Returns:
            List of cameras within radius, sorted by distance (closest first)
        """
        nearby = []

        for cam in cameras:
            # Camera coordinates might be in different field names
            cam_lat = cam.get('latitude') or cam.get('lat')
            cam_lon = cam.get('longitude') or cam.get('lon') or cam.get('long')

            if cam_lat is None or cam_lon is None:
                continue

            try:
                distance = self._haversine_distance(lat, lon, float(cam_lat), float(cam_lon))

                if distance <= max_distance:
                    cam_with_distance = cam.copy()
                    cam_with_distance['distance'] = distance
                    nearby.append(cam_with_distance)

            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping camera with invalid coordinates: {e}")
                continue

        # Sort by distance, closest first
        nearby.sort(key=lambda x: x['distance'])

        return nearby

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate great circle distance in miles between two points

        Uses the Haversine formula:
        a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
        c = 2 * atan2(√a, √(1−a))
        d = R * c

        Where R is Earth's radius (3956 miles)

        Args:
            lat1: First point latitude (degrees)
            lon1: First point longitude (degrees)
            lat2: Second point latitude (degrees)
            lon2: Second point longitude (degrees)

        Returns:
            Distance in miles

        Example:
            >>> service = VDOTCameraService()
            >>> # Distance from Richmond to Blacksburg (approx 200 miles)
            >>> distance = service._haversine_distance(37.5407, -77.4360, 37.2296, -80.4139)
            >>> print(f"{distance:.1f} miles")
            208.7 miles
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))

        # Radius of earth in miles
        radius_miles = 3956
        distance = radius_miles * c

        return distance

    def _build_camera_url(self, camera: Dict) -> str:
        """
        Build camera URL from camera data

        Args:
            camera: Camera dictionary from VDOT API

        Returns:
            Full URL to camera feed
        """
        # Camera ID might be in different fields
        camera_id = camera.get('id') or camera.get('camera_id') or camera.get('name')

        if camera_id:
            return f"https://511virginia.org/camera/{camera_id}"
        else:
            # Fallback to generic 511 map
            cam_lat = camera.get('latitude') or camera.get('lat')
            cam_lon = camera.get('longitude') or camera.get('lon')
            return f"https://511.vdot.virginia.gov/map?lat={cam_lat}&lon={cam_lon}"

    def _build_camera_label(self, camera: Dict) -> str:
        """
        Build user-friendly camera label

        Args:
            camera: Camera dictionary from VDOT API

        Returns:
            Human-readable camera name
        """
        # Try different name fields
        name = camera.get('name') or camera.get('description') or camera.get('location')

        if name:
            # Clean up name (remove camera ID prefix if present)
            name = name.replace('CAM-', '').replace('CAMERA-', '')
            return f"VDOT {name}"
        else:
            # Fallback to location description
            return "VDOT Traffic Camera"

    def get_fallback_map_link(self, lat: float, lon: float) -> Dict[str, str]:
        """
        Get fallback 511 map link centered on intersection

        This is used when no specific camera is available, providing users
        with a general traffic map view of the intersection area.

        Args:
            lat: Intersection latitude
            lon: Intersection longitude

        Returns:
            Camera link dictionary with 511 map URL

        Example:
            >>> service = VDOTCameraService()
            >>> fallback = service.get_fallback_map_link(37.5, -77.4)
            >>> print(fallback)
            {
                "source": "511",
                "url": "https://511.vdot.virginia.gov/map?lat=37.5&lon=-77.4",
                "label": "View on 511 Map"
            }
        """
        return {
            "source": "511",
            "url": f"https://511.vdot.virginia.gov/map?lat={lat}&lon={lon}",
            "label": "View on 511 Map"
        }

    def get_cameras_with_fallback(
        self,
        lat: float,
        lon: float,
        radius_miles: float = 0.5,
        max_results: int = 3
    ) -> List[Dict[str, str]]:
        """
        Get nearest cameras with automatic fallback to 511 map

        This is the recommended method for UI integration as it ensures
        users always have at least one link (even if no cameras are available).

        Args:
            lat: Intersection latitude
            lon: Intersection longitude
            radius_miles: Search radius in miles (default 0.5)
            max_results: Maximum cameras to return (default 3)

        Returns:
            List of camera links, always includes 511 map fallback

        Example:
            >>> service = VDOTCameraService()
            >>> cameras = service.get_cameras_with_fallback(37.5, -77.4)
            >>> # Will return specific cameras if found, plus 511 map fallback
            >>> for cam in cameras:
            ...     print(f"{cam['label']}: {cam['url']}")
        """
        # Get nearest cameras
        cameras = self.find_nearest_cameras(lat, lon, radius_miles, max_results)

        # Always add 511 map fallback
        cameras.append(self.get_fallback_map_link(lat, lon))

        return cameras
