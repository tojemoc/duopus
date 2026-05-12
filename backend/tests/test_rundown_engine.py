"""Rundown engine DB logic with in-memory SQLite."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, col, create_engine, select

import database
import services.rundown_engine as rundown_engine_mod
from models import Rundown, Script, Story, StoryCue
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


def test_sync_set_active_marks_rundown_live_and_first_story_on_air(sqlite_engine):
    rid = uuid4()
    with Session(sqlite_engine) as s:
        a, _b, _c = _seed(s, rid)
    eng = RundownEngine(redis_url="redis://localhost:9")
    eng._sync_set_active_rundown(None, rid)  # noqa: SLF001
    with Session(sqlite_engine) as s:
        r = s.get(Rundown, rid)
        assert r is not None
        assert r.status == "live"
        assert s.get(Story, a).status == "live"  # type: ignore
        others = [
            st
            for st in s.exec(select(Story).where(Story.rundown_id == rid).order_by(col(Story.position))).all()
            if st.id != a
        ]
        assert all(st.status == "pending" for st in others)


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
async def test_next_steps_cues_then_advances_story(sqlite_engine):
    rid = uuid4()
    with Session(sqlite_engine) as s:
        a, _b, _c = _seed(s, rid)
        s.add(Script(story_id=a, body="FULL SCRIPT"))
        s.add(
            StoryCue(
                story_id=a,
                position=0,
                title="H1",
                body="CUE0",
                vmix_function="OverlayInput1In",
                vmix_input=2,
            )
        )
        s.add(StoryCue(story_id=a, position=1, title="SYN", body="CUE1", vmix_function=None))
        s.commit()
    eng = RundownEngine(redis_url="redis://localhost:9")
    eng._sync_set_active_rundown(None, rid)  # noqa: SLF001
    eng.get_active_rundown_id = AsyncMock(return_value=rid)
    eng._publish_state = AsyncMock()  # noqa: SLF001
    eng._live_cue_index = -1

    c1, o1 = await eng.next_step()
    assert c1 and len(o1) == 1 and o1[0][0] == "OverlayInput1In" and o1[0][1] == 2
    assert eng._live_cue_index == 0

    c2, o2 = await eng.next_step()
    assert c2 and o2 == []
    assert eng._live_cue_index == 1

    c3, o3 = await eng.next_step()
    assert c3 and o3 == []
    assert eng._live_cue_index == -1
    snap = eng._build_snapshot_sync(rid, eng._live_started_at)  # noqa: SLF001
    assert snap["live_story"] is not None
    assert snap["live_story"]["title"] == "B"


@pytest.mark.asyncio
async def test_next_without_cues_advances_like_advance(sqlite_engine):
    rid = uuid4()
    with Session(sqlite_engine) as s:
        _seed(s, rid)
    eng = RundownEngine(redis_url="redis://localhost:9")
    eng._sync_set_active_rundown(None, rid)  # noqa: SLF001
    eng.get_active_rundown_id = AsyncMock(return_value=rid)
    eng._publish_state = AsyncMock()  # noqa: SLF001
    ok, ops = await eng.next_step()
    assert ok and ops == []
    snap = eng._build_snapshot_sync(rid, eng._live_started_at)  # noqa: SLF001
    assert snap["live_story"]["title"] == "B"


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
