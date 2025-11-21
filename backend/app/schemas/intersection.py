from pydantic import BaseModel, Field, RootModel
from datetime import datetime
from typing import List, Optional


class IntersectionBase(BaseModel):
    """
    Shared fields for Intersection schemas.
    """

    intersection_name: str = Field(..., example="Glebe & Potomac")
    safety_index: float = Field(..., ge=0, le=100, example=63.0)
    traffic_volume: int = Field(..., ge=0, example=253)
    longitude: float = Field(..., example=-77.053)
    latitude: float = Field(..., example=38.856)


class IntersectionRead(IntersectionBase):
    """
    Schema returned to the client.
    """

    intersection_id: int = Field(..., example=101)


# Optional: list wrapper (FastAPI can also use List[IntersectionRead] directly)
class IntersectionList(RootModel[list[IntersectionRead]]):
    pass


# ============================================================================
# Historical Data Schemas
# ============================================================================

class IntersectionHistoryPoint(BaseModel):
    """
    Single data point in time series.

    Represents one time interval (1-min, hourly, or daily depending on aggregation).
    """
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp for this interval"
    )
    safety_index: float = Field(
        ...,
        ge=0,
        le=100,
        description="Combined safety index (EB-adjusted if available)"
    )
    vru_index: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Vulnerable road user safety index"
    )
    vehicle_index: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Vehicle safety index"
    )
    traffic_volume: int = Field(
        ...,
        ge=0,
        description="Vehicle count for this interval"
    )
    hour_of_day: int = Field(
        ...,
        ge=0,
        le=23,
        description="Hour (0-23) for temporal pattern analysis"
    )
    day_of_week: int = Field(
        ...,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "timestamp": "2025-11-20T14:30:00Z",
                "safety_index": 44.6,
                "vru_index": 42.1,
                "vehicle_index": 48.9,
                "traffic_volume": 94,
                "hour_of_day": 14,
                "day_of_week": 2
            }]
        }
    }


class IntersectionHistory(BaseModel):
    """
    Complete time series data for one intersection.
    """
    intersection_id: str = Field(
        ...,
        description="Unique intersection identifier"
    )
    intersection_name: str = Field(
        ...,
        description="Human-readable intersection name"
    )
    data_points: List[IntersectionHistoryPoint] = Field(
        ...,
        description="Array of time series data points"
    )
    start_date: datetime = Field(
        ...,
        description="Start of queried time range"
    )
    end_date: datetime = Field(
        ...,
        description="End of queried time range"
    )
    total_points: int = Field(
        ...,
        ge=0,
        description="Number of data points returned"
    )
    aggregation: str = Field(
        ...,
        description="Time aggregation level applied (1min, 1hour, 1day, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "intersection_id": "0.0",
                "intersection_name": "Intersection 0.0",
                "start_date": "2025-11-13T00:00:00Z",
                "end_date": "2025-11-20T23:59:59Z",
                "total_points": 168,
                "aggregation": "1hour",
                "data_points": [
                    {
                        "timestamp": "2025-11-20T14:00:00Z",
                        "safety_index": 44.6,
                        "vru_index": 42.1,
                        "vehicle_index": 48.9,
                        "traffic_volume": 94,
                        "hour_of_day": 14,
                        "day_of_week": 2
                    }
                ]
            }]
        }
    }


class IntersectionAggregateStats(BaseModel):
    """
    Aggregated statistics over a time period.
    """
    intersection_id: str
    intersection_name: str
    period_start: datetime
    period_end: datetime

    # Safety Index Statistics
    avg_safety_index: float = Field(..., description="Mean safety index")
    min_safety_index: float = Field(..., description="Minimum observed SI")
    max_safety_index: float = Field(..., description="Maximum observed SI")
    std_safety_index: float = Field(..., description="Standard deviation of SI")

    # Traffic Statistics
    total_traffic_volume: int = Field(..., description="Sum of all vehicle counts")
    avg_traffic_volume: float = Field(..., description="Mean vehicle count per interval")

    # Risk Metrics
    high_risk_intervals: int = Field(
        ...,
        description="Count of intervals where SI > 75"
    )
    high_risk_percentage: float = Field(
        ...,
        description="Percentage of high-risk intervals"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "intersection_id": "0.0",
                "intersection_name": "Intersection 0.0",
                "period_start": "2025-11-13T00:00:00Z",
                "period_end": "2025-11-20T23:59:59Z",
                "avg_safety_index": 44.6,
                "min_safety_index": 18.2,
                "max_safety_index": 78.9,
                "std_safety_index": 12.3,
                "total_traffic_volume": 947280,
                "avg_traffic_volume": 94.0,
                "high_risk_intervals": 12,
                "high_risk_percentage": 7.1
            }]
        }
    }
