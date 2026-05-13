from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from auth import current_active_user
from beat_utils import beats_to_json, planned_duration_from_beats
from database import get_session
from models import Rundown, Script, Story, User, utcnow
from schemas import LockResult, ReadyUpdate, StoryReorder, StoryStatusUpdate, StoryUpdate
from story_lock import LOCK_TTL_SECONDS, lock_expired

router = APIRouter(prefix="/api", tags=["stories"])


@router.patch("/stories/{story_id}")
async def patch_story(
    story_id: int,
    body: StoryUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")

    if s.locked_by and s.locked_by != user.id and not lock_expired(s.locked_at):
        raise HTTPException(status_code=400, detail="Being edited by another user")

    data = body.model_dump(exclude_unset=True)
    beats = data.pop("beats", None)

    override_for_beats = s.planned_duration_override
    if "planned_duration_override" in data:
        override_for_beats = data["planned_duration_override"]

    if beats is not None:
        s.beats = beats_to_json(beats)
        s.planned_duration = planned_duration_from_beats(s.beats, override_for_beats)

    for k, v in data.items():
        setattr(s, k, v)

    if "planned_duration_override" in data and beats is None:
        s.planned_duration = planned_duration_from_beats(s.beats, s.planned_duration_override)

    # Release lock on save
    if s.locked_by == user.id:
        s.locked_by = None
        s.locked_at = None

    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@router.patch("/stories/{story_id}/ready")
async def set_ready(
    story_id: int,
    body: ReadyUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    s.ready = body.ready
    session.add(s)
    await session.commit()
    return {"ok": True, "ready": s.ready}


@router.patch("/stories/{story_id}/status")
async def set_status(
    story_id: int,
    body: StoryStatusUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    s.status = body.status
    session.add(s)
    await session.commit()
    return {"ok": True, "status": s.status}


@router.patch("/stories/reorder")
async def reorder_stories(
    body: StoryReorder,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    rd = await session.get(Rundown, body.rundown_id)
    if not rd:
        raise HTTPException(status_code=404, detail="Rundown not found")
    ids = [it.id for it in body.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Duplicate story ids in reorder request")
    positions = [it.position for it in body.items]
    if len(positions) != len(set(positions)):
        raise HTTPException(status_code=400, detail="Duplicate target positions in reorder request")
    rows = (
        await session.execute(select(Story).where(Story.rundown_id == body.rundown_id, Story.id.in_(ids)))
    ).scalars().all()
    by_id = {s.id: s for s in rows}
    if len(by_id) != len(ids):
        raise HTTPException(status_code=400, detail="One or more stories were not found in this rundown")
    max_pos = (
        await session.execute(select(func.max(Story.position)).where(Story.rundown_id == body.rundown_id))
    ).scalar_one_or_none()
    base = (max_pos or 0) + 100_000
    for i, it in enumerate(body.items):
        s = by_id.get(it.id)
        if not s:
            continue
        s.position = base + i
        session.add(s)
    await session.flush()
    for it in body.items:
        s = by_id.get(it.id)
        if not s:
            continue
        s.position = it.position
        session.add(s)
    await session.commit()
    return {"ok": True}


@router.post("/stories/{story_id}/lock", response_model=LockResult)
async def lock_story(
    story_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")

    expiry_cutoff = utcnow() - timedelta(seconds=LOCK_TTL_SECONDS)
    stmt = (
        sa_update(Story)
        .where(Story.id == story_id)
        .where(
            or_(
                Story.locked_by.is_(None),
                Story.locked_by == user.id,
                Story.locked_at.is_(None),
                Story.locked_at < expiry_cutoff,
            )
        )
        .values(locked_by=user.id, locked_at=utcnow())
    )
    result = await session.execute(stmt)
    await session.commit()

    if result.rowcount == 1:
        fresh = await session.get(Story, story_id)
        assert fresh is not None
        return LockResult(ok=True, locked_by=fresh.locked_by, locked_by_name=user.display_name, locked_at=fresh.locked_at)

    fresh = await session.get(Story, story_id)
    assert fresh is not None
    if fresh.locked_by and fresh.locked_by != user.id and not lock_expired(fresh.locked_at):
        other = await session.get(User, fresh.locked_by)
        return LockResult(
            ok=False,
            locked_by=fresh.locked_by,
            locked_by_name=other.display_name if other else None,
            locked_at=fresh.locked_at,
        )

    return LockResult(ok=False, locked_by=fresh.locked_by, locked_by_name=None, locked_at=fresh.locked_at)


@router.delete("/stories/{story_id}/lock", response_model=LockResult)
async def unlock_story(
    story_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")

    expiry_cutoff = utcnow() - timedelta(seconds=LOCK_TTL_SECONDS)
    stmt = (
        sa_update(Story)
        .where(Story.id == story_id)
        .where(
            or_(
                Story.locked_by.is_(None),
                Story.locked_by == user.id,
                Story.locked_at.is_(None),
                Story.locked_at < expiry_cutoff,
            )
        )
        .values(locked_by=None, locked_at=None)
    )
    result = await session.execute(stmt)
    await session.commit()

    if result.rowcount == 1:
        return LockResult(ok=True, locked_by=None, locked_by_name=None, locked_at=None)

    fresh = await session.get(Story, story_id)
    assert fresh is not None
    if fresh.locked_by is None:
        return LockResult(ok=True, locked_by=None, locked_by_name=None, locked_at=None)
    if fresh.locked_by != user.id and not lock_expired(fresh.locked_at):
        other = await session.get(User, fresh.locked_by)
        return LockResult(
            ok=False,
            locked_by=fresh.locked_by,
            locked_by_name=other.display_name if other else None,
            locked_at=fresh.locked_at,
        )

    return LockResult(ok=False, locked_by=fresh.locked_by, locked_by_name=None, locked_at=fresh.locked_at)
