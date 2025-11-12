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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Export a singleton for easy import
settings = Settings()
