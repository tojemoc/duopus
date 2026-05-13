from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, IntegerIDMixin

from config import get_settings
from user_db import get_user_db
from models import User


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    def __init__(self, user_db):
        super().__init__(user_db)
        sk = get_settings().secret_key
        object.__setattr__(self, "reset_password_token_secret", sk)
        object.__setattr__(self, "verification_token_secret", sk)

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        return


async def get_user_manager(user_db=Depends(get_user_db)) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)
