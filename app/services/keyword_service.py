from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import exists, func, or_, select

from app.core.dify_knowledge_client import DifyKnowledgeClient
from app.core.errors import ErrorCode, build_error
from app.models.article import Article
from app.models.dify_knowledge_document import DifyKnowledgeDocument
from app.models.dongguk_article_trash import DonggukArticleTrash
from app.models.article_match import ArticleMatch
from app.models.user import User
from app.repositories.keyword_repository import (
    create_keyword,
    delete_keyword,
    get_keyword_by_id,
    get_keyword_by_text,
    list_user_keywords,
    update_keyword_settings,
    update_keyword_is_active,
)
from app.schemas.keyword import (
    BatchCreateKeywordResponse,
    BatchKeywordItemResult,
    BatchKeywordItemStatus,
    DeleteKeywordResponse,
    KeywordListItem,
    KeywordListResponse,
    KeywordResponse,
    PageInfo,
    UpdateKeywordStatusResponse,
)

KST = ZoneInfo("Asia/Seoul")


def _parse_send_time(value: str | None) -> tuple[int, int]:
    try:
        hour_text, minute_text = (value or "08:30")[:5].split(":")
        return max(0, min(23, int(hour_text))), max(0, min(59, int(minute_text)))
    except Exception:
        return 8, 30


def _pack_recipients(recipients: list[str] | None) -> str | None:
    if not recipients:
        return None
    cleaned = [email.strip() for email in recipients if email and email.strip()]
    return "\n".join(cleaned) if cleaned else None


def _unpack_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [email.strip() for email in value.replace(",", "\n").splitlines() if email.strip()]


def _keyword_settings(item) -> dict:
    return {
        "dashboard_mode": item.dashboard_mode,
        "client_name": item.client_name,
        "group_name": item.group_name,
        "monitoring_type": item.monitoring_type,
        "priority_level": item.priority_level,
        "crawl_interval_minutes": item.crawl_interval_minutes,
        "crawl_limit": item.crawl_limit,
        "email_auto_send": item.email_auto_send,
        "email_recipients": _unpack_recipients(item.email_recipients),
        "email_send_time": item.email_send_time,
        "email_condition_type": item.email_condition_type,
        "alert_negative_rate_threshold": item.alert_negative_rate_threshold,
        "alert_importance_threshold": item.alert_importance_threshold,
        "alert_article_count_threshold": item.alert_article_count_threshold,
        "importance_criteria": item.importance_criteria,
    }


async def create_user_keyword(
    db: AsyncSession,
    current_user: User,
    keyword: str,
    language: str | None = None,
    dashboard_mode: str = "general",
    client_name: str | None = None,
    group_name: str | None = None,
    monitoring_type: str = "brand",
    priority_level: str = "normal",
    crawl_interval_minutes: int = 1440,
    crawl_limit: int = 10,
    email_auto_send: bool = False,
    email_recipients: list[str] | None = None,
    email_send_time: str = "08:30",
    email_condition_type: str = "daily_summary",
    alert_negative_rate_threshold: int = 25,
    alert_importance_threshold: int = 80,
    alert_article_count_threshold: int = 10,
    importance_criteria: str | None = None,
) -> KeywordResponse:
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        raise build_error(
            ErrorCode.VALIDATION_ERROR,
            "keyword is required",
            details=[{"field": "keyword", "reason": "required"}],
        )

    existing_keyword = await get_keyword_by_text(
        db=db,
        user_id=current_user.id,
        keyword_text=normalized_keyword,
    )
    if existing_keyword is not None:
        raise build_error(
            ErrorCode.CONFLICT_DUPLICATE,
            "keyword already exists",
        )

    final_language = language or current_user.default_language

    created_keyword = await create_keyword(
        db=db,
        user_id=current_user.id,
        keyword_text=normalized_keyword,
        language=final_language,
        dashboard_mode=dashboard_mode,
        client_name=client_name.strip() if client_name else None,
        group_name=group_name.strip() if group_name else None,
        monitoring_type=monitoring_type,
        priority_level=priority_level,
        crawl_interval_minutes=crawl_interval_minutes,
        crawl_limit=crawl_limit,
        email_auto_send=email_auto_send,
        email_recipients=_pack_recipients(email_recipients),
        email_send_time=email_send_time,
        email_condition_type=email_condition_type,
        alert_negative_rate_threshold=alert_negative_rate_threshold,
        alert_importance_threshold=alert_importance_threshold,
        alert_article_count_threshold=alert_article_count_threshold,
        importance_criteria=importance_criteria.strip() if importance_criteria else None,
    )

    await db.commit()

    return KeywordResponse(
        id=created_keyword.id,
        keyword=created_keyword.keyword_text,
        language=created_keyword.language,
        is_active=created_keyword.is_active,
        **_keyword_settings(created_keyword),
        created_at=created_keyword.created_at,
    )


