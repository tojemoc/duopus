from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    message: str


class RundownCreate(BaseModel):
    template_id: int | None = None
    title: str
    show_date: date
    status: str = "preparing"


class RundownUpdate(BaseModel):
    title: str | None = None
    show_date: date | None = None
    status: str | None = None


class Beat(BaseModel):
    id: str
    category: Literal["VO", "ILU", "SYN"]
    duration: int = Field(default=0, ge=0)
    note: str = ""


class StoryUpdate(BaseModel):
    position: int | None = None
    label: str | None = None
    segment: str | None = None
    title_in: int | None = Field(default=None, ge=0)
    title_duration: int | None = Field(default=None, ge=0)
    beats: list[Beat] | None = None
    planned_duration_override: int | None = Field(default=None, ge=0)
    ready: bool | None = None
    status: Literal["pending", "live", "done"] | None = None


class ReadyUpdate(BaseModel):
    ready: bool


class StoryStatusUpdate(BaseModel):
    status: Literal["pending", "live", "done"]


class StoryReorderItem(BaseModel):
    id: int
    position: int = Field(ge=0)


class StoryReorder(BaseModel):
    rundown_id: int
    items: list[StoryReorderItem]


class ScriptRead(BaseModel):
    story_id: int
    body: str
    updated_at: datetime
    updated_by: int | None


class ScriptUpdate(BaseModel):
    body: str


class TemplateSlotIn(BaseModel):
    position: int = Field(ge=0)
    label: str
    segment: str
    planned_duration: int = Field(default=0, ge=0)
    title_in: int = Field(default=0, ge=0)
    title_duration: int = Field(default=5, ge=0)
    notes: str = ""
    beats: list[Beat] = Field(default_factory=list)


class TemplateIn(BaseModel):
    name: str
    recurrence: Literal["daily", "weekdays", "weekly"]
    recurrence_day: int | None = Field(default=None, ge=0, le=6)
    auto_generate_days_ahead: int = Field(default=1, ge=0)
    slots: list[TemplateSlotIn] = Field(default_factory=list)


class TemplatePatch(BaseModel):
    name: str | None = None
    recurrence: Literal["daily", "weekdays", "weekly"] | None = None
    recurrence_day: int | None = Field(default=None, ge=0, le=6)
    auto_generate_days_ahead: int | None = Field(default=None, ge=0)
    slots: list[TemplateSlotIn] | None = None


class LockResult(BaseModel):
    ok: bool
    locked_by: int | None = None
    locked_by_name: str | None = None
    locked_at: datetime | None = None


class PrompterPollResponse(BaseModel):
    story_id: int
    label: str
    segment: str
    beats: list[Beat]
    body: str
    updated_at: datetime
