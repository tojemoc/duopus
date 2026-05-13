from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi_users.exceptions import UserAlreadyExists
from sqlmodel import select

from beat_utils import beats_to_json
from database import get_sessionmaker
from models import Template, TemplateSlot
from schemas import Beat
from user_manager import UserManager
from user_schemas import UserCreate


def _default_beats(categories: list[str]) -> list[Beat]:
    return [Beat(id=str(uuid4()), category=c, duration=0, note="") for c in categories]  # type: ignore[arg-type]


async def ensure_seed_data() -> None:
    SessionMaker = get_sessionmaker()
    async with SessionMaker() as session:
        # Admin user
        manager = UserManager(session_user_db := None)  # placeholder for type checker
        # UserManager expects a user_db object; create it through manager dependency pattern.
        # We avoid importing get_user_db here to keep seed self-contained.
        from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
        from models import User

        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db)
        try:
            await manager.create(
                UserCreate(email="admin@example.com", password="duopus2025", display_name="Admin", role="admin"),
                safe=False,
            )
        except UserAlreadyExists:
            pass

        # Example template
        existing = (await session.execute(select(Template).where(Template.name == "Večerné správy"))).scalars().first()
        if not existing:
            t = Template(
                name="Večerné správy",
                recurrence="daily",
                recurrence_day=None,
                auto_generate_days_ahead=1,
            )
            session.add(t)
            await session.flush()

            slots = [
                ("Intro", "Intro", ["VO"]),
                ("Headlines", "Headlines", ["VO", "SYN"]),
                ("Story 1", "Story", ["VO", "SYN", "VO"]),
                ("Story 2", "Story", ["VO", "SYN", "VO"]),
                ("Sport", "Sport", ["VO", "SYN"]),
                ("Weather", "Weather", ["VO"]),
                ("Outro", "Outro", ["VO"]),
            ]
            for i, (label, segment, cats) in enumerate(slots, start=1):
                session.add(
                    TemplateSlot(
                        template_id=t.id,  # type: ignore[arg-type]
                        position=i,
                        label=label,
                        segment=segment,
                        planned_duration=0,
                        title_in=0,
                        title_duration=5,
                        notes="",
                        beats=beats_to_json(_default_beats(cats)),
                    )
                )
            await session.commit()

        # Ensure today's rundown exists (autogen loop will also do this, but we want immediate first-run UX)
        from models import Rundown
        from services.generate import generate_rundown_from_template

        t = (await session.execute(select(Template).order_by(Template.id))).scalars().first()
        if t:
            today = date.today()
            existing_rd = (
                await session.execute(select(Rundown).where(Rundown.template_id == t.id, Rundown.show_date == today))
            ).scalars().first()
            if not existing_rd:
                await generate_rundown_from_template(session, template_id=t.id, show_date=today)

