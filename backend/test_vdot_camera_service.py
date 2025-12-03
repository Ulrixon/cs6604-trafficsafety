"""
Integration tests for VDOT Camera Service

Tests cover:
- Haversine distance calculation accuracy
- Camera filtering by distance
- API integration (with mocking)
- Fallback behavior
- Error handling
"""

import pytest
from unittest.mock import Mock, patch
import os

from app.services.vdot_camera_service import VDOTCameraService


class TestHaversineDistance:
    """Test haversine distance calculation"""

    def test_distance_same_point(self):
        """Distance between same point should be 0"""
        service = VDOTCameraService()
        distance = service._haversine_distance(37.5, -77.4, 37.5, -77.4)
        assert distance == 0.0

    def test_distance_richmond_to_blacksburg(self):
        """Test known distance: Richmond to Blacksburg (~208 miles)"""
        service = VDOTCameraService()
        # Richmond: 37.5407, -77.4360
        # Blacksburg: 37.2296, -80.4139
        distance = service._haversine_distance(37.5407, -77.4360, 37.2296, -80.4139)

        # Should be approximately 208 miles
        assert 200 < distance < 220, f"Expected ~208 miles, got {distance:.1f}"

    def test_distance_one_mile_north(self):
        """Test distance of approximately 1 mile (1 degree latitude ≈ 69 miles)"""
        service = VDOTCameraService()
        # Move 1/69th of a degree north (approximately 1 mile)
        distance = service._haversine_distance(37.0, -77.0, 37.0 + (1/69), -77.0)

        assert 0.9 < distance < 1.1, f"Expected ~1 mile, got {distance:.2f}"

    def test_distance_symmetry(self):
        """Distance from A to B should equal distance from B to A"""
        service = VDOTCameraService()
        dist_ab = service._haversine_distance(37.0, -77.0, 38.0, -78.0)
        dist_ba = service._haversine_distance(38.0, -78.0, 37.0, -77.0)

        assert abs(dist_ab - dist_ba) < 0.0001, "Distance should be symmetric"


class TestCameraFiltering:
    """Test camera filtering by distance"""

    def test_filter_cameras_within_radius(self):
        """Test filtering cameras within radius"""
        service = VDOTCameraService()

        # Mock cameras at various distances
        cameras = [
            {"id": "CAM1", "latitude": 37.5, "longitude": -77.4},  # 0 miles
            {"id": "CAM2", "latitude": 37.5145, "longitude": -77.4},  # ~1 mile north
            {"id": "CAM3", "latitude": 37.6, "longitude": -77.4},  # ~7 miles north
        ]

        # Filter with 2-mile radius
        nearby = service._filter_by_distance(cameras, 37.5, -77.4, max_distance=2.0)

        assert len(nearby) == 2, "Should find 2 cameras within 2 miles"
        assert nearby[0]["id"] == "CAM1", "Closest camera should be first"
        assert nearby[1]["id"] == "CAM2", "Second closest should be second"

    def test_filter_no_cameras_in_radius(self):
        """Test when no cameras are within radius"""
        service = VDOTCameraService()

        cameras = [
            {"id": "CAM1", "latitude": 38.0, "longitude": -78.0},  # Far away
        ]

        nearby = service._filter_by_distance(cameras, 37.5, -77.4, max_distance=0.5)

        assert len(nearby) == 0, "Should find no cameras within 0.5 miles"

    def test_filter_handles_missing_coordinates(self):
        """Test that cameras with missing coordinates are skipped"""
        service = VDOTCameraService()

        cameras = [
            {"id": "CAM1", "latitude": 37.5, "longitude": -77.4},
            {"id": "CAM2"},  # Missing coordinates
            {"id": "CAM3", "latitude": None, "longitude": -77.4},  # Null lat
        ]

        nearby = service._filter_by_distance(cameras, 37.5, -77.4, max_distance=1.0)

        assert len(nearby) == 1, "Should only include camera with valid coordinates"
        assert nearby[0]["id"] == "CAM1"

    def test_filter_sorts_by_distance(self):
        """Test that results are sorted by distance (closest first)"""
        service = VDOTCameraService()

        cameras = [
            {"id": "CAM_FAR", "latitude": 37.6, "longitude": -77.4},  # ~7 miles
            {"id": "CAM_CLOSE", "latitude": 37.5, "longitude": -77.4},  # 0 miles
            {"id": "CAM_MEDIUM", "latitude": 37.55, "longitude": -77.4},  # ~3.5 miles
        ]

        nearby = service._filter_by_distance(cameras, 37.5, -77.4, max_distance=10.0)

        assert nearby[0]["id"] == "CAM_CLOSE", "Closest should be first"
        assert nearby[1]["id"] == "CAM_MEDIUM", "Medium should be second"
        assert nearby[2]["id"] == "CAM_FAR", "Farthest should be last"


