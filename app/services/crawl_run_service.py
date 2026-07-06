import logging
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, build_error
from app.core.transnews_client import TransNewsClient
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.crawl_run import CrawlRun
from app.models.dify_knowledge_document import DifyKnowledgeDocument
from app.models.keyword import Keyword
from app.models.social_metric import SocialMetric
from app.services.dify_service import DifyArticleUploadService

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


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

    def _is_google_news_url(self, url: str | None) -> bool:
        return bool(url) and "news.google.com/rss/articles" in url

    def _extract_article_url(self, item: dict[str, Any]) -> str | None:
        """
        실제 기사 원문 URL만 반환한다.
        Google News RSS 링크(link/google_news_url)는 원문 URL이 아니므로 fallback으로 쓰지 않는다.
        """
        candidates = [
            item.get("original_url"),
            item.get("source_url"),
            item.get("article_url"),
            item.get("resolved_url"),
            item.get("url"),
        ]

        for url in candidates:
            if not url:
                continue

            url = str(url).strip()
            if not url:
                continue

            if self._is_google_news_url(url):
                continue

            return url

        return None

    def _crawl_window(self, keyword: Keyword) -> tuple[datetime, datetime]:
        end_at = datetime.now(timezone.utc)
        start_at = end_at - timedelta(minutes=keyword.crawl_interval_minutes)
        return start_at, end_at

    def _today_crawl_window(self) -> tuple[datetime, datetime]:
        now_kst = datetime.now(KST)
        start_kst = datetime.combine(now_kst.date(), time.min, tzinfo=KST)
        return start_kst.astimezone(timezone.utc), now_kst.astimezone(timezone.utc)

    def _search_keyword_with_window(self, keyword: Keyword, start_at: datetime, end_at: datetime) -> str:
        after = start_at.strftime("%Y-%m-%d")
        before = (end_at + timedelta(days=1)).strftime("%Y-%m-%d")
        return f"{keyword.keyword_text} after:{after} before:{before}"

    def _parse_published_at(self, item: dict[str, Any]) -> datetime | None:
        published_raw = item.get("published_at") or item.get("published")
        if not published_raw:
            return None
        try:
            parsed = parsedate_to_datetime(published_raw)
        except Exception:
            try:
                parsed = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
            except Exception:
                return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _is_in_crawl_window(self, item: dict[str, Any], start_at: datetime, end_at: datetime) -> bool:
        published_at = self._parse_published_at(item)
        if published_at is None:
            return False
        return start_at <= published_at <= end_at

    def _contains_keyword(self, *, keyword_text: str, item: dict[str, Any]) -> bool:
        keyword = (keyword_text or "").strip().casefold()
        if not keyword:
            return False

        searchable_text = "\n".join(
            str(item.get(field) or "")
            for field in (
                "title",
                "content",
                "summary",
                "description",
                "snippet",
            )
        ).casefold()

        return keyword in searchable_text

    async def create_crawl_run(
        self,
        *,
        user_id: int,
        keyword_ids: list[int] | None = None,
        force: bool = False,
        today_only: bool = False,
    ) -> dict[str, Any]:
        keywords = await self._get_user_keywords(user_id=user_id, keyword_ids=keyword_ids)
        if not keywords:
            raise build_error(ErrorCode.VALIDATION_ERROR, "크롤링할 키워드가 없습니다.")

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
        articles_to_upload: list[tuple[Article, Keyword]] = []

        for keyword in keywords:
            await self._capture_social_metrics(user_id=user_id, keyword=keyword)
            window_start, window_end = self._today_crawl_window() if today_only else self._crawl_window(keyword)
            search_keyword = self._search_keyword_with_window(keyword, window_start, window_end)
            news_response = await self.transnews_client.search_news(
                search_keyword,
                published_after=window_start.isoformat(),
                published_before=window_end.isoformat(),
                limit=keyword.crawl_limit,
            )

            if news_response.get("status") != "SUCCESS":
                logger.debug("NEWS RESPONSE NOT SUCCESS: %s", news_response)
                continue

            news_items = [
                item
                for item in (news_response.get("data") or [])
                if self._is_in_crawl_window(item, window_start, window_end)
            ][: keyword.crawl_limit]
            seen_urls: set[str] = set()

            for item in news_items:
                url = self._extract_article_url(item)

                if not url:
                    logger.debug(
                        "SKIP ITEM: url not resolved title=%s", item.get("title")
                    )
                    continue

                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # 뒤 로직에서도 같은 실제 기사 URL 기준을 쓰도록 통일
                item["url"] = url
                item["original_url"] = url
                try:
                    crawl_data = await self.transnews_client.crawl_article(url)
                    crawled = crawl_data.get("data") or {}

                    content = (
                        crawled.get("content")
                        or crawled.get("body")
                        or crawled.get("article_content")
                        or crawled.get("text")
                        or item.get("content")
                        or ""
                    ).strip()

                    if content:
                        item["content"] = content

                except Exception as e:
                    logger.debug("crawl_article failed url=%s: %s", url, e)

                if not self._contains_keyword(keyword_text=keyword.keyword_text, item=item):
                    logger.info(
                        "skip article without literal keyword keyword_id=%s keyword=%s title=%s url=%s",
                        keyword.id,
                        keyword.keyword_text,
                        item.get("title"),
                        url,
                    )
                    continue

                article, is_new_article = await self._upsert_article(item)
                if article is None:
                    continue

                is_new_match = await self._ensure_article_match(
                    article_id=article.id,
                    keyword_id=keyword.id,
                    crawl_run_id=crawl_run.id,
                )

                should_upload = is_new_article or is_new_match

                if should_upload:
                    if not await self._has_dify_document(article_id=article.id, keyword_id=keyword.id):
                        articles_to_upload.append((article, keyword))

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
        stmt = select(Keyword).where(
            Keyword.user_id == user_id,
            Keyword.is_active.is_(True),
        )
        if keyword_ids:
            stmt = stmt.where(Keyword.id.in_(keyword_ids))

        result = await self.db.execute(stmt)
        keywords = list(result.scalars().all())

        logger.debug(
            "_get_user_keywords result: %s",
            [(k.id, k.keyword_text) for k in keywords],
        )
        return keywords

    async def _upsert_article(self, item: dict[str, Any]) -> tuple[Article | None, bool]:
        url = self._extract_article_url(item)
        published_at = self._parse_published_at(item)

        if not url:
            return None, False

        title = item.get("title") or "제목 없음"
        publisher = item.get("publisher") or item.get("source_name")
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

        if getattr(match, "crawl_run_id", None) is None:
            match.crawl_run_id = crawl_run_id

        return False

    async def crawl_all_active_keywords(self) -> dict[str, Any]:
        result = await self.db.execute(
            select(Keyword.user_id).where(Keyword.is_active.is_(True)).distinct()
        )
        user_ids = [row[0] for row in result.all()]

        total_articles = 0
        runs: list[dict[str, Any]] = []
        for user_id in user_ids:
            try:
                run_result = await self.create_crawl_run(user_id=user_id, force=False)
                total_articles += run_result.get("crawl_count", 0)
                runs.append({"user_id": user_id, **run_result})
            except Exception as exc:
                logger.warning("user_id=%s 크롤링 실패: %s", user_id, exc)

        return {"crawled_user_count": len(user_ids), "total_article_count": total_articles, "runs": runs}

    async def _capture_social_metrics(self, *, user_id: int, keyword: Keyword) -> None:
        try:
            result = await self.transnews_client.get_social_stats(keyword.keyword_text, limit=keyword.crawl_limit, hours=168)
        except Exception as exc:
            logger.warning("social stats failed keyword_id=%s keyword=%s: %s", keyword.id, keyword.keyword_text, exc)
            return

        sources = result.get("sources") or []
        for item in sources:
            self.db.add(
                SocialMetric(
                    user_id=user_id,
                    keyword_id=keyword.id,
                    keyword_text=keyword.keyword_text,
                    source=item.get("source") or "unknown",
                    mention_count=int(item.get("mention_count") or 0),
                    positive_hint_count=int(item.get("positive_hint_count") or 0),
                    negative_hint_count=int(item.get("negative_hint_count") or 0),
                )
            )
        await self.db.flush()

    async def _has_dify_document(self, *, article_id: int, keyword_id: int) -> bool:
        result = await self.db.execute(
            select(DifyKnowledgeDocument.id).where(
                DifyKnowledgeDocument.article_id == article_id,
                DifyKnowledgeDocument.keyword_id == keyword_id,
                DifyKnowledgeDocument.status == "UPLOADED",
            )
        )
        return result.scalar_one_or_none() is not None

    async def _upload_articles_to_dify(self, article_keywords: list[tuple[Article, Keyword]]) -> dict[str, Any]:
        if not article_keywords:
            return {
                "uploaded_count": 0,
                "failed_count": 0,
                "uploaded": [],
                "failed": [],
            }

        uploaded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for article, keyword in article_keywords:
            try:
                result = await self.dify_upload_service.upload_article_to_knowledge(
                    article,
                    keyword_id=keyword.id,
                    keyword_text=keyword.keyword_text,
                )
                uploaded.append(result)
                self.db.add(
                    DifyKnowledgeDocument(
                        user_id=keyword.user_id,
                        article_id=article.id,
                        keyword_id=keyword.id,
                        keyword_text=keyword.keyword_text,
                        dataset_id=result["dataset_id"],
                        document_id=result["document_id"],
                        batch=result.get("batch"),
                        status="UPLOADED",
                    )
                )
            except Exception as e:
                failed.append(
                    {
                        "article_id": getattr(article, "id", None),
                        "keyword_id": getattr(keyword, "id", None),
                        "keyword": getattr(keyword, "keyword_text", None),
                        "title": getattr(article, "title", None),
                        "error": str(e),
                    }
                )

        await self.db.flush()
        return {
            "uploaded_count": len(uploaded),
            "failed_count": len(failed),
            "uploaded": uploaded,
            "failed": failed,
        }
