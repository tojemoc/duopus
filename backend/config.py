import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    postgres_url: str
    redis_url: str
    vmix_host: str
    vmix_port: int


def _read_settings() -> Settings:
    vmix_port_raw = os.getenv("VMIX_PORT", "8099")
    try:
        vmix_port = int(vmix_port_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid VMIX_PORT: {vmix_port_raw}") from exc

    return Settings(
        postgres_url=os.getenv(
            "POSTGRES_URL",
            "postgresql+psycopg://duopus:duopus@localhost:5432/duopus",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        vmix_host=os.getenv("VMIX_HOST", "127.0.0.1"),
        vmix_port=vmix_port,
    )


@lru_cache
def get_settings() -> Settings:
    return _read_settings()
