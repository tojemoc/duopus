from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi_users.exceptions import UserAlreadyExists
from sqlmodel import select

from beat_utils import beats_to_json
from config import get_settings
from database import get_sessionmaker
from models import Template, TemplateSlot
from schemas import Beat
from user_manager import UserManager
from user_schemas import UserCreate

log = logging.getLogger(__name__)


def _default_beats(categories: list[str]) -> list[Beat]:
    return [Beat(id=str(uuid4()), category=c, duration=0, note="") for c in categories]  # type: ignore[arg-type]


async def ensure_seed_data() -> None:
    settings = get_settings()
    SessionMaker = get_sessionmaker()
    async with SessionMaker() as session:
        # Admin user
        from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
        from models import User

        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db)

        if settings.environment == "production":
            admin_pw = settings.admin_password
            if not admin_pw:
                raise RuntimeError(
                    "ADMIN_PASSWORD environment variable is required in production to seed the initial admin user"
                )
            generated_pw: str | None = None
        else:
            if settings.admin_password:
                admin_pw = settings.admin_password
                generated_pw = None
            else:
                admin_pw = secrets.token_urlsafe(16)
                generated_pw = admin_pw

        try:
            await manager.create(
                UserCreate(email="admin@example.com", password=admin_pw, display_name="Admin", role="admin"),
                safe=False,
            )
            if generated_pw is not None:
                log.warning("Generated dev admin password (save securely): %s", generated_pw)
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
            today = datetime.now(timezone.utc).date()
            existing_rd = (
                await session.execute(select(Rundown).where(Rundown.template_id == t.id, Rundown.show_date == today))
            ).scalars().first()
            if not existing_rd:
                await generate_rundown_from_template(session, template_id=t.id, show_date=today)

