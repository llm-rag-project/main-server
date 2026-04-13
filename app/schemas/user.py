from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr


class LanguageEnum(str, Enum):
    ko = "ko"
    en = "en"


class MeResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    created_at: datetime | None = None


class UpdateMeRequest(BaseModel):
    name: str | None = None
    default_language: LanguageEnum | None = None


class UpdateMeResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    default_language: LanguageEnum
    updated_at: datetime