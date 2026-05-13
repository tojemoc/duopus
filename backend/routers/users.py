from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi_users import exceptions

from models import User
from permissions import require_admin
from user_manager import UserManager, get_user_manager
from user_schemas import UserCreate, UserRead, UserUpdate
from database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def list_users(
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return (await session.execute(select(User).order_by(col(User.id)))).scalars().all()


@router.post("", response_model=UserRead)
async def create_user(
    body: UserCreate,
    _: User = Depends(require_admin),
    manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await manager.create(body)
        return user
    except exceptions.UserAlreadyExists:
        raise HTTPException(status_code=400, detail="Username already exists") from None


@router.patch("/{user_id}", response_model=UserRead)
async def patch_user(
    user_id: int,
    body: UserUpdate,
    _: User = Depends(require_admin),
    manager: UserManager = Depends(get_user_manager),
):
    user = await manager.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await manager.update(body, user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    _: User = Depends(require_admin),
    manager: UserManager = Depends(get_user_manager),
):
    user = await manager.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await manager.delete(user)
    return {"ok": True}