class TestVDOTAPIIntegration:
    """Test VDOT API integration with mocking"""

    @patch('app.services.vdot_camera_service.requests.get')
    @patch.dict(os.environ, {"VDOT_API_KEY": "test-key"})
    def test_fetch_cameras_success(self, mock_get):
        """Test successful camera fetch from API"""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "cameras": [
                {
                    "id": "CAM123",
                    "name": "I-95 @ Exit 74",
                    "latitude": 37.5407,
                    "longitude": -77.4360
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = VDOTCameraService()
        cameras = service._fetch_vdot_cameras()

        assert len(cameras) == 1
        assert cameras[0]["id"] == "CAM123"
        mock_get.assert_called_once()

    @patch('app.services.vdot_camera_service.requests.get')
    @patch.dict(os.environ, {"VDOT_API_KEY": "test-key"})
    def test_fetch_cameras_timeout(self, mock_get):
        """Test API timeout handling"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        service = VDOTCameraService()
        cameras = service._fetch_vdot_cameras()

        assert cameras == [], "Should return empty list on timeout"

    @patch('app.services.vdot_camera_service.requests.get')
    @patch.dict(os.environ, {"VDOT_API_KEY": "test-key"})
    def test_fetch_cameras_auth_error(self, mock_get):
        """Test API authentication error handling"""
        import requests
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        service = VDOTCameraService()
        cameras = service._fetch_vdot_cameras()

        assert cameras == [], "Should return empty list on auth error"

    def test_no_api_key_graceful_degradation(self):
        """Test that service works without API key (returns empty list)"""
        # Clear API key
        with patch.dict(os.environ, {}, clear=True):
            service = VDOTCameraService()
            cameras = service.find_nearest_cameras(37.5, -77.4)

            assert cameras == [], "Should return empty list when no API key"


class TestFindNearestCameras:
    """Test find_nearest_cameras end-to-end"""

    @patch('app.services.vdot_camera_service.requests.get')
    @patch.dict(os.environ, {"VDOT_API_KEY": "test-key"})
    def test_find_nearest_cameras_success(self, mock_get):
        """Test successful camera search"""
        # Mock API response with multiple cameras
        mock_response = Mock()
        mock_response.json.return_value = {
            "cameras": [
                {"id": "CAM1", "name": "Main St", "latitude": 37.5, "longitude": -77.4},
                {"id": "CAM2", "name": "Elm St", "latitude": 37.5145, "longitude": -77.4},
                {"id": "CAM3", "name": "Oak Ave", "latitude": 37.6, "longitude": -77.4},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = VDOTCameraService()
        cameras = service.find_nearest_cameras(37.5, -77.4, radius_miles=2.0, max_results=2)

        assert len(cameras) == 2, "Should return max_results cameras"
        assert cameras[0]["source"] == "VDOT"
        assert "https://511virginia.org/camera/CAM1" in cameras[0]["url"]
        assert "VDOT" in cameras[0]["label"]

    @patch('app.services.vdot_camera_service.requests.get')
    @patch.dict(os.environ, {"VDOT_API_KEY": "test-key"})
    def test_find_nearest_cameras_none_in_radius(self, mock_get):
        """Test when no cameras are within radius"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "cameras": [
                {"id": "CAM1", "latitude": 38.0, "longitude": -78.0},  # Far away
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = VDOTCameraService()
        cameras = service.find_nearest_cameras(37.5, -77.4, radius_miles=0.5)

        assert cameras == [], "Should return empty list when no cameras in radius"

    def test_invalid_coordinates(self):
        """Test handling of invalid coordinates"""
        service = VDOTCameraService()

        # Invalid latitude
        cameras = service.find_nearest_cameras(999, -77.4)
        assert cameras == [], "Should return empty for invalid latitude"

        # Invalid longitude
        cameras = service.find_nearest_cameras(37.5, 999)
        assert cameras == [], "Should return empty for invalid longitude"


class TestFallbackBehavior:
    """Test fallback map link behavior"""

    def test_get_fallback_map_link(self):
        """Test fallback map link generation"""
        service = VDOTCameraService()
        fallback = service.get_fallback_map_link(37.5, -77.4)

        assert fallback["source"] == "511"
        assert "https://511.vdot.virginia.gov/map" in fallback["url"]
        assert "lat=37.5" in fallback["url"]
        assert "lon=-77.4" in fallback["url"]
        assert "511 Map" in fallback["label"]

    @patch('app.services.vdot_camera_service.requests.get')
    @patch.dict(os.environ, {"VDOT_API_KEY": "test-key"})
    def test_get_cameras_with_fallback(self, mock_get):
        """Test that fallback is always included"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "cameras": [
                {"id": "CAM1", "name": "Test", "latitude": 37.5, "longitude": -77.4}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        service = VDOTCameraService()
        cameras = service.get_cameras_with_fallback(37.5, -77.4, radius_miles=1.0)

        assert len(cameras) >= 1, "Should always have at least fallback"
        assert cameras[-1]["source"] == "511", "Last item should be 511 fallback"

    def test_fallback_when_no_cameras(self):
        """Test fallback when no cameras found"""
        with patch.dict(os.environ, {}, clear=True):
            service = VDOTCameraService()
            cameras = service.get_cameras_with_fallback(37.5, -77.4)

            assert len(cameras) == 1, "Should have fallback only"
            assert cameras[0]["source"] == "511"


class TestCameraURLBuilding:
    """Test camera URL and label building"""

    def test_build_camera_url_with_id(self):
        """Test URL building when camera has ID"""
        service = VDOTCameraService()
        camera = {"id": "CAM123", "name": "Test Camera"}
        url = service._build_camera_url(camera)

        assert url == "https://511virginia.org/camera/CAM123"

    def test_build_camera_url_fallback(self):
        """Test URL building when camera has no ID"""
        service = VDOTCameraService()
        camera = {"latitude": 37.5, "longitude": -77.4}
        url = service._build_camera_url(camera)

        assert "511.vdot.virginia.gov/map" in url
        assert "lat=37.5" in url

    def test_build_camera_label_with_name(self):
        """Test label building with camera name"""
        service = VDOTCameraService()
        camera = {"name": "I-95 @ Exit 74"}
        label = service._build_camera_label(camera)

        assert "VDOT" in label
        assert "I-95 @ Exit 74" in label

    def test_build_camera_label_fallback(self):
        """Test label building when no name available"""
        service = VDOTCameraService()
        camera = {"id": "CAM123"}
        label = service._build_camera_label(camera)

        assert "VDOT Traffic Camera" == label


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
