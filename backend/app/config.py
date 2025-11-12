"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Trino Configuration
    trino_host: str = "smart-cities-trino.pre-prod.cloud.vtti.vt.edu"
    trino_port: int = 443
    trino_catalog: str = "smartcities_iceberg"
    trino_http_scheme: str = "https"
    
    # PostgreSQL Configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "vtsi"
    postgres_user: str = "vtsi_user"
    postgres_password: str
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    
    # Redis (optional)
    redis_host: Optional[str] = None
    redis_port: int = 6379
    
    # Safety Index Configuration
    empirical_bayes_k: int = 50
    normalization_recalc_days: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
