from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RundownCreate(BaseModel):
    title: str
    show_date: date
    status: str = "preparing"


class RundownUpdate(BaseModel):
    title: str | None = None
    show_date: date | None = None
    status: str | None = None


class StoryCreate(BaseModel):
    title: str
    type: str = "package"
    planned_duration: int = 60
    vmix_input: int | None = None
    position: int | None = None


class StoryUpdate(BaseModel):
    title: str | None = None
    type: str | None = None
    planned_duration: int | None = None
    vmix_input: int | None = None
    position: int | None = None
    status: str | None = None
    actual_duration: int | None = None


class ScriptUpdate(BaseModel):
    body: str


class VmixCommandBody(BaseModel):
    function: str
    input: int | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class GoToStoryBody(BaseModel):
    story_id: UUID


class PrompterSpeedBody(BaseModel):
    delta: Literal[-1, 1]
