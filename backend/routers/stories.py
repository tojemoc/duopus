from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from auth import current_active_user
from beat_utils import beats_to_json, planned_duration_from_beats
from database import get_session
from models import Rundown, Script, Story, User, utcnow
from schemas import LockResult, StoryReorder, StoryUpdate

router = APIRouter(prefix="/api", tags=["stories"])

LOCK_TTL_SECONDS = 5 * 60


def _lock_expired(locked_at: datetime | None) -> bool:
    if not locked_at:
        return True
    return utcnow() - locked_at > timedelta(seconds=LOCK_TTL_SECONDS)


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

    if s.locked_by and s.locked_by != user.id and not _lock_expired(s.locked_at):
        raise HTTPException(status_code=400, detail="Being edited by another user")

    data = body.model_dump(exclude_unset=True)
    beats = data.pop("beats", None)
    if beats is not None:
        s.beats = beats_to_json(beats)
        s.planned_duration = planned_duration_from_beats(s.beats, s.planned_duration_override)

    for k, v in data.items():
        setattr(s, k, v)

    # Recompute planned_duration if override changed and beats have no durations.
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
    body: dict,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    ready = bool(body.get("ready"))
    s.ready = ready
    session.add(s)
    await session.commit()
    return {"ok": True, "ready": s.ready}


@router.patch("/stories/{story_id}/status")
async def set_status(
    story_id: int,
    body: dict,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    status = body.get("status")
    if status not in ("pending", "live", "done"):
        raise HTTPException(status_code=400, detail="Invalid status")
    s.status = status
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
    rows = (
        await session.execute(select(Story).where(Story.rundown_id == body.rundown_id, Story.id.in_(ids)))
    ).scalars().all()
    by_id = {s.id: s for s in rows}
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

    if s.locked_by and s.locked_by != user.id and not _lock_expired(s.locked_at):
        other = await session.get(User, s.locked_by)
        return LockResult(
            ok=False,
            locked_by=s.locked_by,
            locked_by_name=other.display_name if other else None,
            locked_at=s.locked_at,
        )

    s.locked_by = user.id
    s.locked_at = utcnow()
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return LockResult(ok=True, locked_by=s.locked_by, locked_by_name=user.display_name, locked_at=s.locked_at)


@router.delete("/stories/{story_id}/lock", response_model=LockResult)
async def unlock_story(
    story_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    if s.locked_by and s.locked_by != user.id and not _lock_expired(s.locked_at):
        other = await session.get(User, s.locked_by)
        return LockResult(
            ok=False,
            locked_by=s.locked_by,
            locked_by_name=other.display_name if other else None,
            locked_at=s.locked_at,
        )

    s.locked_by = None
    s.locked_at = None
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return LockResult(ok=True, locked_by=None, locked_by_name=None, locked_at=None)
