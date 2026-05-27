"""
Database service layer for PostgreSQL + PostGIS operations.

Provides high-level methods for:
- Inserting safety indices (realtime data)
- Querying latest safety indices
- Querying historical data
- Managing intersections
- Spatial queries
"""

import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.connection import db_session
from app.models.database import (
    HighRiskIntersection,
    IntersectionModel,
    LatestSafetyIndex,
    SafetyIndexRealtimeModel,
    WeatherObservationModel,
)
from app.schemas.intersection import IntersectionSafetyIndex

logger = logging.getLogger(__name__)


def _rows_as_dicts(result) -> List[Dict[str, Any]]:
    """Return SQLAlchemy RowMapping results as plain dictionaries."""
    return [dict(row) for row in result.mappings().all()]


@dataclass
class SafetyIndexRecord:
    """Safety index record for database insertion."""
    intersection_id: int
    timestamp: datetime
    combined_index: float
    combined_index_eb: Optional[float] = None
    vru_index: Optional[float] = None
    vehicle_index: Optional[float] = None
    traffic_volume: int = 0
    vru_count: int = 0
    hour_of_day: Optional[int] = None
    day_of_week: Optional[int] = None


def insert_safety_index(record: SafetyIndexRecord) -> bool:
    """
    Insert a single safety index record into the realtime table.

    Args:
        record: SafetyIndexRecord to insert

    Returns:
        True if successful, False otherwise

    Example:
        ```python
        record = SafetyIndexRecord(
            intersection_id=0,
            timestamp=datetime.now(),
            combined_index=72.5,
            combined_index_eb=68.3,
            traffic_volume=45
        )
        success = insert_safety_index(record)
        ```
    """
    try:
        # Extract hour and day of week from timestamp if not provided
        hour_of_day = record.hour_of_day if record.hour_of_day is not None else record.timestamp.hour
        day_of_week = record.day_of_week if record.day_of_week is not None else record.timestamp.weekday()

        values = {
            "intersection_id": record.intersection_id,
            "timestamp": record.timestamp,
            "combined_index": record.combined_index,
            "combined_index_eb": record.combined_index_eb,
            "vru_index": record.vru_index,
            "vehicle_index": record.vehicle_index,
            "traffic_volume": record.traffic_volume,
            "vru_count": record.vru_count,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
        }
        stmt = pg_insert(SafetyIndexRealtimeModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                SafetyIndexRealtimeModel.id,
                SafetyIndexRealtimeModel.timestamp,
            ],
            set_={
                "combined_index": stmt.excluded.combined_index,
                "combined_index_eb": stmt.excluded.combined_index_eb,
                "vru_index": stmt.excluded.vru_index,
                "vehicle_index": stmt.excluded.vehicle_index,
                "traffic_volume": stmt.excluded.traffic_volume,
                "vru_count": stmt.excluded.vru_count,
            },
        )

        with db_session() as session:
            session.execute(stmt)

        logger.debug(f"Inserted safety index for intersection {record.intersection_id} at {record.timestamp}")
        return True

    except Exception as e:
        logger.error(f"Failed to insert safety index: {e}")
        return False


def insert_safety_indices_batch(records: List[SafetyIndexRecord]) -> int:
    """
    Insert multiple safety index records in a batch.

    Args:
        records: List of SafetyIndexRecord to insert

    Returns:
        Number of successfully inserted records

    Example:
        ```python
        records = [
            SafetyIndexRecord(intersection_id=0, timestamp=dt1, combined_index=70.0, traffic_volume=40),
            SafetyIndexRecord(intersection_id=0, timestamp=dt2, combined_index=75.0, traffic_volume=50),
        ]
        count = insert_safety_indices_batch(records)
        ```
    """
    if not records:
        return 0

    success_count = 0
    try:
        with db_session() as session:
            for record in records:
                try:
                    hour_of_day = record.hour_of_day if record.hour_of_day is not None else record.timestamp.hour
                    day_of_week = record.day_of_week if record.day_of_week is not None else record.timestamp.weekday()

                    values = {
                        "intersection_id": record.intersection_id,
                        "timestamp": record.timestamp,
                        "combined_index": record.combined_index,
                        "combined_index_eb": record.combined_index_eb,
                        "vru_index": record.vru_index,
                        "vehicle_index": record.vehicle_index,
                        "traffic_volume": record.traffic_volume,
                        "vru_count": record.vru_count,
                        "hour_of_day": hour_of_day,
                        "day_of_week": day_of_week,
                    }
                    stmt = pg_insert(SafetyIndexRealtimeModel).values(**values)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[
                            SafetyIndexRealtimeModel.id,
                            SafetyIndexRealtimeModel.timestamp,
                        ],
                        set_={
                            "combined_index": stmt.excluded.combined_index,
                            "combined_index_eb": stmt.excluded.combined_index_eb,
                            "vru_index": stmt.excluded.vru_index,
                            "vehicle_index": stmt.excluded.vehicle_index,
                            "traffic_volume": stmt.excluded.traffic_volume,
                            "vru_count": stmt.excluded.vru_count,
                        },
                    )
                    session.execute(stmt)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to insert record for intersection {record.intersection_id}: {e}")
                    continue

        logger.info(f"Batch inserted {success_count}/{len(records)} safety indices")
        return success_count

    except Exception as e:
        logger.error(f"Batch insert failed: {e}")
        return success_count


