"""
Analytics service for crash correlation analysis.

Provides metrics and visualizations for validating safety index effectiveness.
"""

import logging
import os
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


def _connect_vtti_postgres():
    """Connect to VTTI PostgreSQL, preferring Cloud SQL Unix sockets on Cloud Run."""
    database = os.getenv("VTTI_DB_NAME", "vtsi")
    user = os.getenv("VTTI_DB_USER", "postgres")
    password = os.getenv("VTTI_DB_PASSWORD")
    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME") or os.getenv(
        "VTTI_DB_INSTANCE_CONNECTION_NAME"
    )
    host = os.getenv("VTTI_DB_HOST")

    if not host and instance_connection_name:
        host = f"/cloudsql/{instance_connection_name}"

    if not password:
        raise ValueError("VTTI_DB_PASSWORD is required for VTTI PostgreSQL access")

    connect_kwargs = {
        "host": host or "127.0.0.1",
        "database": database,
        "user": user,
        "password": password,
        "connect_timeout": 10,
    }

    if not connect_kwargs["host"].startswith("/cloudsql/"):
        connect_kwargs["port"] = int(os.getenv("VTTI_DB_PORT", "5432"))

    return psycopg2.connect(**connect_kwargs)


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

        conn = _connect_vtti_postgres()

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


def get_latest_safety_index_date_range(days: int = 30) -> tuple[date, date]:
    """Return a date window ending at the latest available safety-index row."""
    try:
        query = text("SELECT MAX(timestamp) FROM safety_indices_realtime")
        with db_session() as session:
            latest = session.execute(query).scalar()
        if latest is None:
            end_date = date.today()
        else:
            end_date = latest.date() if hasattr(latest, "date") else latest
        return end_date - timedelta(days=days), end_date
    except Exception as e:
        logger.warning(f"Failed to resolve latest safety-index date range: {e}")
        end_date = date.today()
        return end_date - timedelta(days=days), end_date


def _safe_divide(numerator: float, denominator: float) -> Optional[float]:
    return numerator / denominator if denominator else None


