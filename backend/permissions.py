from __future__ import annotations

from fastapi import Depends, HTTPException

from auth import current_active_user
from models import User


async def require_admin(user: User = Depends(current_active_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
