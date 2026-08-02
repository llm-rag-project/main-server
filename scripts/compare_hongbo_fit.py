import asyncio
import logging
from collections import Counter

from sqlalchemy import select

from app.api.v1.reports import (
    _dongguk_mail_section_policy,
    _dongguk_section_label,
    _hongbo_selection_score,
)
from app.db.session import AsyncSessionLocal
from app.models.keyword import Keyword
from app.models.user import User
from scripts.export_dongguk_sheet_rows import dashboard_articles_for_keyword_date


DATES = ["2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16"]


def score_section(article):
    if article.section in {"dongguk_core", "dongguk_media", "foundation"}:
        return "foundation"
    return article.section or ""


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
        for mail_date in DATES:
            articles = await dashboard_articles_for_keyword_date(
                db,
                user_id=user.id,
                keyword_id=keyword.id,
                mail_date=mail_date,
                send_time=keyword.email_send_time,
            )
            selected, _ = _dongguk_mail_section_policy(articles, [], articles, mail_date)
            counts = Counter(_dongguk_section_label(article.section) for article in selected)
            print(f"\n## {mail_date} candidates={len(articles)} selected={len(selected)} sections={dict(counts)}")
            for index, article in enumerate(selected, start=1):
                score = _hongbo_selection_score(article, score_section(article), False, mail_date)
                print(
                    f"{index}. [{_dongguk_section_label(article.section)}] "
                    f"{article.title} / {article.source} / score={score:.1f}"
                )


if __name__ == "__main__":
    asyncio.run(main())
