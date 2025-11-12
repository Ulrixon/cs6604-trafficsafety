"""
Feature engineering service - Phase 3: BSM, PSM, and Event Aggregation
Processes vehicle and VRU behavior data into 15-minute interval features
"""

from datetime import datetime
from typing import Optional
import pandas as pd
import numpy as np
from .trino_client import trino_client
from .data_collection import collect_baseline_events


def calculate_heading_change_rate(heading_series):
    """
    Calculate rate of heading changes as a proxy for weaving behavior.
    Returns standard deviation of heading changes.
    """
    if len(heading_series) < 2:
        return 0.0

    headings = heading_series.dropna().values
    if len(headings) < 2:
        return 0.0

    # Calculate angular differences (handle circular nature of heading)
    diffs = []
    for i in range(1, len(headings)):
        diff = abs(headings[i] - headings[i-1])
        # Handle wrap-around (e.g., 359° to 1° is a 2° change, not 358°)
        if diff > 180:
            diff = 360 - diff
        diffs.append(diff)

    return np.std(diffs) if len(diffs) > 0 else 0.0


def collect_bsm_features(
    intersection: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> pd.DataFrame:
    """Extract vehicle behavior features from BSM data aggregated to 15-minute intervals."""
    where_clauses = ["publish_timestamp > 0", "publish_timestamp < 9999999999999999"]

    if intersection:
        where_clauses.append(f"intersection = '{intersection}'")
    if start_date:
        where_clauses.append(f"publish_timestamp >= {int(start_date.timestamp() * 1000000)}")
    if end_date:
        where_clauses.append(f"publish_timestamp <= {int(end_date.timestamp() * 1000000)}")

    where_clause = " AND ".join(where_clauses)

    query = f"""
    SELECT intersection, from_unixtime(publish_timestamp / 1000000) as time, publish_timestamp,
           id as vehicle_id, lat, lon, speed, heading, brake_applied_status, accel_lon, accel_lat
    FROM alexandria.bsm
    WHERE {where_clause}
    ORDER BY intersection, publish_timestamp
    """

    try:
        df = trino_client.execute_query(query)
        if len(df) == 0:
            print("⚠ No BSM data found")
            return pd.DataFrame()

        print(f"✓ Retrieved {len(df):,} BSM records")
        df['time'] = pd.to_datetime(df['time'], utc=True)
        df['time_15min'] = df['time'].dt.floor('15min')
        df['hard_braking'] = df['brake_applied_status'].apply(
            lambda x: 1 if pd.notna(x) and (int(x) & 0x04) else 0)

        grouped = df.groupby(['intersection', 'time_15min'])
        features = grouped.agg({
            'vehicle_id': 'nunique', 'speed': ['mean', 'std'], 'hard_braking': 'sum',
            'heading': lambda x: calculate_heading_change_rate(x),
            'accel_lon': 'std', 'accel_lat': 'std'
        }).reset_index()

        features.columns = ['intersection', 'time_15min', 'vehicle_count', 'avg_speed',
                            'speed_variance', 'hard_braking_count', 'heading_change_rate',
                            'accel_lon_variance', 'accel_lat_variance']
        features['hour_of_day'] = features['time_15min'].dt.hour
        features['day_of_week'] = features['time_15min'].dt.dayofweek
        print(f"✓ Generated {len(features)} 15-minute feature records")
        return features
    except Exception as e:
        print(f"Error collecting BSM features: {e}")
        return pd.DataFrame()


def collect_psm_features(intersection: Optional[str] = None, start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> pd.DataFrame:
    """Extract VRU features from PSM data."""
    where_clauses = ["publish_timestamp > 0", "publish_timestamp < 9999999999999999"]
    if intersection:
        where_clauses.append(f"intersection = '{intersection}'")
    if start_date:
        where_clauses.append(f"publish_timestamp >= {int(start_date.timestamp() * 1000000)}")
    if end_date:
        where_clauses.append(f"publish_timestamp <= {int(end_date.timestamp() * 1000000)}")

    query = f"""
    SELECT intersection, from_unixtime(publish_timestamp / 1000000) as time, id as vru_id,
           speed, basic_type, event_responder_type
    FROM alexandria.psm
    WHERE {" AND ".join(where_clauses)}
    """

    try:
        df = trino_client.execute_query(query)
        if len(df) == 0:
            print("⚠ No PSM data found (PSM data may be sparse)")
            return pd.DataFrame()

        df['time'] = pd.to_datetime(df['time'], utc=True)
        df['time_15min'] = df['time'].dt.floor('15min')
        df['is_pedestrian'] = df['basic_type'].apply(lambda x: 1 if x == 1 else 0)
        df['is_cyclist'] = df['basic_type'].apply(lambda x: 1 if x == 2 else 0)
        df['is_emergency_responder'] = df['event_responder_type'].apply(
            lambda x: 1 if pd.notna(x) and x > 0 else 0)

        features = df.groupby(['intersection', 'time_15min']).agg({
            'vru_id': 'nunique', 'speed': 'mean', 'is_pedestrian': 'sum',
            'is_cyclist': 'sum', 'is_emergency_responder': 'sum'
        }).reset_index()

        features.columns = ['intersection', 'time_15min', 'vru_count', 'avg_vru_speed',
                            'pedestrian_count', 'cyclist_count', 'emergency_responder_count']
        features['hour_of_day'] = features['time_15min'].dt.hour
        features['day_of_week'] = features['time_15min'].dt.dayofweek
        return features
    except Exception as e:
        print(f"Error collecting PSM features: {e}")
        return pd.DataFrame()


def aggregate_safety_events(intersection: Optional[str] = None, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> pd.DataFrame:
    """Aggregate safety events to 15-minute intervals with severity weighting."""
    events_df = collect_baseline_events(intersection, start_date, end_date)
    if len(events_df) == 0:
        print("⚠ No safety events to aggregate")
        return pd.DataFrame()

    events_df['event_time'] = pd.to_datetime(events_df['event_time'], utc=True)
    events_df['time_15min'] = events_df['event_time'].dt.floor('15min')

    aggregated = events_df.groupby(['intersection', 'time_15min']).agg({
        'event_id': 'count', 'is_vru_involved': 'sum', 'severity_weight': 'sum',
        'event_type': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0]
    }).reset_index()

    aggregated.columns = ['intersection', 'time_15min', 'total_event_count',
                          'vru_event_count', 'severity_weighted_score', 'dominant_event_type']
    aggregated['vehicle_event_count'] = aggregated['total_event_count'] - aggregated['vru_event_count']
    aggregated['I_VRU'] = aggregated['vru_event_count']
    aggregated['hour_of_day'] = aggregated['time_15min'].dt.hour
    aggregated['day_of_week'] = aggregated['time_15min'].dt.dayofweek
    return aggregated


def create_master_feature_table(bsm_features: pd.DataFrame, psm_features: pd.DataFrame,
                                 aggregated_events: pd.DataFrame, vehicle_counts: pd.DataFrame,
                                 vru_counts: pd.DataFrame) -> pd.DataFrame:
    """Join all feature sources into a unified feature table."""
    if len(bsm_features) == 0:
        print("⚠ ERROR: No BSM features available")
        return pd.DataFrame()

    master = bsm_features.copy()

    if len(vehicle_counts) > 0:
        vehicle_counts['time_15min'] = pd.to_datetime(vehicle_counts['time'], utc=True).dt.floor('15min')
        vehicle_agg = vehicle_counts.groupby(['intersection', 'time_15min'])['vehicle_count'].sum().reset_index()
        vehicle_agg.rename(columns={'vehicle_count': 'vehicle_volume'}, inplace=True)
        master = master.merge(vehicle_agg, on=['intersection', 'time_15min'], how='left')
    else:
        master['vehicle_volume'] = 0

    if len(vru_counts) > 0:
        vru_counts['time_15min'] = pd.to_datetime(vru_counts['time'], utc=True).dt.floor('15min')
        vru_agg = vru_counts.groupby(['intersection', 'time_15min'])['vru_count'].sum().reset_index()
        vru_agg.rename(columns={'vru_count': 'vru_volume'}, inplace=True)
        master = master.merge(vru_agg, on=['intersection', 'time_15min'], how='left')
    else:
        master['vru_volume'] = 0

    if len(psm_features) > 0:
        psm_subset = psm_features[['intersection', 'time_15min', 'vru_count',
                                    'avg_vru_speed', 'pedestrian_count', 'cyclist_count']].copy()
        psm_subset.rename(columns={'vru_count': 'psm_vru_count'}, inplace=True)
        master = master.merge(psm_subset, on=['intersection', 'time_15min'], how='left')
    else:
        master[['psm_vru_count', 'avg_vru_speed', 'pedestrian_count', 'cyclist_count']] = 0

    if len(aggregated_events) > 0:
        event_subset = aggregated_events[['intersection', 'time_15min', 'total_event_count',
                                           'vru_event_count', 'vehicle_event_count',
                                           'severity_weighted_score', 'I_VRU']].copy()
        master = master.merge(event_subset, on=['intersection', 'time_15min'], how='left')
    else:
        master[['total_event_count', 'vru_event_count', 'vehicle_event_count',
                'severity_weighted_score', 'I_VRU']] = 0

    # Fill NaN values
    count_cols = ['vehicle_volume', 'vru_volume', 'psm_vru_count', 'pedestrian_count',
                  'cyclist_count', 'total_event_count', 'vru_event_count',
                  'vehicle_event_count', 'severity_weighted_score', 'I_VRU']
    for col in count_cols:
        if col in master.columns:
            master[col] = master[col].fillna(0)

    if 'avg_vru_speed' in master.columns and master['avg_vru_speed'].notna().any():
        master['avg_vru_speed'] = master['avg_vru_speed'].fillna(master['avg_vru_speed'].median())

    print(f"✓ Master table: {len(master)} records, {master['intersection'].nunique()} intersections")
    return master
