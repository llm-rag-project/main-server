import argparse
import asyncio
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.crawl_run_source import CrawlRunSource


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export source diagnostics for Hongbo comparison backfills.")
    parser.add_argument("--backfill-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    backfill = json.loads(args.backfill_json.read_text(encoding="utf-8"))
    run_to_date = {
        int(item["crawl_result"]["crawl_run_id"]): item["mail_date"]
        for item in backfill.get("dates") or []
        if item.get("crawl_result", {}).get("crawl_run_id")
    }
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(CrawlRunSource)
                .where(CrawlRunSource.crawl_run_id.in_(run_to_date))
                .order_by(CrawlRunSource.crawl_run_id, CrawlRunSource.id)
            )
        ).scalars().all()

    per_date = defaultdict(list)
    source_status = Counter()
    for row in rows:
        mail_date = run_to_date[row.crawl_run_id]
        item = {
            "mail_date": mail_date,
            "crawl_run_id": row.crawl_run_id,
            "source": row.source_name,
            "status": row.status,
            "discovered": row.discovered_count,
            "processed": row.processed_count,
            "stored": row.stored_count,
            "duplicates": row.duplicate_count,
            "rejected_date": row.rejected_date_count,
            "retry_count": row.retry_count,
            "duration_ms": row.duration_ms,
            "error": row.error_message or "",
        }
        per_date[mail_date].append(item)
        source_status[(row.source_name, row.status)] += 1

    date_rows = []
    for mail_date, items in sorted(per_date.items()):
        discovered = sum(item["discovered"] for item in items if item["source"] != "merged_pipeline")
        stored = sum(item["stored"] for item in items if item["source"] == "merged_pipeline")
        timeout_sources = [item["source"] for item in items if item["status"] == "timeout"]
        result_sources = [item["source"] for item in items if item["discovered"] > 0 and item["source"] != "merged_pipeline"]
        if stored:
            reason = "신규 기사 저장"
        elif result_sources:
            reason = "검색 결과는 있었으나 중복·날짜·관련성 기준으로 신규 저장되지 않음"
        elif timeout_sources:
            reason = "검색 결과 없음; 일부 소스 시간 초과"
        else:
            reason = "모든 검색 소스가 해당 과거 날짜 결과를 반환하지 않음"
        date_rows.append(
            {
                "메일 날짜": mail_date,
                "소스 발견 건수": discovered,
                "신규 저장 건수": stored,
                "결과 반환 소스": ", ".join(result_sources),
                "시간 초과 소스": ", ".join(timeout_sources),
                "재수집 결과 설명": reason,
            }
        )

    output = {
        "summary": {
            "run_count": len(run_to_date),
            "date_count": len(date_rows),
            "dates_with_stored_articles": sum(row["신규 저장 건수"] > 0 for row in date_rows),
            "dates_with_any_source_result": sum(bool(row["결과 반환 소스"]) for row in date_rows),
            "dates_with_timeout": sum(bool(row["시간 초과 소스"]) for row in date_rows),
            "source_status_counts": [
                {"source": source, "status": status, "count": count}
                for (source, status), count in sorted(source_status.items())
            ],
        },
        "dates": date_rows,
        "sources": [item for values in per_date.values() for item in values],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(date_rows[0]) if date_rows else ["결과 없음"])
        writer.writeheader()
        writer.writerows(date_rows)
    print(json.dumps({"output": str(args.output_json), **output["summary"]}, ensure_ascii=False))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
