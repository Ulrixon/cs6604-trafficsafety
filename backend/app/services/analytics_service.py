"""
Analytics service for crash correlation analysis.

Provides metrics and visualizations for validating safety index effectiveness.
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
from sqlalchemy import text
from math import radians, sin, cos, sqrt, atan2
import psycopg2

from ..db.connection import db_session
from ..schemas.analytics import (
    CorrelationMetrics,
    CrashDataPoint,
    ScatterDataPoint,
    TimeSeriesPoint,
    WeatherImpact
)

logger = logging.getLogger(__name__)

# GCP PostgreSQL Database Configuration (from environment/secrets)
import os
GCP_DB_HOST = os.getenv("VTTI_DB_HOST", "34.140.49.230")
GCP_DB_PORT = int(os.getenv("VTTI_DB_PORT", "5432"))
GCP_DB_NAME = os.getenv("VTTI_DB_NAME", "vtsi")
GCP_DB_USER = os.getenv("VTTI_DB_USER")
GCP_DB_PASSWORD = os.getenv("VTTI_DB_PASSWORD")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth radius in meters

    φ1 = radians(lat1)
    φ2 = radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)

    a = sin(Δφ/2)**2 + cos(φ1) * cos(φ2) * sin(Δλ/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def load_monitored_intersections() -> List[Dict[str, Any]]:
    """Load monitored intersection coordinates from local database."""
    try:
        query = text("""
            SELECT
                id as intersection_id,
                name,
                latitude,
                longitude
            FROM intersections
            ORDER BY id
        """)

        with db_session() as session:
            result = session.execute(query)
            rows = result.fetchall()

            return [
                {
                    'intersection_id': row[0],
                    'name': row[1],
                    'latitude': row[2],
                    'longitude': row[3]
                }
                for row in rows
            ]

    except Exception as e:
        logger.error(f"Failed to load intersections: {e}")
        return []


def load_crashes_from_gcp(
    start_date: date,
    end_date: date,
    proximity_radius: float = 500.0,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Load crash data from GCP PostgreSQL database with spatial filtering.
    """
    try:
        # Load intersections for spatial filtering
        intersections = load_monitored_intersections()
        if not intersections:
            logger.warning("No intersections found for spatial filtering")
            return []

        # Connect to GCP database
        conn = psycopg2.connect(
            host=GCP_DB_HOST,
            port=GCP_DB_PORT,
            database=GCP_DB_NAME,
            user=GCP_DB_USER,
            password=GCP_DB_PASSWORD,
            connect_timeout=10
        )

        query = f"""
            SELECT
                document_nbr as crash_id,
                crash_date,
                crash_time,
                latitude,
                longitude,
                severity,
                total_vehicles,
                total_injured,
                total_killed,
                weather,
                light_condition,
                road_surface,
                locality
            FROM vdot_crashes
            WHERE crash_date >= %(start_date)s
              AND crash_date <= %(end_date)s
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            ORDER BY crash_date DESC, crash_time DESC
            {f"LIMIT {limit}" if limit else ""}
        """

        df = pd.read_sql_query(query, conn, params={
            'start_date': start_date,
            'end_date': end_date
        })
        conn.close()

        if df.empty:
            return []

        # Parse crash timestamps
        def parse_crash_time(row):
            try:
                time_str = str(int(row['crash_time'])).zfill(4)
                hour = int(time_str[:2])
                minute = int(time_str[2:])
                return datetime.combine(row['crash_date'], datetime.min.time()).replace(hour=hour, minute=minute)
            except:
                return datetime.combine(row['crash_date'], datetime.min.time()).replace(hour=12, minute=0)

        df['timestamp'] = df.apply(parse_crash_time, axis=1)

        # Spatial filtering: Find nearest intersection for each crash
        filtered_crashes = []

        for _, crash in df.iterrows():
            crash_lat = crash['latitude']
            crash_lon = crash['longitude']

            if pd.isna(crash_lat) or pd.isna(crash_lon):
                continue

            # Find nearest intersection
            min_distance = float('inf')
            nearest_intersection = None

            for intersection in intersections:
                distance = haversine_distance(
                    crash_lat, crash_lon,
                    intersection['latitude'], intersection['longitude']
                )

                if distance < min_distance:
                    min_distance = distance
                    nearest_intersection = intersection

            # Keep crash if within proximity radius
            if min_distance <= proximity_radius:
                filtered_crashes.append({
                    'crash_id': str(crash['crash_id']),
                    'timestamp': crash['timestamp'],
                    'latitude': float(crash_lat),
                    'longitude': float(crash_lon),
                    'severity': crash['severity'],
                    'nearest_intersection_id': nearest_intersection['intersection_id'],
                    'nearest_intersection_name': nearest_intersection['name'],
                    'distance_to_intersection': float(min_distance),
                    'weather': crash['weather'],
                    'total_injured': int(crash['total_injured']) if pd.notna(crash['total_injured']) else 0,
                    'total_killed': int(crash['total_killed']) if pd.notna(crash['total_killed']) else 0
                })

        logger.info(f"Loaded {len(filtered_crashes)} crashes within {proximity_radius}m of intersections")
        return filtered_crashes

    except psycopg2.OperationalError as e:
        if "timeout" in str(e).lower():
            logger.error("GCP database connection timeout - IP may not be allowlisted")
        else:
            logger.error(f"Failed to connect to GCP database: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to load crash data: {e}")
        return []


