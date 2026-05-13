from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from auth import current_active_user
from beat_utils import beats_from_json
from database import get_session
from models import Script, Story, User
from schemas import PrompterPollResponse

router = APIRouter(prefix="/api/prompter", tags=["prompter"])


@router.get("/{story_id}", response_model=PrompterPollResponse)
async def poll_prompter(
    story_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    s = await session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    sc = (await session.execute(select(Script).where(Script.story_id == story_id))).scalars().first()
    body = sc.body if sc else ""
    updated_at = sc.updated_at if sc else s.locked_at  # best-effort
    return PrompterPollResponse(
        story_id=story_id,
        label=s.label,
        segment=s.segment,
        beats=beats_from_json(s.beats),
        body=body,
        updated_at=updated_at,
    )