async def get_my_keywords(
    db: AsyncSession,
    current_user: User,
    *,
    page: int,
    size: int,
    is_active: bool | None = None,
    language: str | None = None,
    q: str | None = None,
    dashboard_mode: str | None = None,
) -> KeywordListResponse:
    items, total = await list_user_keywords(
        db=db,
        user_id=current_user.id,
        page=page,
        size=size,
        is_active=is_active,
        language=language,
        q=q,
        dashboard_mode=dashboard_mode,
    )
    keyword_ids = [item.id for item in items]
    article_counts: dict[int, int] = {}
    if keyword_ids:
        today = datetime.now(KST).date()
        today_start = datetime.combine(today, time.min, tzinfo=KST)
        today_end = datetime.combine(today, time.max, tzinfo=KST)
        if dashboard_mode == "dongguk":
            for item in items:
                hour, minute = _parse_send_time(item.email_send_time)
                window_start = datetime.combine(today - timedelta(days=1), time(hour, minute), tzinfo=KST)
                window_end = datetime.combine(today, time(hour, minute), tzinfo=KST)
                result = await db.execute(
                    select(func.count(func.distinct(Article.id)))
                    .select_from(ArticleMatch)
                    .join(Article, Article.id == ArticleMatch.article_id)
                    .where(ArticleMatch.keyword_id == item.id)
                    .where(
                        ~exists(
                            select(DonggukArticleTrash.id).where(
                                DonggukArticleTrash.user_id == current_user.id,
                                DonggukArticleTrash.keyword_id == ArticleMatch.keyword_id,
                                DonggukArticleTrash.mail_date == today.isoformat(),
                                DonggukArticleTrash.article_id == Article.id,
                            )
                        )
                    )
                    .where(
                        or_(
                            Article.published_at.between(window_start, window_end),
                            ArticleMatch.matched_at.between(today_start, today_end),
                        )
                    )
                )
                article_counts[item.id] = int(result.scalar_one() or 0)
        else:
            result = await db.execute(
                select(ArticleMatch.keyword_id, func.count(func.distinct(ArticleMatch.article_id)))
                .where(ArticleMatch.keyword_id.in_(keyword_ids))
                .where(ArticleMatch.matched_at >= today_start)
                .group_by(ArticleMatch.keyword_id)
            )
            article_counts = {int(keyword_id): int(count) for keyword_id, count in result.all()}

    return KeywordListResponse(
        items=[
            KeywordListItem(
                id=item.id,
                keyword=item.keyword_text,
                language=item.language,
                is_active=item.is_active,
                article_count=article_counts.get(item.id, 0),
                **_keyword_settings(item),
                created_at=item.created_at,
            )
            for item in items
        ],
        page_info=PageInfo(
            page=page,
            size=size,
            total=total,
            has_next=(page * size) < total,
        ),
    )


