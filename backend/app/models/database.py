"""
SQLAlchemy table metadata for the local Traffic Safety database.

The project mostly returns dataclass/Pydantic DTOs at the service boundary, but
the database layer should still build statements through SQLAlchemy instead of
hand-written SQL strings.
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base


metadata = MetaData()
Base = declarative_base(metadata=metadata)


class IntersectionModel(Base):
    __tablename__ = "intersections"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    lane_count = Column(Integer)
    revision = Column(Integer)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class SafetyIndexRealtimeModel(Base):
    __tablename__ = "safety_indices_realtime"

    id = Column(BigInteger, primary_key=True)
    intersection_id = Column(
        Integer,
        ForeignKey("intersections.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    combined_index = Column(Float, nullable=False)
    combined_index_eb = Column(Float)
    vru_index = Column(Float)
    vehicle_index = Column(Float)
    traffic_volume = Column(Integer, nullable=False)
    vru_count = Column(Integer, nullable=False)
    hour_of_day = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)


class WeatherObservationModel(Base):
    __tablename__ = "weather_observations"

    id = Column(BigInteger, primary_key=True)
    station_id = Column(String(10), nullable=False)
    observation_time = Column(DateTime(timezone=True), nullable=False)
    temperature_c = Column(Float)
    precipitation_mm = Column(Float)
    visibility_m = Column(Float)
    wind_speed_ms = Column(Float)
    wind_direction_deg = Column(Integer)
    weather_condition = Column(String(100))
    temperature_normalized = Column(Float)
    precipitation_normalized = Column(Float)
    visibility_normalized = Column(Float)
    wind_speed_normalized = Column(Float)
    raw_json = Column(JSONB)
    created_at = Column(DateTime(timezone=True))


LatestSafetyIndex = Table(
    "v_latest_safety_indices",
    metadata,
    Column("intersection_id", Integer, primary_key=True),
    Column("intersection_name", String),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime(timezone=True)),
    Column("safety_index", Float),
    Column("safety_index_eb", Float),
    Column("vru_index", Float),
    Column("vehicle_index", Float),
    Column("traffic_volume", Integer),
    Column("vru_count", Integer),
    Column("risk_level", String),
)


HighRiskIntersection = Table(
    "v_high_risk_intersections",
    metadata,
    Column("intersection_id", Integer, primary_key=True),
    Column("intersection_name", String),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("timestamp", DateTime(timezone=True)),
    Column("safety_index", Float),
    Column("traffic_volume", Integer),
)

