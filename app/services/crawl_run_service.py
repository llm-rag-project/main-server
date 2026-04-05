from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.transnews_client import TransNewsClient
from app.models.crawl_run import CrawlRun
from app.models.crawl_run_keyword import CrawlRunKeyword
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.summary import Summary
from app.models.keyword import Keyword


class CrawlRunService:
    def __init__(self, db: AsyncSession, transnews_client: TransNewsClient):
        self.db = db
        self.transnews_client = transnews_client

    async def create_crawl_run(
        self,
        *,
        user_id: int,
        keyword_ids: list[int] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        # 1) 키워드 조회
        keywords = await self._get_user_keywords(user_id=user_id, keyword_ids=keyword_ids)
        if not keywords:
            raise ValueError("크롤링할 키워드가 없습니다.")

        # 2) crawl_run 생성
        crawl_run = CrawlRun(
            user_id=user_id,
            status="RUNNING",
            force_run=force,
            article_count=0,
            started_at=datetime.utcnow(),
        )
        self.db.add(crawl_run)
        await self.db.flush()

        for keyword in keywords:
            self.db.add(CrawlRunKeyword(crawl_run_id=crawl_run.id, keyword_id=keyword.id))

        article_count = 0

        # 3) 키워드별 뉴스 검색
        for keyword in keywords:
            news_response = await self.transnews_client.search_news(keyword.keyword_text)

            # transnews 응답 형태에 맞게 조정
            if news_response.get("status") != "SUCCESS":
                continue

            news_items = news_response.get("data") or []

            for item in news_items:
                article = await self._upsert_article(item)
                await self._ensure_article_match(
                    article_id=article.id,
                    keyword_id=keyword.id,
                    crawl_run_id=crawl_run.id,
                )

                # 필요하면 summary/content 채움
                try:
                    summary_response = await self.transnews_client.summarize_news(article.url)
                    if summary_response.get("status") == "SUCCESS":
                        data = summary_response.get("data") or {}
                        content = data.get("content")
                        summary_text = data.get("summary")

                        if content:
                            article.content = content

                        if summary_text:
                            await self._upsert_summary(article.id, summary_text)
                except Exception:
                    # 요약 실패는 전체 크롤링 실패로 보지 않고 넘어감
                    pass

                article_count += 1

        crawl_run.status = "COMPLETED"
        crawl_run.article_count = article_count
        crawl_run.finished_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(crawl_run)

        return {
            "crawl_run_id": crawl_run.id,
            "status": crawl_run.status,
            "article_count": crawl_run.article_count,
        }

    async def _get_user_keywords(self, *, user_id: int, keyword_ids: list[int] | None):
        from sqlalchemy import select

        stmt = select(Keyword).where(Keyword.user_id == user_id, Keyword.is_active.is_(True))
        if keyword_ids:
            stmt = stmt.where(Keyword.id.in_(keyword_ids))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _upsert_article(self, item: dict[str, Any]) -> Article:
        from sqlalchemy import select

        url = item.get("url")
        title = item.get("title") or "제목 없음"
        publisher = item.get("publisher") or item.get("source")
        published_at = item.get("published_at")

        result = await self.db.execute(select(Article).where(Article.url == url))
        article = result.scalar_one_or_none()

        if article:
            article.title = title
            article.publisher = publisher
            article.source_type = article.source_type or "TRANSNEWS"
            return article

        article = Article(
            source_type="TRANSNEWS",
            source_article_id=None,
            url=url,
            title=title,
            publisher=publisher,
            published_at=published_at,
            content=item.get("content") or "",
            language=item.get("language"),
        )
        self.db.add(article)
        await self.db.flush()
        return article

    async def _ensure_article_match(self, *, article_id: int, keyword_id: int, crawl_run_id: int):
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

    async def _upsert_summary(self, article_id: int, summary_text: str):
        from sqlalchemy import select

        result = await self.db.execute(
            select(Summary).where(Summary.article_id == article_id, Summary.language == "ko")
        )
        summary = result.scalar_one_or_none()

        if summary:
            summary.summary_text = summary_text
            summary.model_name = "transnews-pipeline"
            return

        self.db.add(
            Summary(
                article_id=article_id,
                language="ko",
                summary_text=summary_text,
                model_name="transnews-pipeline",
            )
        )