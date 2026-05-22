import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.job_store import complete_job, create_job, fail_job
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.analysis_service import AnalysisService
from app.services.crawl_run_service import CrawlRunService

logger = logging.getLogger(__name__)

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


async def _run_analysis_bg(job_id: str) -> None:
    """HTTP 응답 후 백그라운드에서 실행되는 분석 태스크."""
    async with AsyncSessionLocal() as db:
        try:
            result = await AnalysisService(db).run_analysis(job_id=job_id)
            complete_job(job_id, result)
        except Exception as e:
            logger.exception("백그라운드 분석 실패: %s", e)
            fail_job(job_id, str(e))


@router.get("/analysis/pending")
async def get_pending_analysis_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    """미분석·분석실패 기사 수를 반환합니다."""
    count = await AnalysisService(db).get_unanalyzed_count()
    return success_response(request, data={"pending_count": count})


@router.post("/analysis")
async def run_analysis(
    request: Request,
    body: RunAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    """미분석 기사에 대해 AI 감성/홍보성 분석을 백그라운드로 실행합니다."""
    job_id = body.job_id or str(__import__("uuid").uuid4())
    create_job("article_analysis", job_id=job_id)
    background_tasks.add_task(_run_analysis_bg, job_id)
    return success_response(
        request,
        status_code=202,
        data={"job_id": job_id, "message": "분석이 시작되었습니다."},
    )
