from __future__ import annotations

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import CookieTransport, AuthenticationBackend
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from config import get_settings
from models import User
from user_manager import get_user_manager
from user_db import get_user_db


cookie_transport = CookieTransport(cookie_name="duopus_session", cookie_max_age=60 * 60 * 24 * 7)


def get_database_strategy(user_db=Depends(get_user_db)):
    # JWT stored in an HttpOnly cookie (keeps client UX session-like).
    return JWTStrategy(secret=get_settings().secret_key, lifetime_seconds=60 * 60 * 24 * 7)


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)

fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