def get_latest_safety_indices() -> List[IntersectionSafetyIndex]:
    """
    Get the latest safety index for all intersections.

    Returns:
        List of IntersectionSafetyIndex objects

    Example:
        ```python
        indices = get_latest_safety_indices()
        for idx in indices:
            print(f"{idx.intersection_name}: {idx.safety_index}")
        ```
    """
    try:
        stmt = select(LatestSafetyIndex).order_by(LatestSafetyIndex.c.intersection_id)
        with db_session() as session:
            rows = _rows_as_dicts(session.execute(stmt))
        return [
            IntersectionSafetyIndex(
                intersection_id=str(row["intersection_id"]),
                intersection_name=row["intersection_name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                safety_index=row["safety_index"] or 0.0,
                traffic_volume=row["traffic_volume"] or 0
            )
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get latest safety indices: {e}")
        return []


def get_safety_index_by_intersection(intersection_id: int) -> Optional[IntersectionSafetyIndex]:
    """
    Get the latest safety index for a specific intersection.

    Args:
        intersection_id: Intersection ID

    Returns:
        IntersectionSafetyIndex or None if not found
    """
    try:
        stmt = select(LatestSafetyIndex).where(
            LatestSafetyIndex.c.intersection_id == intersection_id
        )
        with db_session() as session:
            rows = _rows_as_dicts(session.execute(stmt))
        if not rows:
            return None

        row = rows[0]
        return IntersectionSafetyIndex(
            intersection_id=str(row["intersection_id"]),
            intersection_name=row["intersection_name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            safety_index=row["safety_index"] or 0.0,
            traffic_volume=row["traffic_volume"] or 0
        )
    except Exception as e:
        logger.error(f"Failed to get safety index for intersection {intersection_id}: {e}")
        return None


def get_safety_indices_history(
    intersection_id: int,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """
    Get historical safety indices for an intersection.

    Args:
        intersection_id: Intersection ID
        start_date: Start datetime
        end_date: End datetime

    Returns:
        List of dictionaries with historical data
    """
    try:
        stmt = (
            select(
                SafetyIndexRealtimeModel.timestamp,
                SafetyIndexRealtimeModel.combined_index.label("safety_index"),
                SafetyIndexRealtimeModel.combined_index_eb.label("safety_index_eb"),
                SafetyIndexRealtimeModel.vru_index,
                SafetyIndexRealtimeModel.vehicle_index,
                SafetyIndexRealtimeModel.traffic_volume,
                SafetyIndexRealtimeModel.vru_count,
                SafetyIndexRealtimeModel.hour_of_day,
                SafetyIndexRealtimeModel.day_of_week,
            )
            .where(SafetyIndexRealtimeModel.intersection_id == intersection_id)
            .where(SafetyIndexRealtimeModel.timestamp >= start_date)
            .where(SafetyIndexRealtimeModel.timestamp <= end_date)
            .order_by(SafetyIndexRealtimeModel.timestamp.asc())
        )
        with db_session() as session:
            return _rows_as_dicts(session.execute(stmt))
    except Exception as e:
        logger.error(f"Failed to get history for intersection {intersection_id}: {e}")
        return []


def upsert_intersection(
    intersection_id: int,
    name: str,
    latitude: float,
    longitude: float,
    lane_count: Optional[int] = None,
    revision: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> bool:
    """
    Insert or update an intersection.

    Args:
        intersection_id: Unique intersection ID
        name: Intersection name
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        lane_count: Number of lanes (optional)
        revision: MapData revision number (optional)
        metadata: Additional metadata as JSON (optional)

    Returns:
        True if successful, False otherwise
    """
    try:
        values = {
            "id": intersection_id,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "lane_count": lane_count,
            "revision": revision,
            "metadata_json": metadata,
        }
        stmt = pg_insert(IntersectionModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[IntersectionModel.id],
            set_={
                "name": stmt.excluded.name,
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "lane_count": stmt.excluded.lane_count,
                "revision": stmt.excluded.revision,
                "metadata": stmt.excluded["metadata"],
                "updated_at": func.now(),
            },
        )
        with db_session() as session:
            session.execute(stmt)

        logger.info(f"Upserted intersection {intersection_id}: {name}")
        return True

    except Exception as e:
        logger.error(f"Failed to upsert intersection {intersection_id}: {e}")
        return False


def get_intersections_within_radius(
    center_lat: float,
    center_lon: float,
    radius_meters: float
) -> List[Dict[str, Any]]:
    """
    Get intersections within a radius of a point using PostGIS spatial functions.

    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        radius_meters: Search radius in meters

    Returns:
        List of intersections with distance information
    """
    try:
        stmt = select(
            func.get_intersections_within_radius(
                center_lat,
                center_lon,
                radius_meters,
            ).table_valued(
                "id",
                "name",
                "latitude",
                "longitude",
                "distance_meters",
            )
        )
        with db_session() as session:
            return _rows_as_dicts(session.execute(stmt))
    except Exception as e:
        logger.error(f"Spatial query failed: {e}")
        return []


def get_high_risk_intersections() -> List[IntersectionSafetyIndex]:
    """
    Get all intersections currently in high-risk state (safety index > 75).

    Returns:
        List of IntersectionSafetyIndex for high-risk intersections
    """
    try:
        stmt = select(HighRiskIntersection).order_by(
            HighRiskIntersection.c.safety_index.desc()
        )
        with db_session() as session:
            rows = _rows_as_dicts(session.execute(stmt))
        return [
            IntersectionSafetyIndex(
                intersection_id=str(row["intersection_id"]),
                intersection_name=row["intersection_name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                safety_index=row["safety_index"],
                traffic_volume=row["traffic_volume"]
            )
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Failed to get high-risk intersections: {e}")
        return []


@dataclass
class WeatherObservationRecord:
    """Weather observation record for database insertion."""
    station_id: str
    observation_time: datetime
    temperature_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    visibility_m: Optional[float] = None
    wind_speed_ms: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    weather_condition: Optional[str] = None
    temperature_normalized: Optional[float] = None
    precipitation_normalized: Optional[float] = None
    visibility_normalized: Optional[float] = None
    wind_speed_normalized: Optional[float] = None


def insert_weather_observation(record: WeatherObservationRecord) -> bool:
    """
    Insert a single weather observation record into the database.

    Args:
        record: WeatherObservationRecord to insert

    Returns:
        True if successful, False otherwise

    Example:
        ```python
        record = WeatherObservationRecord(
            station_id='KRIC',
            observation_time=datetime.now(),
            temperature_c=18.3,
            precipitation_mm=2.5,
            visibility_m=8000,
            wind_speed_ms=5.2,
            temperature_normalized=0.1,
            precipitation_normalized=0.125
        )
        success = insert_weather_observation(record)
        ```
    """
    try:
        values = {
            "station_id": record.station_id,
            "observation_time": record.observation_time,
            "temperature_c": record.temperature_c,
            "precipitation_mm": record.precipitation_mm,
            "visibility_m": record.visibility_m,
            "wind_speed_ms": record.wind_speed_ms,
            "wind_direction_deg": record.wind_direction_deg,
            "weather_condition": record.weather_condition,
            "temperature_normalized": record.temperature_normalized,
            "precipitation_normalized": record.precipitation_normalized,
            "visibility_normalized": record.visibility_normalized,
            "wind_speed_normalized": record.wind_speed_normalized,
        }
        stmt = pg_insert(WeatherObservationModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                WeatherObservationModel.station_id,
                WeatherObservationModel.observation_time,
            ],
            set_={
                "temperature_c": stmt.excluded.temperature_c,
                "precipitation_mm": stmt.excluded.precipitation_mm,
                "visibility_m": stmt.excluded.visibility_m,
                "wind_speed_ms": stmt.excluded.wind_speed_ms,
                "wind_direction_deg": stmt.excluded.wind_direction_deg,
                "weather_condition": stmt.excluded.weather_condition,
                "temperature_normalized": stmt.excluded.temperature_normalized,
                "precipitation_normalized": stmt.excluded.precipitation_normalized,
                "visibility_normalized": stmt.excluded.visibility_normalized,
                "wind_speed_normalized": stmt.excluded.wind_speed_normalized,
            },
        )

        with db_session() as session:
            session.execute(stmt)

        logger.debug(f"Inserted weather observation for station {record.station_id} at {record.observation_time}")
        return True

    except Exception as e:
        logger.error(f"Failed to insert weather observation: {e}")
        return False


def insert_weather_observations_batch(records: List[WeatherObservationRecord]) -> int:
    """
    Insert multiple weather observation records in a batch.

    Args:
        records: List of WeatherObservationRecord to insert

    Returns:
        Number of successfully inserted records

    Example:
        ```python
        records = [
            WeatherObservationRecord(
                station_id='KRIC',
                observation_time=dt1,
                temperature_c=18.3,
                temperature_normalized=0.1
            ),
            WeatherObservationRecord(
                station_id='KRIC',
                observation_time=dt2,
                temperature_c=20.0,
                temperature_normalized=0.0
            ),
        ]
        count = insert_weather_observations_batch(records)
        ```
    """
    if not records:
        return 0

    success_count = 0
    try:
        with db_session() as session:
            for record in records:
                try:
                    values = {
                        "station_id": record.station_id,
                        "observation_time": record.observation_time,
                        "temperature_c": record.temperature_c,
                        "precipitation_mm": record.precipitation_mm,
                        "visibility_m": record.visibility_m,
                        "wind_speed_ms": record.wind_speed_ms,
                        "wind_direction_deg": record.wind_direction_deg,
                        "weather_condition": record.weather_condition,
                        "temperature_normalized": record.temperature_normalized,
                        "precipitation_normalized": record.precipitation_normalized,
                        "visibility_normalized": record.visibility_normalized,
                        "wind_speed_normalized": record.wind_speed_normalized,
                    }
                    stmt = pg_insert(WeatherObservationModel).values(**values)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[
                            WeatherObservationModel.station_id,
                            WeatherObservationModel.observation_time,
                        ],
                        set_={
                            "temperature_c": stmt.excluded.temperature_c,
                            "precipitation_mm": stmt.excluded.precipitation_mm,
                            "visibility_m": stmt.excluded.visibility_m,
                            "wind_speed_ms": stmt.excluded.wind_speed_ms,
                            "wind_direction_deg": stmt.excluded.wind_direction_deg,
                            "weather_condition": stmt.excluded.weather_condition,
                            "temperature_normalized": stmt.excluded.temperature_normalized,
                            "precipitation_normalized": stmt.excluded.precipitation_normalized,
                            "visibility_normalized": stmt.excluded.visibility_normalized,
                            "wind_speed_normalized": stmt.excluded.wind_speed_normalized,
                        },
                    )
                    session.execute(stmt)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to insert weather record for station {record.station_id}: {e}")
                    continue

        logger.info(f"Batch inserted {success_count}/{len(records)} weather observations")
        return success_count

    except Exception as e:
        logger.error(f"Weather batch insert failed: {e}")
        return success_count


def get_weather_observations(
    station_id: str,
    start_time: datetime,
    end_time: datetime
) -> List[Dict[str, Any]]:
    """
    Get weather observations for a station within a time range.

    Args:
        station_id: Weather station ID (e.g., 'KRIC')
        start_time: Start datetime
        end_time: End datetime

    Returns:
        List of dictionaries with weather observation data

    Example:
        ```python
        observations = get_weather_observations(
            'KRIC',
            datetime(2024, 11, 21, 0, 0),
            datetime(2024, 11, 21, 23, 59)
        )
        ```
    """
    try:
        stmt = (
            select(
                WeatherObservationModel.station_id,
                WeatherObservationModel.observation_time,
                WeatherObservationModel.temperature_c,
                WeatherObservationModel.precipitation_mm,
                WeatherObservationModel.visibility_m,
                WeatherObservationModel.wind_speed_ms,
                WeatherObservationModel.wind_direction_deg,
                WeatherObservationModel.weather_condition,
                WeatherObservationModel.temperature_normalized,
                WeatherObservationModel.precipitation_normalized,
                WeatherObservationModel.visibility_normalized,
                WeatherObservationModel.wind_speed_normalized,
            )
            .where(WeatherObservationModel.station_id == station_id)
            .where(WeatherObservationModel.observation_time >= start_time)
            .where(WeatherObservationModel.observation_time <= end_time)
            .order_by(WeatherObservationModel.observation_time.asc())
        )
        with db_session() as session:
            return _rows_as_dicts(session.execute(stmt))
    except Exception as e:
        logger.error(f"Failed to get weather observations for station {station_id}: {e}")
        return []
