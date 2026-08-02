import asyncio
import json
import os
from datetime import datetime

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.article import Article
from app.models.article_match import ArticleMatch


async def main() -> None:
    target_date = datetime.strptime(os.environ["TARGET_DATE"], "%Y-%m-%d").date()
    keyword_id = int(os.getenv("KEYWORD_ID", "86"))
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(
                    Article.id,
                    Article.title,
                    Article.section,
                    Article.source_type,
                    Article.collection_source,
                    Article.published_at,
                    ArticleMatch.matched_at,
                    ArticleMatch.crawl_run_id,
                )
                .join(ArticleMatch, ArticleMatch.article_id == Article.id)
                .where(
                    ArticleMatch.keyword_id == keyword_id,
                    ArticleMatch.matched_at >= datetime.combine(target_date, datetime.min.time()),
                    ArticleMatch.matched_at <= datetime.combine(target_date, datetime.max.time()),
                )
                .order_by(ArticleMatch.matched_at, Article.id)
            )
        ).mappings().all()
        print(json.dumps([dict(row) for row in rows], ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
