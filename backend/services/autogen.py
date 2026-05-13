from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import col, select

from database import get_sessionmaker
from models import Rundown, Template
from services.generate import generate_rundown_from_template


def _parse_time_utc(raw: str) -> time:
    hh, mm = raw.split(":")
    return time(hour=int(hh), minute=int(mm), tzinfo=timezone.utc)


def _should_generate(t: Template, d: date) -> bool:
    if t.recurrence == "daily":
        return True
    if t.recurrence == "weekdays":
        return d.weekday() <= 4
    if t.recurrence == "weekly":
        return t.recurrence_day is not None and d.weekday() == t.recurrence_day
    return False


async def autogen_once() -> None:
    SessionMaker = get_sessionmaker()
    async with SessionMaker() as session:
        templates = (await session.execute(select(Template).order_by(col(Template.id)))).scalars().all()
        for t in templates:
            days = max(0, int(t.auto_generate_days_ahead or 0))
            for i in range(days + 1):
                d = date.today() + timedelta(days=i)
                if not _should_generate(t, d):
                    continue
                existing = (
                    await session.execute(select(Rundown).where(Rundown.template_id == t.id, Rundown.show_date == d))
                ).scalars().first()
                if existing:
                    continue
                await generate_rundown_from_template(session, template_id=t.id, show_date=d)


async def autogen_loop(stop: asyncio.Event, autogen_time_utc: str) -> None:
    at = _parse_time_utc(autogen_time_utc)
    last_run_date: date | None = None
    while not stop.is_set():
        now = datetime.now(timezone.utc)
        if now.time().hour == at.hour and now.time().minute == at.minute:
            if last_run_date != now.date():
                await autogen_once()
                last_run_date = now.date()
        await asyncio.sleep(20)

