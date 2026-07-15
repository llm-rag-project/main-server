from datetime import datetime, timezone
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
from app.core.transnews_client import TransNewsClient
from app.services.auto_ai_service import AutoAiService
from app.services.article_service import ArticleService
from app.services.article_identity import canonicalize_article_url, content_fingerprint
from app.services.importance_service import ImportanceService

router = APIRouter(prefix="/articles", tags=["articles"])


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


@router.get("")
async def get_articles(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
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

    canonical_url = canonicalize_article_url(url)
    fingerprint = content_fingerprint(content)
    result = await db.execute(
        select(Article).where(
            (Article.url == url) | (Article.canonical_url == canonical_url)
        ).limit(1)
    )
    article = result.scalar_one_or_none()
    created = False

    if article:
        article.title = title or article.title
        article.publisher = publisher or article.publisher
        article.language = article.language or language
        article.published_at = article.published_at or published_at
        if content and (not article.content or len(content) > len(article.content)):
            article.content = content
        if thumbnail_url and not article.thumbnail_url:
            article.thumbnail_url = thumbnail_url
        article.canonical_url = article.canonical_url or canonical_url
        article.content_fingerprint = article.content_fingerprint or fingerprint
    else:
        article = Article(
            source_type="MANUAL_URL",
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
    service = ArticleService(db)
    client = TransNewsClient()
    refreshed: dict[str, str] = {}
    article_ids = list(dict.fromkeys(body.article_ids))[:30]

    for article_id in article_ids:
        if not await service.article_repository.has_article_access(current_user.id, article_id):
            continue
        article = await service.get_article_by_id(article_id)
        if not article:
            continue
        if article.thumbnail_url:
            refreshed[str(article.id)] = article.thumbnail_url
            continue
        try:
            crawl_data = await client.crawl_article(article.url)
            data = crawl_data.get("data") or crawl_data
            thumbnail_url = _extract_thumbnail_url(data)
        except Exception as exc:
            print(f"thumbnail refresh failed article_id={article_id}: {exc}")
            thumbnail_url = None
        if thumbnail_url:
            article.thumbnail_url = thumbnail_url
            refreshed[str(article.id)] = thumbnail_url

    await db.commit()
    return success_response(request=request, data={"items": refreshed})


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
    service = ArticleService(db)
    result = await service.delete_article(user_id=current_user.id, article_id=article_id)
    await db.commit()
    return success_response(request, data=result.model_dump())


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
