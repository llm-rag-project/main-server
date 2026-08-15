from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, delete, exists, func, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, build_error
from app.models.article import Article
from app.models.article_analysis import ArticleAnalysis
from app.models.article_match import ArticleMatch
from app.models.dongguk_article_trash import DonggukArticleTrash
from app.models.feedback import Feedback
from app.models.importance_score import ImportanceScore
from app.models.keyword import Keyword
from app.models.summary import Summary
from app.schemas.articles import ArticleListQuery


KST = ZoneInfo("Asia/Seoul")


class ArticleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    

    async def get_article_list(
        self,
        user_id: int,
        query: ArticleListQuery,
    ) -> Tuple[List[Dict[str, Any]], int]:
        latest_summary_expr = (
            select(Summary.summary_text)
            .where(Summary.article_id == Article.id)
            .order_by(Summary.created_at.desc())
            .limit(1)
            .correlate(Article)
            .scalar_subquery()
        )

        latest_importance_subq = (
            select(
                ImportanceScore.article_id.label("article_id"),
                ImportanceScore.user_id.label("user_id"),
                ImportanceScore.score.label("score"),
                ImportanceScore.status.label("status"),
                ImportanceScore.created_at.label("scored_at"),
            )
            .where(ImportanceScore.is_current.is_(True))
            .subquery()
        )

        if query.keyword_id:
            matched_keyword_expr = literal(query.keyword_id)
            matched_at_expr = ArticleMatch.matched_at
        else:
            matched_keyword_expr = (
                select(func.min(ArticleMatch.keyword_id))
                .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                .where(
                    ArticleMatch.article_id == Article.id,
                    Keyword.user_id == user_id,
                )
                .correlate(Article)
                .scalar_subquery()
            )
            matched_at_expr = (
                select(func.max(ArticleMatch.matched_at))
                .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                .where(
                    ArticleMatch.article_id == Article.id,
                    Keyword.user_id == user_id,
                )
                .correlate(Article)
                .scalar_subquery()
            )

        has_feedback_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
            )
        )

        is_liked_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
                Feedback.label == "LIKE",
            )
        )

        accessible_articles_expr = None
        if not query.keyword_id:
            accessible_articles_expr = exists(
                select(literal(1))
                .select_from(ArticleMatch)
                .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                .where(
                    ArticleMatch.article_id == Article.id,
                    Keyword.user_id == user_id,
                )
            )
        trash_conditions = [
            DonggukArticleTrash.user_id == user_id,
            DonggukArticleTrash.article_id == Article.id,
        ]
        if query.keyword_id:
            trash_conditions.append(DonggukArticleTrash.keyword_id == query.keyword_id)
        is_trashed_expr = exists(
            select(literal(1))
            .select_from(DonggukArticleTrash)
            .where(*trash_conditions)
        )

        stmt = (
            select(
                Article.id,
                Article.title,
                latest_summary_expr.label("summary"),
                Article.url,
                Article.thumbnail_url,
                Article.publisher.label("source"),
                Article.collection_source,
                Article.language,
                Article.published_at,
                Article.created_at.label("collected_at"),
                matched_at_expr.label("matched_at"),
                matched_keyword_expr.label("keyword_id"),
                latest_importance_subq.c.score.label("importance"),
                case((is_liked_expr, True), else_=False).label("is_liked"),
                case((has_feedback_expr, True), else_=False).label("has_feedback"),
                ArticleAnalysis.sentiment,
                ArticleAnalysis.is_promotion,
                Article.section,
                Article.pool,
                Article.source_type,
                Article.category,
                Article.trusted_source,
                Article.priority_boost,
                Article.board,
                Article.board_name,
            )
            .select_from(Article)
            .outerjoin(
                latest_importance_subq,
                and_(
                    latest_importance_subq.c.article_id == Article.id,
                    latest_importance_subq.c.user_id == user_id,
                ),
            )
            .outerjoin(
                ArticleAnalysis,
                ArticleAnalysis.article_id == Article.id,
            )
        )
        if query.keyword_id:
            stmt = (
                stmt.join(ArticleMatch, ArticleMatch.article_id == Article.id)
                .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                .where(
                    ArticleMatch.keyword_id == query.keyword_id,
                    Keyword.user_id == user_id,
                )
            )
        else:
            stmt = stmt.where(accessible_articles_expr)
        stmt = stmt.where(~is_trashed_expr)

        if query.q:
            like_expr = f"%{query.q.strip()}%"
            stmt = stmt.where(
                or_(
                    Article.title.ilike(like_expr),
                    Article.content.ilike(like_expr),
                    latest_summary_expr.ilike(like_expr),
                )
            )

        if query.language:
            stmt = stmt.where(Article.language == query.language.value)

        if query.from_at:
            stmt = stmt.where(Article.published_at >= query.from_at)
        elif query.from_date:
            stmt = stmt.where(
                Article.published_at >= datetime.combine(query.from_date, time.min, tzinfo=KST)
            )

        if query.to_at:
            stmt = stmt.where(Article.published_at <= query.to_at)
        elif query.to_date:
            stmt = stmt.where(
                Article.published_at <= datetime.combine(query.to_date, time.max, tzinfo=KST)
            )

        if query.collected_from_date:
            stmt = stmt.where(
                Article.created_at >= datetime.combine(query.collected_from_date, time.min, tzinfo=KST)
            )

        if query.collected_to_date:
            stmt = stmt.where(
                Article.created_at <= datetime.combine(query.collected_to_date, time.max, tzinfo=KST)
            )

        if query.matched_from_date or query.matched_to_date:
            if query.keyword_id:
                if query.matched_from_date:
                    stmt = stmt.where(
                        ArticleMatch.matched_at >= datetime.combine(query.matched_from_date, time.min, tzinfo=KST)
                    )
                if query.matched_to_date:
                    stmt = stmt.where(
                        ArticleMatch.matched_at <= datetime.combine(query.matched_to_date, time.max, tzinfo=KST)
                    )
            else:
                match_conditions = [
                    ArticleMatch.article_id == Article.id,
                    Keyword.user_id == user_id,
                ]
                if query.matched_from_date:
                    match_conditions.append(
                        ArticleMatch.matched_at >= datetime.combine(query.matched_from_date, time.min, tzinfo=KST)
                    )
                if query.matched_to_date:
                    match_conditions.append(
                        ArticleMatch.matched_at <= datetime.combine(query.matched_to_date, time.max, tzinfo=KST)
                    )
                stmt = stmt.where(
                    exists(
                        select(literal(1))
                        .select_from(ArticleMatch)
                        .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                        .where(*match_conditions)
                    )
                )

        if query.min_importance is not None:
            stmt = stmt.where(latest_importance_subq.c.score >= query.min_importance)

        if query.max_importance is not None:
            stmt = stmt.where(latest_importance_subq.c.score <= query.max_importance)

        if query.has_feedback is not None:
            stmt = stmt.where(has_feedback_expr if query.has_feedback else ~has_feedback_expr)

        if query.liked is not None:
            stmt = stmt.where(is_liked_expr if query.liked else ~is_liked_expr)

        total = 0
        if query.include_total:
            count_source = stmt.with_only_columns(Article.id).order_by(None).subquery()
            count_stmt = select(func.count()).select_from(count_source)
            total = await self.db.scalar(count_stmt) or 0

        sort_map = {
            "published_at_desc": Article.published_at.desc().nullslast(),
            "published_at_asc": Article.published_at.asc().nullsfirst(),
            "importance_desc": latest_importance_subq.c.score.desc().nullslast(),
            "importance_asc": latest_importance_subq.c.score.asc().nullsfirst(),
            "sentiment_negative_first": case(
                (or_(ArticleAnalysis.sentiment.ilike("%부정%"), ArticleAnalysis.sentiment.ilike("%negative%")), 0),
                (or_(ArticleAnalysis.sentiment.ilike("%중립%"), ArticleAnalysis.sentiment.ilike("%neutral%")), 1),
                (or_(ArticleAnalysis.sentiment.ilike("%긍정%"), ArticleAnalysis.sentiment.ilike("%positive%")), 2),
                else_=3,
            ).asc(),
            "sentiment_positive_first": case(
                (or_(ArticleAnalysis.sentiment.ilike("%긍정%"), ArticleAnalysis.sentiment.ilike("%positive%")), 0),
                (or_(ArticleAnalysis.sentiment.ilike("%중립%"), ArticleAnalysis.sentiment.ilike("%neutral%")), 1),
                (or_(ArticleAnalysis.sentiment.ilike("%부정%"), ArticleAnalysis.sentiment.ilike("%negative%")), 2),
                else_=3,
            ).asc(),
            "promotion_first": case(
                (ArticleAnalysis.is_promotion.is_(True), 0),
                (ArticleAnalysis.is_promotion.is_(False), 1),
                else_=2,
            ).asc(),
            "organic_first": case(
                (ArticleAnalysis.is_promotion.is_(False), 0),
                (ArticleAnalysis.is_promotion.is_(True), 1),
                else_=2,
            ).asc(),
        }

        stmt = stmt.order_by(sort_map[query.sort.value], Article.id.desc())
        stmt = stmt.offset((query.page - 1) * query.size).limit(query.size)

        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        if not query.include_total:
            loaded = (query.page - 1) * query.size + len(rows)
            total = loaded + (1 if len(rows) == query.size else 0)

        return [dict(row) for row in rows], total

    async def get_article_detail(self, user_id: int, article_id: int) -> Optional[Dict[str, Any]]:
        latest_summary_expr = (
            select(Summary.summary_text)
            .where(Summary.article_id == Article.id)
            .order_by(Summary.created_at.desc())
            .limit(1)
            .correlate(Article)
            .scalar_subquery()
        )

        latest_importance_subq = (
            select(
                ImportanceScore.article_id.label("article_id"),
                ImportanceScore.user_id.label("user_id"),
                ImportanceScore.score.label("score"),
            )
            .where(ImportanceScore.is_current.is_(True))
            .subquery()
        )

        has_feedback_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
            )
        )

        is_liked_expr = exists(
            select(literal(1))
            .select_from(Feedback)
            .where(
                Feedback.article_id == Article.id,
                Feedback.user_id == user_id,
                Feedback.label == "LIKE",
            )
        )

        matched_keyword_expr = (
            select(func.min(ArticleMatch.keyword_id))
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                ArticleMatch.article_id == Article.id,
                Keyword.user_id == user_id,
            )
            .correlate(Article)
            .scalar_subquery()
        )

        stmt = (
            select(
                Article.id,
                Article.title,
                latest_summary_expr.label("summary"),
                Article.content,
                Article.url,
                Article.thumbnail_url,
                Article.publisher.label("source"),
                Article.collection_source,
                Article.language,
                Article.published_at,
                matched_keyword_expr.label("keyword_id"),
                latest_importance_subq.c.score.label("importance"),
                case((is_liked_expr, True), else_=False).label("is_liked"),
                case((has_feedback_expr, True), else_=False).label("has_feedback"),
                Article.created_at,
            )
            .select_from(Article)
            .outerjoin(
                latest_importance_subq,
                and_(
                    latest_importance_subq.c.article_id == Article.id,
                    latest_importance_subq.c.user_id == user_id,
                ),
            )
            .where(Article.id == article_id)
        )

        result = await self.db.execute(stmt)
        row = result.mappings().first()
        if not row:
            return None
        return dict(row)

    async def article_exists(self, article_id: int) -> bool:
        stmt = select(func.count()).select_from(Article).where(Article.id == article_id)
        count = await self.db.scalar(stmt)
        return bool(count)

    async def has_article_access(self, user_id: int, article_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(ArticleMatch)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                ArticleMatch.article_id == article_id,
                Keyword.user_id == user_id,
            )
        )
        count = await self.db.scalar(stmt)
        return bool(count)
    
    
    
    async def get_article_importance(self, user_id: int, article_id: int) -> dict | None:
        stmt = (
            select(
                ImportanceScore.article_id,
                ImportanceScore.status,
                ImportanceScore.score,
                ImportanceScore.engine,
                ImportanceScore.version,
                ImportanceScore.scored_at,
                ImportanceScore.created_at,
                ImportanceScore.updated_at,
            )
            .where(ImportanceScore.article_id == article_id)
            .where(ImportanceScore.user_id == user_id)
            .where(ImportanceScore.is_current.is_(True))
            .limit(1)
        )

        result = await self.db.execute(stmt)
        row = result.mappings().first()
        if not row:
            return None

        row = dict(row)
        model_name = None
        if row.get("engine"):
            version = row.get("version")
            model_name = f"{row['engine']}-v{version}" if version is not None else row["engine"]

        return {
            "article_id": row["article_id"],
            "status": row["status"] or "PENDING",
            "score": row["score"],
            "model": model_name,
            "scored_at": row["scored_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }    

    async def upsert_article_feedback(
        self,
        user_id: int,
        article_id: int,
        action: str,
    ) -> dict:
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .where(Feedback.article_id == article_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        feedback = result.scalar_one_or_none()

        created = False

        if feedback is None:
            feedback = Feedback(
                user_id=user_id,
                article_id=article_id,
                label=action,
            )
            self.db.add(feedback)
            created = True
        else:
            feedback.label = action

        await self.db.flush()
        await self.db.refresh(feedback)

        updated_at = getattr(feedback, "updated_at", None) or feedback.created_at

        return {
            "article_id": article_id,
            "action": feedback.label,
            "created": created,
            "updated_at": updated_at,
        }
        
    async def get_my_feedback_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> dict | None:
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .where(Feedback.article_id == article_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        feedback = result.scalar_one_or_none()

        if feedback is None:
            return None

        updated_at = getattr(feedback, "updated_at", None) or feedback.created_at

        return {
            "feedback_id": feedback.id,
            "article_id": feedback.article_id,
            "action": feedback.label,
            "created_at": feedback.created_at,
            "updated_at": updated_at,
        }

    async def get_feedback_by_id(self, feedback_id: int) -> Feedback | None:
        stmt = select(Feedback).where(Feedback.id == feedback_id).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_feedback(self, feedback: Feedback) -> dict:
        feedback_id = feedback.id
        await self.db.delete(feedback)
        await self.db.flush()

        return {
            "deleted": True,
            "feedback_id": feedback_id,
        }

    async def validate_articles_exist_and_accessible(
        self,
        user_id: int,
        article_ids: list[int],
        keyword_id: int | None = None,
    ) -> None:
        if not article_ids:
            raise build_error(ErrorCode.VALIDATION_ERROR, "article_ids is required")

        stmt = (
            select(func.count(func.distinct(Article.id)))
            .select_from(Article)
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(Article.id.in_(article_ids))
            .where(Keyword.user_id == user_id)
        )

        if keyword_id is not None:
            stmt = stmt.where(ArticleMatch.keyword_id == keyword_id)

        count = await self.db.scalar(stmt)
        count = count or 0

        if count != len(set(article_ids)):
            raise build_error(ErrorCode.NOT_FOUND, "article not found or not accessible")
    async def get_my_feedback_entity_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> Feedback | None:
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .where(Feedback.article_id == article_id)
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_my_feedback_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> dict:
        feedback = await self.get_my_feedback_entity_by_article(
            user_id=user_id,
            article_id=article_id,
        )

        if feedback is None:
            raise build_error(ErrorCode.NOT_FOUND, "feedback not found")

        await self.db.delete(feedback)
        await self.db.flush()

        return {
            "deleted": True,
            "article_id": article_id,
        }

    async def delete_article_for_user(self, user_id: int, article_id: int) -> dict | None:
        result = await self.db.execute(
            select(Article)
            .where(Article.id == article_id)
            .where(
                exists(
                    select(literal(1))
                    .select_from(ArticleMatch)
                    .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                    .where(
                        ArticleMatch.article_id == Article.id,
                        Keyword.user_id == user_id,
                    )
                )
            )
            .limit(1)
        )
        article = result.scalar_one_or_none()
        if article is None:
            return None

        title = article.title
        await self.db.delete(article)
        await self.db.flush()
        return {
            "deleted": True,
            "article_id": article_id,
            "title": title,
        }
    
    async def get_article_ids_by_keyword(
        self,
        user_id: int,
        keyword_id: int,
    ) -> list[int]:
        """키워드에 속한 모든 기사 ID를 반환 (최신순)"""
        stmt = (
            select(Article.id)
            .select_from(Article)
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(ArticleMatch.keyword_id == keyword_id)
            .where(Keyword.user_id == user_id)
            .order_by(Article.id.desc())
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_articles_for_importance_scoring(
        self,
        user_id: int,
        article_ids: list[int],
    ) -> list[dict]:
            if not article_ids:
                return []

            stmt = (
                select(
                    Article.id.label("article_id"),
                    Article.title,
                    Article.content,
                )
                .select_from(Article)
                .where(Article.id.in_(article_ids))
                .where(
                    exists(
                        select(literal(1))
                        .select_from(ArticleMatch)
                        .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
                        .where(
                            ArticleMatch.article_id == Article.id,
                            Keyword.user_id == user_id,
                        )
                    )
                )
                .order_by(Article.id.asc())
            )

            result = await self.db.execute(stmt)
            rows = result.mappings().all()
            return [dict(row) for row in rows]
