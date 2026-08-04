"""
Application configuration.

All environment-specific values are sourced from environment variables
(optionally loaded from a local ``.env`` file via ``python-dotenv``/pydantic).
No module outside of this file should read ``os.environ`` directly; every
other module imports the single ``settings`` singleton defined here.
"""
import os
from typing import List

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Strongly-typed application settings, populated from environment/.env."""

    # --- General ---
    APP_NAME: str = "Reservation Management System"
    APP_ENV: str = Field(default="development")
    APP_DEBUG: bool = Field(default=False)
    API_V1_PREFIX: str = "/api/v1"

    # --- Security / JWT ---
    SECRET_KEY: str = Field(default="INSECURE-DEV-KEY-CHANGE-ME")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    BCRYPT_ROUNDS: int = Field(default=12)

    # --- Database ---
    DATABASE_URL: str = Field(default="sqlite:///./reservation_system.db")
    DATABASE_ECHO: bool = Field(default=False)

    # --- Logging ---
    LOG_LEVEL: str = Field(default="INFO")
    LOG_DIR: str = Field(default="./logs")
    LOG_FILE_MAX_BYTES: int = Field(default=10 * 1024 * 1024)
    LOG_FILE_BACKUP_COUNT: int = Field(default=10)

    # --- Excel export/import ---
    EXPORT_DIR: str = Field(default="./logs/exports")
    MAX_EXPORT_ROWS: int = Field(default=50000)

    # --- CORS ---
    CORS_ALLOWED_ORIGINS: str = Field(default="http://localhost:8000")

    # --- Business rules ---
    RESERVATION_MIN_LEAD_MINUTES: int = Field(default=0)
    SWAP_REQUIRE_SAME_PRODUCT: bool = Field(default=True)

    # --- Seed admin (Owner) account, used only by scripts/create_admin.py ---
    SEED_ADMIN_USERNAME: str = Field(default="admin")
    SEED_ADMIN_EMAIL: str = Field(default="admin@example.com")
    SEED_ADMIN_PASSWORD: str = Field(default="ChangeMe123!")
    SEED_ADMIN_FULL_NAME: str = Field(default="System Owner")

    # --- Background jobs ---
    ENABLE_SCHEDULER: bool = Field(default=True)
    RESERVATION_SWEEP_INTERVAL_MINUTES: int = Field(default=5)
    ANNOUNCEMENT_SWEEP_INTERVAL_MINUTES: int = Field(default=15)

    @validator("APP_ENV")
    def _validate_app_env(cls, value: str) -> str:  # noqa: N805
        """Restrict APP_ENV to a known, finite set of environments."""
        allowed = {"development", "staging", "production", "test"}
        if value not in allowed:
            raise ValueError("APP_ENV must be one of: {0}".format(", ".join(sorted(allowed))))
        return value

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the comma-separated CORS origins string into a list."""
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = os.environ.get("ENV_FILE", ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


def _load_settings() -> Settings:
    """Factory so settings can be reloaded/overridden cleanly in tests."""
    return Settings()


settings: Settings = _load_settings()


def get_settings() -> Settings:
    """FastAPI-dependency-friendly accessor for the settings singleton."""
    return settings
