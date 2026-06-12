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
from sqlalchemy import func, select
from math import radians, sin, cos, sqrt, atan2
import psycopg2

from ..db.connection import db_session
from ..models.database import IntersectionModel, SafetyIndexRealtimeModel
from ..schemas.analytics import (
    CorrelationMetrics,
    CrashDataPoint,
    ScatterDataPoint,
    TimeSeriesPoint,
    WeatherImpact
)

logger = logging.getLogger(__name__)


DEMO_VALIDATION_INTERSECTIONS = [
    {
        "intersection_id": 101,
        "name": "birch_st-w_broad_st",
        "latitude": 38.893545860190606,
        "longitude": -77.18864276028934,
        "risk_bias": 20.0,
    },
    {
        "intersection_id": 105,
        "name": "e_broad_st-n_washington_st",
        "latitude": 38.88223323981943,
        "longitude": -77.17108624034019,
        "risk_bias": 17.0,
    },
    {
        "intersection_id": 107,
        "name": "glebe-potomac",
        "latitude": 38.83269441895485,
        "longitude": -77.04779677097797,
        "risk_bias": 8.0,
    },
    {
        "intersection_id": 111,
        "name": "n_maple_ave-w_broad_st",
        "latitude": 38.883190450004506,
        "longitude": -77.17257386986567,
        "risk_bias": 12.0,
    },
    {
        "intersection_id": 116,
        "name": "s_west_st-w_broad_st",
        "latitude": 38.89085382989225,
        "longitude": -77.18444008981216,
        "risk_bias": 15.0,
    },
    {
        "intersection_id": 118,
        "name": "w_annandale_rd-w_broad_st",
        "latitude": 38.88476273999137,
        "longitude": -77.1749917802795,
        "risk_bias": 10.0,
    },
]

