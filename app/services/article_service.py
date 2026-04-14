from fastapi import HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.repositories.article_repository import ArticleRepository
from app.schemas.articles import ArticleDetailResponse


class ArticleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.article_repository = ArticleRepository(db)

    async def get_article_by_id(self, article_id: int) -> Article | None:
        result = await self.db.execute(
            select(Article).where(Article.id == article_id)
        )
        return result.scalar_one_or_none()

    async def get_article_detail(self, user_id: int, article_id: int) -> ArticleDetailResponse:
        article = await self.article_repository.get_article_detail(user_id, article_id)

        if article is None:
            raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")

        return ArticleDetailResponse(**article)

    async def get_articles_by_keyword_id(self, keyword_id: int) -> list[Article]:
        result = await self.db.execute(
            select(Article)
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .where(ArticleMatch.keyword_id == keyword_id)
            .order_by(Article.published_at.desc())
        )
        return list(result.scalars().all())

    async def get_article_list(self, user_id: int, query):
        return await self.article_repository.get_article_list(
            user_id=user_id,
            query=query,
        )