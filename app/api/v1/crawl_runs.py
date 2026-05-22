from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.job_store import complete_job, create_job, fail_job
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.models.user import User
from app.services.analysis_service import AnalysisService
from app.services.crawl_run_service import CrawlRunService

router = APIRouter(prefix="/crawl-runs", tags=["crawl-runs"])


class CreateCrawlRunRequest(BaseModel):
    keyword_ids: list[int] | None = None
    force: bool = False


@router.post("")
async def create_crawl_run(
    request: Request,
    body: CreateCrawlRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = CrawlRunService(db=db, transnews_client=TransNewsClient())

    try:
        result = await service.create_crawl_run(
            user_id=current_user.id,
            keyword_ids=body.keyword_ids,
            force=body.force,
        )
    except TransNewsClientError as e:
        raise build_error(ErrorCode.UPSTREAM_ERROR, str(e))

    return success_response(request, status_code=202, data=result)


class RunAnalysisRequest(BaseModel):
    job_id: str | None = None


@router.get("/analysis/pending")
async def get_pending_analysis_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    """미분석 기사 수를 반환합니다."""
    count = await AnalysisService(db).get_unanalyzed_count()
    return success_response(request, data={"pending_count": count})


@router.post("/analysis")
async def run_analysis(
    request: Request,
    body: RunAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    """미분석 기사에 대해 AI 감성/홍보성 분석을 수동으로 실행합니다."""
    job_id = body.job_id
    if job_id:
        create_job("article_analysis", job_id=job_id)
    try:
        result = await AnalysisService(db).run_analysis(job_id=job_id)
        if job_id:
            complete_job(job_id, result)
        return success_response(request, data=result)
    except Exception as e:
        if job_id:
            fail_job(job_id, str(e))
        raise
