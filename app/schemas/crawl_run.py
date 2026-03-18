from datetime import datetime
from pydantic import BaseModel, Field


class CreateCrawlRunRequest(BaseModel):
    keyword_ids: list[int] | None = None
    force: bool = False


class CreateCrawlRunResponse(BaseModel):
    crawl_run_id: int
    status: str


class CrawlRunDetailResponse(BaseModel):
    id: int
    status: str
    keyword_count: int
    article_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime