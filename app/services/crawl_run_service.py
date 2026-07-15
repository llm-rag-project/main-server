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
from app.services.article_identity import (
    canonicalize_article_url,
    content_fingerprint,
    is_same_publisher_article,
)

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
        ?ㅼ젣 湲곗궗 ?먮Ц URL留?諛섑솚?쒕떎.
        Google News RSS 留곹겕(link/google_news_url)???먮Ц URL???꾨땲誘濡?fallback?쇰줈 ?곗? ?딅뒗??
        """
        candidates = [
            item.get("original_url"),
            item.get("originallink"),
            item.get("originalLink"),
            item.get("source_url"),
            item.get("article_link"),
            item.get("article_url"),
            item.get("resolved_url"),
            item.get("url"),
            item.get("link"),
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

    def _extract_thumbnail_url(self, item: dict[str, Any]) -> str | None:
        candidates = [
            item.get("thumbnail_url"),
            item.get("image_url"),
            item.get("image"),
            item.get("thumbnail"),
            item.get("og_image"),
            item.get("lead_image"),
            item.get("main_image"),
        ]

        images = item.get("images")
        if isinstance(images, list):
            candidates.extend(images)
        elif isinstance(images, dict):
            candidates.extend(images.values())

        for value in candidates:
            if isinstance(value, dict):
                value = value.get("url") or value.get("src")
            if not value:
                continue
            url = str(value).strip()
            if url.startswith("http://") or url.startswith("https://"):
                return url
        return None

    def _crawl_window(self, keyword: Keyword) -> tuple[datetime, datetime]:
        end_at = datetime.now(timezone.utc)
        start_at = end_at - timedelta(minutes=keyword.crawl_interval_minutes)
        return start_at, end_at

    def _parse_send_time(self, value: str | None) -> time:
        try:
            hour_text, minute_text = (value or "08:30")[:5].split(":")
            return time(hour=int(hour_text), minute=int(minute_text))
        except Exception:
            return time(hour=8, minute=30)

    def _today_crawl_window(self, keyword: Keyword) -> tuple[datetime, datetime]:
        now_kst = datetime.now(KST)
        end_kst = datetime.combine(now_kst.date(), self._parse_send_time(keyword.email_send_time), tzinfo=KST)
        start_kst = end_kst - timedelta(days=1)
        return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)

    def _keyword_aliases(self, keyword_text: str) -> list[str]:
        keyword = (keyword_text or "").strip()
        aliases = [keyword] if keyword else []
        if keyword.endswith("대학교") and len(keyword) > 3:
            aliases.append(f"{keyword[:-3]}대")
        elif keyword.endswith("대") and len(keyword) > 1:
            aliases.append(f"{keyword[:-1]}대학교")
        return list(dict.fromkeys(alias for alias in aliases if alias))

    def _search_keyword_with_window(self, keyword: Keyword, start_at: datetime, end_at: datetime) -> str:
        aliases = self._keyword_aliases(keyword.keyword_text)
        if len(aliases) > 1 and keyword.keyword_text.endswith("대학교"):
            return aliases[1]
        return keyword.keyword_text

    def _contains_any_alias(self, text: str, aliases: list[str]) -> bool:
        normalized = (text or "").casefold()
        return any(alias in normalized for alias in aliases)

    def _content_alias_count(self, text: str, aliases: list[str]) -> int:
        normalized = (text or "").casefold()
        count = 0
        for alias in sorted(aliases, key=len, reverse=True):
            if not alias:
                continue
            alias_count = normalized.count(alias)
            count += alias_count
            normalized = normalized.replace(alias, " ")
        return count

    def _parse_published_at(self, item: dict[str, Any]) -> datetime | None:
        published_raw = (
            item.get("published_at")
            or item.get("published")
            or item.get("pubDate")
            or item.get("pubdate")
            or item.get("date")
        )
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
        aliases = [alias.casefold() for alias in self._keyword_aliases(keyword_text)]
        if not aliases:
            return False

        headline_text = "\n".join(
            str(item.get(field) or "")
            for field in ("title", "summary")
        )
        if self._contains_any_alias(headline_text, aliases):
            return True

        body_text = "\n".join(
            str(item.get(field) or "")
            for field in ("content", "body", "text")
        )
        return self._content_alias_count(body_text, aliases) >= 2

    async def create_crawl_run(
        self,
        *,
        user_id: int,
        keyword_ids: list[int] | None = None,
        force: bool = False,
        today_only: bool = False,
        custom_start_at: datetime | None = None,
        custom_end_at: datetime | None = None,
    ) -> dict[str, Any]:
        keywords = await self._get_user_keywords(user_id=user_id, keyword_ids=keyword_ids)
        if not keywords:
            raise build_error(ErrorCode.VALIDATION_ERROR, "?щ·留곹븷 ?ㅼ썙?쒓? ?놁뒿?덈떎.")

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
            try:
                await self._capture_social_metrics(user_id=user_id, keyword=keyword)
                if custom_start_at and custom_end_at:
                    window_start, window_end = custom_start_at, custom_end_at
                else:
                    window_start, window_end = self._today_crawl_window(keyword) if today_only else self._crawl_window(keyword)
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
    
                    canonical_url = canonicalize_article_url(url)
                    if canonical_url in seen_urls:
                        continue
                    seen_urls.add(canonical_url)
    
                    # ??濡쒖쭅?먯꽌??媛숈? ?ㅼ젣 湲곗궗 URL 湲곗????곕룄濡??듭씪
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

                        thumbnail_url = self._extract_thumbnail_url(crawled)
                        if thumbnail_url:
                            item["thumbnail_url"] = thumbnail_url
    
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
            except Exception:
                logger.exception(
                    "keyword crawling failed keyword_id=%s keyword=%s",
                    keyword.id,
                    keyword.keyword_text,
                )
                continue

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
        publisher = (
            item.get("publisher")
            or item.get("source_name")
            or item.get("source")
            or item.get("media")
            or item.get("media_name")
            or item.get("press")
        )
        language = item.get("language") or "ko"
        content = (
            item.get("content")
            or item.get("description")
            or item.get("summary")
            or item.get("snippet")
            or ""
        ).strip()
        thumbnail_url = self._extract_thumbnail_url(item)
        canonical_url = canonicalize_article_url(url)
        fingerprint = content_fingerprint(content)

        identity_conditions = [Article.url == url]
        if canonical_url:
            identity_conditions.append(Article.canonical_url == canonical_url)
        if fingerprint:
            identity_conditions.append(Article.content_fingerprint == fingerprint)
        from sqlalchemy import or_
        result = await self.db.execute(select(Article).where(or_(*identity_conditions)).limit(1))
        article = result.scalar_one_or_none()

        # Legacy rows do not have identity columns yet. Compare a small same-publisher time window.
        if article is None and publisher and published_at:
            start_at = published_at - timedelta(days=2)
            end_at = published_at + timedelta(days=2)
            candidates = await self.db.execute(
                select(Article).where(
                    Article.publisher == publisher,
                    Article.published_at.between(start_at, end_at),
                ).limit(50)
            )
            article = next((candidate for candidate in candidates.scalars() if is_same_publisher_article(
                left_title=title, left_publisher=publisher, left_content=content, left_url=url,
                right_title=candidate.title, right_publisher=candidate.publisher,
                right_content=candidate.content, right_url=candidate.url,
            )), None)

        if article:
            article.title = title
            article.publisher = publisher
            article.source_type = article.source_type or "TRANSNEWS"
            article.language = article.language or language
            article.canonical_url = article.canonical_url or canonical_url
            article.content_fingerprint = article.content_fingerprint or fingerprint

            if published_at is not None:
                article.published_at = published_at

            if content and not (article.content or "").strip():
                article.content = content

            if thumbnail_url and not article.thumbnail_url:
                article.thumbnail_url = thumbnail_url

            return article, False

        article = Article(
            source_type="TRANSNEWS",
            source_article_id=None,
            url=url,
            canonical_url=canonical_url,
            content_fingerprint=fingerprint,
            title=title,
            publisher=publisher,
            published_at=published_at,
            thumbnail_url=thumbnail_url,
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
                logger.warning("user_id=%s ?щ·留??ㅽ뙣: %s", user_id, exc)

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

