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
    mcdm_index: float = Field(
        ...,
        ge=0,
        le=100,
        example=67.66,
        description="MCDM prioritization index (0-100)",
    )
    vehicle_count: int = Field(..., ge=0, example=184)
    vru_count: int = Field(..., ge=0, example=11)
    avg_speed: float = Field(..., ge=0, example=25.5)
    speed_variance: float = Field(..., ge=0, example=12.3)
    incident_count: int = Field(..., ge=0, example=2)
    near_miss_count: int = Field(
        ..., ge=0, example=1, description="Count of near-miss events (NM-VRU, NM-VV)"
    )
    saw_score: float = Field(..., ge=0, le=100, example=45.2)
    edas_score: float = Field(..., ge=0, le=100, example=67.8)
    codas_score: float = Field(..., ge=0, le=100, example=72.1)

    # RT-SI components
    rt_si_score: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        example=71.79,
        description="Real-Time Safety Index (0-100, higher=safer)",
    )
    vru_index: Optional[float] = Field(
        None, ge=0, example=0.0, description="VRU sub-index from RT-SI calculation"
    )
    vehicle_index: Optional[float] = Field(
        None,
        ge=0,
        example=0.071,
        description="Vehicle sub-index from RT-SI calculation",
    )
    raw_crash_rate: Optional[float] = Field(
        None,
        example=0.00045,
        description="Raw historical crash rate (crashes per vehicle-hour)",
    )
    eb_crash_rate: Optional[float] = Field(
        None,
        example=0.00038,
        description="Empirical Bayes adjusted crash rate",
    )

    # RT-SI uplift factors for correlation analysis
    F_speed: Optional[float] = Field(
        None, example=0.45, description="Speed reduction uplift factor"
    )
    F_variance: Optional[float] = Field(
        None, example=0.23, description="Speed variance uplift factor"
    )
    F_conflict: Optional[float] = Field(
        None, example=0.12, description="VRU-vehicle conflict uplift factor"
    )
    uplift_factor: Optional[float] = Field(
        None, example=1.35, description="Combined uplift factor (U)"
    )

    # Final blended safety index
    final_safety_index: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        example=69.5,
        description="Blended final safety index: α*RT-SI + (1-α)*MCDM",
    )


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


class TrendMetadata(BaseModel):
    """Metadata for trend analysis response."""

    intersection: str = Field(..., example="glebe-potomac")
    start_time: str = Field(..., example="2025-11-01T08:00:00")
    end_time: str = Field(..., example="2025-11-23T18:00:00")
    bin_minutes: int = Field(..., example=15)
    data_points: int = Field(..., example=2112)


class SafetyScoreTrendWithCorrelations(BaseModel):
    """
    Safety score trend with correlation analysis.

    This response includes time series data plus statistical analysis showing
    how each component of RT-SI and MCDM indices relates to real safety outcomes.
    """

    time_series: list[SafetyScoreTimePoint] = Field(
        ..., description="Time series safety data"
    )
    correlation_analysis: Optional[dict] = Field(
        None,
        description="Correlation analysis showing relationships between variables and safety indices",
    )
    metadata: TrendMetadata = Field(..., description="Query metadata")
