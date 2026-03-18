from app.core.errors import build_error, ErrorCode
from app.models.user import User
from app.repositories.crawl_run_repository import (
    add_crawl_run_keywords,
    create_crawl_run,
    get_crawl_run_by_id,
)
from app.repositories.keyword_repository import (
    get_all_active_keywords_for_user,
    get_keywords_by_ids_for_user,
)
from app.schemas.crawl_run import (
    CreateCrawlRunResponse,
    CrawlRunDetailResponse,
)


async def request_crawl_run(
    db,
    current_user: User,
    *,
    keyword_ids: list[int] | None = None,
    force: bool = False,
) -> CreateCrawlRunResponse:
    if keyword_ids:
        keywords = await get_keywords_by_ids_for_user(
            db=db,
            user_id=current_user.id,
            keyword_ids=keyword_ids,
        )

        if len(keywords) != len(set(keyword_ids)):
            raise build_error(
                ErrorCode.VALIDATION_ERROR,
                "keyword_ids is invalid",
            )
    else:
        keywords = await get_all_active_keywords_for_user(
            db=db,
            user_id=current_user.id,
        )

    if not keywords:
        raise build_error(
            ErrorCode.VALIDATION_ERROR,
            "keyword_ids is invalid",
        )

    run = await create_crawl_run(
        db=db,
        user_id=current_user.id,
        force_run=force,
    )

    await add_crawl_run_keywords(
        db=db,
        crawl_run_id=run.id,
        keyword_ids=[k.id for k in keywords],
    )

    # 여기서 실제 큐 작업 enqueue가 들어갈 자리
    # ex) Celery / RQ / Dramatiq / BackgroundTasks
    await db.commit()

    return CreateCrawlRunResponse(
        crawl_run_id=run.id,
        status=run.status,
    )


async def get_crawl_run_detail(
    db,
    current_user: User,
    *,
    run_id: int,
) -> CrawlRunDetailResponse:
    run = await get_crawl_run_by_id(db, run_id)

    if run is None:
        raise build_error(
            ErrorCode.NOT_FOUND,
            "crawl run not found",
        )

    if run.user_id != current_user.id:
        raise build_error(
            ErrorCode.FORBIDDEN,
            "You do not have permission to access this crawl run",
        )

    return CrawlRunDetailResponse(
        id=run.id,
        status=run.status,
        keyword_count=len(run.run_keywords),
        article_count=run.article_count,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
    )