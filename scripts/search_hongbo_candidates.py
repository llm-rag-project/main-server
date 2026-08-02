import asyncio
import logging

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.keyword import Keyword
from app.models.user import User
from scripts.export_dongguk_sheet_rows import dashboard_articles_for_keyword_date


QUERIES = {
    "2026-07-13": ["선재봇", "한양대", "황창순", "강수철", "낙산사", "등록금"],
    "2026-07-14": ["황훈성", "하안거", "Dream Workshop", "법무대학원", "교원창업", "정광고", "보존처리"],
    "2026-07-15": ["지능IoT", "중구불교협의회", "명상엑스포", "핀테크", "고등교육법", "비파괴", "종교까지"],
    "2026-07-16": ["C포럼", "창업가", "이경", "명상엑스포", "교육교부금", "부산", "불교중앙박물관"],
}


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
        for mail_date, words in QUERIES.items():
            articles = await dashboard_articles_for_keyword_date(
                db,
                user_id=user.id,
                keyword_id=keyword.id,
                mail_date=mail_date,
                send_time=keyword.email_send_time,
            )
            print(f"\n## {mail_date} candidates={len(articles)}")
            for word in words:
                matches = [
                    article
                    for article in articles
                    if word.lower() in f"{article.title or ''} {article.summary or ''}".lower()
                ]
                print(f"- {word}: {len(matches)}")
                for article in matches[:5]:
                    print(f"  * {article.title} / {article.source} / {article.published_at}")


if __name__ == "__main__":
    asyncio.run(main())