async def patch_keyword_is_active(
    db: AsyncSession,
    current_user: User,
    *,
    keyword_id: int,
    is_active: bool | None = None,
    keyword_text: str | None = None,
    dashboard_mode: str | None = None,
    client_name: str | None = None,
    group_name: str | None = None,
    monitoring_type: str | None = None,
    priority_level: str | None = None,
    crawl_interval_minutes: int | None = None,
    crawl_limit: int | None = None,
    email_auto_send: bool | None = None,
    email_recipients: list[str] | None = None,
    email_send_time: str | None = None,
    email_condition_type: str | None = None,
    alert_negative_rate_threshold: int | None = None,
    alert_importance_threshold: int | None = None,
    alert_article_count_threshold: int | None = None,
    importance_criteria: str | None = None,
) -> UpdateKeywordStatusResponse:
    keyword = await get_keyword_by_id(db, keyword_id)

    if keyword is None:
        raise build_error(
            ErrorCode.NOT_FOUND,
            "keyword not found",
        )

    if keyword.user_id != current_user.id:
        raise build_error(
            ErrorCode.FORBIDDEN,
            "You do not have permission to modify this keyword",
        )

    updated_keyword = keyword

    settings_changed = any(
        value is not None
        for value in (
            keyword_text,
            dashboard_mode,
            client_name,
            group_name,
            monitoring_type,
            priority_level,
            crawl_interval_minutes,
            crawl_limit,
            email_auto_send,
            email_recipients,
            email_send_time,
            email_condition_type,
            alert_negative_rate_threshold,
            alert_importance_threshold,
            alert_article_count_threshold,
            importance_criteria,
        )
    )

    if settings_changed:
        normalized_keyword = keyword_text.strip() if keyword_text is not None else keyword.keyword_text
        if not normalized_keyword:
            raise build_error(
                ErrorCode.VALIDATION_ERROR,
                "keyword is required",
                details=[{"field": "keyword", "reason": "required"}],
            )

        existing_keyword = await get_keyword_by_text(
            db=db,
            user_id=current_user.id,
            keyword_text=normalized_keyword,
        )
        if existing_keyword is not None and existing_keyword.id != keyword.id:
            raise build_error(
                ErrorCode.CONFLICT_DUPLICATE,
                "keyword already exists",
            )

        updated_keyword = await update_keyword_settings(
            db=db,
            keyword=keyword,
            keyword_text=normalized_keyword,
            dashboard_mode=dashboard_mode or keyword.dashboard_mode,
            client_name=client_name.strip() if client_name else None,
            group_name=group_name.strip() if group_name else None,
            monitoring_type=monitoring_type or keyword.monitoring_type,
            priority_level=priority_level or keyword.priority_level,
            crawl_interval_minutes=crawl_interval_minutes or keyword.crawl_interval_minutes,
            crawl_limit=crawl_limit or keyword.crawl_limit,
            email_auto_send=keyword.email_auto_send if email_auto_send is None else email_auto_send,
            email_recipients=keyword.email_recipients if email_recipients is None else _pack_recipients(email_recipients),
            email_send_time=email_send_time or keyword.email_send_time,
            email_condition_type=email_condition_type or keyword.email_condition_type,
            alert_negative_rate_threshold=alert_negative_rate_threshold if alert_negative_rate_threshold is not None else keyword.alert_negative_rate_threshold,
            alert_importance_threshold=alert_importance_threshold if alert_importance_threshold is not None else keyword.alert_importance_threshold,
            alert_article_count_threshold=alert_article_count_threshold if alert_article_count_threshold is not None else keyword.alert_article_count_threshold,
            importance_criteria=importance_criteria.strip() if importance_criteria is not None and importance_criteria.strip() else None if importance_criteria is not None else keyword.importance_criteria,
        )

    if is_active is not None:
        updated_keyword = await update_keyword_is_active(
            db=db,
            keyword=updated_keyword,
            is_active=is_active,
        )
    await db.commit()

    return UpdateKeywordStatusResponse(
        id=updated_keyword.id,
        keyword=updated_keyword.keyword_text,
        language=updated_keyword.language,
        is_active=updated_keyword.is_active,
        **_keyword_settings(updated_keyword),
        updated_at=updated_keyword.updated_at,
    )


async def remove_keyword(
    db: AsyncSession,
    current_user: User,
    *,
    keyword_id: int,
) -> DeleteKeywordResponse:
    keyword = await get_keyword_by_id(db, keyword_id)

    if keyword is None:
        raise build_error(
            ErrorCode.NOT_FOUND,
            "keyword not found",
        )

    if keyword.user_id != current_user.id:
        raise build_error(
            ErrorCode.FORBIDDEN,
            "You do not have permission to delete this keyword",
        )

    deleted_keyword_text = keyword.keyword_text
    dify_deleted_count = 0
    dify_failed_items: list[dict] = []

    refs_result = await db.execute(
        select(DifyKnowledgeDocument).where(
            DifyKnowledgeDocument.user_id == current_user.id,
            DifyKnowledgeDocument.keyword_id == keyword_id,
            DifyKnowledgeDocument.status == "UPLOADED",
        )
    )
    dify_refs = list(refs_result.scalars().all())
    if dify_refs:
        try:
            dify_client = DifyKnowledgeClient()
        except Exception as exc:
            dify_client = None
            for ref in dify_refs:
                ref.status = "DELETE_FAILED"
                ref.delete_error = f"Dify client unavailable: {exc}"
            dify_failed_items = [
                {
                    "document_id": ref.document_id,
                    "article_id": ref.article_id,
                    "error": f"Dify client unavailable: {exc}",
                }
                for ref in dify_refs
            ]

        if dify_client:
            for ref in dify_refs:
                try:
                    await dify_client.delete_document(document_id=ref.document_id)
                    ref.status = "DELETED"
                    ref.delete_error = None
                    dify_deleted_count += 1
                except Exception as exc:
                    ref.status = "DELETE_FAILED"
                    ref.delete_error = str(exc)
                    dify_failed_items.append(
                        {
                            "document_id": ref.document_id,
                            "article_id": ref.article_id,
                            "error": str(exc),
                        }
                    )

    cleanup_summary = [
        "키워드 목차에서 제거",
        "자동 수집 및 예약 이메일 대상에서 제외",
        f"Dify 지식 문서 {dify_deleted_count}건 삭제",
        "키워드-기사 매칭, 크롤링 실행 연결, SNS 지표 연결 정리",
        "기사 원문과 기존 AI 분석 결과는 공유 데이터일 수 있어 보존",
    ]
    if dify_failed_items:
        cleanup_summary.append(f"Dify 지식 문서 {len(dify_failed_items)}건은 삭제 실패로 기록")

    await delete_keyword(db, keyword)
    await db.commit()

    return DeleteKeywordResponse(
        deleted=True,
        keyword_id=keyword_id,
        keyword=deleted_keyword_text,
        cleanup_summary=cleanup_summary,
        dify_deleted_count=dify_deleted_count,
        dify_failed_count=len(dify_failed_items),
        dify_failed_items=dify_failed_items,
    )


