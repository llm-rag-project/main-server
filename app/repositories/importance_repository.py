from datetime import datetime, time
from typing import Any, Dict, List, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.importance_score import ImportanceScore
from app.models.keyword import Keyword
from app.schemas.importance import ImportanceListQuery


class ImportanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_importance_list(
        self,
        user_id: int,
        query: ImportanceListQuery,
    ) -> Tuple[List[Dict[str, Any]], int]:
        matched_keyword_subq = (
            select(
                ArticleMatch.article_id.label("article_id"),
                func.min(ArticleMatch.keyword_id).label("keyword_id"),
            )
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(Keyword.user_id == user_id)
            .group_by(ArticleMatch.article_id)
            .subquery()
        )

        stmt = (
            select(
                ImportanceScore.article_id,
                Article.title,
                Article.url,
                matched_keyword_subq.c.keyword_id,
                ImportanceScore.score,
                ImportanceScore.status,
                ImportanceScore.created_at.label("scored_at"),
                ImportanceScore.created_at,
            )
            .join(Article, Article.id == ImportanceScore.article_id)
            .outerjoin(
                matched_keyword_subq,
                matched_keyword_subq.c.article_id == ImportanceScore.article_id,
            )
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.is_current.is_(True))
        )

        if query.keyword_id:
            stmt = stmt.where(
                ImportanceScore.article_id.in_(
                    select(ArticleMatch.article_id)
                    .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                    .where(
                        ArticleMatch.keyword_id == query.keyword_id,
                        Keyword.user_id == user_id,
                    )
                )
            )

        if query.from_date:
            stmt = stmt.where(
                Article.published_at >= datetime.combine(query.from_date, time.min)
            )

        if query.to_date:
            stmt = stmt.where(
                Article.published_at <= datetime.combine(query.to_date, time.max)
            )

        if query.min_score is not None:
            stmt = stmt.where(ImportanceScore.score >= query.min_score)

        if query.max_score is not None:
            stmt = stmt.where(ImportanceScore.score <= query.max_score)

        if query.status:
            stmt = stmt.where(ImportanceScore.status == query.status.value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)
        total = total or 0

        sort_map = {
            "scored_at_desc": ImportanceScore.created_at.desc().nullslast(),
            "scored_at_asc": ImportanceScore.created_at.asc().nullsfirst(),
            "score_desc": ImportanceScore.score.desc().nullslast(),
            "score_asc": ImportanceScore.score.asc().nullsfirst(),
        }

        stmt = stmt.order_by(sort_map[query.sort.value], ImportanceScore.id.desc())
        stmt = stmt.offset((query.page - 1) * query.size).limit(query.size)

        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [dict(row) for row in rows], total