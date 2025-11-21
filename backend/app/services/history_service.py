"""
Service layer for historical intersection safety data.

This service provides time series queries and aggregation over
stored Parquet files with 1-minute interval safety indices.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional
import pandas as pd
import logging

from .parquet_storage import parquet_storage
from ..schemas.intersection import (
    IntersectionHistory,
    IntersectionHistoryPoint,
    IntersectionAggregateStats
)

logger = logging.getLogger(__name__)

# Aggregation constants
AGGREGATION_LEVELS = ["1min", "1hour", "1day", "1week", "1month"]
MAX_POINTS_THRESHOLD = 10000  # Warn if query would return >10k points


def get_intersection_history(
    intersection_id: str,
    start_date: date,
    end_date: date,
    aggregation: Optional[str] = None
) -> IntersectionHistory:
    """
    Retrieve historical time series data for an intersection.

    Args:
        intersection_id: Unique intersection identifier
        start_date: Start date for query (inclusive)
        end_date: End date for query (inclusive)
        aggregation: Time aggregation level or None for auto-select

    Returns:
        IntersectionHistory object with time series data

    Raises:
        ValueError: If no data found or invalid parameters
    """
    # Validate dates
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    # Apply smart defaults if aggregation not specified
    if aggregation is None:
        aggregation = _get_smart_default_aggregation(start_date, end_date)
    elif aggregation not in AGGREGATION_LEVELS:
        raise ValueError(f"Invalid aggregation. Must be one of {AGGREGATION_LEVELS}")

    logger.info(f"Querying history for {intersection_id}: {start_date} to {end_date}, agg={aggregation}")

    # Load raw data from Parquet storage
    try:
        # Convert intersection_id to match storage format (may be stored as float)
        # Try to convert string to float if it looks like a number
        storage_intersection_id = intersection_id
        try:
            storage_intersection_id = float(intersection_id)
        except (ValueError, TypeError):
            # Keep as string if not convertible
            pass

        indices_df = parquet_storage.load_indices(
            start_date=start_date,
            end_date=end_date,
            intersection_id=storage_intersection_id
        )
    except Exception as e:
        logger.error(f"Failed to load indices: {e}")
        raise ValueError(f"Unable to load data for intersection {intersection_id}")

    if len(indices_df) == 0:
        raise ValueError(
            f"No data found for intersection {intersection_id} "
            f"between {start_date} and {end_date}"
        )

    # Apply aggregation if needed
    if aggregation != "1min":
        indices_df = _aggregate_time_series(indices_df, aggregation)

    # Convert DataFrame to Pydantic models
    data_points = _dataframe_to_history_points(indices_df)

    # Get intersection name (with fallback)
    intersection_name = _get_intersection_name(intersection_id)

    return IntersectionHistory(
        intersection_id=intersection_id,
        intersection_name=intersection_name,
        data_points=data_points,
        start_date=datetime.combine(start_date, datetime.min.time()),
        end_date=datetime.combine(end_date, datetime.max.time()),
        total_points=len(data_points),
        aggregation=aggregation
    )


def get_aggregate_stats(
    intersection_id: str,
    start_date: date,
    end_date: date
) -> IntersectionAggregateStats:
    """
    Compute aggregated statistics over a time period.

    Args:
        intersection_id: Unique intersection identifier
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        IntersectionAggregateStats with computed metrics
    """
    # Load data
    # Convert intersection_id to match storage format (may be stored as float)
    storage_intersection_id = intersection_id
    try:
        storage_intersection_id = float(intersection_id)
    except (ValueError, TypeError):
        pass

    indices_df = parquet_storage.load_indices(
        start_date=start_date,
        end_date=end_date,
        intersection_id=storage_intersection_id
    )

    if len(indices_df) == 0:
        raise ValueError(f"No data found for intersection {intersection_id}")

    # Determine which safety index column to use (prefer EB-adjusted)
    safety_col = _get_safety_index_column(indices_df)

    # Compute statistics
    high_risk_count = int((indices_df[safety_col] > 75).sum())
    total_intervals = len(indices_df)

    # Handle std deviation for single data point (would be NaN)
    std_value = float(indices_df[safety_col].std())
    if pd.isna(std_value) or not pd.api.types.is_finite(std_value):
        std_value = 0.0

    return IntersectionAggregateStats(
        intersection_id=intersection_id,
        intersection_name=_get_intersection_name(intersection_id),
        period_start=indices_df['time_15min'].min(),
        period_end=indices_df['time_15min'].max(),
        avg_safety_index=float(indices_df[safety_col].mean()),
        min_safety_index=float(indices_df[safety_col].min()),
        max_safety_index=float(indices_df[safety_col].max()),
        std_safety_index=std_value,
        total_traffic_volume=int(indices_df['vehicle_count'].sum()),
        avg_traffic_volume=float(indices_df['vehicle_count'].mean()),
        high_risk_intervals=high_risk_count,
        high_risk_percentage=round((high_risk_count / total_intervals) * 100, 2) if total_intervals > 0 else 0.0
    )


def get_all_intersections_history(
    start_date: date,
    end_date: date,
    aggregation: Optional[str] = None
) -> List[IntersectionHistory]:
    """
    Get history for all intersections.

    Note: May return large dataset. Consider limiting date range.
    """
    # Load all indices (no intersection filter)
    indices_df = parquet_storage.load_indices(
        start_date=start_date,
        end_date=end_date,
        intersection_id=None
    )

    if len(indices_df) == 0:
        return []

    # Group by intersection
    histories = []
    for intersection_id in indices_df['intersection'].unique():
        try:
            history = get_intersection_history(
                str(intersection_id),
                start_date,
                end_date,
                aggregation
            )
            histories.append(history)
        except Exception as e:
            logger.warning(f"Failed to load history for {intersection_id}: {e}")
            continue

    return histories


# ============================================================================
# INTERNAL HELPER FUNCTIONS
# ============================================================================

def _get_smart_default_aggregation(start_date: date, end_date: date) -> str:
    """
    Determine appropriate aggregation level based on date range.

    Rules:
    - ≤1 day: 1-minute intervals
    - ≤7 days: Hourly aggregation
    - ≤30 days: Daily aggregation
    - ≤90 days: Weekly aggregation
    - >90 days: Monthly aggregation
    """
    days = (end_date - start_date).days + 1  # Inclusive

    if days <= 1:
        return "1min"
    elif days <= 7:
        return "1hour"
    elif days <= 30:
        return "1day"
    elif days <= 90:
        return "1week"
    else:
        return "1month"


def _aggregate_time_series(df: pd.DataFrame, aggregation: str) -> pd.DataFrame:
    """
    Resample time series to coarser granularity.

    Aggregation rules:
    - Safety indices: Mean
    - Traffic volume: Sum
    - Hour/day: First value in period
    """
    df = df.copy()
    df['time_15min'] = pd.to_datetime(df['time_15min'])
    df = df.set_index('time_15min')

    # Map aggregation string to pandas resample rule
    resample_rule = {
        "1min": "1min",
        "1hour": "1h",
        "1day": "1D",
        "1week": "1W",
        "1month": "1ME"  # Month end
    }.get(aggregation, "1h")

    # Define aggregation functions for columns that may exist
    agg_dict = {}

    # Safety indices (mean)
    for col in ['Combined_Index', 'Combined_Index_EB', 'VRU_Index', 'VRU_Index_EB',
                'Vehicle_Index', 'Vehicle_Index_EB']:
        if col in df.columns:
            agg_dict[col] = 'mean'

    # Traffic volume (sum)
    if 'vehicle_count' in df.columns:
        agg_dict['vehicle_count'] = 'sum'

    # Temporal metadata (first)
    for col in ['hour_of_day', 'day_of_week']:
        if col in df.columns:
            agg_dict[col] = 'first'

    # Resample - handle intersection column separately if it exists
    if 'intersection' in df.columns:
        resampled = df.groupby('intersection').resample(resample_rule).agg(
            agg_dict
        ).reset_index()
    else:
        resampled = df.resample(resample_rule).agg(agg_dict).reset_index()

    return resampled


def _dataframe_to_history_points(df: pd.DataFrame) -> List[IntersectionHistoryPoint]:
    """
    Convert DataFrame to list of IntersectionHistoryPoint objects.
    """
    points = []
    safety_col = _get_safety_index_column(df)

    for _, row in df.iterrows():
        # Get VRU and Vehicle indices (prefer EB-adjusted)
        vru_index = None
        if 'VRU_Index_EB' in df.columns and pd.notna(row.get('VRU_Index_EB')):
            vru_index = float(row['VRU_Index_EB'])
        elif 'VRU_Index' in df.columns and pd.notna(row.get('VRU_Index')):
            vru_index = float(row['VRU_Index'])

        vehicle_index = None
        if 'Vehicle_Index_EB' in df.columns and pd.notna(row.get('Vehicle_Index_EB')):
            vehicle_index = float(row['Vehicle_Index_EB'])
        elif 'Vehicle_Index' in df.columns and pd.notna(row.get('Vehicle_Index')):
            vehicle_index = float(row['Vehicle_Index'])

        point = IntersectionHistoryPoint(
            timestamp=pd.to_datetime(row['time_15min']),
            safety_index=float(row[safety_col]),
            vru_index=vru_index,
            vehicle_index=vehicle_index,
            traffic_volume=int(row['vehicle_count']),
            hour_of_day=int(row['hour_of_day']),
            day_of_week=int(row['day_of_week'])
        )
        points.append(point)

    return points


def _get_safety_index_column(df: pd.DataFrame) -> str:
    """
    Determine which safety index column to use.
    Prefer Empirical Bayes adjusted (_EB suffix) if available.
    """
    if 'Combined_Index_EB' in df.columns:
        return 'Combined_Index_EB'
    elif 'Combined_Index' in df.columns:
        return 'Combined_Index'
    else:
        raise ValueError("No safety index column found in data")


def _get_intersection_name(intersection_id: str) -> str:
    """
    Lookup human-readable intersection name.

    TODO: Implement proper lookup from MapData cache or database.
    For now, return formatted ID.
    """
    return f"Intersection {intersection_id}"
