from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

from app.models.keyword import Keyword

#대소문자 구분 x
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    )
    return result.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()

async def create_user(
    db: AsyncSession,
    email: str,
    hashed_password: str,
    name: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password=hashed_password,
        name=name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user

async def update_user_profile(
    db: AsyncSession,
    user: User,
    *,
    name: str | None = None,
    default_language: str | None = None,
    update_name: bool = False,
    update_default_language: bool = False,
) -> User:
    if update_name:
        user.name = name

    if update_default_language:
        user.default_language = default_language

    await db.flush()
    await db.refresh(user)
    return user

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