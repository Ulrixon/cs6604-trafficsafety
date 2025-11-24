"""
Pydantic schemas for analytics endpoints.
"""

from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional


class CorrelationMetrics(BaseModel):
    """Correlation analysis metrics"""
    total_crashes: int
    total_intervals: int
    crash_rate: float

    # Classification metrics
    threshold: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float

    # Correlation coefficients
    pearson_correlation: float
    spearman_correlation: float

    # Weather impact
    weather_crash_multiplier: Optional[float] = None
    rain_crash_rate: Optional[float] = None
    clear_crash_rate: Optional[float] = None

    # Date range
    start_date: date
    end_date: date


class CrashDataPoint(BaseModel):
    """Individual crash data point"""
    crash_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    severity: str
    nearest_intersection_id: Optional[int] = None
    nearest_intersection_name: Optional[str] = None
    distance_to_intersection: Optional[float] = None


class ScatterDataPoint(BaseModel):
    """Data point for scatter plot"""
    timestamp: datetime
    safety_index: float
    had_crash: bool
    crash_count: int
    intersection_id: Optional[int] = None


class TimeSeriesPoint(BaseModel):
    """Time series data with crash overlay"""
    timestamp: datetime
    safety_index: float
    vru_index: Optional[float] = None
    vehicle_index: Optional[float] = None
    weather_index: Optional[float] = None
    crash_count: int
    had_crash: bool


class WeatherImpact(BaseModel):
    """Weather impact analysis"""
    condition: str
    crash_count: int
    total_intervals: int
    crash_rate: float
    avg_safety_index: float
