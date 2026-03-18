from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class ArticleLanguage(str, Enum):
    ko = "ko"
    en = "en"


class ArticleSort(str, Enum):
    published_at_desc = "published_at_desc"
    published_at_asc = "published_at_asc"
    importance_desc = "importance_desc"
    importance_asc = "importance_asc"


class ArticleListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    keyword_id: Optional[int] = Field(default=None, ge=1)
    q: Optional[str] = None
    language: Optional[ArticleLanguage] = None
    from_date: Optional[date] = Field(default=None, alias="from")
    to_date: Optional[date] = Field(default=None, alias="to")
    min_importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    has_feedback: Optional[bool] = None
    liked: Optional[bool] = None
    sort: ArticleSort = ArticleSort.published_at_desc

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("'from' must be less than or equal to 'to'")
        if (
            self.min_importance is not None
            and self.max_importance is not None
            and self.min_importance > self.max_importance
        ):
            raise ValueError("'min_importance' must be less than or equal to 'max_importance'")
        return self


class ArticleListItem(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    url: str
    source: Optional[str]
    language: str
    published_at: Optional[datetime]
    keyword_id: Optional[int]
    importance: Optional[float]
    is_liked: bool
    has_feedback: bool


class ArticleDetailResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    content: Optional[str]
    url: str
    source: Optional[str]
    language: str
    published_at: Optional[datetime]
    keyword_id: Optional[int]
    importance: Optional[float]
    is_liked: bool
    has_feedback: bool
    created_at: datetime


class PageInfo(BaseModel):
    page: int
    size: int
    total: int
    has_next: bool


class ArticleListResponse(BaseModel):
    items: List[ArticleListItem]
    page_info: PageInfo
    
class FeedbackAction(str, Enum):
    LIKE = "LIKE"
    DISLIKE = "DISLIKE"


class ArticleImportanceResponse(BaseModel):
    article_id: int
    status: str
    score: Optional[float]
    model: Optional[str]
    scored_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ArticleFeedbackRequest(BaseModel):
    action: FeedbackAction


class ArticleFeedbackResponse(BaseModel):
    article_id: int
    action: str
    created: bool
    updated_at: datetime