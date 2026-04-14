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
            seen_urls: set[str] = set()

            for item in news_items:
                url = item.get("url") or item.get("link")
                if not url:
                    continue

                first_seen_in_response = url not in seen_urls
                if first_seen_in_response:
                    seen_urls.add(url)
                else:
                    continue

                # 뉴스 목록 응답에는 본문이 비어 있을 수 있어서, 기사 상세 크롤링으로 본문 보강
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

                    print(
                        f"[DEBUG] CRAWL ARTICLE url={url}, content_length={len(item.get('content') or '')}"
                    )
                except Exception as e:
                    print(f"[DEBUG] crawl_article failed url={url}: {e}")

                article, is_new_article = await self._upsert_article(item)
                if article is None:
                    continue

                is_new_match = await self._ensure_article_match(
                    article_id=article.id,
                    keyword_id=keyword.id,
                    crawl_run_id=crawl_run.id,
                )

                should_upload = is_new_article or is_new_match or first_seen_in_response

                if should_upload:
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
        keywords = list(result.scalars().all())

        # DB에서 실제로 어떤 키워드들이 조회됐는지 확인
        print("[DEBUG] _get_user_keywords result =", [(k.id, k.keyword_text) for k in keywords])

        return keywords

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

        # URL이 없으면 기사로 저장할 수 없으므로 스킵
        if not url:
            print("[DEBUG] UPSERT SKIP: url is missing")
            return None, False

        title = item.get("title") or "제목 없음"
        publisher = item.get("publisher") or item.get("source")
        language = item.get("language") or "ko"
        content = (item.get("content") or "").strip()

        result = await self.db.execute(select(Article).where(Article.url == url))
        article = result.scalar_one_or_none()

        # 같은 URL이 이미 있으면 기존 기사로 판단
        print("[DEBUG] UPSERT CHECK =", {"url": url, "exists": article is not None})

        if article:
            article.title = title
            article.publisher = publisher
            article.source_type = article.source_type or "TRANSNEWS"
            article.language = article.language or language

            if published_at is not None:
                article.published_at = published_at

            # 기존 기사에 content가 비어 있으면 이번 content로 보완
            if content and not (article.content or "").strip():
                article.content = content
                print(f"[DEBUG] FILLED EMPTY CONTENT article_id={article.id}")

            return article, False

        # 같은 URL이 없으면 새 기사로 생성
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

        print(f"[DEBUG] NEW ARTICLE CREATED article_id={article.id}, url={url}")

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

        # 이미 같은 article_id + keyword_id 매칭이 있는지 확인
        print(
            "[DEBUG] ENSURE_MATCH CHECK =",
            {
                "article_id": article_id,
                "keyword_id": keyword_id,
                "exists": match is not None,
            },
        )

        if match is None:
            self.db.add(
                ArticleMatch(
                    article_id=article_id,
                    keyword_id=keyword_id,
                    crawl_run_id=crawl_run_id,
                )
            )
            await self.db.flush()

            print(
                f"[DEBUG] NEW MATCH CREATED article_id={article_id}, "
                f"keyword_id={keyword_id}"
            )
            return True

        # 기존 매칭인데 crawl_run_id가 비어 있으면 보완
        if getattr(match, "crawl_run_id", None) is None:
            match.crawl_run_id = crawl_run_id
            print(
                f"[DEBUG] EXISTING MATCH UPDATED crawl_run_id "
                f"article_id={article_id}, keyword_id={keyword_id}"
            )

        return False

    async def _upload_articles_to_dify(self, articles: list[Article]) -> dict[str, Any]:
        # 업로드 대상이 없으면 바로 0건 반환
        if not articles:
            print("[DEBUG] NO ARTICLES TO UPLOAD TO DIFY")
            return {
                "uploaded_count": 0,
                "failed_count": 0,
                "uploaded": [],
                "failed": [],
            }

        # 실제 Dify 업로드 대상 article_id 확인
        print("[DEBUG] DIFY UPLOAD ARTICLE IDS =", [article.id for article in articles])

        return await self.dify_upload_service.upload_articles_to_knowledge(articles)