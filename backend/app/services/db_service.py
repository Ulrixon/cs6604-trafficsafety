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

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import db_session, execute_raw_sql
from app.schemas.intersection import IntersectionSafetyIndex

logger = logging.getLogger(__name__)


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

        sql = text("""
            INSERT INTO safety_indices_realtime (
                intersection_id, timestamp, combined_index, combined_index_eb,
                vru_index, vehicle_index, traffic_volume, vru_count,
                hour_of_day, day_of_week
            )
            VALUES (
                :intersection_id, :timestamp, :combined_index, :combined_index_eb,
                :vru_index, :vehicle_index, :traffic_volume, :vru_count,
                :hour_of_day, :day_of_week
            )
            ON CONFLICT (id, timestamp) DO UPDATE SET
                combined_index = EXCLUDED.combined_index,
                combined_index_eb = EXCLUDED.combined_index_eb,
                vru_index = EXCLUDED.vru_index,
                vehicle_index = EXCLUDED.vehicle_index,
                traffic_volume = EXCLUDED.traffic_volume,
                vru_count = EXCLUDED.vru_count
        """)

        with db_session() as session:
            session.execute(sql, {
                "intersection_id": record.intersection_id,
                "timestamp": record.timestamp,
                "combined_index": record.combined_index,
                "combined_index_eb": record.combined_index_eb,
                "vru_index": record.vru_index,
                "vehicle_index": record.vehicle_index,
                "traffic_volume": record.traffic_volume,
                "vru_count": record.vru_count,
                "hour_of_day": hour_of_day,
                "day_of_week": day_of_week
            })

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
    sql = text("""
        INSERT INTO safety_indices_realtime (
            intersection_id, timestamp, combined_index, combined_index_eb,
            vru_index, vehicle_index, traffic_volume, vru_count,
            hour_of_day, day_of_week
        )
        VALUES (
            :intersection_id, :timestamp, :combined_index, :combined_index_eb,
            :vru_index, :vehicle_index, :traffic_volume, :vru_count,
            :hour_of_day, :day_of_week
        )
        ON CONFLICT (id, timestamp) DO UPDATE SET
            combined_index = EXCLUDED.combined_index,
            combined_index_eb = EXCLUDED.combined_index_eb,
            vru_index = EXCLUDED.vru_index,
            vehicle_index = EXCLUDED.vehicle_index,
            traffic_volume = EXCLUDED.traffic_volume,
            vru_count = EXCLUDED.vru_count
    """)

    try:
        with db_session() as session:
            for record in records:
                try:
                    hour_of_day = record.hour_of_day if record.hour_of_day is not None else record.timestamp.hour
                    day_of_week = record.day_of_week if record.day_of_week is not None else record.timestamp.weekday()

                    session.execute(sql, {
                        "intersection_id": record.intersection_id,
                        "timestamp": record.timestamp,
                        "combined_index": record.combined_index,
                        "combined_index_eb": record.combined_index_eb,
                        "vru_index": record.vru_index,
                        "vehicle_index": record.vehicle_index,
                        "traffic_volume": record.traffic_volume,
                        "vru_count": record.vru_count,
                        "hour_of_day": hour_of_day,
                        "day_of_week": day_of_week
                    })
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
    sql = """
        SELECT
            intersection_id,
            intersection_name,
            latitude,
            longitude,
            timestamp,
            safety_index,
            safety_index_eb,
            vru_index,
            vehicle_index,
            traffic_volume,
            vru_count,
            risk_level
        FROM v_latest_safety_indices
        ORDER BY intersection_id
    """

    try:
        rows = execute_raw_sql(sql)
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
    sql = """
        SELECT
            intersection_id,
            intersection_name,
            latitude,
            longitude,
            timestamp,
            safety_index,
            safety_index_eb,
            vru_index,
            vehicle_index,
            traffic_volume,
            vru_count,
            risk_level
        FROM v_latest_safety_indices
        WHERE intersection_id = :id
    """

    try:
        rows = execute_raw_sql(sql, {"id": intersection_id})
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
    sql = """
        SELECT
            timestamp,
            combined_index AS safety_index,
            combined_index_eb AS safety_index_eb,
            vru_index,
            vehicle_index,
            traffic_volume,
            vru_count,
            hour_of_day,
            day_of_week
        FROM safety_indices_realtime
        WHERE intersection_id = :id
          AND timestamp >= :start_date
          AND timestamp <= :end_date
        ORDER BY timestamp ASC
    """

    try:
        rows = execute_raw_sql(sql, {
            "id": intersection_id,
            "start_date": start_date,
            "end_date": end_date
        })
        return rows
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
    sql = text("""
        INSERT INTO intersections (id, name, latitude, longitude, lane_count, revision, metadata)
        VALUES (:id, :name, :lat, :lon, :lane_count, :revision, :metadata::jsonb)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            lane_count = EXCLUDED.lane_count,
            revision = EXCLUDED.revision,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
    """)

    try:
        import json
        with db_session() as session:
            session.execute(sql, {
                "id": intersection_id,
                "name": name,
                "lat": latitude,
                "lon": longitude,
                "lane_count": lane_count,
                "revision": revision,
                "metadata": json.dumps(metadata) if metadata else None
            })

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
    sql = """
        SELECT * FROM get_intersections_within_radius(:lat, :lon, :radius)
    """

    try:
        rows = execute_raw_sql(sql, {
            "lat": center_lat,
            "lon": center_lon,
            "radius": radius_meters
        })
        return rows
    except Exception as e:
        logger.error(f"Spatial query failed: {e}")
        return []


def get_high_risk_intersections() -> List[IntersectionSafetyIndex]:
    """
    Get all intersections currently in high-risk state (safety index > 75).

    Returns:
        List of IntersectionSafetyIndex for high-risk intersections
    """
    sql = """
        SELECT
            intersection_id,
            intersection_name,
            latitude,
            longitude,
            timestamp,
            safety_index,
            traffic_volume
        FROM v_high_risk_intersections
        ORDER BY safety_index DESC
    """

    try:
        rows = execute_raw_sql(sql)
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
