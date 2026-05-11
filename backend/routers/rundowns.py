from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from database import get_session
from models import Rundown, Script, Story
from schemas import RundownCreate, RundownUpdate
from deps import RundownEngineDep

router = APIRouter(prefix="/api/rundowns", tags=["rundowns"])


@router.get("")
def list_rundowns(session: Session = Depends(get_session)):
    stmt = select(Rundown).order_by(col(Rundown.created_at).desc())
    return list(session.exec(stmt).all())


@router.post("", response_model=Rundown)
def create_rundown(body: RundownCreate, session: Session = Depends(get_session)):
    r = Rundown(title=body.title, show_date=body.show_date, status=body.status)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.get("/{rundown_id}", response_model=Rundown)
def get_rundown(rundown_id: UUID, session: Session = Depends(get_session)):
    r = session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    return r


@router.patch("/{rundown_id}", response_model=Rundown)
def update_rundown(
    rundown_id: UUID,
    body: RundownUpdate,
    session: Session = Depends(get_session),
):
    r = session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(r, k, v)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.delete("/{rundown_id}")
def delete_rundown(rundown_id: UUID, session: Session = Depends(get_session)):
    r = session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    for s in session.exec(select(Story).where(Story.rundown_id == rundown_id)).all():
        sc = session.exec(select(Script).where(Script.story_id == s.id)).first()
        if sc:
            session.delete(sc)
        session.delete(s)
    session.delete(r)
    session.commit()
    return {"ok": True}


@router.post("/{rundown_id}/activate")
async def activate_rundown(
    rundown_id: UUID,
    session: Session = Depends(get_session),
    engine: RundownEngineDep,
):
    r = session.get(Rundown, rundown_id)
    if not r:
        raise HTTPException(status_code=404, detail="Rundown not found")
    await engine.set_active_rundown(rundown_id)
    return {"ok": True, "active_rundown_id": str(rundown_id)}
