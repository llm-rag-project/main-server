from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# =========================
# ENUMS
# =========================


# =========================
# CREATE CHAT
# =========================

class ChatCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    keyword_id: Optional[int] = Field(default=None, ge=1)
    
class ChatCreateResponse(BaseModel):
    id: int
    title: Optional[str]
    created_at: datetime


# =========================
# LIST
# =========================

class ChatListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    q: Optional[str] = None
    keyword_id: Optional[int] = Field(default=None, ge=1)
    
class PageInfo(BaseModel):
    page: int
    size: int
    total: int
    has_next: bool


class ChatListItem(BaseModel):
    id: int
    keyword_id: Optional[int] = None
    title: Optional[str]
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    created_at: datetime


class ChatListResponse(BaseModel):
    items: List[ChatListItem]
    page_info: PageInfo


class ChatMessageItem(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime


# =========================
# DETAIL (❗ 메시지 제거됨)
# =========================

class ChatDetailResponse(BaseModel):
    id: int
    keyword_id: Optional[int] = None
    title: Optional[str]
    external_conversation_id: Optional[str]
    last_message: Optional[str]
    last_message_at: Optional[datetime]
    created_at: datetime
    messages: List[ChatMessageItem] = Field(default_factory=list)


# =========================
# SEND MESSAGE
# =========================

class ChatSendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None
    article_ids: Optional[List[int]] = None


class ChatSendMessageResponse(BaseModel):
    answer: str
    conversation_id: Optional[str]
    created_at: datetime
