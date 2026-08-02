import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.job_store import complete_job, create_job, fail_job
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.api.v1.reports import prebuild_dongguk_mail_drafts_for_scheduler
from app.services.analysis_service import AnalysisService
from app.services.auto_ai_service import AutoAiService
from app.services.crawl_run_service import CrawlRunService
from app.services.crawl_health_service import CrawlHealthService

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

router = APIRouter(prefix="/crawl-runs", tags=["crawl-runs"])


class CreateCrawlRunRequest(BaseModel):
    keyword_ids: list[int] | None = None
    force: bool = False
    today_only: bool = False
    from_date: date | None = None
    to_date: date | None = None


class ReplayCrawlRunRequest(BaseModel):
    keyword_id: int
    from_date: date
    to_date: date


@router.post("")
async def create_crawl_run(
    request: Request,
    body: CreateCrawlRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = CrawlRunService(db=db, transnews_client=TransNewsClient())

    try:
        custom_start_at = None
        custom_end_at = None
        if body.from_date or body.to_date:
            if not body.from_date or not body.to_date:
                raise build_error(ErrorCode.VALIDATION_ERROR, "from_date와 to_date를 함께 입력해 주세요.")
            custom_start_at = datetime.combine(body.from_date, time.min, tzinfo=KST)
            custom_end_at = datetime.combine(body.to_date, time.max, tzinfo=KST)
        result = await service.create_crawl_run(
            user_id=current_user.id,
            keyword_ids=body.keyword_ids,
            force=body.force,
            today_only=body.today_only,
            custom_start_at=custom_start_at,
            custom_end_at=custom_end_at,
            discovery_only=True,
            enrich_for_relevance=True,
        )
    except TransNewsClientError as e:
        raise build_error(ErrorCode.UPSTREAM_ERROR, str(e))

    if result.get("crawl_run_id"):
        background_tasks.add_task(_run_auto_ai_for_crawl_bg, current_user.id, result["crawl_run_id"])

    return success_response(request, status_code=202, data=result)


@router.get("/health")
async def get_crawl_health(
    request: Request,
    keyword_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await CrawlHealthService(db).summary(
        user_id=current_user.id,
        keyword_id=keyword_id,
        days=days,
        limit=limit,
    )
    return success_response(request, data=data)


@router.get("/{run_id}/audit")
async def get_crawl_run_audit(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await CrawlHealthService(db).run_detail(
        user_id=current_user.id,
        run_id=run_id,
    )
    if data is None:
        raise build_error(ErrorCode.NOT_FOUND, "수집 실행 기록을 찾을 수 없습니다.")
    return success_response(request, data=data)


@router.post("/replay")
async def replay_crawl_run(
    request: Request,
    body: ReplayCrawlRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    if body.from_date > body.to_date:
        raise build_error(ErrorCode.VALIDATION_ERROR, "시작일은 종료일보다 늦을 수 없습니다.")
    if (body.to_date - body.from_date).days > 31:
        raise build_error(ErrorCode.VALIDATION_ERROR, "한 번에 다시 수집할 수 있는 기간은 최대 31일입니다.")
    result = await CrawlRunService(db=db, transnews_client=TransNewsClient()).create_crawl_run(
        user_id=current_user.id,
        keyword_ids=[body.keyword_id],
        force=True,
        custom_start_at=datetime.combine(body.from_date, time.min, tzinfo=KST),
        custom_end_at=datetime.combine(body.to_date, time.max, tzinfo=KST),
        trigger_type="replay",
        enrich_for_relevance=True,
    )
    if result.get("crawl_run_id"):
        background_tasks.add_task(
            _run_auto_ai_for_crawl_bg,
            current_user.id,
            result["crawl_run_id"],
        )
    return success_response(request, status_code=202, data=result)


class RunAnalysisRequest(BaseModel):
    job_id: str | None = None


async def _run_analysis_bg(job_id: str) -> None:
    """HTTP ?묐떟 ??諛깃렇?쇱슫?쒖뿉???ㅽ뻾?섎뒗 遺꾩꽍 ?쒖뒪??"""
    async with AsyncSessionLocal() as db:
        try:
            result = await AnalysisService(db).run_analysis(job_id=job_id)
            complete_job(job_id, result)
        except Exception as e:
            logger.exception("諛깃렇?쇱슫??遺꾩꽍 ?ㅽ뙣: %s", e)
            fail_job(job_id, str(e))


async def _run_auto_ai_for_crawl_bg(user_id: int, crawl_run_id: int) -> None:
    async with AsyncSessionLocal() as db:
        try:
            result = await AutoAiService(db).run_for_crawl_run(
                user_id=user_id,
                crawl_run_id=crawl_run_id,
            )
            logger.info("?먮룞 ?붿빟/以묒슂??怨꾩궛 ?꾨즺: user_id=%s crawl_run_id=%s result=%s", user_id, crawl_run_id, result)
            prebuild_result = await prebuild_dongguk_mail_drafts_for_scheduler(db, user_id=user_id)
            logger.info("Dongguk mail draft prebuilt after crawl: user_id=%s result=%s", user_id, prebuild_result)
        except Exception:
            logger.exception("?먮룞 ?붿빟/以묒슂??怨꾩궛 ?ㅽ뙣: user_id=%s crawl_run_id=%s", user_id, crawl_run_id)


@router.get("/analysis/pending")
async def get_pending_analysis_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    """誘몃텇?씲룸텇?앹떎??湲곗궗 ?섎? 諛섑솚?⑸땲??"""
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
    """誘몃텇??湲곗궗?????AI 媛먯꽦/?띾낫??遺꾩꽍??諛깃렇?쇱슫?쒕줈 ?ㅽ뻾?⑸땲??"""
    job_id = body.job_id or str(__import__("uuid").uuid4())
    create_job("article_analysis", job_id=job_id)
    background_tasks.add_task(_run_analysis_bg, job_id)
    return success_response(
        request,
        status_code=202,
        data={"job_id": job_id, "message": "遺꾩꽍???쒖옉?섏뿀?듬땲??"},
    )