def load_safety_indices(
    start_date: date,
    end_date: date,
    intersection_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Load safety indices from local PostgreSQL database."""
    try:
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query_text = """
            SELECT
                timestamp,
                intersection_id,
                combined_index,
                vru_index,
                vehicle_index,
                traffic_volume,
                vru_count
            FROM safety_indices_realtime
            WHERE timestamp >= :start_date
              AND timestamp <= :end_date
        """

        if intersection_id is not None:
            query_text += " AND intersection_id = :intersection_id"

        query_text += " ORDER BY timestamp"

        query = text(query_text)

        with db_session() as session:
            params = {'start_date': start_dt, 'end_date': end_dt}
            if intersection_id is not None:
                params['intersection_id'] = intersection_id

            result = session.execute(query, params)
            rows = result.fetchall()

            return [
                {
                    'timestamp': row[0],
                    'intersection_id': row[1],
                    'combined_index': float(row[2]) if row[2] is not None else 0.0,
                    'vru_index': float(row[3]) if row[3] is not None else 0.0,
                    'vehicle_index': float(row[4]) if row[4] is not None else 0.0,
                    'traffic_volume': int(row[5]) if row[5] is not None else 0,
                    'vru_count': int(row[6]) if row[6] is not None else 0
                }
                for row in rows
            ]

    except Exception as e:
        logger.error(f"Failed to load safety indices: {e}")
        return []


def get_correlation_metrics(
    start_date: date,
    end_date: date,
    threshold: float = 60.0,
    proximity_radius: float = 500.0
) -> CorrelationMetrics:
    """
    Compute correlation metrics between safety indices and crashes.
    """
    try:
        # Load crashes and safety indices
        crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius)
        indices = load_safety_indices(start_date, end_date)

        if not crashes or not indices:
            # Return empty metrics if no data
            return CorrelationMetrics(
                total_crashes=0,
                total_intervals=0,
                crash_rate=0.0,
                threshold=threshold,
                true_positives=0,
                false_positives=0,
                true_negatives=0,
                false_negatives=0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                accuracy=0.0,
                pearson_correlation=0.0,
                spearman_correlation=0.0,
                start_date=start_date,
                end_date=end_date
            )

        # Convert to DataFrames
        df_crashes = pd.DataFrame(crashes)
        df_indices = pd.DataFrame(indices)

        # Create time bins (15-minute intervals)
        df_crashes['time_bin'] = pd.to_datetime(df_crashes['timestamp']).dt.floor('15min')
        df_indices['time_bin'] = pd.to_datetime(df_indices['timestamp']).dt.floor('15min')

        # Count crashes per time bin
        crash_counts = df_crashes.groupby('time_bin').size().reset_index(name='crash_count')

        # Create full time series
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        all_bins = pd.DataFrame({
            'time_bin': pd.date_range(start=start_dt, end=end_dt, freq='15min')
        })

        # Merge everything
        merged = all_bins.merge(crash_counts, on='time_bin', how='left')
        merged['crash_count'] = merged['crash_count'].fillna(0)
        merged['had_crash'] = (merged['crash_count'] > 0).astype(int)

        # Merge with safety indices
        merged = merged.merge(
            df_indices[['time_bin', 'combined_index']],
            on='time_bin',
            how='left'
        )

        # Filter to rows with both crash data and index data
        valid_data = merged[merged['combined_index'].notna()].copy()

        if len(valid_data) == 0:
            raise ValueError("No overlapping data between crashes and safety indices")

        # Binary classification
        y_true = valid_data['had_crash'].values
        y_pred = (valid_data['combined_index'] >= threshold).astype(int).values

        # Confusion matrix
        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        tn = int(np.sum((y_pred == 0) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))

        # Metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0.0

        # Correlation
        pearson = float(np.corrcoef(valid_data['combined_index'], y_true)[0, 1])

        # Spearman correlation (requires scipy)
        try:
            from scipy.stats import spearmanr
            spearman, _ = spearmanr(valid_data['combined_index'], y_true)
            spearman = float(spearman)
        except ImportError:
            spearman = 0.0

        return CorrelationMetrics(
            total_crashes=int(y_true.sum()),
            total_intervals=len(valid_data),
            crash_rate=float(y_true.mean()),
            threshold=threshold,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            accuracy=accuracy,
            pearson_correlation=pearson,
            spearman_correlation=spearman,
            start_date=start_date,
            end_date=end_date
        )

    except Exception as e:
        logger.error(f"Failed to compute correlation metrics: {e}")
        raise


def get_crash_data_for_period(
    start_date: date,
    end_date: date,
    proximity_radius: float = 500.0,
    limit: int = 1000
) -> List[CrashDataPoint]:
    """Get crash data for visualization."""
    crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius, limit)
    return [CrashDataPoint(**crash) for crash in crashes]


def get_scatter_plot_data(
    start_date: date,
    end_date: date,
    proximity_radius: float = 500.0
) -> List[ScatterDataPoint]:
    """Get data for scatter plot: Safety Index vs Crash Occurrence."""
    crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius)
    indices = load_safety_indices(start_date, end_date)

    if not indices:
        return []

    df_indices = pd.DataFrame(indices)
    df_crashes = pd.DataFrame(crashes) if crashes else pd.DataFrame()

    # Create time bins
    df_indices['time_bin'] = pd.to_datetime(df_indices['timestamp']).dt.floor('15min')

    if not df_crashes.empty:
        df_crashes['time_bin'] = pd.to_datetime(df_crashes['timestamp']).dt.floor('15min')
        crash_counts = df_crashes.groupby('time_bin').size().reset_index(name='crash_count')
    else:
        crash_counts = pd.DataFrame(columns=['time_bin', 'crash_count'])

    # Merge
    merged = df_indices.merge(crash_counts, on='time_bin', how='left')
    merged['crash_count'] = merged['crash_count'].fillna(0)
    merged['had_crash'] = merged['crash_count'] > 0

    result = []
    for _, row in merged.iterrows():
        result.append(ScatterDataPoint(
            timestamp=row['timestamp'],
            safety_index=row['combined_index'],
            had_crash=bool(row['had_crash']),
            crash_count=int(row['crash_count']),
            intersection_id=row['intersection_id']
        ))

    return result


def get_time_series_with_crashes(
    start_date: date,
    end_date: date,
    intersection_id: Optional[int] = None,
    proximity_radius: float = 500.0
) -> List[TimeSeriesPoint]:
    """Get time series data with crash overlay."""
    crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius)
    indices = load_safety_indices(start_date, end_date, intersection_id)

    if not indices:
        return []

    df_indices = pd.DataFrame(indices)
    df_crashes = pd.DataFrame(crashes) if crashes else pd.DataFrame()

    # Filter crashes by intersection if specified
    if intersection_id is not None and not df_crashes.empty:
        df_crashes = df_crashes[df_crashes['nearest_intersection_id'] == intersection_id]

    # Create time bins
    df_indices['time_bin'] = pd.to_datetime(df_indices['timestamp']).dt.floor('15min')

    if not df_crashes.empty:
        df_crashes['time_bin'] = pd.to_datetime(df_crashes['timestamp']).dt.floor('15min')
        crash_counts = df_crashes.groupby('time_bin').size().reset_index(name='crash_count')
    else:
        crash_counts = pd.DataFrame(columns=['time_bin', 'crash_count'])

    # Merge
    merged = df_indices.merge(crash_counts, on='time_bin', how='left')
    merged['crash_count'] = merged['crash_count'].fillna(0)
    merged['had_crash'] = merged['crash_count'] > 0

    result = []
    for _, row in merged.iterrows():
        result.append(TimeSeriesPoint(
            timestamp=row['timestamp'],
            safety_index=row['combined_index'],
            vru_index=row['vru_index'],
            vehicle_index=row['vehicle_index'],
            weather_index=None,  # Would need to add this to schema
            crash_count=int(row['crash_count']),
            had_crash=bool(row['had_crash'])
        ))

    return result


def get_weather_impact_analysis(
    start_date: date,
    end_date: date,
    proximity_radius: float = 500.0
) -> List[WeatherImpact]:
    """Analyze crash rates by weather condition."""
    crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius)
    indices = load_safety_indices(start_date, end_date)

    if not crashes or not indices:
        return []

    df_crashes = pd.DataFrame(crashes)
    df_indices = pd.DataFrame(indices)

    # Create time bins
    df_crashes['time_bin'] = pd.to_datetime(df_crashes['timestamp']).dt.floor('15min')
    df_indices['time_bin'] = pd.to_datetime(df_indices['timestamp']).dt.floor('15min')

    # Group by weather condition
    weather_stats = {}

    for weather in df_crashes['weather'].dropna().unique():
        weather_crashes = df_crashes[df_crashes['weather'] == weather]
        crash_bins = set(weather_crashes['time_bin'])

        # Count intervals with this weather condition
        # (Simplified - would need actual weather data for each time bin)
        total_intervals = len(df_indices)
        crash_count = len(weather_crashes)
        crash_rate = crash_count / total_intervals if total_intervals > 0 else 0.0

        # Average safety index during these crashes
        crash_indices = df_indices[df_indices['time_bin'].isin(crash_bins)]
        avg_index = crash_indices['combined_index'].mean() if len(crash_indices) > 0 else 0.0

        weather_stats[weather] = WeatherImpact(
            condition=weather,
            crash_count=crash_count,
            total_intervals=total_intervals,
            crash_rate=crash_rate,
            avg_safety_index=avg_index
        )

    return list(weather_stats.values())
