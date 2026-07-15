from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword import Keyword


async def get_keyword_by_text(
    db: AsyncSession,
    user_id: int,
    keyword_text: str,
) -> Keyword | None:
    result = await db.execute(
        select(Keyword).where(
            Keyword.user_id == user_id,
            func.lower(Keyword.keyword_text) == keyword_text.lower(),
        )
    )
    return result.scalar_one_or_none()


async def create_keyword(
    db: AsyncSession,
    user_id: int,
    keyword_text: str,
    language: str,
    dashboard_mode: str = "general",
    client_name: str | None = None,
    group_name: str | None = None,
    monitoring_type: str = "brand",
    priority_level: str = "normal",
    crawl_interval_minutes: int = 1440,
    crawl_limit: int = 10,
    email_auto_send: bool = False,
    email_recipients: str | None = None,
    email_send_time: str = "08:30",
    email_condition_type: str = "daily_summary",
    alert_negative_rate_threshold: int = 25,
    alert_importance_threshold: int = 80,
    alert_article_count_threshold: int = 10,
    importance_criteria: str | None = None,
) -> Keyword:
    keyword = Keyword(
        user_id=user_id,
        keyword_text=keyword_text,
        language=language,
        dashboard_mode=dashboard_mode,
        is_active=True,
        client_name=client_name,
        group_name=group_name,
        monitoring_type=monitoring_type,
        priority_level=priority_level,
        crawl_interval_minutes=crawl_interval_minutes,
        crawl_limit=crawl_limit,
        email_auto_send=email_auto_send,
        email_recipients=email_recipients,
        email_send_time=email_send_time,
        email_condition_type=email_condition_type,
        alert_negative_rate_threshold=alert_negative_rate_threshold,
        alert_importance_threshold=alert_importance_threshold,
        alert_article_count_threshold=alert_article_count_threshold,
        importance_criteria=importance_criteria,
    )
    db.add(keyword)
    await db.flush()
    await db.refresh(keyword)
    return keyword


async def update_keyword_is_active(
    db: AsyncSession,
    keyword: Keyword,
    is_active: bool,
) -> Keyword:
    keyword.is_active = is_active
    await db.flush()
    await db.refresh(keyword)
    return keyword


async def update_keyword_settings(
    db: AsyncSession,
    keyword: Keyword,
    *,
    keyword_text: str,
    dashboard_mode: str,
    client_name: str | None,
    group_name: str | None,
    monitoring_type: str,
    priority_level: str,
    crawl_interval_minutes: int,
    crawl_limit: int,
    email_auto_send: bool,
    email_recipients: str | None,
    email_send_time: str,
    email_condition_type: str,
    alert_negative_rate_threshold: int,
    alert_importance_threshold: int,
    alert_article_count_threshold: int,
    importance_criteria: str | None,
) -> Keyword:
    keyword.keyword_text = keyword_text
    keyword.dashboard_mode = dashboard_mode
    keyword.client_name = client_name
    keyword.group_name = group_name
    keyword.monitoring_type = monitoring_type
    keyword.priority_level = priority_level
    keyword.crawl_interval_minutes = crawl_interval_minutes
    keyword.crawl_limit = crawl_limit
    keyword.email_auto_send = email_auto_send
    keyword.email_recipients = email_recipients
    keyword.email_send_time = email_send_time
    keyword.email_condition_type = email_condition_type
    keyword.alert_negative_rate_threshold = alert_negative_rate_threshold
    keyword.alert_importance_threshold = alert_importance_threshold
    keyword.alert_article_count_threshold = alert_article_count_threshold
    keyword.importance_criteria = importance_criteria
    await db.flush()
    await db.refresh(keyword)
    return keyword


async def get_keyword_by_id(
    db: AsyncSession,
    keyword_id: int,
) -> Keyword | None:
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id)
    )
    return result.scalar_one_or_none()



async def list_user_keywords(
    db: AsyncSession,
    user_id: int,
    *,
    page: int,
    size: int,
    is_active: bool | None = None,
    language: str | None = None,
    q: str | None = None,
    dashboard_mode: str | None = None,
) -> tuple[list[Keyword], int]:
    query = select(Keyword).where(Keyword.user_id == user_id)
    count_query = select(func.count()).select_from(Keyword).where(Keyword.user_id == user_id)

    if is_active is not None:
        query = query.where(Keyword.is_active == is_active)
        count_query = count_query.where(Keyword.is_active == is_active)

    if language is not None:
        query = query.where(Keyword.language == language)
        count_query = count_query.where(Keyword.language == language)

    if dashboard_mode is not None:
        query = query.where(Keyword.dashboard_mode == dashboard_mode)
        count_query = count_query.where(Keyword.dashboard_mode == dashboard_mode)

    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(Keyword.keyword_text.ilike(pattern))
        count_query = count_query.where(Keyword.keyword_text.ilike(pattern))

    query = query.order_by(Keyword.created_at.desc()).offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    items = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    return items, total


async def delete_keyword(
    db: AsyncSession,
    keyword: Keyword,
) -> None:
    await db.delete(keyword)
    await db.flush()
    
async def get_keywords_by_ids_for_user(
    db: AsyncSession,
    user_id: int,
    keyword_ids: list[int],
) -> list[Keyword]:
    if not keyword_ids:
        return []

    result = await db.execute(
        select(Keyword).where(
            Keyword.user_id == user_id,
            Keyword.id.in_(keyword_ids),
        )
    )
    return result.scalars().all()


async def get_all_active_keywords_for_user(
    db: AsyncSession,
    user_id: int,
) -> list[Keyword]:
    result = await db.execute(
        select(Keyword).where(
            Keyword.user_id == user_id,
            Keyword.is_active == True,  # noqa: E712
        )
    )
    return result.scalars().all()
