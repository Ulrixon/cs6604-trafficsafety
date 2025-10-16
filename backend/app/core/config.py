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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Export a singleton for easy import
settings = Settings()
