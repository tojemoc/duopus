from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_settings().postgres_url,
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
