from pydantic import BaseModel
from typing import Optional

#ai서비스 관련 프론트에서 받을 요청/응답 모델들

class AIChatRequest(BaseModel):
    message: str
    article_id: Optional[int] = None
    conversation_id: Optional[str] = ""


class AIChatResponse(BaseModel):
    answer: str
    conversation_id: Optional[str] = None


class SummaryRequest(BaseModel):
    article_id: int
    job_id: Optional[str] = None  # 프론트에서 미리 생성한 UUID (진행률 폴링용)


class SummaryResponse(BaseModel):
    article_id: int
    summary_text: str
    language: str
    model_name: str


class ImportanceBatchRequest(BaseModel):
    keyword_id: int


class ImportanceItemResponse(BaseModel):
    article_id: int
    score: float
    reason: Optional[str] = None


class ImportanceBatchResponse(BaseModel):
    keyword_id: int
    processed_count: int
    results: list[ImportanceItemResponse]