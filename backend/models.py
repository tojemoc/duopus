from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Rundown(SQLModel, table=True):
    __tablename__ = "rundown"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str = Field(index=True)
    show_date: date
    status: str = Field(default="preparing", index=True)  # preparing | live | done
    created_at: datetime = Field(default_factory=utcnow)
    stories: list["Story"] = Relationship(back_populates="rundown")


class Story(SQLModel, table=True):
    __tablename__ = "story"
    __table_args__ = (UniqueConstraint("rundown_id", "position", name="uq_story_rundown_position"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    rundown_id: UUID = Field(foreign_key="rundown.id", index=True)
    position: int = Field(default=0, index=True)
    title: str
    type: str = Field(default="package")  # package | live | break | intro
    planned_duration: int = Field(default=60)  # seconds
    actual_duration: Optional[int] = None
    vmix_input: Optional[int] = None
    status: str = Field(default="pending", index=True)  # pending | live | done

    rundown: Optional[Rundown] = Relationship(back_populates="stories")
    script: Optional["Script"] = Relationship(
        back_populates="story",
        sa_relationship_kwargs={"uselist": False},
    )
    cues: list["StoryCue"] = Relationship(back_populates="story")


class StoryCue(SQLModel, table=True):
    """Ordered sub-steps within a story (headline, ILU, SYN, …) with optional vMix FUNCTION."""

    __tablename__ = "story_cue"
    __table_args__ = (UniqueConstraint("story_id", "position", name="uq_story_cue_position"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    story_id: UUID = Field(foreign_key="story.id", index=True)
    position: int = Field(default=0, index=True)
    title: str = Field(default="")
    body: str = Field(default="")
    vmix_function: Optional[str] = None
    vmix_input: Optional[int] = None
    vmix_params: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    story: Optional[Story] = Relationship(back_populates="cues")


class Script(SQLModel, table=True):
    __tablename__ = "script"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    story_id: UUID = Field(foreign_key="story.id", unique=True, index=True)
    body: str = Field(default="")
    updated_at: datetime = Field(default_factory=utcnow)

    story: Optional[Story] = Relationship(back_populates="script")
