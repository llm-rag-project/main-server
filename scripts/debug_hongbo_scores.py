import asyncio
import logging

from sqlalchemy import select

from app.api.v1.reports import (
    _dongguk_candidate_section_key,
    _hongbo_selection_score,
)
from app.db.session import AsyncSessionLocal
from app.models.keyword import Keyword
from app.models.user import User
from scripts.export_dongguk_sheet_rows import dashboard_articles_for_keyword_date


async def main():
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
    async with AsyncSessionLocal() as db:
        try:
            db.bind.echo = False
        except Exception:
            pass
        row = await db.execute(
            select(Keyword, User)
            .join(User, User.id == Keyword.user_id)
            .where(Keyword.keyword_text == "동국대학교")
            .limit(1)
        )
        keyword, user = row.first()
        mail_date = "2026-07-15"
        articles = await dashboard_articles_for_keyword_date(
            db,
            user_id=user.id,
            keyword_id=keyword.id,
            mail_date=mail_date,
            send_time=keyword.email_send_time,
        )
        rows = []
        for article in articles:
            section = _dongguk_candidate_section_key(article)
            if section == "foundation":
                rows.append((_hongbo_selection_score(article, section, False, mail_date), article))
        for score, article in sorted(rows, key=lambda row: row[0], reverse=True)[:20]:
            print(f"{score:.1f} / {article.title} / {article.source} / {article.published_at}")


if __name__ == "__main__":
    asyncio.run(main())
