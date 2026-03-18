from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class ArticleFeedbackGetResponse(BaseModel):
    article_id: int
    action: str
    created_at: datetime
    updated_at: datetime


class DeleteFeedbackResponse(BaseModel):
    deleted: bool
    article_id: int


class RankingFeedbackRequest(BaseModel):
    article_ids: List[int] = Field(..., min_length=1)
    keyword_id: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_article_ids(self):
        if not self.article_ids:
            raise ValueError("article_ids must not be empty")

        if len(set(self.article_ids)) != len(self.article_ids):
            raise ValueError("article_ids must not contain duplicates")

        return self


class RankingFeedbackResponse(BaseModel):
    saved: bool
    count: int
    created_at: datetime