# DB session 제공
# 현재 사용자 가져오기
import os
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, build_error
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.repositories.user_repository import get_user_by_id


bearer_scheme = HTTPBearer(auto_error=False)



LOGIN_DISABLED = os.getenv("LOGIN_DISABLED", "false").lower() == "true"
       

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise build_error(ErrorCode.AUTH_REQUIRED, "Authentication required")

    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise build_error(ErrorCode.AUTH_REQUIRED, "Authentication required")

    user_id = payload.get("sub")
    token_type = payload.get("type")

    if not user_id or token_type != "access":
        raise build_error(ErrorCode.AUTH_REQUIRED, "Authentication required")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise build_error(ErrorCode.AUTH_REQUIRED, "Authentication required")

    return user


async def get_current_user_or_dev_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if LOGIN_DISABLED:
        user = User()
        user.id = 1
        user.email = "dev@example.com"
        user.name = "dev user"
        return user

    return await get_current_user(db=db, credentials=credentials)