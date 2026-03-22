from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.core.response import success_response
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    SignupRequest,
)
from app.services.auth_service import (
    login_user,
    logout_user,
    refresh_access_token,
    signup_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await login_user(
        db=db,
        email=payload.email,
        password=payload.password,
    )
    return success_response(request, data=data)


@router.post("/signup", status_code=201)
async def signup(
    request: Request,
    payload: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await signup_user(
        db=db,
        email=payload.email,
        password=payload.password,
        name=payload.name,
    )
    return success_response(request, data=data, status_code=201)


@router.post("/logout")
async def logout(
    request: Request,
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await logout_user(
        db=db,
        refresh_token=payload.refresh_token,
    )
    return success_response(request, data=data)


@router.post("/refresh")
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await refresh_access_token(
        db=db,
        current_user_id=current_user.id,
        refresh_token=payload.refresh_token,
    )
    return success_response(request, data=data)