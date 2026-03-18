from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class LanguageEnum(str, Enum):
    ko = "ko"
    en = "en"


class CreateKeywordRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    language: LanguageEnum | None = None


class KeywordResponse(BaseModel):
    id: int
    keyword: str
    language: LanguageEnum
    is_active: bool
    created_at: datetime

class KeywordListItem(BaseModel):
    id: int
    keyword: str
    language: LanguageEnum
    is_active: bool
    created_at: datetime


class PageInfo(BaseModel):
    page: int
    size: int
    total: int
    has_next: bool


class KeywordListResponse(BaseModel):
    items: list[KeywordListItem]
    page_info: PageInfo


class UpdateKeywordStatusRequest(BaseModel):
    is_active: bool


class UpdateKeywordStatusResponse(BaseModel):
    id: int
    keyword: str
    language: LanguageEnum
    is_active: bool
    updated_at: datetime


class DeleteKeywordResponse(BaseModel):
    deleted: bool
    keyword_id: int


class BatchCreateKeywordRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1)
    language: LanguageEnum | None = None


class BatchKeywordItemStatus(str, Enum):
    CREATED = "CREATED"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
    SKIPPED_ALREADY_EXISTS = "SKIPPED_ALREADY_EXISTS"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class BatchKeywordItemResult(BaseModel):
    keyword: str
    status: BatchKeywordItemStatus
    id: int | None = None
    reason: str | None = None
    
class KeywordListItem(BaseModel):
    id: int
    keyword: str
    language: LanguageEnum
    is_active: bool
    created_at: datetime


class PageInfo(BaseModel):
    page: int
    size: int
    total: int
    has_next: bool


class KeywordListResponse(BaseModel):
    items: list[KeywordListItem]
    page_info: PageInfo


class UpdateKeywordStatusRequest(BaseModel):
    is_active: bool


class UpdateKeywordStatusResponse(BaseModel):
    id: int
    keyword: str
    language: LanguageEnum
    is_active: bool
    updated_at: datetime


class DeleteKeywordResponse(BaseModel):
    deleted: bool
    keyword_id: int


class BatchCreateKeywordRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1)
    language: LanguageEnum | None = None


class BatchKeywordItemStatus(str, Enum):
    CREATED = "CREATED"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
    SKIPPED_ALREADY_EXISTS = "SKIPPED_ALREADY_EXISTS"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class BatchKeywordItemResult(BaseModel):
    keyword: str
    status: BatchKeywordItemStatus
    id: int | None = None
    reason: str | None = None

class BatchCreateKeywordResponse(BaseModel):
    created_count: int
    skipped_count: int
    items: list[BatchKeywordItemResult]