from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """
    FastAPI-Users-compatible user table (email used as username).
    """

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    is_verified: bool = Field(default=False)

    display_name: str
    role: str = Field(default="editor")  # editor | admin


class Template(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    recurrence: str  # daily | weekdays | weekly
    recurrence_day: int | None = None  # 0=Mon–6=Sun, only for weekly
    auto_generate_days_ahead: int = 1


class TemplateSlot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    template_id: int = Field(foreign_key="template.id", index=True)
    position: int
    label: str
    segment: str
    planned_duration: int = 0
    title_in: int = 0
    title_duration: int = 5
    notes: str = ""
    beats: str = "[]"


class Rundown(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    template_id: int | None = Field(default=None, foreign_key="template.id", index=True)
    title: str
    show_date: date = Field(index=True)
    status: str = Field(default="preparing", index=True)  # preparing | live | done
    generated_at: datetime | None = None


class Story(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("rundown_id", "position", name="uq_story_rundown_position"),)

    id: int | None = Field(default=None, primary_key=True)
    rundown_id: int = Field(foreign_key="rundown.id", index=True)
    position: int = Field(default=0, index=True)
    label: str
    segment: str
    planned_duration: int = 0
    planned_duration_override: int | None = None
    title_in: int = 0
    title_duration: int = 5
    ready: bool = False
    status: str = Field(default="pending", index=True)  # pending | live | done
    beats: str = "[]"
    locked_by: int | None = Field(default=None, foreign_key="user.id", index=True)
    locked_at: datetime | None = None

    # relationships intentionally omitted for SQLite-first Phase 1 simplicity


class Script(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    story_id: int = Field(foreign_key="story.id", unique=True, index=True)
    body: str = ""
    updated_at: datetime = Field(default_factory=utcnow)
    updated_by: int | None = Field(default=None, foreign_key="user.id")

    # relationships intentionally omitted for SQLite-first Phase 1 simplicity
