import argparse
import csv
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path

from app.services.article_identity import canonicalize_article_url
from app.services.hongbo_evaluation_service import (
    DEFAULT_ARCHIVE_PATH,
    build_hongbo_evaluation,
)


URL_METHOD = "URL 일치"
TITLE_METHOD = "제목 일치"
TOPIC_METHOD = "동일 주제·다른 대표 기사"
NO_MATCH_METHOD = "불일치"
MATCH_THRESHOLD = 0.58
POLICY_EXCLUDED_STATUS = "AI/정책 제외"
NOT_SELECTED_STATUS = "선정되지 않음"
CANDIDATE_MISSING_STATUS = "후보 미확보"

TOPIC_STOPWORDS = {
    "동국", "동국대", "동국대학교", "기사", "관련", "보도", "개최", "진행", "위해",
    "이번", "통해", "대한", "한다", "했다", "에서", "으로", "그리고", "대학", "학교",
    "포토", "단독", "종합", "뉴스", "오늘", "공식", "소식",
}
STRONG_EVENT_TOKENS = {
    "연등회", "공동학위", "로터스관", "명상엑스포", "불교박람회", "불교사전", "하안거",
    "교사연수", "학술대회", "봉정식", "출가상담", "교육교부금", "고등교육법",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare original Hongbo mails with fresh AI selections.")
    parser.add_argument("--original-json", type=Path, required=True)
    parser.add_argument("--selection-json", type=Path, required=True)
    parser.add_argument("--natural-audit-json", type=Path, required=True)
    parser.add_argument("--final-audit-json", type=Path, required=True)
    parser.add_argument("--archive-json", type=Path, default=DEFAULT_ARCHIVE_PATH)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-date-csv", type=Path, required=True)
    parser.add_argument("--output-detail-csv", type=Path, required=True)
    parser.add_argument("--output-server-only-csv", type=Path, required=True)
    return parser.parse_args()


def _normalize_topic_text(value: str | None) -> str:
    text = unescape(str(value or "")).casefold()
    text = re.sub(r"<[^>]+>|\[[^\]]*언론사[^\]]*\]", " ", text)
    text = text.replace("동국대학교", "동국대").replace("동국대 wise", "동국대")
    replacements = (
        (r"불교동아리들?", "불교동아리"),
        (r"참가(?:한|해|했다|하다)?|참여(?:한|해|했다|하다)?", "참여"),
        (r"업무\s*협약|mou|협약\s*체결", "협약"),
        (r"기부(?:금)?|희사|쾌척", "기부"),
        (r"건립\s*기금|발전\s*기금", "발전기금"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(value: str | None) -> str:
    text = _normalize_topic_text(value)
    text = re.sub(r"\[[^\]]+\]\s*$", " ", text)
    text = re.sub(r"\s*[-|]\s*[^-|]{2,35}$", " ", text)
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def title_tokens(value: str | None) -> set[str]:
    text = re.sub(r"[^0-9a-z가-힣]+", " ", _normalize_topic_text(value))
    return {
        token
        for token in text.split()
        if len(token) >= 2 and token not in TOPIC_STOPWORDS
    }


def urls(item: dict) -> set[str]:
    values = [
        item.get("url"),
        item.get("main_url"),
        *(item.get("urls") or []),
        *(item.get("links") or []),
        *(item.get("related_links") or []),
    ]
    return {canonicalize_article_url(value) for value in values if value}


def _same_section(left: dict, right: dict) -> bool:
    left_section = str(left.get("section") or left.get("section_label") or "")
    right_section = str(right.get("section") or right.get("section_label") or "")
    aliases = {
        "foundation": "foundation", "dongguk_core": "foundation", "법인": "foundation", "건학": "foundation",
        "education": "education", "교육": "education",
        "buddhism": "buddhism", "불교": "buddhism", "종단": "buddhism",
    }

    def key(value: str) -> str:
        return next((target for marker, target in aliases.items() if marker in value), value)

    return bool(left_section and right_section and key(left_section) == key(right_section))


def score_pair(left: dict, right: dict) -> tuple[float, str]:
    if urls(left) & urls(right):
        return 1.0, URL_METHOD

    left_title = normalize_title(left.get("title"))
    right_title = normalize_title(right.get("title"))
    if left_title and left_title == right_title:
        return 0.98, TITLE_METHOD

    sequence = SequenceMatcher(None, left_title, right_title).ratio() if left_title and right_title else 0.0
    left_tokens = title_tokens(left.get("title"))
    right_tokens = title_tokens(right.get("title"))
    shared = left_tokens & right_tokens
    union = left_tokens | right_tokens
    jaccard = len(shared) / len(union) if union else 0.0
    containment = len(shared) / max(1, min(len(left_tokens), len(right_tokens)))
    score = max(sequence, jaccard * 0.95, containment * 0.88)

    same_section = _same_section(left, right)
    has_event_anchor = bool(shared & STRONG_EVENT_TOKENS)
    if same_section and len(shared) >= 3 and containment >= 0.5:
        score = max(score, 0.64)
    elif same_section and has_event_anchor and len(shared) >= 2 and containment >= 0.4:
        score = max(score, 0.61)

    return score, TOPIC_METHOD if score >= MATCH_THRESHOLD else NO_MATCH_METHOD


def greedy_matches(originals: list[dict], server_items: list[dict], threshold: float = MATCH_THRESHOLD) -> list[dict]:
    pairs = []
    for original_index, original in enumerate(originals):
        for server_index, server in enumerate(server_items):
            score, method = score_pair(original, server)
            if score >= threshold:
                pairs.append((score, original_index, server_index, method))
    pairs.sort(reverse=True)
    used_originals: set[int] = set()
    used_server: set[int] = set()
    matches = []
    for score, original_index, server_index, method in pairs:
        if original_index in used_originals or server_index in used_server:
            continue
        used_originals.add(original_index)
        used_server.add(server_index)
        matches.append({
            "original_index": original_index,
            "server_index": server_index,
            "score": round(score, 4),
            "method": method,
        })
    return matches


def audit_match_map(audit_date: dict) -> dict[str, dict]:
    return {normalize_title(item.get("original_title")): item for item in audit_date.get("matches") or []}


def find_excluded(original: dict, excluded: list[dict]) -> tuple[dict | None, float, str]:
    best_item = None
    best_score = 0.0
    best_method = NO_MATCH_METHOD
    for item in excluded:
        score, method = score_pair(original, item)
        if score > best_score:
            best_item, best_score, best_method = item, score, method
    return (best_item, best_score, best_method) if best_score >= MATCH_THRESHOLD else (None, best_score, best_method)


def friendly_reason(value: str | None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return "AI 대표 기사 선정 또는 메일 정책 단계에서 제외되었습니다."
    if "밀려" in text or "최대 기사 수" in text or "목표 수량" in text:
        return "동일 섹션 기사 중 현재 우선순위 기준과 메일 최대 기사 수를 적용한 결과 대표 목록에 포함되지 않았습니다."
    if "관리자가" in text and "제외" in text:
        return "현재 메일 포함 설정에서 제외된 기사입니다."
    return text


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0]) if rows else ["결과 없음"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    original = json.loads(args.original_json.read_text(encoding="utf-8"))
    selection = json.loads(args.selection_json.read_text(encoding="utf-8"))
    natural_audit = json.loads(args.natural_audit_json.read_text(encoding="utf-8"))
    final_audit = json.loads(args.final_audit_json.read_text(encoding="utf-8"))

    date_rows: list[dict] = []
    detail_rows: list[dict] = []
    server_only_rows: list[dict] = []
    reason_counts: Counter = Counter()
    method_counts: Counter = Counter()
    result_dates = {}

    for mail_date, original_doc in sorted(original["dates"].items()):
        originals = original_doc["articles"]
        selected_date = (selection.get("dates") or {}).get(mail_date) or {}
        selected = selected_date.get("selected_articles") or []
        excluded = selected_date.get("excluded_articles") or []
        matches = greedy_matches(originals, selected)
        matched_original = {item["original_index"]: item for item in matches}
        matched_server = {item["server_index"]: item for item in matches}
        url_count = sum(item["method"] == URL_METHOD for item in matches)
        title_count = sum(item["method"] == TITLE_METHOD for item in matches)
        exact_count = sum(item["method"] in {URL_METHOD, TITLE_METHOD} for item in matches)
        topic_count = sum(item["method"] == TOPIC_METHOD for item in matches)
        natural_map = audit_match_map((natural_audit.get("dates") or {}).get(mail_date) or {})
        final_map = audit_match_map((final_audit.get("dates") or {}).get(mail_date) or {})

        per_date_details = []
        date_status_counts: Counter = Counter()
        for index, original_item in enumerate(originals):
            match = matched_original.get(index)
            natural_item = natural_map.get(normalize_title(original_item.get("title"))) or {}
            final_item = final_map.get(normalize_title(original_item.get("title"))) or {}
            if match:
                server_item = selected[match["server_index"]]
                reason = "홍보처 원본과 AI 선정 결과가 일치합니다."
                status = "일치" if match["method"] != TOPIC_METHOD else "동일 주제 대표 매체 차이"
                method_counts[match["method"]] += 1
            else:
                server_item = None
                excluded_item, _, _ = find_excluded(original_item, excluded)
                if excluded_item:
                    status = POLICY_EXCLUDED_STATUS
                    reason = friendly_reason(
                        excluded_item.get("selection_reason")
                        or excluded_item.get("summary")
                    )
                elif final_item.get("matched"):
                    status = NOT_SELECTED_STATUS
                    reason = "후보에는 있었지만 현재 우선순위와 메일 기사 수 정책에 따라 대표 목록에 포함되지 않았습니다."
                else:
                    status = CANDIDATE_MISSING_STATUS
                    reason = "일반 재수집과 원본 URL 검증 백필에서도 서버 후보를 확인하지 못했습니다."
                reason_counts[status] += 1
            date_status_counts[status] += 1
            row = {
                "메일 날짜": mail_date,
                "원본 섹션": original_item.get("section_label"),
                "원본 순번": original_item.get("number"),
                "원본 기사 제목": original_item.get("title"),
                "원본 언론사": original_item.get("source"),
                "원본 URL": "\n".join(original_item.get("urls") or []),
                "비교 결과": status,
                "일치 방식": match["method"] if match else "",
                "유사도": match["score"] if match else "",
                "서버 선정 제목": server_item.get("title") if server_item else "",
                "서버 선정 언론사": server_item.get("source") if server_item else "",
                "서버 선정 URL": "\n".join(server_item.get("links") or []) if server_item else "",
                "차이/제외 이유": reason,
                "일반 재수집 후보 확인": "예" if natural_item.get("matched") else "아니오",
                "최종 후보 확인": "예" if final_item.get("matched") else "아니오",
                "후보 확보 확인": "예" if final_item.get("matched") or match else "아니오",
            }
            detail_rows.append(row)
            per_date_details.append(row)

        per_date_server_only = []
        for index, server_item in enumerate(selected):
            if index in matched_server:
                continue
            item = {
                "메일 날짜": mail_date,
                "서버 선정 제목": server_item.get("title"),
                "언론사": server_item.get("source"),
                "상위 분류": server_item.get("section"),
                "하위 분류": server_item.get("category"),
                "우선순위": server_item.get("priority_name") or server_item.get("priority"),
                "선정 이유": server_item.get("selection_reason"),
                "URL": "\n".join(server_item.get("links") or []),
            }
            server_only_rows.append(item)
            per_date_server_only.append(item)

        original_count = len(originals)
        natural_candidate_count = sum(item["일반 재수집 후보 확인"] == "예" for item in per_date_details)
        verified_candidate_count = sum(item["후보 확보 확인"] == "예" for item in per_date_details)
        policy_excluded_count = (
            date_status_counts[POLICY_EXCLUDED_STATUS]
            + date_status_counts[NOT_SELECTED_STATUS]
        )
        row = {
            "날짜": mail_date,
            "홍보처 원본 기사": original_count,
            "서버 후보 기사": selected_date.get("candidate_count", 0),
            "AI 선정 기사": len(selected),
            "URL 일치": url_count,
            "제목 일치": title_count,
            "정확 일치": exact_count,
            "동일 주제·대표 매체 차이": topic_count,
            "총 일치": len(matches),
            "AI/정책 제외": policy_excluded_count,
            "일반 재수집 후보": natural_candidate_count,
            "날짜 범위 후보 확보": verified_candidate_count,
            "후보 내 비교 대상": verified_candidate_count,
            "원본 기준 일치 실패": original_count - len(matches),
            "서버만 선정": len(selected) - len(matches),
            "일반 재수집률(%)": round(natural_candidate_count / original_count * 100, 1) if original_count else 0,
            "날짜 범위 후보율(%)": round(verified_candidate_count / original_count * 100, 1) if original_count else 0,
            "URL 일치율(%)": round(url_count / original_count * 100, 1) if original_count else 0,
            "정확 일치율(%)": round(exact_count / original_count * 100, 1) if original_count else 0,
            "주제 포함 일치율(%)": round(len(matches) / original_count * 100, 1) if original_count else 0,
            "후보 내 AI 재현율(%)": round(len(matches) / verified_candidate_count * 100, 1) if verified_candidate_count else 0,
            "선택 기사 정확도(%)": round(len(matches) / len(selected) * 100, 1) if selected else 0,
        }
        date_rows.append(row)
        result_dates[mail_date] = {
            "summary": row,
            "details": per_date_details,
            "server_only": per_date_server_only,
        }

    original_count = sum(row["홍보처 원본 기사"] for row in date_rows)
    selected_count = sum(row["AI 선정 기사"] for row in date_rows)
    exact_count = sum(row["정확 일치"] for row in date_rows)
    topic_only_count = sum(row["동일 주제·대표 매체 차이"] for row in date_rows)
    total_match_count = exact_count + topic_only_count
    policy_excluded_count = sum(row["AI/정책 제외"] for row in date_rows)
    natural_candidate_count = sum(row["일반 재수집 후보"] for row in date_rows)
    verified_candidate_count = sum(row["날짜 범위 후보 확보"] for row in date_rows)
    result = {
        "summary": {
            "date_count": len(date_rows),
            "original_count": original_count,
            "selected_count": selected_count,
            "url_match_count": sum(row["URL 일치"] for row in date_rows),
            "title_match_count": sum(row["제목 일치"] for row in date_rows),
            "exact_match_count": exact_count,
            "topic_match_count": topic_only_count,
            "total_match_count": total_match_count,
            "policy_excluded_count": policy_excluded_count,
            "natural_candidate_count": natural_candidate_count,
            "verified_candidate_count": verified_candidate_count,
            "historical_recall_rate": round(total_match_count / original_count * 100, 1) if original_count else 0,
            "natural_candidate_rate": round(natural_candidate_count / original_count * 100, 1) if original_count else 0,
            "verified_candidate_rate": round(verified_candidate_count / original_count * 100, 1) if original_count else 0,
            "candidate_selection_recall_rate": round(total_match_count / verified_candidate_count * 100, 1) if verified_candidate_count else 0,
            "selection_precision_rate": round(total_match_count / selected_count * 100, 1) if selected_count else 0,
            "original_unmatched_count": original_count - total_match_count,
            "server_only_count": selected_count - total_match_count,
            "reason_counts": dict(reason_counts),
            "match_method_counts": dict(method_counts),
        },
        "dates": result_dates,
    }
    archive_stored_count = None
    if args.archive_json.exists():
        archive_payload = json.loads(args.archive_json.read_text(encoding="utf-8"))
        archive_stored_count = int(archive_payload.get("unique_article_count") or 0)
    result["evaluation"] = build_hongbo_evaluation(
        result,
        archive_stored_count=archive_stored_count,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(args.output_date_csv, date_rows)
    write_csv(args.output_detail_csv, detail_rows)
    write_csv(args.output_server_only_csv, server_only_rows)
    print(json.dumps({"output": str(args.output_json), **result["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
