from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from auth import current_active_user
from database import get_session
from models import Script, Story, User, utcnow
from schemas import ScriptRead, ScriptUpdate
from story_lock import lock_expired

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("/{story_id}", response_model=ScriptRead)
async def get_script(
    story_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    sc = (await session.execute(select(Script).where(Script.story_id == story_id))).scalars().first()
    if not sc:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptRead(story_id=story_id, body=sc.body, updated_at=sc.updated_at, updated_by=sc.updated_by)


@router.put("/{story_id}", response_model=ScriptRead)
async def put_script(
    story_id: int,
    body: ScriptUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")

    if s.locked_by and s.locked_by != user.id and not lock_expired(s.locked_at):
        raise HTTPException(status_code=400, detail="Being edited by another user")

    sc = (await session.execute(select(Script).where(Script.story_id == story_id))).scalars().first()
    if not sc:
        sc = Script(story_id=story_id, body=body.body, updated_at=utcnow(), updated_by=user.id)
        session.add(sc)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            s = await session.get(Story, story_id)
            if not s:
                raise HTTPException(status_code=404, detail="Story not found") from None
            if s.locked_by and s.locked_by != user.id and not lock_expired(s.locked_at):
                raise HTTPException(status_code=400, detail="Being edited by another user") from None
            sc = (await session.execute(select(Script).where(Script.story_id == story_id))).scalars().first()
            if not sc:
                raise HTTPException(status_code=500, detail="Could not save script after a concurrent update") from None
            sc.body = body.body
            sc.updated_at = utcnow()
            sc.updated_by = user.id
            session.add(sc)
    else:
        sc.body = body.body
        sc.updated_at = utcnow()
        sc.updated_by = user.id
        session.add(sc)

    s_final = await session.get(Story, story_id)
    if s_final and s_final.locked_by == user.id:
        s_final.locked_by = None
        s_final.locked_at = None
        session.add(s_final)

    await session.commit()
    await session.refresh(sc)
    return ScriptRead(story_id=story_id, body=sc.body, updated_at=sc.updated_at, updated_by=sc.updated_by)
