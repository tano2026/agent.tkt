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

    # Backend server configuration (default 6969, overridable via PORT env var in main.py)
    backend_port: int = 6969
    backend_host: str = "0.0.0.0"

    # CORS
    frontend_origin: str = "http://localhost:4321"
    # Google Gemini API (for LLM chat)
    gemini_api_key: str = ""

    # OmniRoute / 9Router API (for LLM chat)
    omniroute_api_key: str = ""
    omniroute_base_url: str = "http://100.64.173.75:20128/v1"  # VPS OmniRoute

    # Redis (optional, for caching reference data)
    redis_url: str = ""

    # Logging
    log_level: str = "INFO"

    # LLM Gateway
    llm_api_key: str = ""
    llm_base_url: str = "http://100.64.173.75:20128/v1"
    llm_model: str = "oc/deepseek-v4-flash-free"
    openai_base_url: str = "http://100.64.173.75:20128/v1"
    openai_api_key: str = "sk-omn"
    openai_model: str = "oc/deepseek-v4-flash-free"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
