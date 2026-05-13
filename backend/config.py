import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: str
    autogen_time_utc: str
    secret_key: str
    environment: str
    admin_password: str | None


def _read_settings() -> Settings:
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise ValueError("SECRET_KEY environment variable is required")
    env = (os.getenv("ENVIRONMENT") or "development").strip().lower()
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./duopus.db"),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173"),
        autogen_time_utc=os.getenv("AUTOGEN_TIME_UTC", "03:00"),
        secret_key=secret_key,
        environment=env,
        admin_password=os.getenv("ADMIN_PASSWORD"),
    )


@lru_cache
def get_settings() -> Settings:
    return _read_settings()
