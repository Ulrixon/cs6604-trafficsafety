from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """

    # Project metadata
    PROJECT_NAME: str = Field("Traffic Safety API", env="PROJECT_NAME")
    VERSION: str = Field("0.1.0", env="VERSION")
    DEBUG: bool = Field(True, env="DEBUG")

    # Base URL for the service
    BASE_URL: str = Field("http://localhost:8000", env="BASE_URL")

    # PostgreSQL + PostGIS database configuration
    DATABASE_URL: str = Field(
        "postgresql://trafficsafety:trafficsafety_dev@db:5432/trafficsafety",
        env="DATABASE_URL",
        description="PostgreSQL connection string"
    )
    DB_POOL_SIZE: int = Field(
        5,
        env="DB_POOL_SIZE",
        description="Number of database connections to maintain in pool"
    )
    DB_MAX_OVERFLOW: int = Field(
        10,
        env="DB_MAX_OVERFLOW",
        description="Maximum overflow connections beyond pool size"
    )

    # Trino database configuration
    TRINO_HOST: str = Field(
        "smart-cities-trino.pre-prod.cloud.vtti.vt.edu",
        env="TRINO_HOST"
    )
    TRINO_PORT: int = Field(443, env="TRINO_PORT")
    TRINO_HTTP_SCHEME: str = Field("https", env="TRINO_HTTP_SCHEME")
    TRINO_CATALOG: str = Field("smartcities_iceberg", env="TRINO_CATALOG")

    # Safety Index computation settings
    EMPIRICAL_BAYES_K: int = Field(
        50,
        env="EMPIRICAL_BAYES_K",
        description="Tuning parameter for Empirical Bayes adjustment"
    )
    DEFAULT_LOOKBACK_DAYS: int = Field(
        7,
        env="DEFAULT_LOOKBACK_DAYS",
        description="Default number of days to analyze"
    )

    # VCC API configuration
    VCC_BASE_URL: str = Field(
        "https://vcc.vtti.vt.edu",
        env="VCC_BASE_URL",
        description="Base URL for VCC API"
    )
    VCC_CLIENT_ID: str = Field(
        "",
        env="VCC_CLIENT_ID",
        description="OAuth2 client ID for VCC API"
    )
    VCC_CLIENT_SECRET: str = Field(
        "",
        env="VCC_CLIENT_SECRET",
        description="OAuth2 client secret for VCC API"
    )
    DATA_SOURCE: str = Field(
        "trino",
        env="DATA_SOURCE",
        description="Data source: 'trino', 'vcc', or 'both'"
    )
    PARQUET_STORAGE_PATH: str = Field(
        "backend/data/parquet",
        env="PARQUET_STORAGE_PATH",
        description="Path to Parquet storage directory"
    )
    REALTIME_ENABLED: bool = Field(
        False,
        env="REALTIME_ENABLED",
        description="Enable real-time WebSocket streaming"
    )

    # Feature flags for PostgreSQL migration
    USE_POSTGRESQL: bool = Field(
        False,
        env="USE_POSTGRESQL",
        description="Use PostgreSQL for queries (migration feature flag)"
    )
    FALLBACK_TO_PARQUET: bool = Field(
        True,
        env="FALLBACK_TO_PARQUET",
        description="Fallback to Parquet if PostgreSQL query fails"
    )
    ENABLE_DUAL_WRITE: bool = Field(
        False,
        env="ENABLE_DUAL_WRITE",
        description="Write to both PostgreSQL and Parquet during migration"
    )

    # GCP Cloud Storage configuration (for future use)
    GCS_BUCKET_NAME: str = Field(
        "",
        env="GCS_BUCKET_NAME",
        description="GCP bucket name for Parquet storage (e.g., trafficsafety-prod-parquet)"
    )
    GCS_PROJECT_ID: str = Field(
        "",
        env="GCS_PROJECT_ID",
        description="GCP project ID"
    )
    ENABLE_GCS_UPLOAD: bool = Field(
        False,
        env="ENABLE_GCS_UPLOAD",
        description="Enable uploading Parquet files to GCS"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Export a singleton for easy import
settings = Settings()
