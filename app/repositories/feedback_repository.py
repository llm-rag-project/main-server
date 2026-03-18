from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.keyword import Keyword
from app.models.ranking_feedback import RankingFeedback
from app.models.ranking_feedback_item import RankingFeedbackItem


class FeedbackRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_articles_exist_and_accessible(
        self,
        user_id: int,
        article_ids: list[int],
        keyword_id: int | None = None,
    ) -> None:
        stmt = (
            select(Article.id)
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(Article.id.in_(article_ids))
            .where(Keyword.user_id == user_id)
            .distinct()
        )

        if keyword_id is not None:
            stmt = stmt.where(ArticleMatch.keyword_id == keyword_id)

        result = await self.db.execute(stmt)
        accessible_ids = {row[0] for row in result.all()}

        if len(accessible_ids) != len(set(article_ids)):
            raise ValueError("NOT_FOUND")

    async def save_ranking_feedback(
        self,
        user_id: int,
        article_ids: list[int],
        keyword_id: int | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)

        ranking_feedback = RankingFeedback(
            user_id=user_id,
            keyword_id=keyword_id,
            created_at=now,
        )
        self.db.add(ranking_feedback)
        await self.db.flush()

        for rank, article_id in enumerate(article_ids, start=1):
            item = RankingFeedbackItem(
                ranking_feedback_id=ranking_feedback.id,
                article_id=article_id,
                rank_order=rank,
            )
            self.db.add(item)

        await self.db.flush()

        return {
            "saved": True,
            "count": len(article_ids),
            "created_at": ranking_feedback.created_at,
        }