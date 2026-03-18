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
) -> Keyword:
    keyword = Keyword(
        user_id=user_id,
        keyword_text=keyword_text,
        language=language,
        is_active=True,
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
) -> tuple[list[Keyword], int]:
    query = select(Keyword).where(Keyword.user_id == user_id)
    count_query = select(func.count()).select_from(Keyword).where(Keyword.user_id == user_id)

    if is_active is not None:
        query = query.where(Keyword.is_active == is_active)
        count_query = count_query.where(Keyword.is_active == is_active)

    if language is not None:
        query = query.where(Keyword.language == language)
        count_query = count_query.where(Keyword.language == language)

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