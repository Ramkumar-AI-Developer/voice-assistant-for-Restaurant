"""
Authentication API routes.
  POST /auth/login    — get JWT token
  POST /auth/register — create new user (admin only)
  GET  /auth/me       — get current user info
"""

import logging
from pydantic import BaseModel
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.db_models import User
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_admin_user,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request/Response schemas ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    is_admin: bool = False

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    is_admin: bool
    is_active: bool

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT token."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(data={"sub": user.username})

    return LoginResponse(
        access_token=token,
        username=user.username,
        is_admin=user.is_admin,
    )


@router.post("/register", response_model=UserResponse)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Create a new user. Only admins can access this."""
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"New user created: {user.username} (admin={user.is_admin}) by {admin.username}")
    return user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return current_user
