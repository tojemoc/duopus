from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import auth_backend, current_active_user, fastapi_users
from models import User
from user_schemas import UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Provides:
# - POST /api/auth/login (form data: username/email + password)
# - POST /api/auth/logout
router.include_router(fastapi_users.get_auth_router(auth_backend), prefix="")

@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(current_active_user)):
    return user
