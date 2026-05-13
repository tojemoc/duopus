from __future__ import annotations

import os
from typing import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, IntegerIDMixin

from user_db import get_user_db
from models import User


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    reset_password_token_secret = os.getenv("SECRET_KEY", "dev-secret-key")
    verification_token_secret = os.getenv("SECRET_KEY", "dev-secret-key")

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        return


async def get_user_manager(user_db=Depends(get_user_db)) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)
