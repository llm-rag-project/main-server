import argparse
import asyncio
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select

from app.api.v1.reports import _dongguk_articles_for_keyword_date, _draft_response
from app.db.session import AsyncSessionLocal, engine
from app.models.dongguk_mail_draft import DonggukMailDraft
from app.models.keyword import Keyword


SECTION_KEYS = {
    "dongguk_core": "foundation",
    "dongguk_media": "foundation",
    "foundation": "foundation",
    "education": "education",
    "buddhism": "buddhism",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit server coverage against original Hongbo daily mails.")
    parser.add_argument("--original-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keyword-id", type=int, default=86)
    return parser.parse_args()


def canonical_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = re.sub(r"^(?:www\.|m\.)", "", parsed.netloc.lower())
    path = re.sub(r"/+", "/", parsed.path or "/")
    path = re.sub(r"/(?:amp|mobile)/", "/", path, flags=re.I)
    path = re.sub(r"articleViewAmp(?=\.)", "articleView", path, flags=re.I)
    path = path.rstrip("/") or "/"
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    stable_keys = ("arcid", "idxno", "no", "article_id", "articleid", "aid", "id", "key")
    stable_key = next((key for key in stable_keys if params.get(key)), None)
    if stable_key:
        query = urlencode({stable_key: params[stable_key]})
    else:
        ignored = {"cp", "from", "gclid", "fbclid", "medium", "ncid", "ocid", "ref", "source"}
        query = urlencode(
            sorted(
                (key, item)
                for key, item in params.items()
                if not key.lower().startswith("utm_") and key.lower() not in ignored
            )
        )
    return urlunparse(("https", host, path, "", query, "")).rstrip("/")


def normalized_title(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"\[[^\]]+\]\s*$", " ", text)
    text = re.sub(r"\s*[-|]\s*[^-|]{2,30}$", " ", text)
    return re.sub(r"[^0-9a-z가-힣]", "", text.lower())


def title_tokens(value: str | None) -> set[str]:
    text = re.sub(r"[^0-9a-z가-힣]+", " ", str(value or "").lower())
    return {token for token in text.split() if len(token) >= 2}


def match_score(original: dict, candidate) -> tuple[float, str]:
    original_urls = {canonical_url(url) for url in original.get("urls") or [] if canonical_url(url)}
    candidate_urls = {
        canonical_url(url)
        for url in [candidate.url, *(candidate.links or [])]
        if canonical_url(url)
    }
    if original_urls & candidate_urls:
        return 1.0, "URL 일치"
    left = normalized_title(original.get("title"))
    right = normalized_title(candidate.title)
    if left and left == right:
        return 0.98, "제목 정규화 일치"
    sequence = SequenceMatcher(None, left, right).ratio() if left and right else 0.0
    left_tokens = title_tokens(original.get("title"))
    right_tokens = title_tokens(candidate.title)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    score = max(sequence, jaccard * 0.92)
    return score, "유사 제목" if score >= 0.68 else "미일치"


def section_key(value: str | None) -> str:
    return SECTION_KEYS.get(value or "", "unclassified")


async def main() -> None:
    args = parse_args()
    original_payload = json.loads(args.original_json.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "keyword_id": args.keyword_id,
        "original_json": str(args.original_json),
        "dates": {},
    }

    async with AsyncSessionLocal() as db:
        keyword = await db.get(Keyword, args.keyword_id)
        if keyword is None:
            raise SystemExit(f"keyword_id={args.keyword_id} does not exist")
        for mail_date, original_document in sorted(original_payload["dates"].items()):
            candidates = await _dongguk_articles_for_keyword_date(
                db,
                user_id=keyword.user_id,
                keyword_id=keyword.id,
                mail_date=mail_date,
            )
            draft = (
                await db.execute(
                    select(DonggukMailDraft)
                    .where(
                        DonggukMailDraft.user_id == keyword.user_id,
                        DonggukMailDraft.keyword_id == keyword.id,
                        DonggukMailDraft.mail_date == mail_date,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            draft_data = _draft_response(draft)
            selected = draft_data.get("selected_articles") or []
            matches = []
            matched_count = 0
            for original in original_document["articles"]:
                best_candidate = None
                best_score = 0.0
                best_method = "미일치"
                for candidate in candidates:
                    score, method = match_score(original, candidate)
                    if score > best_score:
                        best_candidate = candidate
                        best_score = score
                        best_method = method
                is_match = best_score >= 0.68
                matched_count += int(is_match)
                matches.append(
                    {
                        "original_title": original["title"],
                        "original_section": original["section"],
                        "original_urls": original.get("urls") or [],
                        "matched": is_match,
                        "score": round(best_score, 4),
                        "method": best_method if is_match else "서버 후보 미확인",
                        "candidate_id": best_candidate.id if is_match and best_candidate else None,
                        "candidate_title": best_candidate.title if is_match and best_candidate else None,
                        "candidate_url": best_candidate.url if is_match and best_candidate else None,
                    }
                )
            result["dates"][mail_date] = {
                "original_count": original_document["article_count"],
                "original_section_counts": original_document["section_counts"],
                "candidate_count": len(candidates),
                "candidate_section_counts": dict(Counter(section_key(item.section) for item in candidates)),
                "draft_found": bool(draft_data.get("found")),
                "draft_selected_count": len(selected),
                "draft_selected_section_counts": dict(
                    Counter(section_key(item.get("section")) for item in selected)
                ),
                "original_found_in_candidates": matched_count,
                "original_missing_from_candidates": original_document["article_count"] - matched_count,
                "matches": matches,
            }

    summary = {
        "date_count": len(result["dates"]),
        "dates_with_candidates": sum(bool(item["candidate_count"]) for item in result["dates"].values()),
        "dates_with_drafts": sum(bool(item["draft_found"]) for item in result["dates"].values()),
        "candidate_count": sum(item["candidate_count"] for item in result["dates"].values()),
        "original_count": sum(item["original_count"] for item in result["dates"].values()),
        "original_found_in_candidates": sum(
            item["original_found_in_candidates"] for item in result["dates"].values()
        ),
        "original_missing_from_candidates": sum(
            item["original_missing_from_candidates"] for item in result["dates"].values()
        ),
    }
    result["summary"] = summary
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **summary}, ensure_ascii=False))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
