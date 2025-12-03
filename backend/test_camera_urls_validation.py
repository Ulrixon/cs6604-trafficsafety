"""
Unit tests for camera_urls field validation in Intersection schemas.

Tests ensure that camera_urls:
- Accepts valid camera link arrays
- Validates required fields (source, url, label)
- Validates URL format (must start with http:// or https://)
- Handles null/None values gracefully
- Returns None for invalid data (backward compatibility)
"""

import pytest
from pydantic import ValidationError

from app.schemas.intersection import IntersectionRead, CameraLink


class TestCameraLinkValidation:
    """Test CameraLink schema validation"""

    def test_valid_camera_link(self):
        """Test that valid camera link is accepted"""
        valid_link = {
            "source": "VDOT",
            "url": "https://511virginia.org/camera/CAM123",
            "label": "VDOT Camera - Main St"
        }
        camera = CameraLink(**valid_link)
        assert camera.source == "VDOT"
        assert camera.url == "https://511virginia.org/camera/CAM123"
        assert camera.label == "VDOT Camera - Main St"

    def test_http_url_accepted(self):
        """Test that HTTP URLs are accepted (not just HTTPS)"""
        valid_link = {
            "source": "511",
            "url": "http://example.com/camera",
            "label": "Test Camera"
        }
        camera = CameraLink(**valid_link)
        assert camera.url == "http://example.com/camera"

    def test_invalid_url_format(self):
        """Test that non-HTTP URLs are rejected"""
        invalid_link = {
            "source": "VDOT",
            "url": "ftp://invalid.com",
            "label": "Invalid Camera"
        }
        with pytest.raises(ValidationError) as exc_info:
            CameraLink(**invalid_link)
        assert "url" in str(exc_info.value)

    def test_missing_required_fields(self):
        """Test that missing required fields are rejected"""
        # Missing source
        with pytest.raises(ValidationError):
            CameraLink(url="https://example.com", label="Test")

        # Missing url
        with pytest.raises(ValidationError):
            CameraLink(source="VDOT", label="Test")

        # Missing label
        with pytest.raises(ValidationError):
            CameraLink(source="VDOT", url="https://example.com")

    def test_empty_string_fields(self):
        """Test that empty strings are rejected"""
        with pytest.raises(ValidationError):
            CameraLink(source="", url="https://example.com", label="Test")

        with pytest.raises(ValidationError):
            CameraLink(source="VDOT", url="https://example.com", label="")


class TestIntersectionReadCameraURLs:
    """Test IntersectionRead schema with camera_urls field"""

    def test_intersection_with_valid_camera_urls(self):
        """Test intersection with valid camera_urls array"""
        data = {
            "intersection_id": 1,
            "intersection_name": "Test Intersection",
            "safety_index": 65.0,
            "index_type": "RT-SI-Full",
            "traffic_volume": 250,
            "longitude": -77.053,
            "latitude": 38.856,
            "camera_urls": [
                {
                    "source": "VDOT",
                    "url": "https://511virginia.org/camera/CAM123",
                    "label": "VDOT Camera 1"
                },
                {
                    "source": "511",
                    "url": "https://511.vdot.virginia.gov/map?lat=38.856&lon=-77.053",
                    "label": "View on 511 Map"
                }
            ]
        }
        intersection = IntersectionRead(**data)
        assert len(intersection.camera_urls) == 2
        assert intersection.camera_urls[0]["source"] == "VDOT"
        assert intersection.camera_urls[1]["source"] == "511"

    def test_intersection_with_null_camera_urls(self):
        """Test that null camera_urls is accepted (optional field)"""
        data = {
            "intersection_id": 1,
            "intersection_name": "Test Intersection",
            "safety_index": 65.0,
            "index_type": "RT-SI-Full",
            "traffic_volume": 250,
            "longitude": -77.053,
            "latitude": 38.856,
            "camera_urls": None
        }
        intersection = IntersectionRead(**data)
        assert intersection.camera_urls is None

    def test_intersection_without_camera_urls_field(self):
        """Test that camera_urls can be omitted (backward compatibility)"""
        data = {
            "intersection_id": 1,
            "intersection_name": "Test Intersection",
            "safety_index": 65.0,
            "index_type": "RT-SI-Full",
            "traffic_volume": 250,
            "longitude": -77.053,
            "latitude": 38.856
        }
        intersection = IntersectionRead(**data)
        assert intersection.camera_urls is None

    def test_intersection_with_empty_camera_urls_array(self):
        """Test that empty camera_urls array is handled"""
        data = {
            "intersection_id": 1,
            "intersection_name": "Test Intersection",
            "safety_index": 65.0,
            "index_type": "RT-SI-Full",
            "traffic_volume": 250,
            "longitude": -77.053,
            "latitude": 38.856,
            "camera_urls": []
        }
        intersection = IntersectionRead(**data)
        # Empty array should be converted to empty list by validator
        assert intersection.camera_urls == []

    def test_intersection_with_invalid_camera_url_returns_none(self):
        """Test that invalid camera_urls returns None (graceful degradation)"""
        data = {
            "intersection_id": 1,
            "intersection_name": "Test Intersection",
            "safety_index": 65.0,
            "index_type": "RT-SI-Full",
            "traffic_volume": 250,
            "longitude": -77.053,
            "latitude": 38.856,
            "camera_urls": [
                {
                    "source": "VDOT",
                    # Missing url and label - should fail validation
                }
            ]
        }
        # Should not raise error, but set camera_urls to None
        intersection = IntersectionRead(**data)
        assert intersection.camera_urls is None

    def test_intersection_with_single_camera(self):
        """Test intersection with single camera URL"""
        data = {
            "intersection_id": 1,
            "intersection_name": "Test Intersection",
            "safety_index": 65.0,
            "index_type": "RT-SI-Full",
            "traffic_volume": 250,
            "longitude": -77.053,
            "latitude": 38.856,
            "camera_urls": [
                {
                    "source": "VDOT",
                    "url": "https://511virginia.org/camera/CAM456",
                    "label": "VDOT Main Camera"
                }
            ]
        }
        intersection = IntersectionRead(**data)
        assert len(intersection.camera_urls) == 1
        assert intersection.camera_urls[0]["source"] == "VDOT"

    def test_intersection_with_multiple_camera_sources(self):
        """Test intersection with cameras from different sources"""
        data = {
            "intersection_id": 1,
            "intersection_name": "Test Intersection",
            "safety_index": 65.0,
            "index_type": "RT-SI-Full",
            "traffic_volume": 250,
            "longitude": -77.053,
            "latitude": 38.856,
            "camera_urls": [
                {"source": "VDOT", "url": "https://vdot.com/cam1", "label": "VDOT Cam"},
                {"source": "511", "url": "https://511.com/map", "label": "511 Map"},
                {"source": "TrafficLand", "url": "https://trafficland.com/cam", "label": "TL Cam"}
            ]
        }
        intersection = IntersectionRead(**data)
        assert len(intersection.camera_urls) == 3
        sources = [cam["source"] for cam in intersection.camera_urls]
        assert "VDOT" in sources
        assert "511" in sources
        assert "TrafficLand" in sources


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
