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
    VTTI_DB_HOST: str = "127.0.0.1"
    VTTI_DB_PORT: int = 9470
    VTTI_DB_NAME: str = "vtsi"
    VTTI_DB_USER: str = "postgres"
    VTTI_DB_PASSWORD: str = ""  # Must be set in .env file

    # MCDM Safety Index settings
    MCDM_BIN_MINUTES: int = Field(
        default=15, description="Time bin size in minutes for MCDM calculation"
    )
    MCDM_LOOKBACK_HOURS: int = Field(
        default=24,
        description="Hours of historical data to use for MCDM CRITIC weights",
    )

    # VCC credentials (optional, for other services)
    VCC_CLIENT_ID: str = ""
    VCC_CLIENT_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
        extra="ignore",  # Allow extra fields from .env
    )


# Export a singleton for easy import
settings = Settings()
