import logging
from datetime import datetime, time, timedelta, timezone
import asyncio
import hashlib
import random
import httpx
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, build_error
from app.core.metrics import track_crawl_run_metrics
from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.crawl_run import CrawlRun
from app.models.crawl_run_article import CrawlRunArticle
from app.models.crawl_run_keyword import CrawlRunKeyword
from app.models.crawl_run_source import CrawlRunSource
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

    def _audit_source_name(self, item: dict[str, Any]) -> str:
        values = [
            item.get("collection_source"),
            item.get("source_type"),
            item.get("pool"),
        ]
        text_value = " ".join(str(value or "") for value in values).casefold()
        if "naver" in text_value:
            return "naver"
        if "google" in text_value or "rss" in text_value:
            return "google_rss"
        if "dongguk_official" in text_value:
            return "dongguk_official"
        if "relation" in text_value:
            return "relation_expansion"
        if "site_direct" in text_value:
            return "media_site_direct"
        if "media_direct" in text_value:
            return "media_direct_pool"
        if (
            "section" in text_value
            and str(item.get("section") or "").casefold() == "education"
        ):
            return "section_pool_education"
        if (
            "section" in text_value
            and str(item.get("section") or "").casefold() == "buddhism"
        ):
            return "section_pool_buddhism"
        if "section" in text_value:
            return "section_pool"
        return "merged_pipeline"

    def _crawl_lock_key(
        self,
        *,
        user_id: int,
        keyword_id: int,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        payload = (
            f"{user_id}:{keyword_id}:{window_start.isoformat()}:{window_end.isoformat()}"
        ).encode("utf-8")
        return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)

    async def _acquire_crawl_lock(
        self,
        *,
        user_id: int,
        keyword_id: int,
        window_start: datetime,
        window_end: datetime,
    ) -> bool:
        lock_key = self._crawl_lock_key(
            user_id=user_id,
            keyword_id=keyword_id,
            window_start=window_start,
            window_end=window_end,
        )
        acquired = await self.db.scalar(
            text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )
        return bool(acquired)

    async def _search_news_with_retry(self, **kwargs) -> tuple[dict[str, Any], int]:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                return await self.transnews_client.search_news(**kwargs), attempt - 1
            except (TransNewsClientError, TimeoutError, OSError, httpx.TransportError) as exc:
                last_error = exc
                if attempt == 3:
                    break
                await asyncio.sleep(
                    min((2 ** (attempt - 1)) + random.uniform(0.1, 0.5), 4.0)
                )
        assert last_error is not None
        raise last_error

    def _record_candidate(
        self,
        *,
        crawl_run_id: int,
        keyword_id: int,
        item: dict[str, Any],
        status: str,
        reason_code: str | None = None,
        article_id: int | None = None,
        is_reconstructed: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        url = self._extract_article_url(item)
        self.db.add(
            CrawlRunArticle(
                crawl_run_id=crawl_run_id,
                keyword_id=keyword_id,
                article_id=article_id,
                source_name=self._audit_source_name(item),
                status=status,
                reason_code=reason_code,
                candidate_url=url,
                canonical_url=canonicalize_article_url(url),
                title=item.get("title"),
                published_at=self._parse_published_at(item),
                is_reconstructed=is_reconstructed,
                details=details or {},
            )
        )

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

        google_news_fallback = None
        for url in candidates:
            if not url:
                continue

            url = str(url).strip()
            if not url:
                continue

            if self._is_google_news_url(url):
                google_news_fallback = google_news_fallback or url
                continue

            return url

        if (
            google_news_fallback
            and item.get("source_type") == "section_pool"
            and item.get("section") in {"education", "buddhism"}
        ):
            return google_news_fallback

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
        if (
            "동국" in (keyword_text or "")
            and item.get("source_type") == "section_pool"
            and item.get("section") in {"education", "buddhism"}
        ):
            return True

        aliases = [alias.casefold() for alias in self._keyword_aliases(keyword_text)]
        if not aliases:
            return False

        headline_text = "\n".join(
            str(item.get(field) or "")
            for field in ("title", "summary")
        )
        if self._contains_any_alias(headline_text, aliases):
            return True

        metadata_values: list[str] = []
        for field in (
            "publisher",
            "source_name",
            "author",
            "byline",
            "keywords",
            "annotations",
            "board",
            "board_name",
        ):
            value = item.get(field)
            if isinstance(value, dict):
                metadata_values.extend(str(item_value) for item_value in value.values())
            elif isinstance(value, (list, tuple, set)):
                metadata_values.extend(str(item_value) for item_value in value)
            elif value not in (None, ""):
                metadata_values.append(str(value))
        if self._contains_any_alias("\n".join(metadata_values), aliases):
            return True

        body_text = "\n".join(
            str(item.get(field) or "")
            for field in ("content", "body", "text")
        )
        return self._content_alias_count(body_text, aliases) >= 2

    def _has_usable_text(self, item: dict[str, Any]) -> bool:
        return any(
            str(item.get(field) or "").strip()
            for field in ("content", "description", "summary", "snippet")
        )

    def _merge_crawled_metadata(
        self,
        item: dict[str, Any],
        crawled: dict[str, Any],
    ) -> None:
        for field in (
            "content",
            "body",
            "text",
            "description",
            "summary",
            "publisher",
            "source_name",
            "author",
            "byline",
            "keywords",
            "annotations",
            "board",
            "board_name",
        ):
            value = crawled.get(field)
            if value not in (None, "", [], {}):
                item[field] = value

        thumbnail_url = self._extract_thumbnail_url(crawled)
        if thumbnail_url:
            item["thumbnail_url"] = thumbnail_url

    async def _enrich_relevance_candidates(
        self,
        *,
        items: list[dict[str, Any]],
        keyword_text: str,
        window_start: datetime,
        window_end: datetime,
    ) -> None:
        candidates_by_url: dict[str, dict[str, Any]] = {}
        for item in items:
            if not self._is_in_crawl_window(item, window_start, window_end):
                continue
            if self._contains_keyword(keyword_text=keyword_text, item=item):
                continue
            url = self._extract_article_url(item)
            if not url:
                continue
            canonical_url = canonicalize_article_url(url)
            entry = candidates_by_url.setdefault(
                canonical_url,
                {"url": url, "items": []},
            )
            entry["items"].append(item)

        semaphore = asyncio.Semaphore(8)

        async def enrich(entry: dict[str, Any]) -> None:
            for item in entry["items"]:
                item["_relevance_enrichment_attempted"] = True
            try:
                async with semaphore:
                    response = await self.transnews_client.crawl_article(entry["url"])
                crawled = response.get("data") or {}
                for item in entry["items"]:
                    item["_relevance_crawled"] = crawled
                    self._merge_crawled_metadata(item, crawled)
            except Exception as exc:
                logger.debug(
                    "relevance enrichment failed url=%s: %s",
                    entry["url"],
                    exc,
                )

        if candidates_by_url:
            await asyncio.gather(
                *(enrich(entry) for entry in candidates_by_url.values())
            )

    @track_crawl_run_metrics
    async def create_crawl_run(
        self,
        *,
        user_id: int,
        keyword_ids: list[int] | None = None,
        force: bool = False,
        today_only: bool = False,
        custom_start_at: datetime | None = None,
        custom_end_at: datetime | None = None,
        capture_social_metrics: bool = True,
        discovery_only: bool = True,
        enrich_for_relevance: bool = True,
        trigger_type: str = "manual",
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
        self.db.add_all(
            CrawlRunKeyword(crawl_run_id=crawl_run.id, keyword_id=keyword.id)
            for keyword in keywords
        )
        await self.db.flush()

        article_count = 0
        articles_to_upload: list[tuple[Article, Keyword]] = []
        partial_success = False

        for keyword in keywords:
            try:
                if capture_social_metrics:
                    await self._capture_social_metrics(user_id=user_id, keyword=keyword)
                if custom_start_at and custom_end_at:
                    window_start, window_end = custom_start_at, custom_end_at
                else:
                    window_start, window_end = self._today_crawl_window(keyword) if today_only else self._crawl_window(keyword)
                acquired = await self._acquire_crawl_lock(
                    user_id=user_id,
                    keyword_id=keyword.id,
                    window_start=window_start,
                    window_end=window_end,
                )
                if not acquired:
                    self.db.add(
                        CrawlRunSource(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            source_name="coordination",
                            trigger_type=trigger_type,
                            status="skipped_locked",
                            window_start=window_start,
                            window_end=window_end,
                            error_message="같은 키워드와 기간의 수집이 이미 실행 중입니다.",
                            diagnostics={},
                        )
                    )
                    partial_success = True
                    continue
                search_keyword = self._search_keyword_with_window(keyword, window_start, window_end)
                is_dongguk_keyword = "동국" in (keyword.keyword_text or "")
                effective_crawl_limit = max(keyword.crawl_limit or 0, 100) if is_dongguk_keyword else keyword.crawl_limit
                try:
                    news_response, gateway_retry_count = await self._search_news_with_retry(
                        keyword=search_keyword,
                        published_after=window_start.isoformat(),
                        published_before=window_end.isoformat(),
                        limit=effective_crawl_limit,
                        include_dongguk_official=is_dongguk_keyword,
                        include_section_pools=is_dongguk_keyword,
                        include_empty_content=is_dongguk_keyword,
                        section_pool_target_count=3 if is_dongguk_keyword else None,
                        timeout_seconds=90 if is_dongguk_keyword else None,
                        discovery_only=discovery_only,
                        include_source_debug=True,
                    )
                except (TransNewsClientError, TimeoutError, OSError, httpx.TransportError) as exc:
                    self.db.add(
                        CrawlRunSource(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            source_name="transnews_gateway",
                            trigger_type=trigger_type,
                            status="failed",
                            window_start=window_start,
                            window_end=window_end,
                            retry_count=2,
                            failed_count=1,
                            error_message=str(exc),
                            diagnostics={"attempt_count": 3},
                        )
                    )
                    partial_success = True
                    logger.exception(
                        "news gateway failed after retries keyword_id=%s keyword=%s",
                        keyword.id,
                        keyword.keyword_text,
                    )
                    continue
    
                if news_response.get("status") != "SUCCESS":
                    logger.debug("NEWS RESPONSE NOT SUCCESS: %s", news_response)
                    partial_success = True
                    continue

                source_records: dict[str, CrawlRunSource] = {}

                def ensure_source_record(source_name: str) -> CrawlRunSource:
                    record = source_records.get(source_name)
                    if record is None:
                        record = CrawlRunSource(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            source_name=source_name,
                            trigger_type=trigger_type,
                            status="success",
                            window_start=window_start,
                            window_end=window_end,
                            diagnostics={},
                        )
                        self.db.add(record)
                        source_records[source_name] = record
                    return record

                def bump_outcome(item: dict[str, Any], field_name: str) -> None:
                    source_names = {"merged_pipeline", self._audit_source_name(item)}
                    for source_name in source_names:
                        record = ensure_source_record(source_name)
                        setattr(record, field_name, int(getattr(record, field_name) or 0) + 1)

                source_debug = news_response.get("source_debug") or {}
                for source_name, debug in source_debug.items():
                    record = ensure_source_record(str(source_name))
                    raw_status = str(debug.get("status") or "unknown").casefold()
                    status_map = {
                        "ok": "success",
                        "empty": "empty",
                        "partial": "partial",
                        "timeout": "timeout",
                        "error": "failed",
                    }
                    record.status = status_map.get(raw_status, raw_status)
                    record.discovered_count = int(debug.get("count") or 0)
                    record.retry_count = int(debug.get("retry_count") or 0)
                    record.duration_ms = int(debug.get("duration_ms") or 0) or None
                    record.error_message = debug.get("error")
                    record.diagnostics = debug
                    if record.status in {"timeout", "failed", "partial"}:
                        partial_success = True

                news_items = list(news_response.get("data") or [])
                if enrich_for_relevance:
                    await self._enrich_relevance_candidates(
                        items=news_items,
                        keyword_text=keyword.keyword_text,
                        window_start=window_start,
                        window_end=window_end,
                    )
                merged_record = ensure_source_record("merged_pipeline")
                merged_record.discovered_count = len(news_items)
                merged_record.retry_count = gateway_retry_count
                merged_record.diagnostics = {
                    "gateway_retry_count": gateway_retry_count,
                    "source_count": len(source_debug),
                }
                if any(
                    record.status in {"timeout", "failed"}
                    for record in source_records.values()
                ):
                    merged_record.status = "partial"
                seen_urls: set[str] = set()
    
                for item in news_items:
                    if not self._is_in_crawl_window(item, window_start, window_end):
                        self._record_candidate(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            item=item,
                            status="rejected",
                            reason_code="outside_date_window",
                        )
                        bump_outcome(item, "rejected_date_count")
                        continue

                    for source_name in {"merged_pipeline", self._audit_source_name(item)}:
                        record = ensure_source_record(source_name)
                        record.processed_count = int(record.processed_count or 0) + 1

                    url = self._extract_article_url(item)
    
                    if not url:
                        logger.debug(
                            "SKIP ITEM: url not resolved title=%s", item.get("title")
                        )
                        self._record_candidate(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            item=item,
                            status="failed",
                            reason_code="url_not_resolved",
                        )
                        bump_outcome(item, "failed_count")
                        continue
    
                    canonical_url = canonicalize_article_url(url)
                    if canonical_url in seen_urls:
                        self._record_candidate(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            item=item,
                            status="duplicate",
                            reason_code="duplicate_in_run",
                        )
                        bump_outcome(item, "duplicate_count")
                        continue
                    seen_urls.add(canonical_url)
    
                    # ??濡쒖쭅?먯꽌??媛숈? ?ㅼ젣 湲곗궗 URL 湲곗????곕룄濡??듭씪
                    item["url"] = url
                    item["original_url"] = url
                    is_relevant = self._contains_keyword(
                        keyword_text=keyword.keyword_text,
                        item=item,
                    )
                    crawled = item.pop("_relevance_crawled", {}) or {}
                    enrichment_attempted = bool(
                        item.pop("_relevance_enrichment_attempted", False)
                    )
                    if not is_relevant and enrich_for_relevance and not enrichment_attempted:
                        try:
                            crawl_response = await self.transnews_client.crawl_article(url)
                            crawled = crawl_response.get("data") or {}
                            self._merge_crawled_metadata(item, crawled)
                            is_relevant = self._contains_keyword(
                                keyword_text=keyword.keyword_text,
                                item=item,
                            )
                        except Exception as exc:
                            logger.debug(
                                "relevance enrichment failed url=%s: %s",
                                url,
                                exc,
                            )

                    if not is_relevant:
                        logger.info(
                            "skip article without literal keyword keyword_id=%s keyword=%s title=%s url=%s",
                            keyword.id,
                            keyword.keyword_text,
                            item.get("title"),
                            url,
                        )
                        self._record_candidate(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            item=item,
                            status="rejected",
                            reason_code="keyword_not_found",
                        )
                        bump_outcome(item, "rejected_relevance_count")
                        continue

                    # The search server already attempts body enrichment. Do not
                    # synchronously crawl the same URL again when it supplied a
                    # usable description/body; a slow publisher previously held
                    # up the entire collection run.
                    if not self._has_usable_text(item):
                        try:
                            if not crawled:
                                crawl_data = await self.transnews_client.crawl_article(url)
                                crawled = crawl_data.get("data") or {}
                            self._merge_crawled_metadata(item, crawled)
                        except Exception as e:
                            logger.debug("crawl_article failed url=%s: %s", url, e)
    
                    article, is_new_article = await self._upsert_article(item)
                    if article is None:
                        self._record_candidate(
                            crawl_run_id=crawl_run.id,
                            keyword_id=keyword.id,
                            item=item,
                            status="failed",
                            reason_code="article_upsert_failed",
                        )
                        bump_outcome(item, "failed_count")
                        continue
    
                    is_new_match = await self._ensure_article_match(
                        article_id=article.id,
                        keyword_id=keyword.id,
                        crawl_run_id=crawl_run.id,
                    )
    
                    should_upload = is_new_article or is_new_match

                    if should_upload:
                        candidate_status = "stored"
                        reason_code = "new_article" if is_new_article else "new_keyword_match"
                        bump_outcome(item, "stored_count")
                    else:
                        candidate_status = "duplicate"
                        reason_code = "already_linked"
                        bump_outcome(item, "duplicate_count")
                    self._record_candidate(
                        crawl_run_id=crawl_run.id,
                        keyword_id=keyword.id,
                        item=item,
                        status=candidate_status,
                        reason_code=reason_code,
                        article_id=article.id,
                    )
    
                    if should_upload:
                        if not await self._has_dify_document(article_id=article.id, keyword_id=keyword.id):
                            articles_to_upload.append((article, keyword))
    
                    article_count += 1
            except DBAPIError:
                logger.exception(
                    "database failure during keyword crawl keyword_id=%s keyword=%s",
                    keyword.id,
                    keyword.keyword_text,
                )
                raise
            except Exception:
                partial_success = True
                logger.exception(
                    "keyword crawling failed keyword_id=%s keyword=%s",
                    keyword.id,
                    keyword.keyword_text,
                )
                continue

        dify_result = await self._upload_articles_to_dify(articles_to_upload)

        crawl_run.status = "PARTIAL" if partial_success else "COMPLETED"
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
        collection_source = item.get("collection_source")
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
            article.collection_source = collection_source or article.collection_source
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

            self._apply_crawler_metadata(article, item)

            return article, False

        article = Article(
            source_type=item.get("source_type") if item.get("source_type") in {"section_pool", "dongguk_official"} else "TRANSNEWS",
            source_article_id=None,
            url=url,
            canonical_url=canonical_url,
            content_fingerprint=fingerprint,
            title=title,
            publisher=publisher,
            collection_source=collection_source,
            published_at=published_at,
            thumbnail_url=thumbnail_url,
            content=content,
            language=language,
            section=item.get("section"),
            pool=item.get("pool"),
            category=item.get("category"),
            trusted_source=item.get("trusted_source"),
            priority_boost=item.get("priority_boost"),
            board=item.get("board"),
            board_name=item.get("board_name"),
        )
        self.db.add(article)
        await self.db.flush()

        return article, True

    def _apply_crawler_metadata(self, article: Article, item: dict[str, Any]) -> None:
        source_type = item.get("source_type")
        crawler_section = item.get("section")
        crawler_pool = item.get("pool")
        crawler_category = item.get("category")
        collection_source = item.get("collection_source")

        if source_type in {"section_pool", "dongguk_official"}:
            article.source_type = source_type
        if collection_source:
            article.collection_source = collection_source

        if crawler_section and source_type in {"section_pool", "dongguk_official"}:
            article.section = crawler_section
        elif crawler_section and not article.section:
            article.section = crawler_section

        if crawler_pool:
            article.pool = crawler_pool
        if crawler_category:
            article.category = crawler_category
        if item.get("trusted_source") is not None:
            article.trusted_source = item.get("trusted_source")
        if item.get("priority_boost") is not None:
            article.priority_boost = item.get("priority_boost")
        if item.get("board"):
            article.board = item.get("board")
        if item.get("board_name"):
            article.board_name = item.get("board_name")

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
                run_result = await self.create_crawl_run(
                    user_id=user_id,
                    force=False,
                    discovery_only=True,
                    enrich_for_relevance=True,
                    trigger_type="scheduled",
                )
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

    async def _record_dify_document(
        self,
        *,
        article: Article,
        keyword: Keyword,
        upload_result: dict[str, Any],
    ) -> bool:
        dataset_id = upload_result["dataset_id"]
        document_id = upload_result["document_id"]

        article_keyword_result = await self.db.execute(
            select(DifyKnowledgeDocument).where(
                DifyKnowledgeDocument.article_id == article.id,
                DifyKnowledgeDocument.keyword_id == keyword.id,
            )
        )
        article_keyword_doc = article_keyword_result.scalar_one_or_none()
        if article_keyword_doc:
            article_keyword_doc.dataset_id = dataset_id
            article_keyword_doc.document_id = document_id
            article_keyword_doc.batch = upload_result.get("batch")
            article_keyword_doc.status = "UPLOADED"
            article_keyword_doc.delete_error = None
            return False

        dataset_document_result = await self.db.execute(
            select(DifyKnowledgeDocument).where(
                DifyKnowledgeDocument.dataset_id == dataset_id,
                DifyKnowledgeDocument.document_id == document_id,
            )
        )
        dataset_document = dataset_document_result.scalar_one_or_none()
        if dataset_document:
            dataset_document.status = "UPLOADED"
            dataset_document.batch = upload_result.get("batch") or dataset_document.batch
            dataset_document.delete_error = None
            logger.info(
                "reused existing Dify document record document_id=%s existing_article_id=%s article_id=%s keyword_id=%s",
                document_id,
                dataset_document.article_id,
                article.id,
                keyword.id,
            )
            return False

        self.db.add(
            DifyKnowledgeDocument(
                user_id=keyword.user_id,
                article_id=article.id,
                keyword_id=keyword.id,
                keyword_text=keyword.keyword_text,
                dataset_id=dataset_id,
                document_id=document_id,
                batch=upload_result.get("batch"),
                status="UPLOADED",
            )
        )
        return True

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
                await self._record_dify_document(article=article, keyword=keyword, upload_result=result)
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

