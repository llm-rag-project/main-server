from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator


class ImportanceStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ImportanceSort(str, Enum):
    scored_at_desc = "scored_at_desc"
    scored_at_asc = "scored_at_asc"
    score_desc = "score_desc"
    score_asc = "score_asc"


class ImportanceListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    keyword_id: Optional[int] = Field(default=None, ge=1)
    from_date: Optional[date] = Field(default=None, alias="from")
    to_date: Optional[date] = Field(default=None, alias="to")
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    status: Optional[ImportanceStatus] = None
    sort: ImportanceSort = ImportanceSort.scored_at_desc

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("'from' must be less than or equal to 'to'")
        if self.min_score is not None and self.max_score is not None and self.min_score > self.max_score:
            raise ValueError("'min_score' must be less than or equal to 'max_score'")
        return self


class ImportanceListItem(BaseModel):
    article_id: int
    title: str
    url: str
    keyword_id: Optional[int]
    score: Optional[float]
    status: str
    scored_at: Optional[datetime]
    created_at: datetime


class PageInfo(BaseModel):
    page: int
    size: int
    total: int
    has_next: bool


class ImportanceListResponse(BaseModel):
    items: List[ImportanceListItem]
    page_info: PageInfo