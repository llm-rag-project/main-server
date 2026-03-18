from datetime import datetime, timedelta, timezone
from typing import Any
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from pydantic import BaseModel, Field, EmailStr

import re

from app.core.errors import build_error, ErrorCode


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def get_refresh_token_expires_at(days: int | None = None) -> datetime:
    expire_days = days or settings.refresh_token_expire_days
    return datetime.now(timezone.utc) + timedelta(days=expire_days)

def validate_password_policy(password: str) -> None:
    reasons = []

    if len(password) < 8:
        reasons.append({"field": "password", "reason": "min_length_8"})
    if not re.search(r"[A-Za-z]", password):
        reasons.append({"field": "password", "reason": "must_include_letter"})
    if not re.search(r"\d", password):
        reasons.append({"field": "password", "reason": "must_include_number"})
    if not re.search(r"[^\w\s]", password):
        reasons.append({"field": "password", "reason": "must_include_special_char"})

    if reasons:
        raise build_error(
            ErrorCode.VALIDATION_ERROR,
            "password does not meet policy",
            details=reasons,
        )