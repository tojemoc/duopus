from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from beat_utils import planned_duration_from_beats
from models import Rundown, Script, Story, Template, TemplateSlot, utcnow


async def generate_rundown_from_template(
    session: AsyncSession,
    template_id: int,
    show_date: date,
) -> Rundown:
    template = await session.get(Template, template_id)
    if not template:
        raise ValueError("Template not found")

    slots = (
        await session.execute(
            select(TemplateSlot)
            .where(TemplateSlot.template_id == template_id)
            .order_by(col(TemplateSlot.position))
        )
    ).scalars().all()

    rundown = Rundown(
        template_id=template_id,
        title=template.name,
        show_date=show_date,
        status="preparing",
        generated_at=utcnow(),
    )
    session.add(rundown)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = (
            await session.execute(
                select(Rundown).where(Rundown.template_id == template_id, Rundown.show_date == show_date)
            )
        ).scalars().first()
        if existing:
            return existing
        raise

    for i, slot in enumerate(slots, start=1):
        story = Story(
            rundown_id=rundown.id,  # type: ignore[arg-type]
            position=i,
            label=slot.label,
            segment=slot.segment,
            beats=slot.beats,
            title_in=slot.title_in,
            title_duration=slot.title_duration,
            planned_duration_override=slot.planned_duration,
            planned_duration=planned_duration_from_beats(slot.beats, slot.planned_duration),
            ready=False,
            status="pending",
        )
        session.add(story)
        await session.flush()
        session.add(Script(story_id=story.id, body="", updated_at=utcnow(), updated_by=None))  # type: ignore[arg-type]

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = (
            await session.execute(
                select(Rundown).where(Rundown.template_id == template_id, Rundown.show_date == show_date)
            )
        ).scalars().first()
        if existing:
            return existing
        raise

    await session.refresh(rundown)
    return rundown

