import os
from functools import lru_cache


class Settings:
    postgres_url: str = os.getenv(
        "POSTGRES_URL",
        "postgresql+psycopg://duopus:duopus@localhost:5432/duopus",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    vmix_host: str = os.getenv("VMIX_HOST", "127.0.0.1")
    vmix_port: int = int(os.getenv("VMIX_PORT", "8099"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
