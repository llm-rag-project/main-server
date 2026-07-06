from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class LanguageEnum(str, Enum):
    ko = "ko"
    en = "en"


class KeywordSettings(BaseModel):
    client_name: str | None = None
    group_name: str | None = None
    monitoring_type: str = Field(default="brand", pattern=r"^(brand|competitor|campaign|issue)$")
    priority_level: str = Field(default="normal", pattern=r"^(low|normal|high|critical)$")
    crawl_interval_minutes: int = Field(default=1440, ge=10, le=43200)
    crawl_limit: int = Field(default=10, ge=1, le=100)
    email_auto_send: bool = False
    email_recipients: list[EmailStr] = Field(default_factory=list)
    email_send_time: str = Field(default="08:30", pattern=r"^\d{2}:\d{2}$")
    email_condition_type: str = Field(default="daily_summary", pattern=r"^(daily_summary|risk_only|negative_or_risk|activity_threshold)$")
    alert_negative_rate_threshold: int = Field(default=25, ge=0, le=100)
    alert_importance_threshold: int = Field(default=80, ge=0, le=100)
    alert_article_count_threshold: int = Field(default=10, ge=1, le=1000)
    importance_criteria: str | None = Field(default=None, max_length=3000)


class CreateKeywordRequest(KeywordSettings):
    keyword: str = Field(..., min_length=1)
    language: LanguageEnum | None = None


class KeywordResponse(KeywordSettings):
    id: int
    keyword: str
    language: LanguageEnum
    is_active: bool
    created_at: datetime


class KeywordListItem(KeywordResponse):
    pass


class PageInfo(BaseModel):
    page: int
    size: int
    total: int
    has_next: bool


class KeywordListResponse(BaseModel):
    items: list[KeywordListItem]
    page_info: PageInfo


class UpdateKeywordStatusRequest(BaseModel):
    is_active: bool | None = None
    keyword: str | None = Field(default=None, min_length=1)
    client_name: str | None = None
    group_name: str | None = None
    monitoring_type: str | None = Field(default=None, pattern=r"^(brand|competitor|campaign|issue)$")
    priority_level: str | None = Field(default=None, pattern=r"^(low|normal|high|critical)$")
    crawl_interval_minutes: int | None = Field(default=None, ge=10, le=43200)
    crawl_limit: int | None = Field(default=None, ge=1, le=100)
    email_auto_send: bool | None = None
    email_recipients: list[EmailStr] | None = None
    email_send_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    email_condition_type: str | None = Field(default=None, pattern=r"^(daily_summary|risk_only|negative_or_risk|activity_threshold)$")
    alert_negative_rate_threshold: int | None = Field(default=None, ge=0, le=100)
    alert_importance_threshold: int | None = Field(default=None, ge=0, le=100)
    alert_article_count_threshold: int | None = Field(default=None, ge=1, le=1000)
    importance_criteria: str | None = Field(default=None, max_length=3000)


class UpdateKeywordStatusResponse(KeywordSettings):
    id: int
    keyword: str
    language: LanguageEnum
    is_active: bool
    updated_at: datetime


class DeleteKeywordResponse(BaseModel):
    deleted: bool
    keyword_id: int
    keyword: str
    cleanup_summary: list[str]
    dify_deleted_count: int = 0
    dify_failed_count: int = 0
    dify_failed_items: list[dict] = Field(default_factory=list)


class BatchCreateKeywordRequest(KeywordSettings):
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
