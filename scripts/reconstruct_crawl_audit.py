import argparse
import asyncio
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.crawl_run import CrawlRun
from app.models.crawl_run_article import CrawlRunArticle
from app.models.crawl_run_keyword import CrawlRunKeyword
from app.models.crawl_run_source import CrawlRunSource


KST = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct best-effort audit records for legacy crawl runs."
    )
    parser.add_argument("--keyword-id", type=int, required=True)
    parser.add_argument("--run-id-start", type=int, required=True)
    parser.add_argument("--run-id-end", type=int, required=True)
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    expected_count = args.run_id_end - args.run_id_start + 1
    async with AsyncSessionLocal() as db:
        runs = list(
            (
                await db.execute(
                    select(CrawlRun)
                    .join(
                        CrawlRunKeyword,
                        CrawlRunKeyword.crawl_run_id == CrawlRun.id,
                    )
                    .where(
                        CrawlRun.id.between(args.run_id_start, args.run_id_end),
                        CrawlRunKeyword.keyword_id == args.keyword_id,
                    )
                    .order_by(CrawlRun.id)
                )
            ).scalars()
        )
        if len(runs) != expected_count:
            raise RuntimeError(
                f"Expected {expected_count} runs but found {len(runs)}. "
                "Refusing to infer an incomplete date mapping."
            )

        created_sources = 0
        created_articles = 0
        for offset, run in enumerate(runs):
            target_date = args.from_date + timedelta(days=offset)
            window_start = datetime.combine(target_date, time.min, tzinfo=KST)
            window_end = datetime.combine(target_date, time.max, tzinfo=KST)
            existing = await db.scalar(
                select(CrawlRunSource.id).where(
                    CrawlRunSource.crawl_run_id == run.id,
                    CrawlRunSource.keyword_id == args.keyword_id,
                    CrawlRunSource.source_name == "merged_pipeline",
                )
            )
            if existing:
                continue

            match_rows = (
                await db.execute(
                    select(ArticleMatch, Article)
                    .join(Article, Article.id == ArticleMatch.article_id)
                    .where(
                        ArticleMatch.crawl_run_id == run.id,
                        ArticleMatch.keyword_id == args.keyword_id,
                    )
                )
            ).all()
            stored_count = len(match_rows)
            accepted_count = int(run.article_count or 0)
            inferred_duplicate_count = max(accepted_count - stored_count, 0)
            db.add(
                CrawlRunSource(
                    crawl_run_id=run.id,
                    keyword_id=args.keyword_id,
                    source_name="merged_pipeline",
                    trigger_type="backfill",
                    status="reconstructed",
                    window_start=window_start,
                    window_end=window_end,
                    discovered_count=accepted_count,
                    processed_count=accepted_count,
                    stored_count=stored_count,
                    duplicate_count=inferred_duplicate_count,
                    is_reconstructed=True,
                    diagnostics={
                        "reconstruction_method": "crawl_run.article_count + article_matches.crawl_run_id",
                        "source_breakdown_available": False,
                        "exact_candidate_outcomes_available": False,
                        "note": (
                            "백필 당시 저장된 실행 합계와 신규 기사 연결을 이용해 재구성했습니다. "
                            "소스별 최초 후보 및 개별 제외 사유는 당시 저장되지 않았습니다."
                        ),
                    },
                )
            )
            created_sources += 1

            for match, article in match_rows:
                db.add(
                    CrawlRunArticle(
                        crawl_run_id=run.id,
                        keyword_id=args.keyword_id,
                        article_id=article.id,
                        source_name=article.collection_source or "legacy_combined",
                        status="stored",
                        reason_code="reconstructed_new_keyword_match",
                        candidate_url=article.url,
                        canonical_url=article.canonical_url,
                        title=article.title,
                        published_at=article.published_at,
                        is_reconstructed=True,
                        details={
                            "reconstruction_method": "article_matches.crawl_run_id",
                        },
                    )
                )
                created_articles += 1

        if args.dry_run:
            await db.rollback()
        else:
            await db.commit()
        print(
            {
                "run_count": len(runs),
                "created_source_records": created_sources,
                "created_article_records": created_articles,
                "dry_run": args.dry_run,
                "from_date": args.from_date.isoformat(),
                "to_date": (args.from_date + timedelta(days=len(runs) - 1)).isoformat(),
            }
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