DEMO_VALIDATION_WARNING = (
    "Demo validation data was generated deterministically because the persisted "
    "safety-index interval table has no rows for the public demo window."
)


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
        stmt = select(
            IntersectionModel.id.label("intersection_id"),
            IntersectionModel.name,
            IntersectionModel.latitude,
            IntersectionModel.longitude,
        ).order_by(IntersectionModel.id.asc())

        with db_session() as session:
            rows = session.execute(stmt).mappings().all()

            return [
                {
                    'intersection_id': row["intersection_id"],
                    'name': row["name"],
                    'latitude': row["latitude"],
                    'longitude': row["longitude"]
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

        query = """
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
        """
        params = {
            'start_date': start_date,
            'end_date': end_date,
        }
        if limit:
            query += " LIMIT %(limit)s"
            params["limit"] = limit

        df = pd.read_sql_query(query, conn, params=params)
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

        stmt = (
            select(
                SafetyIndexRealtimeModel.timestamp,
                SafetyIndexRealtimeModel.intersection_id,
                SafetyIndexRealtimeModel.combined_index,
                SafetyIndexRealtimeModel.vru_index,
                SafetyIndexRealtimeModel.vehicle_index,
                SafetyIndexRealtimeModel.traffic_volume,
                SafetyIndexRealtimeModel.vru_count,
            )
            .where(SafetyIndexRealtimeModel.timestamp >= start_dt)
            .where(SafetyIndexRealtimeModel.timestamp <= end_dt)
            .order_by(SafetyIndexRealtimeModel.timestamp.asc())
        )

        if intersection_id is not None:
            stmt = stmt.where(SafetyIndexRealtimeModel.intersection_id == intersection_id)

        with db_session() as session:
            rows = session.execute(stmt).mappings().all()

            return [
                {
                    'timestamp': row["timestamp"],
                    'intersection_id': row["intersection_id"],
                    'combined_index': float(row["combined_index"]) if row["combined_index"] is not None else 0.0,
                    'vru_index': float(row["vru_index"]) if row["vru_index"] is not None else 0.0,
                    'vehicle_index': float(row["vehicle_index"]) if row["vehicle_index"] is not None else 0.0,
                    'traffic_volume': int(row["traffic_volume"]) if row["traffic_volume"] is not None else 0,
                    'vru_count': int(row["vru_count"]) if row["vru_count"] is not None else 0
                }
                for row in rows
            ]

    except Exception as e:
        logger.error(f"Failed to load safety indices: {e}")
        return []


def get_latest_safety_index_date_range(days: int = 30) -> tuple[date, date]:
    """Return a date window ending at the latest available safety-index row."""
    try:
        stmt = select(func.max(SafetyIndexRealtimeModel.timestamp))
        with db_session() as session:
            latest = session.execute(stmt).scalar()
        if latest is None:
            end_date = date.today()
        else:
            end_date = latest.date() if hasattr(latest, "date") else latest
        return end_date - timedelta(days=days), end_date
    except Exception as e:
        logger.warning(f"Failed to resolve latest safety-index date range: {e}")
        end_date = date.today()
        return end_date - timedelta(days=days), end_date


def _generate_demo_validation_inputs(
    start_date: date,
    end_date: date,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate deterministic demo validation rows.

    The public demo can compute live/current scores on demand, but the analytics
    endpoints need persisted interval rows. When that table is empty, explicit
    demo mode uses these labeled rows so the validation UI can show the complete
    workflow without pretending the data came from production persistence.
    """
    if end_date < start_date:
        return [], []

    indices: List[Dict[str, Any]] = []
    crashes: List[Dict[str, Any]] = []
    days = (end_date - start_date).days + 1
    weather_cycle = ["Clear", "Clear", "Rain", "Cloudy", "Wet pavement"]

    for day_index in range(days):
        current_day = start_date + timedelta(days=day_index)
        day_wave = float(np.sin(day_index * 0.72) * 5.5)
        for hour in (8, 10, 12, 14, 16, 18):
            hour_pressure = {
                8: 3.0,
                10: -2.0,
                12: 5.0,
                14: 9.0,
                16: 16.0,
                18: 12.0,
            }[hour]
            timestamp = datetime.combine(
                current_day,
                datetime.min.time(),
            ).replace(hour=hour)

            for intersection_index, intersection in enumerate(
                DEMO_VALIDATION_INTERSECTIONS
            ):
                periodic = ((day_index + intersection_index * 2 + hour) % 5) * 2.1
                score = (
                    31.0
                    + intersection["risk_bias"]
                    + hour_pressure
                    + day_wave
                    + periodic
                )
                combined_index = float(max(0.0, min(100.0, score)))
                vru_index = float(max(0.0, min(100.0, combined_index * 0.55 + periodic)))
                vehicle_index = float(
                    max(0.0, min(100.0, combined_index * 0.72 + hour_pressure))
                )

                indices.append(
                    {
                        "timestamp": timestamp,
                        "intersection_id": intersection["intersection_id"],
                        "combined_index": combined_index,
                        "vru_index": vru_index,
                        "vehicle_index": vehicle_index,
                        "traffic_volume": int(
                            420
                            + intersection_index * 95
                            + max(hour_pressure, 0) * 34
                            + day_index * 7
                        ),
                        "vru_count": int(max(0, vru_index // 8)),
                    }
                )

                crash_signal = combined_index + ((day_index + hour) % 4) * 3
                has_crash = crash_signal >= 68 and (
                    (day_index + intersection_index + hour // 2) % 4 in {0, 1}
                )
                if has_crash:
                    crash_count = 2 if combined_index >= 82 else 1
                    for crash_number in range(crash_count):
                        offset = 0.00035 * (crash_number + 1)
                        crashes.append(
                            {
                                "crash_id": (
                                    f"DEMO-{current_day:%Y%m%d}-"
                                    f"{intersection['intersection_id']}-{hour}-"
                                    f"{crash_number + 1}"
                                ),
                                "timestamp": timestamp + timedelta(minutes=3 + crash_number),
                                "latitude": intersection["latitude"] + offset,
                                "longitude": intersection["longitude"] - offset,
                                "severity": "Injury" if combined_index >= 78 else "PDO",
                                "nearest_intersection_id": intersection[
                                    "intersection_id"
                                ],
                                "nearest_intersection_name": intersection["name"],
                                "distance_to_intersection": 55.0
                                + crash_number * 22.0,
                                "weather": weather_cycle[
                                    (day_index + intersection_index + hour) %
                                    len(weather_cycle)
                                ],
                                "total_injured": 1 if combined_index >= 78 else 0,
                                "total_killed": 0,
                            }
                        )

    return indices, crashes


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
    proximity_radius: float = 500.0,
    demo: bool = False,
) -> CorrelationMetrics:
    """
    Compute correlation metrics between safety indices and crashes.
    """
    warnings: List[str] = []
    try:
        if demo:
            indices, crashes = _generate_demo_validation_inputs(
                start_date,
                end_date,
            )
            warnings.append(DEMO_VALIDATION_WARNING)
        else:
            crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius)
            indices = load_safety_indices(start_date, end_date)

        if not indices:
            return _empty_correlation_metrics(
                start_date=start_date,
                end_date=end_date,
                threshold=threshold,
                data_status="no_index_data" if not demo else "demo_empty",
                warnings=warnings + [
                    "No safety-index intervals were found for the selected date range."
                ],
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
            data_status="demo" if demo else ("ok" if crashes else "no_crash_data"),
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
    limit: int = 1000,
    demo: bool = False,
) -> List[CrashDataPoint]:
    """Get crash data for visualization."""
    if demo:
        _, crashes = _generate_demo_validation_inputs(start_date, end_date)
        crashes = crashes[:limit]
    else:
        crashes = load_crashes_from_gcp(start_date, end_date, proximity_radius, limit)
    return [CrashDataPoint(**crash) for crash in crashes]


def get_scatter_plot_data(
    start_date: date,
    end_date: date,
    proximity_radius: float = 500.0,
    demo: bool = False,
) -> List[ScatterDataPoint]:
    """Get data for scatter plot: Safety Index vs Crash Occurrence."""
    if demo:
        indices, crashes = _generate_demo_validation_inputs(start_date, end_date)
    else:
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
    proximity_radius: float = 500.0,
    demo: bool = False,
) -> List[TimeSeriesPoint]:
    """Get time series data with crash overlay."""
    if demo:
        indices, crashes = _generate_demo_validation_inputs(start_date, end_date)
        if intersection_id is not None:
            indices = [
                row for row in indices
                if row.get("intersection_id") == intersection_id
            ]
    else:
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
    proximity_radius: float = 500.0,
    demo: bool = False,
) -> List[WeatherImpact]:
    """Analyze crash rates by weather condition."""
    if demo:
        indices, crashes = _generate_demo_validation_inputs(start_date, end_date)
    else:
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
