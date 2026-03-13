from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.response import success_response
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models.credit import CreditWallet, CreditTransaction
from app.models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None
    default_language: Literal["ko", "en"] = "ko"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise build_error(
            ErrorCode.INVALID_CREDENTIALS,
            "이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    access_token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return success_response(
        request,
        data={
            "access_token": access_token,
            "token_type": "Bearer",
        },
    )


@router.post("/signup")
async def signup(
    request: Request,
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    # 1. 이메일 중복 검사
    existing_user_result = await db.execute(
        select(User).where(User.email == body.email)
    )
    existing_user = existing_user_result.scalar_one_or_none()

    if existing_user is not None:
        raise build_error(
            ErrorCode.CONFLICT_DUPLICATE,
            "이미 가입된 이메일입니다.",
        )

    # 2. 비밀번호 해싱
    hashed_password = get_password_hash(body.password)

    # 3. 유저 생성
    new_user = User(
        email=body.email,
        hashed_password=hashed_password,
        name=body.name,
        default_language=body.default_language,
    )
    db.add(new_user)

    # flush를 해야 new_user.id를 바로 사용할 수 있음
    await db.flush()

    # 4. 크레딧 자동 생성
    new_credit = CreditWallet(
        user_id=new_user.id,
        balance=0,
    )
    db.add(new_credit)

    # 5. 최종 저장
    await db.commit()

    # 6. created_at 등 최신 값 다시 반영
    await db.refresh(new_user)

    return success_response(
        request,
        status_code=201,
        data={
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "default_language": new_user.default_language,
            "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
        },
    )


@router.post("/logout")
async def logout(
    request: Request,
    body: RefreshRequest,
    current_user: User = Depends(get_current_user),
):
    return success_response(
        request,
        data={
            "logged_out": True,
        },
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    current_user: User = Depends(get_current_user),
):
    access_token = create_access_token(
        subject=current_user.id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    return success_response(
        request,
        data={
            "access_token": access_token,
            "token_type": "Bearer",
            "refresh_token": None,
        },
    )