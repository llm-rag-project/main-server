import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.response import success_response
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.keyword import Keyword
from app.models.user import User
import app.schemas.articles
from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.services.auto_ai_service import AutoAiService
from app.services.article_service import ArticleService
from app.services.article_identity import canonicalize_article_url, content_fingerprint
from app.services.importance_service import ImportanceService

router = APIRouter(prefix="/articles", tags=["articles"])
logger = logging.getLogger(__name__)
WEB_SEARCH_CACHE_TTL_SECONDS = 300
WEB_SEARCH_CACHE_MAX_ITEMS = 64
WEB_SEARCH_FETCH_LIMIT = 50
_web_search_cache: dict[tuple, tuple[float, dict]] = {}
_web_search_inflight: dict[tuple, asyncio.Task] = {}


class ArticleThumbnailRefreshRequest(BaseModel):
    article_ids: list[int]


class ArticleFromUrlRequest(BaseModel):
    keyword_id: int = Field(..., ge=1)
    url: str


def _extract_thumbnail_url(item: dict) -> str | None:
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


def _parse_manual_published_at(item: dict) -> datetime | None:
    value = (
        item.get("published_at")
        or item.get("published")
        or item.get("pubDate")
        or item.get("date")
        or item.get("datetime")
    )
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    try:
        parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _clean_text(value: object, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] if limit else text


def _clean_search_summary(value: object, limit: int = 500) -> str | None:
    text = _clean_text(value, limit)
    if not text:
        return None
    replacement_count = text.count("\ufffd")
    if replacement_count >= 3 or replacement_count / max(len(text), 1) > 0.01:
        return None
    return text


