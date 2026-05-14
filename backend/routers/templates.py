from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from beat_utils import beats_to_json
from database import get_session
from models import Rundown, Script, Story, Template, TemplateSlot, User
from permissions import require_admin
from schemas import TemplateIn, TemplatePatch
from services.generate import generate_rundown_from_template

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
async def list_templates(
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(select(Template).order_by(col(Template.id)))).scalars().all()
    return rows


@router.post("")
async def create_template(
    body: TemplateIn,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    t = Template(
        name=body.name,
        recurrence=body.recurrence,
        recurrence_day=body.recurrence_day,
        auto_generate_days_ahead=body.auto_generate_days_ahead,
    )
    session.add(t)
    await session.flush()

    for slot in body.slots:
        session.add(
            TemplateSlot(
                template_id=t.id,  # type: ignore[arg-type]
                position=slot.position,
                label=slot.label,
                segment=slot.segment,
                planned_duration=slot.planned_duration,
                title_in=slot.title_in,
                title_duration=slot.title_duration,
                notes=slot.notes,
                beats=beats_to_json(slot.beats),
            )
        )
    await session.commit()
    await session.refresh(t)
    return t


@router.patch("/{template_id}")
async def patch_template(
    template_id: int,
    body: TemplatePatch,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    t = await session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    data = body.model_dump(exclude_unset=True)
    slots = data.pop("slots", None)
    for k, v in data.items():
        setattr(t, k, v)
    session.add(t)

    if slots is not None:
        await session.execute(delete(TemplateSlot).where(TemplateSlot.template_id == template_id))
        for slot in slots:
            session.add(
                TemplateSlot(
                    template_id=template_id,
                    position=slot["position"],
                    label=slot["label"],
                    segment=slot["segment"],
                    planned_duration=slot.get("planned_duration", 0),
                    title_in=slot.get("title_in", 0),
                    title_duration=slot.get("title_duration", 5),
                    notes=slot.get("notes", ""),
                    beats=beats_to_json(slot.get("beats", [])),
                )
            )

    await session.commit()
    await session.refresh(t)
    return t


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    t = await session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    await session.execute(delete(TemplateSlot).where(TemplateSlot.template_id == template_id))
    await session.execute(delete(Template).where(Template.id == template_id))
    await session.commit()
    return {"ok": True}


@router.post("/{template_id}/generate")
async def generate_template_rundown(
    template_id: int,
    show_date: date = Query(..., alias="date"),
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    # Do not overwrite existing.
    existing = (
        await session.execute(
            select(Rundown).where(Rundown.template_id == template_id, Rundown.show_date == show_date)
        )
    ).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Rundown already exists for that template and date")

    t = await session.get(Template, template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    rundown = await generate_rundown_from_template(session, template_id=template_id, show_date=show_date)
    return {"ok": True, "rundown_id": rundown.id}

