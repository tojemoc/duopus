import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: str
    autogen_time_utc: str


def _read_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./duopus.db"),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173"),
        autogen_time_utc=os.getenv("AUTOGEN_TIME_UTC", "03:00"),
    )


@lru_cache
def get_settings() -> Settings:
    return _read_settings()