@router.get("")
async def get_articles(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    include_total: bool = Query(True),
    keyword_id: int | None = Query(None, ge=1),
    q: str | None = Query(None),
    language: app.schemas.articles.ArticleLanguage | None = Query(None),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    from_at: str | None = Query(None),
    to_at: str | None = Query(None),
    collected_from_date: str | None = Query(None, alias="collected_from"),
    collected_to_date: str | None = Query(None, alias="collected_to"),
    matched_from_date: str | None = Query(None, alias="matched_from"),
    matched_to_date: str | None = Query(None, alias="matched_to"),
    min_importance: float | None = Query(None, ge=0.0, le=1.0),
    max_importance: float | None = Query(None, ge=0.0, le=1.0),
    has_feedback: bool | None = Query(None),
    liked: bool | None = Query(None),
    sort: app.schemas.articles.ArticleSort = Query(app.schemas.articles.ArticleSort.published_at_desc),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    query = app.schemas.articles.ArticleListQuery(
        page=page,
        size=size,
        include_total=include_total,
        keyword_id=keyword_id,
        q=q,
        language=language,
        **{
            "from": from_date,
            "to": to_date,
            "from_at": from_at,
            "to_at": to_at,
            "collected_from": collected_from_date,
            "collected_to": collected_to_date,
            "matched_from": matched_from_date,
            "matched_to": matched_to_date,
            "min_importance": min_importance,
            "max_importance": max_importance,
            "has_feedback": has_feedback,
            "liked": liked,
            "sort": sort,
        },
    )

    service = ArticleService(db)
    items, total = await service.get_article_list(user_id=current_user.id, query=query)

    response = app.schemas.articles.ArticleListResponse(
        items=[app.schemas.articles.ArticleListItem(**item) for item in items],
        page_info=app.schemas.articles.PageInfo(
            page=query.page,
            size=query.size,
            total=total,
            has_next=(query.page * query.size) < total,
        ),
    )
    return success_response(request=request, data=response.model_dump())


@router.post("/from-url")
async def create_article_from_url(
    request: Request,
    body: ArticleFromUrlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise build_error(ErrorCode.VALIDATION_ERROR, "http 또는 https 기사 URL을 입력해 주세요.")

    keyword = await db.get(Keyword, body.keyword_id)
    if not keyword or keyword.user_id != current_user.id:
        raise build_error(ErrorCode.NOT_FOUND, "keyword not found")

    client = TransNewsClient()
    crawl_data = await client.crawl_article(url)
    data = crawl_data.get("data") or crawl_data
    resolved_url = _clean_text(data.get("url") or data.get("original_url") or url)

    title = _clean_text(
        data.get("title")
        or data.get("headline")
        or data.get("name")
        or "제목 없음",
    )
    publisher = _clean_text(
        data.get("publisher")
        or data.get("source")
        or data.get("source_name")
        or data.get("media")
        or data.get("press"),
        255,
    ) or None
    content = _clean_text(
        data.get("content")
        or data.get("body")
        or data.get("article_content")
        or data.get("text")
        or data.get("summary")
        or data.get("description")
        or title,
    )
    published_at = _parse_manual_published_at(data) or datetime.now(timezone.utc)
    thumbnail_url = _extract_thumbnail_url(data)
    language = data.get("language") or "ko"

    canonical_url = canonicalize_article_url(resolved_url)
    fingerprint = content_fingerprint(content)
    result = await db.execute(
        select(Article).where(
            (Article.url == url)
            | (Article.url == resolved_url)
            | (Article.canonical_url == canonical_url)
        ).limit(1)
    )
    article = result.scalar_one_or_none()
    created = False

    if article:
        article.url = resolved_url
        article.title = title or article.title
        article.publisher = publisher or article.publisher
        article.language = article.language or language
        article.published_at = article.published_at or published_at
        if content and (not article.content or len(content) > len(article.content)):
            article.content = content
        if thumbnail_url and not article.thumbnail_url:
            article.thumbnail_url = thumbnail_url
        article.canonical_url = canonical_url
        article.content_fingerprint = article.content_fingerprint or fingerprint
    else:
        article = Article(
            source_type="MANUAL_URL",
            source_article_id=None,
            url=resolved_url,
            canonical_url=canonical_url,
            content_fingerprint=fingerprint,
            title=title,
            publisher=publisher,
            published_at=published_at,
            thumbnail_url=thumbnail_url,
            content=content,
            language=language,
        )
        db.add(article)
        await db.flush()
        created = True

    match_result = await db.execute(
        select(ArticleMatch).where(
            ArticleMatch.article_id == article.id,
            ArticleMatch.keyword_id == keyword.id,
        )
    )
    matched = match_result.scalar_one_or_none()
    if matched is None:
        db.add(ArticleMatch(article_id=article.id, keyword_id=keyword.id, crawl_run_id=None))
        await db.flush()

    ai_result = await AutoAiService(db).run_for_articles(
        user_id=current_user.id,
        article_ids=[article.id],
    )
    await db.commit()

    service = ArticleService(db)
    detail = await service.get_article_detail(user_id=current_user.id, article_id=article.id)
    return success_response(
        request=request,
        data={
            "article": detail.model_dump(),
            "created": created,
            "summary_count": ai_result.get("summary_count", 0),
            "importance_count": ai_result.get("importance_count", 0),
            "already_scored_count": ai_result.get("already_scored_count", 0),
        },
    )


async def search_web_news(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100),
    page: int = Query(1, ge=1, le=10),
    size: int = Query(10, ge=1, le=20),
    sort: app.schemas.articles.WebNewsSort = Query(app.schemas.articles.WebNewsSort.relevance),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    publisher: str | None = Query(None, max_length=100),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    del current_user  # Authentication is required even though search itself is not user-specific.
    if from_date and to_date and from_date > to_date:
        raise build_error(ErrorCode.VALIDATION_ERROR, "시작일은 종료일보다 늦을 수 없습니다.")
    if from_date and to_date and (to_date - from_date).days > 31:
        raise build_error(ErrorCode.VALIDATION_ERROR, "웹 검색 기간은 최대 31일입니다.")

    fetch_limit = WEB_SEARCH_FETCH_LIMIT
    search_key = (
        q.strip().casefold(),
        from_date.isoformat() if from_date else "",
        to_date.isoformat() if to_date else "",
        sort.value,
    )
    now = time.monotonic()
    cached = _web_search_cache.get(search_key)
    if cached and now - cached[0] <= WEB_SEARCH_CACHE_TTL_SECONDS:
        result = cached[1]
    else:
        try:
            task = _web_search_inflight.get(search_key)
            if task is None or task.done():
                task = asyncio.create_task(
                    TransNewsClient().search_news(
                        q.strip(),
                        published_after=from_date.isoformat() if from_date else None,
                        published_before=to_date.isoformat() if to_date else None,
                        limit=fetch_limit,
                        include_empty_content=True,
                        timeout_seconds=15,
                        discovery_only=True,
                        search_sort=sort.value,
                    )
                )
                _web_search_inflight[search_key] = task
            result = await asyncio.shield(task)
        except TransNewsClientError as exc:
            raise build_error(ErrorCode.UPSTREAM_ERROR, f"뉴스 검색 서버 오류: {exc}") from exc
        except Exception as exc:
            logger.exception("web news search failed")
            raise build_error(ErrorCode.UPSTREAM_ERROR, "뉴스 검색 서버에 연결할 수 없습니다.") from exc
        finally:
            active_task = _web_search_inflight.get(search_key)
            if active_task is not None and active_task.done():
                _web_search_inflight.pop(search_key, None)
        if len(_web_search_cache) >= WEB_SEARCH_CACHE_MAX_ITEMS:
            oldest_key = min(_web_search_cache, key=lambda key: _web_search_cache[key][0])
            _web_search_cache.pop(oldest_key, None)
        _web_search_cache[search_key] = (now, result)

    normalized: list[dict] = []
    seen_urls: set[str] = set()
    publisher_filter = (publisher or "").strip().lower()
    for item in result.get("data") or []:
        url = _clean_text(
            item.get("original_url")
            or item.get("article_link")
            or item.get("link")
        )
        if not url or not url.startswith(("http://", "https://")):
            continue
        canonical_url = canonicalize_article_url(url)
        if canonical_url in seen_urls:
            continue
        source = _clean_text(item.get("source_name") or item.get("publisher") or item.get("source"), 255)
        if publisher_filter and publisher_filter not in (source or "").lower():
            continue
        published_at = _parse_manual_published_at(item)
        if from_date and published_at and published_at.date() < from_date:
            continue
        if to_date and published_at and published_at.date() > to_date:
            continue
        seen_urls.add(canonical_url)
        normalized.append(
            {
                "title": _clean_text(item.get("title") or "제목 없음"),
                "source": source or None,
                "published_at": published_at,
                "summary": _clean_search_summary(
                    item.get("content") or item.get("summary") or item.get("description")
                ),
                "url": url,
                "thumbnail_url": _extract_thumbnail_url(item),
            }
        )

    if sort == app.schemas.articles.WebNewsSort.latest:
        normalized.sort(
            key=lambda item: item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    offset = (page - 1) * size
    items = normalized[offset:offset + size]
    response = app.schemas.articles.WebNewsSearchResponse(
        items=[app.schemas.articles.WebNewsSearchItem(**item) for item in items],
        page_info=app.schemas.articles.PageInfo(
            page=page,
            size=size,
            total=len(normalized),
            has_next=(offset + size) < len(normalized),
        ),
        query=q.strip(),
        sort=sort,
    )
    return success_response(request=request, data=response.model_dump())


@router.get("/{article_id}")
async def get_article_detail(
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = ArticleService(db)
    result = await service.get_article_detail(user_id=current_user.id, article_id=article_id)
    return success_response(request=request, data=result.model_dump())


@router.post("/thumbnails/refresh")
async def refresh_article_thumbnails(
    request: Request,
    body: ArticleThumbnailRefreshRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    client = TransNewsClient()
    refreshed: dict[str, str] = {}
    article_ids = list(dict.fromkeys(body.article_ids))[:30]
    if not article_ids:
        return success_response(request=request, data={"items": refreshed, "attempted_count": 0})

    result = await db.execute(
        select(Article)
        .join(ArticleMatch, ArticleMatch.article_id == Article.id)
        .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
        .where(
            Article.id.in_(article_ids),
            Keyword.user_id == current_user.id,
        )
        .distinct()
    )
    articles_by_id = {article.id: article for article in result.scalars().all()}
    articles = [articles_by_id[article_id] for article_id in article_ids if article_id in articles_by_id]
    retry_after = datetime.now(timezone.utc) - timedelta(hours=6)
    pending: list[Article] = []

    for article in articles:
        if article.thumbnail_url:
            refreshed[str(article.id)] = article.thumbnail_url
            continue
        if article.thumbnail_checked_at and article.thumbnail_checked_at >= retry_after:
            continue
        pending.append(article)

    semaphore = asyncio.Semaphore(5)

    async def fetch_thumbnail(article: Article) -> tuple[Article, str | None]:
        try:
            async with semaphore:
                crawl_data = await client.crawl_article(article.url)
                data = crawl_data.get("data") or crawl_data
                return article, _extract_thumbnail_url(data)
        except Exception as exc:
            logger.info("thumbnail refresh failed article_id=%s: %s", article.id, exc)
            return article, None

    fetched = await asyncio.gather(*(fetch_thumbnail(article) for article in pending))
    checked_at = datetime.now(timezone.utc)
    for article, thumbnail_url in fetched:
        article.thumbnail_checked_at = checked_at
        if thumbnail_url:
            article.thumbnail_url = thumbnail_url
            refreshed[str(article.id)] = thumbnail_url

    await db.commit()
    return success_response(
        request=request,
        data={
            "items": refreshed,
            "attempted_count": len(pending),
            "skipped_recent_count": len(articles) - len(pending) - len(refreshed),
        },
    )


@router.get("/{article_id}/feedback")
async def get_my_article_feedback(
    request: Request,
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = ArticleService(db)
    result = await service.get_my_feedback_by_article(
        user_id=current_user.id,
        article_id=article_id,
    )
    return success_response(request, data=result.model_dump() if result else None)


@router.delete("/{article_id}/feedback")
async def delete_my_article_feedback(
    request: Request,
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = ArticleService(db)
    result = await service.delete_my_feedback_by_article(
        user_id=current_user.id,
        article_id=article_id,
    )
    await db.commit()
    return success_response(request, data=result.model_dump())


@router.delete("/{article_id}")
async def delete_article(
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    raise build_error(
        ErrorCode.VALIDATION_ERROR,
        "기사 삭제는 먼저 휴지통으로 이동한 뒤 휴지통 화면에서 영구 삭제해 주세요.",
    )


@router.get("/{article_id}/importance")
async def get_article_importance(
    article_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = ImportanceService(db)
    result = await service.get_article_importance(
        user_id=current_user.id,
        article_id=article_id,
    )
    return success_response(request=request, data=result)
