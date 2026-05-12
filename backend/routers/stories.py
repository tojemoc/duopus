from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from database import get_session
from models import Rundown, Script, Story, StoryCue, utcnow
from schemas import ScriptUpdate, StoryCreate, StoryCueReplaceBody, StoryUpdate

router = APIRouter(tags=["stories"])


@router.get("/api/rundowns/{rundown_id}/stories")
def list_stories(rundown_id: UUID, session: Session = Depends(get_session)):
    if not session.get(Rundown, rundown_id):
        raise HTTPException(status_code=404, detail="Rundown not found")
    stmt = (
        select(Story)
        .where(Story.rundown_id == rundown_id)
        .order_by(col(Story.position))
    )
    return list(session.exec(stmt).all())


@router.post("/api/rundowns/{rundown_id}/stories", response_model=Story)
def create_story(
    rundown_id: UUID,
    body: StoryCreate,
    session: Session = Depends(get_session),
):
    lock_stmt = select(Rundown).where(Rundown.id == rundown_id).with_for_update()
    rd = session.exec(lock_stmt).first()
    if not rd:
        raise HTTPException(status_code=404, detail="Rundown not found")
    pos = body.position
    if pos is None:
        stmt = select(func.max(Story.position)).where(Story.rundown_id == rundown_id)
        max_pos = session.exec(stmt).one()
        pos = (max_pos or 0) + 1
    story = Story(
        rundown_id=rundown_id,
        position=pos,
        title=body.title,
        type=body.type,
        planned_duration=body.planned_duration,
        vmix_input=body.vmix_input,
    )
    session.add(story)
    session.flush()
    session.add(Script(story_id=story.id, body=""))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Position {pos} already taken in this rundown",
        ) from None
    session.refresh(story)
    return story


@router.get("/api/stories/{story_id}", response_model=Story)
def get_story(story_id: UUID, session: Session = Depends(get_session)):
    s = session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    return s


@router.patch("/api/stories/{story_id}", response_model=Story)
def update_story(
    story_id: UUID,
    body: StoryUpdate,
    session: Session = Depends(get_session),
):
    s = session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(s, k, v)
    session.add(s)
    attempted_pos = s.position
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Position {attempted_pos} already taken in this rundown",
        ) from None
    session.refresh(s)
    return s


@router.put("/api/stories/{story_id}/cues")
def replace_story_cues(
    story_id: UUID,
    body: StoryCueReplaceBody,
    session: Session = Depends(get_session),
):
    s = session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    for c in session.exec(select(StoryCue).where(StoryCue.story_id == story_id)).all():
        session.delete(c)
    for item in body.cues:
        session.add(
            StoryCue(
                story_id=story_id,
                position=item.position,
                title=item.title,
                body=item.body,
                vmix_function=item.vmix_function,
                vmix_input=item.vmix_input,
                vmix_params=item.vmix_params,
            )
        )
    session.commit()
    stmt = select(StoryCue).where(StoryCue.story_id == story_id).order_by(col(StoryCue.position))
    return list(session.exec(stmt).all())


@router.delete("/api/stories/{story_id}")
def delete_story(story_id: UUID, session: Session = Depends(get_session)):
    s = session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    for c in session.exec(select(StoryCue).where(StoryCue.story_id == s.id)).all():
        session.delete(c)
    sc = session.exec(select(Script).where(Script.story_id == s.id)).first()
    if sc:
        session.delete(sc)
    session.delete(s)
    session.commit()
    return {"ok": True}


@router.get("/api/stories/{story_id}/script")
def get_script(story_id: UUID, session: Session = Depends(get_session)):
    s = session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    sc = session.exec(select(Script).where(Script.story_id == story_id)).first()
    if not sc:
        raise HTTPException(status_code=404, detail="Script not found")
    return {"story_id": str(story_id), "body": sc.body, "updated_at": sc.updated_at.isoformat()}


@router.put("/api/stories/{story_id}/script")
def put_script(
    story_id: UUID,
    body: ScriptUpdate,
    session: Session = Depends(get_session),
):
    s = session.get(Story, story_id)
    if not s:
        raise HTTPException(status_code=404, detail="Story not found")
    sc = session.exec(select(Script).where(Script.story_id == story_id)).first()
    if not sc:
        sc = Script(story_id=story_id, body=body.body, updated_at=utcnow())
        session.add(sc)
    else:
        sc.body = body.body
        sc.updated_at = utcnow()
        session.add(sc)
    session.commit()
    session.refresh(sc)
    return {"story_id": str(story_id), "body": sc.body, "updated_at": sc.updated_at.isoformat()}
