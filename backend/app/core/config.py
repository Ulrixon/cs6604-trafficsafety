from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """

    # Project metadata
    PROJECT_NAME: str = "Traffic Safety API"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Base URL for the service
    BASE_URL: str = "http://localhost:8000"

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
    TRINO_HOST: str = "smart-cities-trino.pre-prod.cloud.vtti.vt.edu"
    TRINO_PORT: int = 443
    TRINO_HTTP_SCHEME: str = "https"
    TRINO_CATALOG: str = "smartcities_iceberg"

    # Safety Index computation settings
    EMPIRICAL_BAYES_K: int = Field(
        default=50, description="Tuning parameter for Empirical Bayes adjustment"
    )
    DEFAULT_LOOKBACK_DAYS: int = Field(
        default=7, description="Default number of days to analyze"
    )

    # PostgreSQL database configuration (for MCDM calculations)
    # For local development: use VTTI_DB_HOST and VTTI_DB_PORT
    # For Cloud Run: use VTTI_DB_INSTANCE_CONNECTION_NAME (Unix socket)
    VTTI_DB_HOST: str = "127.0.0.1"
    VTTI_DB_PORT: int = 9470
    VTTI_DB_NAME: str = "vtsi"
    VTTI_DB_USER: str = "postgres"
    VTTI_DB_PASSWORD: str = ""  # Must be set in .env file
    VTTI_DB_INSTANCE_CONNECTION_NAME: str = (
        ""  # Cloud SQL instance (e.g., project:region:instance)
    )

    # MCDM Safety Index settings
    MCDM_BIN_MINUTES: int = Field(
        default=15, description="Time bin size in minutes for MCDM calculation"
    )
    MCDM_LOOKBACK_HOURS: int = Field(
        default=24,
        description="Hours of historical data to use for MCDM CRITIC weights",
    )

    # VCC API configuration (optional, for other services)
    VCC_BASE_URL: str = "https://api.vcc.vtti.vt.edu"
    VCC_CLIENT_ID: str = ""
    VCC_CLIENT_SECRET: str = ""
    DATA_SOURCE: str = "vcc"  # Data source for VCC API
    REALTIME_ENABLED: bool = False  # Enable real-time streaming

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

    # Data Plugin System Configuration
    ENABLE_DATA_PLUGINS: bool = Field(
        False,
        env="ENABLE_DATA_PLUGINS",
        description="Enable plugin-based data source architecture"
    )

    # VCC Plugin Configuration
    USE_VCC_PLUGIN: bool = Field(
        False,
        env="USE_VCC_PLUGIN",
        description="Use VCC as a plugin (vs legacy VCC client)"
    )
    VCC_PLUGIN_WEIGHT: float = Field(
        0.70,
        env="VCC_PLUGIN_WEIGHT",
        description="Weight of VCC features in safety index (0.0-1.0)"
    )

    # Weather Plugin Configuration
    ENABLE_WEATHER_PLUGIN: bool = Field(
        False,
        env="ENABLE_WEATHER_PLUGIN",
        description="Enable NOAA/NWS weather data plugin"
    )
    WEATHER_PLUGIN_WEIGHT: float = Field(
        0.15,
        env="WEATHER_PLUGIN_WEIGHT",
        description="Weight of weather features in safety index (0.0-1.0)"
    )
    WEATHER_STATION_ID: str = Field(
        "KRIC",
        env="WEATHER_STATION_ID",
        description="NOAA weather station ID (default: KRIC - Richmond Intl Airport)"
    )
    WEATHER_API_BASE: str = Field(
        "https://api.weather.gov",
        env="WEATHER_API_BASE",
        description="NOAA API base URL"
    )
    WEATHER_API_TIMEOUT: int = Field(
        10,
        env="WEATHER_API_TIMEOUT",
        description="Weather API request timeout (seconds)"
    )
    WEATHER_RETRY_ATTEMPTS: int = Field(
        3,
        env="WEATHER_RETRY_ATTEMPTS",
        description="Number of retry attempts for weather API failures"
    )

    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        extra="ignore",  # Allow extra fields from .env
    )


# Export a singleton for easy import
settings = Settings()
