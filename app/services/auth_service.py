from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import build_error, ErrorCode
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    get_refresh_token_expires_at,
)
from app.repositories.auth_token_repository import (
    create_refresh_token_record,
    get_refresh_token_record,
    revoke_refresh_token,
)
from app.repositories.user_repository import get_user_by_email
from app.schemas.auth import (
    LoginResponse,
    LogoutResponse,
    RefreshTokenResponse,
)
from app.core.errors import build_error, ErrorCode
from app.core.security import (
    get_password_hash,
    validate_password_policy,
    create_access_token,
    create_refresh_token,
    get_refresh_token_expires_at,
)
from app.core.config import settings
from app.repositories.user_repository import get_user_by_email, create_user
from app.repositories.credit_wallet_repository import create_credit_wallet
from app.repositories.auth_token_repository import create_refresh_token_record
from app.schemas.auth import SignupResponse, SignupUserResponse

async def login_user(db: AsyncSession, email: str, password: str) -> LoginResponse:
    user = await get_user_by_email(db, email)

    if user is None:
        raise build_error(
            ErrorCode.INVALID_CREDENTIALS,
            "이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    if not verify_password(password, user.hashed_password):
        raise build_error(
            ErrorCode.INVALID_CREDENTIALS,
            "이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token()
    refresh_token_expires_at = get_refresh_token_expires_at()

    await create_refresh_token_record(
        db=db,
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=refresh_token_expires_at,
    )
    await db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
    )


async def logout_user(
    db: AsyncSession,
    refresh_token: str,
) -> LogoutResponse:
    token_record = await get_refresh_token_record(db, refresh_token)

    if token_record is None:
        return LogoutResponse(logged_out=True)

    if not token_record.is_revoked:
        await revoke_refresh_token(db, token_record)
        await db.commit()

    return LogoutResponse(logged_out=True)


async def refresh_access_token(
    db,
    current_user_id: int,
    refresh_token: str,
) -> RefreshTokenResponse:

    token_record = await get_refresh_token_record(db, refresh_token)

    # 1. 존재하지 않음
    if token_record is None:
        raise build_error(
            ErrorCode.REFRESH_TOKEN_INVALID,
            "refresh_token이 없거나 유효하지 않습니다.",
        )

    # 2. 폐기됨
    if token_record.is_revoked:
        raise build_error(
            ErrorCode.TOKEN_REVOKED,
            "폐기된 토큰입니다. 다시 로그인해 주세요.",
        )

    # 3. 사용자 불일치
    if token_record.user_id != current_user_id:
        raise build_error(
            ErrorCode.TOKEN_MISMATCH,
            "토큰 정보가 일치하지 않습니다.",
        )

    # 4. 만료
    if token_record.expires_at <= datetime.now(timezone.utc):
        raise build_error(
            ErrorCode.REFRESH_TOKEN_INVALID,
            "refresh_token이 만료되었습니다.",
        )

    # 5. 정상 → 새 access token 발급
    access_token = create_access_token(subject=current_user_id)

    return RefreshTokenResponse(
        access_token=access_token,
        token_type="Bearer",
    )
    
    
async def signup_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str | None = None,
) -> SignupResponse:
    existing_user = await get_user_by_email(db, email)
    if existing_user is not None:
        raise build_error(
            ErrorCode.CONFLICT_DUPLICATE,
            "Email already exists",
        )

    validate_password_policy(password)
    hashed_password = get_password_hash(password)

    user = await create_user(
        db=db,
        email=email,
        hashed_password=hashed_password,
        name=name,
    )

    await create_credit_wallet(
        db=db,
        user_id=user.id,
    )

    refresh_token = create_refresh_token()
    refresh_token_expires_at = get_refresh_token_expires_at()

    await create_refresh_token_record(
        db=db,
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=refresh_token_expires_at,
    )

    access_token = create_access_token(subject=user.id)

    await db.commit()
    await db.refresh(user)

    return SignupResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=SignupUserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            created_at=user.created_at,
        ),
    )