def _safe_correlation(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    if len(x) < 2 or len(y) < 2:
        return None
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    corr = float(np.corrcoef(x, y)[0, 1])
    return corr if np.isfinite(corr) else None


def _safe_spearman(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    if len(x) < 2 or len(y) < 2:
        return None
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    try:
        from scipy.stats import spearmanr
        corr, _ = spearmanr(x, y)
        return float(corr) if np.isfinite(corr) else None
    except ImportError:
        logger.warning("scipy is not installed; Spearman correlation unavailable")
        return None


def _empty_correlation_metrics(
    start_date: date,
    end_date: date,
    threshold: float,
    data_status: str,
    warnings: List[str],
) -> CorrelationMetrics:
    return CorrelationMetrics(
        total_crashes=0,
        total_intervals=0,
        crash_rate=0.0,
        threshold=threshold,
        true_positives=0,
        false_positives=0,
        true_negatives=0,
        false_negatives=0,
        precision=None,
        recall=None,
        f1_score=None,
        accuracy=0.0,
        pearson_correlation=None,
        spearman_correlation=None,
        data_status=data_status,
        warnings=warnings,
        index_interval_count=0,
        crash_event_count=0,
        overlap_interval_count=0,
        start_date=start_date,
        end_date=end_date,
    )


def _build_validation_frame(
    indices: List[Dict[str, Any]],
    crashes: List[Dict[str, Any]],
) -> pd.DataFrame:
    """Merge safety-index intervals with crash counts by time bin and intersection."""
    if not indices:
        return pd.DataFrame()

    df_indices = pd.DataFrame(indices)
    df_indices["time_bin"] = pd.to_datetime(df_indices["timestamp"]).dt.floor("15min")
    df_indices["intersection_id"] = pd.to_numeric(
        df_indices["intersection_id"], errors="coerce"
    ).astype("Int64")
    df_indices = (
        df_indices.groupby(["time_bin", "intersection_id"], as_index=False)
        .agg(
            timestamp=("timestamp", "min"),
            combined_index=("combined_index", "mean"),
            vru_index=("vru_index", "mean"),
            vehicle_index=("vehicle_index", "mean"),
        )
    )

    if crashes:
        df_crashes = pd.DataFrame(crashes)
        df_crashes["time_bin"] = pd.to_datetime(df_crashes["timestamp"]).dt.floor("15min")
        df_crashes["intersection_id"] = pd.to_numeric(
            df_crashes["nearest_intersection_id"], errors="coerce"
        ).astype("Int64")
        crash_counts = (
            df_crashes.dropna(subset=["intersection_id"])
            .groupby(["time_bin", "intersection_id"])
            .size()
            .reset_index(name="crash_count")
        )
    else:
        crash_counts = pd.DataFrame({
            "time_bin": pd.Series(dtype="datetime64[ns]"),
            "intersection_id": pd.Series(dtype="Int64"),
            "crash_count": pd.Series(dtype="int64"),
        })

    merged = df_indices.merge(crash_counts, on=["time_bin", "intersection_id"], how="left")
    merged["crash_count"] = merged["crash_count"].fillna(0).astype(int)
    merged["had_crash"] = merged["crash_count"] > 0
    return merged


def get_correlation_metrics(
    start_date: date,
    end_date: date,
    threshold: float = 60.0,
    proximity_radius: float = 500.0
) -> CorrelationMetrics:
    """
    Compute correlation metrics between safety indices and crashes.
    """
    warnings: List[str] = []
    try:
        crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius)
        indices = load_safety_indices(start_date, end_date)

        if not indices:
            return _empty_correlation_metrics(
                start_date=start_date,
                end_date=end_date,
                threshold=threshold,
                data_status="no_index_data",
                warnings=["No safety-index intervals were found for the selected date range."],
            )

        if not crashes:
            warnings.append("No crashes were found within the selected radius and date range; metrics are based on no-crash intervals.")

        valid_data = _build_validation_frame(indices, crashes)
        valid_data = valid_data[valid_data["combined_index"].notna()].copy()

        if valid_data.empty:
            return _empty_correlation_metrics(
                start_date=start_date,
                end_date=end_date,
                threshold=threshold,
                data_status="no_overlap",
                warnings=["Safety-index and crash data did not overlap after time/intersection matching."],
            )

        y_true = valid_data["had_crash"].astype(int).values
        y_pred = (valid_data["combined_index"] >= threshold).astype(int).values

        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        tn = int(np.sum((y_pred == 0) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))

        precision = _safe_divide(tp, tp + fp)
        recall = _safe_divide(tp, tp + fn)
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if precision is not None and recall is not None and (precision + recall) > 0
            else None
        )
        accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0.0
        pearson = _safe_correlation(valid_data["combined_index"].values, y_true)
        spearman = _safe_spearman(valid_data["combined_index"].values, y_true)

        if pearson is None:
            warnings.append("Pearson correlation is unavailable because safety scores or crash labels have insufficient variation.")
        if spearman is None:
            warnings.append("Spearman correlation is unavailable because safety scores or crash labels have insufficient variation or scipy is unavailable.")

        crash_event_count = int(valid_data["crash_count"].sum())

        return CorrelationMetrics(
            total_crashes=crash_event_count,
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
            data_status="ok" if crashes else "no_crash_data",
            warnings=warnings,
            index_interval_count=len(indices),
            crash_event_count=crash_event_count,
            overlap_interval_count=len(valid_data),
            start_date=start_date,
            end_date=end_date
        )

    except Exception as e:
        logger.error(f"Failed to compute correlation metrics: {e}")
        return _empty_correlation_metrics(
            start_date=start_date,
            end_date=end_date,
            threshold=threshold,
            data_status="error",
            warnings=[str(e)],
        )


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

    merged = _build_validation_frame(indices, crashes)

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

    if intersection_id is not None and crashes:
        crashes = [
            crash for crash in crashes
            if crash.get('nearest_intersection_id') == intersection_id
        ]

    merged = _build_validation_frame(indices, crashes)

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
