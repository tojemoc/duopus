"""Rundown engine DB logic with in-memory SQLite."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import database
import services.rundown_engine as rundown_engine_mod
from models import Rundown, Story
from services.rundown_engine import RundownEngine


@pytest.fixture()
def sqlite_engine(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "_engine", engine)

    def _get():
        return engine

    monkeypatch.setattr(database, "get_engine", _get)
    monkeypatch.setattr(rundown_engine_mod, "get_engine", _get)
    return engine


def _seed(session: Session, rid: UUID) -> tuple[UUID, UUID, UUID]:
    a = uuid4()
    b = uuid4()
    c = uuid4()
    session.add(Rundown(id=rid, title="T", show_date=date.today(), status="preparing"))
    session.add(
        Story(
            id=a,
            rundown_id=rid,
            position=1,
            title="A",
            type="package",
            planned_duration=60,
            vmix_input=1,
            status="pending",
        )
    )
    session.add(
        Story(
            id=b,
            rundown_id=rid,
            position=2,
            title="B",
            type="package",
            planned_duration=60,
            vmix_input=2,
            status="pending",
        )
    )
    session.add(
        Story(
            id=c,
            rundown_id=rid,
            position=3,
            title="C",
            type="package",
            planned_duration=60,
            vmix_input=3,
            status="pending",
        )
    )
    session.commit()
    return a, b, c


@pytest.mark.asyncio
async def test_advance_selects_first_pending(sqlite_engine):
    rid = uuid4()
    with Session(sqlite_engine) as s:
        _seed(s, rid)
    eng = RundownEngine(redis_url="redis://localhost:9")
    eng.get_active_rundown_id = AsyncMock(return_value=rid)
    eng._publish_state = AsyncMock()  # noqa: SLF001
    ok = await eng.advance()
    assert ok is True
    snap = eng._build_snapshot_sync(rid, eng._live_started_at)  # noqa: SLF001
    assert snap["live_story"]["title"] == "A"


@pytest.mark.asyncio
async def test_program_input_marks_live(sqlite_engine):
    rid = uuid4()
    with Session(sqlite_engine) as s:
        a, b, _c = _seed(s, rid)
        sa = s.get(Story, a)
        assert sa is not None
        sa.status = "live"
        s.add(sa)
        s.commit()
    eng = RundownEngine(redis_url="redis://localhost:9")
    eng._live_started_at = None  # noqa: SLF001
    changed = eng._sync_on_program_input_with_timer(rid, 2)  # noqa: SLF001
    assert changed is True
    with Session(sqlite_engine) as s:
        assert s.get(Story, a).status == "done"  # type: ignore
        assert s.get(Story, b).status == "live"  # type: ignore
