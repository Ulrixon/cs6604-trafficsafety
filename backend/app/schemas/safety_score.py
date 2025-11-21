"""
Schemas for safety score time-based queries
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class SafetyScoreTimePoint(BaseModel):
    """Safety score for a specific time point."""

    intersection: str = Field(..., example="glebe-potomac")
    time_bin: datetime = Field(..., example="2025-11-09T10:00:00")
    safety_score: float = Field(..., ge=0, le=100, example=67.66)
    mcdm_index: float = Field(..., ge=0, le=100, example=67.66)
    vehicle_count: int = Field(..., ge=0, example=184)
    vru_count: int = Field(..., ge=0, example=11)
    avg_speed: float = Field(..., ge=0, example=25.5)
    speed_variance: float = Field(..., ge=0, example=12.3)
    incident_count: int = Field(..., ge=0, example=2)
    saw_score: float = Field(..., ge=0, le=100, example=45.2)
    edas_score: float = Field(..., ge=0, le=100, example=67.8)
    codas_score: float = Field(..., ge=0, le=100, example=72.1)


class SafetyScoreTrend(BaseModel):
    """Safety score trend over time for an intersection."""

    intersection: str = Field(..., example="glebe-potomac")
    time_points: list[SafetyScoreTimePoint] = Field(..., description="Time series data")
    avg_safety_score: float = Field(..., example=65.5)
    min_safety_score: float = Field(..., example=50.2)
    max_safety_score: float = Field(..., example=75.8)
    total_vehicles: int = Field(..., example=1500)
    total_incidents: int = Field(..., example=12)


class IntersectionList(BaseModel):
    """List of available intersections."""

    intersections: list[str] = Field(..., example=["glebe-potomac", "duke-jordan"])
