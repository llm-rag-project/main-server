from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.core.response import success_response
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
)
from app.services.auth_service import (
    login_user,
    logout_user,
    refresh_access_token,
)
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.articles import router as articles_router
from app.api.v1.feedbacks import router as feedbacks_router

api_router = APIRouter()

api_router.include_router(articles_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(keywords_router)
api_router.include_router(feedbacks_router)


@api_router.post("/login")
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


@api_router.post("/logout")
async def logout(
    request: Request,
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await logout_user(
        db=db,
        user_id=current_user.id,
        refresh_token=payload.refresh_token,
    )
    return success_response(request, data=data)


@api_router.post("/refresh")
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

