from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from auth import current_active_user
from database import get_session
from models import Rundown, Script, Story
from models import User
from schemas import RundownCreate, RundownUpdate

router = APIRouter(prefix="/api/rundowns", tags=["rundowns"])


@router.get("")
async def list_rundowns(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Rundown).order_by(col(Rundown.show_date).desc())
    return (await session.execute(stmt)).scalars().all()


@router.post("")
async def create_rundown(
    body: RundownCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    r = Rundown(template_id=body.template_id, title=body.title, show_date=body.show_date, status=body.status)
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


@router.get("/{rundown_id}")
async def get_rundown(
    rundown_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    return r


@router.get("/{rundown_id}/full")
async def get_rundown_full(
    rundown_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    stories = (
        await session.execute(select(Story).where(Story.rundown_id == rundown_id).order_by(col(Story.position)))
    ).scalars().all()
    scripts = (
        await session.execute(select(Script).where(Script.story_id.in_([s.id for s in stories if s.id is not None])))
    ).scalars().all()
    by_story = {sc.story_id: sc for sc in scripts}
    return {
        "rundown": r,
        "stories": [
            {
                **s.model_dump(),
                "script": (by_story.get(s.id).model_dump() if s.id in by_story else None),
            }
            for s in stories
        ],
    }


@router.patch("/{rundown_id}")
async def update_rundown(
    rundown_id: int,
    body: RundownUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(r, k, v)
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


@router.delete("/{rundown_id}")
async def delete_rundown(
    rundown_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    r = await session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    story_ids = (
        await session.execute(select(Story.id).where(Story.rundown_id == rundown_id))
    ).scalars().all()
    if story_ids:
        await session.execute(delete(Script).where(Script.story_id.in_(story_ids)))
        await session.execute(delete(Story).where(Story.id.in_(story_ids)))
    await session.execute(delete(Rundown).where(Rundown.id == rundown_id))
    await session.commit()
    return {"ok": True}
