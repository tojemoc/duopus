from __future__ import annotations

from typing import Literal

from fastapi_users import schemas

UserRole = Literal["editor", "admin"]


class UserRead(schemas.BaseUser[int]):
    display_name: str
    role: UserRole


class UserCreate(schemas.BaseUserCreate):
    # BaseUserCreate expects email + password
    display_name: str
    role: UserRole = "editor"


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    role: UserRole | None = None
