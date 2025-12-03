"""
Pydantic models for Intersection data with validation.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Intersection(BaseModel):
    """
    Data model for a traffic intersection with safety metrics.

    Attributes:
        intersection_id: Unique identifier for the intersection
        intersection_name: Human-readable name/location
        safety_index: Primary safety score (RT-SI or MCDM, 0-100, higher = less safe)
        index_type: Calculation method ("RT-SI-Full", "RT-SI-Realtime", or "MCDM")
        traffic_volume: Traffic count or volume metric
        latitude: Geographic latitude (-90 to 90)
        longitude: Geographic longitude (-180 to 180)
        mcdm_index: Optional MCDM comparison metric (when RT-SI is primary)
    """

    intersection_id: int = Field(..., description="Unique intersection identifier")
    intersection_name: str = Field(..., description="Intersection name or location")
    safety_index: float = Field(..., ge=0, le=100, description="Blended safety index (0-100)")
    index_type: str = Field(default="MCDM", description="Index calculation method")
    traffic_volume: float = Field(..., ge=0, description="Traffic volume metric")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    mcdm_index: Optional[float] = Field(None, ge=0, le=100, description="MCDM score")
    rt_si_index: Optional[float] = Field(None, ge=0, le=100, description="RT-SI score")

    @field_validator("safety_index")
    @classmethod
    def clamp_safety_index(cls, v: float) -> float:
        """Ensure safety index is within valid range."""
        return max(0.0, min(100.0, v))

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is within valid geographic range."""
        if not -90 <= v <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {v}")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is within valid geographic range."""
        if not -180 <= v <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {v}")
        return v

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame compatibility."""
        return {
            "intersection_id": self.intersection_id,
            "intersection_name": self.intersection_name,
            "safety_index": self.safety_index,
            "rt_si_index": self.rt_si_index,
            "mcdm_index": self.mcdm_index,
            "index_type": self.index_type,
            "traffic_volume": self.traffic_volume,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }

    def get_risk_level(self) -> str:
        """
        Get risk level category based on safety index.

        Returns:
            Risk level: 'Low', 'Medium', or 'High'
        """
        if self.safety_index < 60:
            return "Low"
        elif self.safety_index <= 75:
            return "Medium"
        else:
            return "High"

    def get_risk_color(self) -> str:
        """
        Get color code for risk level.

        Returns:
            Hex color code
        """
        if self.safety_index < 60:
            return "#2ECC71"  # Green
        elif self.safety_index <= 75:
            return "#F39C12"  # Orange
        else:
            return "#E74C3C"  # Red


class IntersectionList(BaseModel):
    """Container for a list of intersections."""

    intersections: list[Intersection]

    @property
    def count(self) -> int:
        """Get count of intersections."""
        return len(self.intersections)

    def to_list_of_dicts(self) -> list[dict]:
        """Convert all intersections to list of dictionaries."""
        return [i.to_dict() for i in self.intersections]