async def batch_create_user_keywords(
    db: AsyncSession,
    current_user: User,
    *,
    keywords: list[str],
    language: str | None = None,
    crawl_interval_minutes: int = 1440,
    crawl_limit: int = 10,
    email_auto_send: bool = False,
    email_recipients: list[str] | None = None,
    email_send_time: str = "08:30",
    email_condition_type: str = "daily_summary",
    alert_negative_rate_threshold: int = 25,
    alert_importance_threshold: int = 80,
    alert_article_count_threshold: int = 10,
    client_name: str | None = None,
    group_name: str | None = None,
    monitoring_type: str = "brand",
    priority_level: str = "normal",
    dashboard_mode: str = "general",
    importance_criteria: str | None = None,
) -> BatchCreateKeywordResponse:
    final_language = language or current_user.default_language

    seen_in_request: set[str] = set()
    created_count = 0
    skipped_count = 0
    results: list[BatchKeywordItemResult] = []

    for raw_keyword in keywords:
        if not isinstance(raw_keyword, str):
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=str(raw_keyword),
                    status=BatchKeywordItemStatus.FAILED_VALIDATION,
                    reason="keyword must be a string",
                )
            )
            continue

        normalized_keyword = raw_keyword.strip()
        normalized_key = normalized_keyword.lower()

        if not normalized_keyword:
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=raw_keyword,
                    status=BatchKeywordItemStatus.FAILED_VALIDATION,
                    reason="keyword is required",
                )
            )
            continue

        if normalized_key in seen_in_request:
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=normalized_keyword,
                    status=BatchKeywordItemStatus.SKIPPED_DUPLICATE,
                    reason="duplicate keyword in request",
                )
            )
            continue

        seen_in_request.add(normalized_key)

        existing_keyword = await get_keyword_by_text(
            db=db,
            user_id=current_user.id,
            keyword_text=normalized_keyword,
        )
        if existing_keyword is not None:
            skipped_count += 1
            results.append(
                BatchKeywordItemResult(
                    keyword=normalized_keyword,
                    status=BatchKeywordItemStatus.SKIPPED_ALREADY_EXISTS,
                    id=existing_keyword.id,
                    reason="keyword already exists",
                )
            )
            continue

        created_keyword = await create_keyword(
            db=db,
            user_id=current_user.id,
            keyword_text=normalized_keyword,
            language=final_language,
            dashboard_mode=dashboard_mode,
            client_name=client_name.strip() if client_name else None,
            group_name=group_name.strip() if group_name else None,
            monitoring_type=monitoring_type,
            priority_level=priority_level,
            crawl_interval_minutes=crawl_interval_minutes,
            crawl_limit=crawl_limit,
            email_auto_send=email_auto_send,
            email_recipients=_pack_recipients(email_recipients),
            email_send_time=email_send_time,
            email_condition_type=email_condition_type,
            alert_negative_rate_threshold=alert_negative_rate_threshold,
            alert_importance_threshold=alert_importance_threshold,
            alert_article_count_threshold=alert_article_count_threshold,
            importance_criteria=importance_criteria.strip() if importance_criteria else None,
        )
        created_count += 1
        results.append(
            BatchKeywordItemResult(
                keyword=normalized_keyword,
                status=BatchKeywordItemStatus.CREATED,
                id=created_keyword.id,
                reason=None,
            )
        )

    await db.commit()

    return BatchCreateKeywordResponse(
        created_count=created_count,
        skipped_count=skipped_count,
        items=results,
    )
