import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.schemas.keyword import (
    BatchCreateKeywordRequest,
    CreateKeywordRequest,
    UpdateKeywordStatusRequest,
)
from app.services.crawl_run_service import CrawlRunService
from app.services.auto_ai_service import AutoAiService
from app.services.keyword_service import (
    batch_create_user_keywords,
    create_user_keyword,
    get_my_keywords,
    patch_keyword_is_active,
    remove_keyword,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/keywords", tags=["keywords"])


async def _run_auto_ai_bg(user_id: int, crawl_run_id: int) -> None:
    try:
        async with AsyncSessionLocal() as db:
            result = await AutoAiService(db).run_for_crawl_run(
                user_id=user_id,
                crawl_run_id=crawl_run_id,
            )
            logger.info("auto ai completed user_id=%s crawl_run_id=%s result=%s", user_id, crawl_run_id, result)
    except Exception:
        logger.exception("auto ai failed user_id=%s crawl_run_id=%s", user_id, crawl_run_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_keyword_api(
    request: Request,
    payload: CreateKeywordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await create_user_keyword(
        db=db,
        current_user=current_user,
        keyword=payload.keyword,
        language=payload.language,
        dashboard_mode=payload.dashboard_mode,
        client_name=payload.client_name,
        group_name=payload.group_name,
        monitoring_type=payload.monitoring_type,
        priority_level=payload.priority_level,
        crawl_interval_minutes=payload.crawl_interval_minutes,
        crawl_limit=payload.crawl_limit,
        email_auto_send=payload.email_auto_send,
        email_recipients=payload.email_recipients,
        email_send_time=payload.email_send_time,
        email_condition_type=payload.email_condition_type,
        alert_negative_rate_threshold=payload.alert_negative_rate_threshold,
        alert_importance_threshold=payload.alert_importance_threshold,
        alert_article_count_threshold=payload.alert_article_count_threshold,
        importance_criteria=payload.importance_criteria,
    )

    crawl_service = CrawlRunService(db=db, transnews_client=TransNewsClient())
    crawl_result = await crawl_service.create_crawl_run(
        user_id=current_user.id,
        keyword_ids=[data.id],
        force=False,
    )
    if crawl_result.get("crawl_run_id"):
        background_tasks.add_task(_run_auto_ai_bg, current_user.id, crawl_result["crawl_run_id"])
    logger.debug("created keyword id = %s", data.id)
    logger.debug("crawl_result = %s", crawl_result)

    return success_response(
        request,
        data={
            "keyword": data.model_dump(),
            "crawl_result": crawl_result,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def get_keyword_list_api(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    language: str | None = Query(None),
    q: str | None = Query(None),
    dashboard_mode: str | None = Query(None, pattern=r"^(general|dongguk)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await get_my_keywords(
        db=db,
        current_user=current_user,
        page=page,
        size=size,
        is_active=is_active,
        language=language,
        q=q,
        dashboard_mode=dashboard_mode,
    )
    return success_response(request, data=data.model_dump())


@router.patch("/{keyword_id}")
async def update_keyword_status_api(
    request: Request,
    keyword_id: int,
    payload: UpdateKeywordStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await patch_keyword_is_active(
        db=db,
        current_user=current_user,
        keyword_id=keyword_id,
        is_active=payload.is_active,
        keyword_text=payload.keyword,
        dashboard_mode=payload.dashboard_mode,
        client_name=payload.client_name,
        group_name=payload.group_name,
        monitoring_type=payload.monitoring_type,
        priority_level=payload.priority_level,
        crawl_interval_minutes=payload.crawl_interval_minutes,
        crawl_limit=payload.crawl_limit,
        email_auto_send=payload.email_auto_send,
        email_recipients=payload.email_recipients,
        email_send_time=payload.email_send_time,
        email_condition_type=payload.email_condition_type,
        alert_negative_rate_threshold=payload.alert_negative_rate_threshold,
        alert_importance_threshold=payload.alert_importance_threshold,
        alert_article_count_threshold=payload.alert_article_count_threshold,
        importance_criteria=payload.importance_criteria,
    )
    return success_response(request, data=data.model_dump())


@router.delete("/{keyword_id}")
async def delete_keyword_api(
    request: Request,
    keyword_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await remove_keyword(
        db=db,
        current_user=current_user,
        keyword_id=keyword_id,
    )
    return success_response(request, data=data.model_dump())


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def batch_create_keywords_api(
    request: Request,
    payload: BatchCreateKeywordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await batch_create_user_keywords(
        db=db,
        current_user=current_user,
        keywords=payload.keywords,
        language=payload.language,
        client_name=payload.client_name,
        group_name=payload.group_name,
        monitoring_type=payload.monitoring_type,
        priority_level=payload.priority_level,
        crawl_interval_minutes=payload.crawl_interval_minutes,
        crawl_limit=payload.crawl_limit,
        email_auto_send=payload.email_auto_send,
        email_recipients=payload.email_recipients,
        email_send_time=payload.email_send_time,
        email_condition_type=payload.email_condition_type,
        alert_negative_rate_threshold=payload.alert_negative_rate_threshold,
        alert_importance_threshold=payload.alert_importance_threshold,
        alert_article_count_threshold=payload.alert_article_count_threshold,
        importance_criteria=payload.importance_criteria,
    )
    return success_response(request, data=data.model_dump(), status_code=status.HTTP_201_CREATED)
