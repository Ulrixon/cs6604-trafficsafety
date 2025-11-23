"""
Crash correlation analytics API endpoints.

Provides validation metrics and visualizations for safety index effectiveness.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

from ..schemas.analytics import (
    CorrelationMetrics,
    CrashDataPoint,
    ScatterDataPoint,
    TimeSeriesPoint,
    WeatherImpact
)
from ..services.analytics_service import (
    get_correlation_metrics,
    get_crash_data_for_period,
    get_scatter_plot_data,
    get_time_series_with_crashes,
    get_weather_impact_analysis
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics & Validation"]
)


@router.get("/correlation", response_model=CorrelationMetrics)
def get_correlation(
    start_date: Optional[date] = Query(
        None,
        description="Start date (YYYY-MM-DD). Defaults to 30 days ago."
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date (YYYY-MM-DD). Defaults to today."
    ),
    threshold: float = Query(
        60.0,
        ge=0,
        le=100,
        description="Safety index threshold for high risk classification"
    ),
    proximity_radius: float = Query(
        500.0,
        ge=100,
        le=10000,
        description="Maximum distance from intersection in meters (default: 500m)"
    )
) -> CorrelationMetrics:
    """
    Get crash correlation metrics for the specified period.

    Analyzes how well safety indices correlate with actual crash occurrences.
    Includes precision, recall, F1 score, and correlation coefficients.
    """
    try:
        # Default date range
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        metrics = get_correlation_metrics(
            start_date=start_date,
            end_date=end_date,
            threshold=threshold,
            proximity_radius=proximity_radius
        )

        return metrics

    except Exception as e:
        logger.error(f"Failed to get correlation metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crashes", response_model=List[CrashDataPoint])
def get_crashes(
    start_date: Optional[date] = Query(
        None,
        description="Start date (YYYY-MM-DD)"
    ),
    end_date: Optional[date] = Query(
        None,
        description="End date (YYYY-MM-DD)"
    ),
    proximity_radius: float = Query(
        500.0,
        description="Maximum distance from intersection in meters"
    ),
    limit: int = Query(
        1000,
        ge=1,
        le=10000,
        description="Maximum number of crashes to return"
    )
) -> List[CrashDataPoint]:
    """
    Get crash data near monitored intersections for the specified period.
    """
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        crashes = get_crash_data_for_period(
            start_date=start_date,
            end_date=end_date,
            proximity_radius=proximity_radius,
            limit=limit
        )

        return crashes

    except Exception as e:
        logger.error(f"Failed to get crash data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scatter-data", response_model=List[ScatterDataPoint])
def get_scatter_data(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    proximity_radius: float = Query(500.0)
) -> List[ScatterDataPoint]:
    """
    Get data for scatter plot: Safety Index vs Crash Occurrence.

    Returns time-binned data showing safety index values and whether crashes occurred.
    """
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        data = get_scatter_plot_data(
            start_date=start_date,
            end_date=end_date,
            proximity_radius=proximity_radius
        )

        return data

    except Exception as e:
        logger.error(f"Failed to get scatter plot data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/time-series", response_model=List[TimeSeriesPoint])
def get_time_series(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    intersection_id: Optional[int] = Query(
        None,
        description="Filter by specific intersection (optional)"
    ),
    proximity_radius: float = Query(500.0)
) -> List[TimeSeriesPoint]:
    """
    Get time series data with safety indices and crash overlay.

    Shows how safety indices change over time with crash occurrences marked.
    """
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        data = get_time_series_with_crashes(
            start_date=start_date,
            end_date=end_date,
            intersection_id=intersection_id,
            proximity_radius=proximity_radius
        )

        return data

    except Exception as e:
        logger.error(f"Failed to get time series data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weather-impact", response_model=List[WeatherImpact])
def get_weather_analysis(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    proximity_radius: float = Query(500.0)
) -> List[WeatherImpact]:
    """
    Get weather impact analysis showing crash rates by weather condition.
    """
    try:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        data = get_weather_impact_analysis(
            start_date=start_date,
            end_date=end_date,
            proximity_radius=proximity_radius
        )

        return data

    except Exception as e:
        logger.error(f"Failed to get weather impact analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
