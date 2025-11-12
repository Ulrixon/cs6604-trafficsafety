"""
Data collection service - Phase 2: Baseline & Exposure Metrics
Queries Trino for safety events, vehicle counts, and VRU counts
"""

from datetime import datetime
from typing import Tuple, Optional
import pandas as pd
from .trino_client import trino_client


# Severity weights from checkpoint document
SEVERITY_WEIGHTS = {
    'FATAL': 10,
    'INJURY': 3,
    'PDO': 1,  # Property Damage Only
    'DEFAULT': 1  # For events without explicit severity
}


def collect_baseline_events(
    intersection: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> pd.DataFrame:
    """
    Collect and weight safety events for baseline risk calculation.

    Args:
        intersection: Specific intersection or None for all
        start_date: Start of analysis period (datetime)
        end_date: End of analysis period

    Returns:
        DataFrame with weighted events by intersection, with columns:
        - intersection, event_type, event_id, event_time, time_at_site
        - hour_of_day, day_of_week, object1_class, object2_class
        - detection_area, severity_weight, is_vru_involved
    """
    # Build query with optional filters
    where_clauses = ["time_at_site > 0", "time_at_site < 9999999999999999"]

    if intersection:
        where_clauses.append(f"intersection = '{intersection}'")
    if start_date:
        where_clauses.append(
            f"time_at_site >= {int(start_date.timestamp() * 1000000)}")
    if end_date:
        where_clauses.append(
            f"time_at_site <= {int(end_date.timestamp() * 1000000)}")

    where_clause = " AND ".join(where_clauses)

    query = f"""
    SELECT
        intersection,
        event_type,
        event_id,
        from_unixtime(time_at_site / 1000000) as event_time,
        time_at_site,
        HOUR(from_unixtime(time_at_site / 1000000)) as hour_of_day,
        DAY_OF_WEEK(from_unixtime(time_at_site / 1000000)) as day_of_week,
        object1_class,
        object2_class,
        detection_area
    FROM alexandria."safety-event"
    WHERE {where_clause}
    ORDER BY intersection, time_at_site
    """

    try:
        df = trino_client.execute_query(query)

        if len(df) > 0:
            # Apply severity weighting
            def assign_severity_weight(row):
                event_type = str(row['event_type']).upper()

                # VRU-involved events get higher weight
                is_vru = ('PEDESTRIAN' in str(row['object1_class']).upper() or
                          'CYCLIST' in str(row['object1_class']).upper() or
                          'PEDESTRIAN' in str(row['object2_class']).upper() or
                          'CYCLIST' in str(row['object2_class']).upper())

                if 'FATAL' in event_type or 'DEATH' in event_type:
                    return SEVERITY_WEIGHTS['FATAL']
                elif 'INJURY' in event_type or is_vru:
                    return SEVERITY_WEIGHTS['INJURY']
                else:
                    return SEVERITY_WEIGHTS['PDO']

            df['severity_weight'] = df.apply(assign_severity_weight, axis=1)
            df['is_vru_involved'] = df.apply(
                lambda row: 1 if ('PEDESTRIAN' in str(row['object1_class']).upper() or
                                  'CYCLIST' in str(row['object1_class']).upper() or
                                  'PEDESTRIAN' in str(row['object2_class']).upper() or
                                  'CYCLIST' in str(row['object2_class']).upper()) else 0,
                axis=1
            )

        return df

    except Exception as e:
        print(f"Error collecting baseline events: {e}")
        return pd.DataFrame()


def collect_exposure_metrics(
    intersection: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Collect vehicle and VRU counts for exposure normalization.

    Args:
        intersection: Specific intersection or None for all
        start_date: Start of analysis period
        end_date: End of analysis period

    Returns:
        Tuple of (vehicle_counts DataFrame, vru_counts DataFrame)

        vehicle_counts columns:
        - intersection, time, publish_timestamp, approach, movement
        - vehicle_class, vehicle_count, hour_of_day, day_of_week

        vru_counts columns:
        - intersection, time, publish_timestamp, approach
        - vru_count, hour_of_day, day_of_week
    """
    # Build WHERE clause
    where_clauses = ["publish_timestamp > 0",
                     "publish_timestamp < 9999999999999999"]

    if intersection:
        where_clauses.append(f"intersection = '{intersection}'")
    if start_date:
        where_clauses.append(
            f"publish_timestamp >= {int(start_date.timestamp() * 1000000)}")
    if end_date:
        where_clauses.append(
            f"publish_timestamp <= {int(end_date.timestamp() * 1000000)}")

    where_clause = " AND ".join(where_clauses)

    # Collect vehicle counts
    vehicle_query = f"""
    SELECT
        intersection,
        from_unixtime(publish_timestamp / 1000000) as time,
        publish_timestamp,
        approach,
        movement,
        class as vehicle_class,
        count as vehicle_count,
        HOUR(from_unixtime(publish_timestamp / 1000000)) as hour_of_day,
        DAY_OF_WEEK(from_unixtime(publish_timestamp / 1000000)) as day_of_week
    FROM alexandria."vehicle-count"
    WHERE {where_clause}
    ORDER BY intersection, publish_timestamp
    """

    # Collect VRU counts
    vru_query = f"""
    SELECT
        intersection,
        from_unixtime(publish_timestamp / 1000000) as time,
        publish_timestamp,
        approach,
        count as vru_count,
        HOUR(from_unixtime(publish_timestamp / 1000000)) as hour_of_day,
        DAY_OF_WEEK(from_unixtime(publish_timestamp / 1000000)) as day_of_week
    FROM alexandria."vru-count"
    WHERE {where_clause}
    ORDER BY intersection, publish_timestamp
    """

    try:
        # Get vehicle counts
        vehicle_df = trino_client.execute_query(vehicle_query)

        # Get VRU counts
        vru_df = trino_client.execute_query(vru_query)

        return vehicle_df, vru_df

    except Exception as e:
        print(f"Error collecting exposure metrics: {e}")
        return pd.DataFrame(), pd.DataFrame()
