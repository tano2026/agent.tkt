"""
Configuration module for the ABTrip backend.

Reads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # AGT API Configuration
    agt_api_host: str = "https://api.abtrip.vn"
    agt_private_key: str = ""
    agt_api_account: str = ""
    agt_api_password: str = ""

    # Backend server configuration
    backend_port: int = 8000
    backend_host: str = "0.0.0.0"

    # CORS
    frontend_origin: str = "http://localhost:4321"

    # Redis (optional, for caching reference data)
    redis_url: str = ""

    # Logging
    log_level: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
