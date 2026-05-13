from __future__ import annotations

from fastapi_users import schemas


class UserRead(schemas.BaseUser[int]):
    display_name: str
    role: str


class UserCreate(schemas.BaseUserCreate):
    # BaseUserCreate expects email + password
    display_name: str
    role: str = "editor"


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    role: str | None = None
