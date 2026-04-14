from datetime import datetime
from typing import Any
from email.utils import parsedate_to_datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.transnews_client import TransNewsClient
from app.models.crawl_run import CrawlRun
from app.models.crawl_run_keyword import CrawlRunKeyword
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.summary import Summary
from app.models.keyword import Keyword
from app.services.dify_service import DifyArticleUploadService


class CrawlRunService:
    def __init__(
        self,
        db: AsyncSession,
        transnews_client: TransNewsClient,
        dify_upload_service: DifyArticleUploadService | None = None,
    ):
        self.db = db
        self.transnews_client = transnews_client
        self.dify_upload_service = dify_upload_service or DifyArticleUploadService()

    async def create_crawl_run(
        self,
        *,
        user_id: int,
        keyword_ids: list[int] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        keywords = await self._get_user_keywords(user_id=user_id, keyword_ids=keyword_ids)
        if not keywords:
            raise ValueError("크롤링할 키워드가 없습니다.")

        crawl_run = CrawlRun(
            user_id=user_id,
            status="RUNNING",
            force_run=force,
            article_count=0,
            started_at=datetime.utcnow(),
        )
        self.db.add(crawl_run)
        await self.db.flush()

        article_count = 0
        articles_to_upload: list[Article] = []

        for keyword in keywords:
            news_response = await self.transnews_client.search_news(keyword.keyword_text)

            if news_response.get("status") != "SUCCESS":
                continue

            news_items = news_response.get("data") or []

            for item in news_items:
                article, is_new_article = await self._upsert_article(item)

                if article is None:
                    continue

                is_new_match = await self._ensure_article_match(
                    article_id=article.id,
                    keyword_id=keyword.id,
                    crawl_run_id=crawl_run.id,
                )

                if is_new_article or is_new_match:
                    if not any(existing.id == article.id for existing in articles_to_upload):
                        articles_to_upload.append(article)

                article_count += 1

        dify_result = await self._upload_articles_to_dify(articles_to_upload)

        crawl_run.status = "COMPLETED"
        crawl_run.article_count = article_count
        crawl_run.finished_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(crawl_run)

        return {
            "crawl_run_id": crawl_run.id,
            "status": crawl_run.status,
            "crawl_count": crawl_run.article_count,
            "upload_target_count": len(articles_to_upload),
            "dify_uploaded_count": dify_result["uploaded_count"],
            "dify_failed_count": dify_result["failed_count"],
            "dify_failed_items": dify_result["failed"],
        }
    
    async def _get_user_keywords(self, *, user_id: int, keyword_ids: list[int] | None):
        from sqlalchemy import select

        stmt = select(Keyword).where(
            Keyword.user_id == user_id,
            Keyword.is_active.is_(True),
        )
        if keyword_ids:
            stmt = stmt.where(Keyword.id.in_(keyword_ids))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _upsert_article(self, item: dict[str, Any]) -> tuple[Article | None, bool]:
        from sqlalchemy import select

        url = item.get("url") or item.get("link")
        published_raw = item.get("published_at") or item.get("published")

        published_at = None
        if published_raw:
            try:
                published_at = parsedate_to_datetime(published_raw)
            except Exception:
                pass

        if not url:
            return None, False

        title = item.get("title") or "제목 없음"
        publisher = item.get("publisher") or item.get("source")
        language = item.get("language") or "ko"
        content = (item.get("content") or "").strip()

        result = await self.db.execute(select(Article).where(Article.url == url))
        article = result.scalar_one_or_none()

        if article:
            article.title = title
            article.publisher = publisher
            article.source_type = article.source_type or "TRANSNEWS"
            article.language = article.language or language

            if published_at is not None:
                article.published_at = published_at

            if content and not (article.content or "").strip():
                article.content = content

            return article, False

        article = Article(
            source_type="TRANSNEWS",
            source_article_id=None,
            url=url,
            title=title,
            publisher=publisher,
            published_at=published_at,
            content=content,
            language=language,
        )
        self.db.add(article)
        await self.db.flush()

        return article, True
    
    async def _ensure_article_match(
        self,
        *,
        article_id: int,
        keyword_id: int,
        crawl_run_id: int,
    ) -> bool:
        from sqlalchemy import select

        result = await self.db.execute(
            select(ArticleMatch).where(
                ArticleMatch.article_id == article_id,
                ArticleMatch.keyword_id == keyword_id,
            )
        )
        match = result.scalar_one_or_none()

        if match is None:
            self.db.add(
                ArticleMatch(
                    article_id=article_id,
                    keyword_id=keyword_id,
                    crawl_run_id=crawl_run_id,
                )
            )
            await self.db.flush()
            return True

        # 기존 매칭인데 crawl_run_id가 비어 있으면 보완
        if getattr(match, "crawl_run_id", None) is None:
            match.crawl_run_id = crawl_run_id

        return False

    async def _upload_articles_to_dify(self, articles: list[Article]) -> dict[str, Any]:
        if not articles:
            return {
                "uploaded_count": 0,
                "failed_count": 0,
                "uploaded": [],
                "failed": [],
            }

        return await self.dify_upload_service.upload_articles_to_knowledge(articles)