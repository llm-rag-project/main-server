from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPARISON_PATH = (
    PROJECT_ROOT / "artifacts" / "hongbo_original_comparison" / "comparison_final.json"
)
DEFAULT_ARCHIVE_PATH = (
    PROJECT_ROOT / "artifacts" / "hongbo_original_comparison" / "archive_url_backfill.json"
)
SECTION_ORDER = (
    "동국대 [법인/건학위]",
    "대학 [교육]",
    "불교 [종단]",
)
EXACT_METHODS = {"URL 일치", "제목 일치"}
TOPIC_METHOD = "동일 주제·다른 대표 기사"
RECOVERED_STATUS = "일반 수집 누락"
MISSING_STATUS = "후보 미확보"
POLICY_EXCLUDED_STATUS = "AI/정책 제외"
NOT_SELECTED_STATUS = "선정되지 않음"


def _rate(count: int, total: int) -> float:
    return round(count / total * 100, 1) if total else 0.0


def _target_gap(current: int, total: int, target_rate: float) -> int:
    return max(0, math.ceil(total * target_rate / 100) - current)


def _empty_category(label: str) -> dict:
    return {
        "label": label,
        "original_count": 0,
        "archive_stored_count": 0,
        "automatic_collection_count": 0,
        "recovered_collection_count": 0,
        "candidate_available_count": 0,
        "url_match_count": 0,
        "title_match_count": 0,
        "exact_match_count": 0,
        "topic_only_match_count": 0,
        "topic_inclusive_match_count": 0,
        "policy_excluded_count": 0,
        "candidate_missing_count": 0,
    }


def _yes(value: object) -> bool:
    return str(value or "").strip() == "예"


def build_hongbo_evaluation(
    payload: dict,
    *,
    target_collection_rate: float = 95.0,
    archive_stored_count: int | None = None,
) -> dict:
    details = [
        item
        for date_result in (payload.get("dates") or {}).values()
        for item in (date_result.get("details") or [])
    ]
    categories = {label: _empty_category(label) for label in SECTION_ORDER}
    method_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for item in details:
        label = str(item.get("원본 섹션") or "미분류").strip()
        category = categories.setdefault(label, _empty_category(label))
        category["original_count"] += 1

        method = str(item.get("일치 방식") or "").strip()
        status = str(item.get("비교 결과") or "").strip()
        if method:
            method_counts[method] += 1
        if status:
            status_counts[status] += 1

        has_candidate_audit = "후보 확보 확인" in item or "최종 후보 확인" in item
        if has_candidate_audit:
            candidate_available = _yes(item.get("후보 확보 확인")) or _yes(item.get("최종 후보 확인"))
            automatic_available = _yes(item.get("일반 재수집 후보 확인"))
        else:
            candidate_available = status != MISSING_STATUS
            automatic_available = status not in {RECOVERED_STATUS, MISSING_STATUS}

        category["automatic_collection_count"] += int(automatic_available)
        category["candidate_available_count"] += int(candidate_available)
        category["recovered_collection_count"] += int(candidate_available and not automatic_available)
        category["candidate_missing_count"] += int(not candidate_available)
        if status in {POLICY_EXCLUDED_STATUS, NOT_SELECTED_STATUS}:
            category["policy_excluded_count"] += 1
        if method == "URL 일치":
            category["url_match_count"] += 1
        elif method == "제목 일치":
            category["title_match_count"] += 1
        if method in EXACT_METHODS:
            category["exact_match_count"] += 1
        elif method == TOPIC_METHOD:
            category["topic_only_match_count"] += 1
        if method in EXACT_METHODS or method == TOPIC_METHOD:
            category["topic_inclusive_match_count"] += 1

    category_rows = []
    for label in [*SECTION_ORDER, *sorted(set(categories) - set(SECTION_ORDER))]:
        row = categories[label]
        total = row["original_count"]
        policy_comparable_count = row["candidate_available_count"]
        row.update(
            {
                "policy_comparable_count": policy_comparable_count,
                "archive_stored_rate": _rate(row["archive_stored_count"], total),
                "automatic_collection_rate": _rate(row["automatic_collection_count"], total),
                "candidate_recall_rate": _rate(row["candidate_available_count"], total),
                "url_match_rate": _rate(row["url_match_count"], total),
                "exact_match_rate": _rate(row["exact_match_count"], total),
                "topic_match_rate": _rate(row["topic_inclusive_match_count"], total),
                "policy_adjusted_url_match_rate": _rate(row["url_match_count"], policy_comparable_count),
                "policy_adjusted_topic_match_rate": _rate(row["topic_inclusive_match_count"], policy_comparable_count),
                "candidate_selection_recall_rate": _rate(row["topic_inclusive_match_count"], policy_comparable_count),
            }
        )
        category_rows.append(row)

    total = sum(row["original_count"] for row in category_rows)
    automatic_count = sum(row["automatic_collection_count"] for row in category_rows)
    recovered_count = sum(row["recovered_collection_count"] for row in category_rows)
    candidate_count = sum(row["candidate_available_count"] for row in category_rows)
    url_count = sum(row["url_match_count"] for row in category_rows)
    title_count = sum(row["title_match_count"] for row in category_rows)
    exact_count = url_count + title_count
    topic_only_count = sum(row["topic_only_match_count"] for row in category_rows)
    topic_count = exact_count + topic_only_count
    missing_count = sum(row["candidate_missing_count"] for row in category_rows)
    policy_excluded_count = sum(row["policy_excluded_count"] for row in category_rows)
    policy_comparable_count = candidate_count
    selected_count = int((payload.get("summary") or {}).get("selected_count") or 0)
    stored_count = max(0, min(total, int(archive_stored_count or 0)))
    archive_rate = _rate(stored_count, total)
    if stored_count >= total:
        for row in category_rows:
            row["archive_stored_count"] = row["original_count"]
            row["archive_stored_rate"] = _rate(
                row["archive_stored_count"],
                row["original_count"],
            )

    date_rows = []
    for mail_date, date_result in sorted((payload.get("dates") or {}).items()):
        summary = date_result.get("summary") or {}
        details_for_date = date_result.get("details") or []
        original_count = int(summary.get("홍보처 원본 기사") or 0)
        exact_match_count = int(summary.get("정확 일치") or 0)
        topic_only_match_count = int(summary.get("동일 주제·대표 매체 차이") or 0)
        candidate_available_count = sum(
            _yes(item.get("후보 확보 확인"))
            or _yes(item.get("최종 후보 확인"))
            or bool(item.get("일치 방식"))
            for item in details_for_date
        )
        date_rows.append(
            {
                "date": mail_date,
                "original_count": original_count,
                "exact_match_count": exact_match_count,
                "topic_only_match_count": topic_only_match_count,
                "topic_match_rate": _rate(exact_match_count + topic_only_match_count, original_count),
                "candidate_available_count": candidate_available_count,
                "candidate_selection_recall_rate": _rate(
                    exact_match_count + topic_only_match_count,
                    candidate_available_count,
                ),
            }
        )

    lowest_dates = sorted(
        date_rows,
        key=lambda item: (item["topic_match_rate"], -item["original_count"], item["date"]),
    )[:8]
    automatic_rate = _rate(automatic_count, total)
    candidate_rate = _rate(candidate_count, total)

    return {
        "available": bool(details),
        "evaluation_date_count": len(payload.get("dates") or {}),
        "target_collection_rate": target_collection_rate,
        "target_met": archive_rate >= target_collection_rate if archive_stored_count is not None else automatic_rate >= target_collection_rate,
        "metrics": {
            "original_count": total,
            "archive_stored_count": stored_count,
            "archive_stored_rate": archive_rate,
            "automatic_collection_count": automatic_count,
            "automatic_collection_rate": automatic_rate,
            "recovered_collection_count": recovered_count,
            "candidate_available_count": candidate_count,
            "candidate_recall_rate": candidate_rate,
            "collection_target_gap_count": _target_gap(stored_count, total, target_collection_rate),
            "url_match_count": url_count,
            "url_match_rate": _rate(url_count, total),
            "policy_adjusted_url_match_rate": _rate(url_count, policy_comparable_count),
            "title_match_count": title_count,
            "exact_match_count": exact_count,
            "exact_match_rate": _rate(exact_count, total),
            "topic_only_match_count": topic_only_count,
            "topic_inclusive_match_count": topic_count,
            "topic_match_rate": _rate(topic_count, total),
            "policy_excluded_count": policy_excluded_count,
            "policy_comparable_count": policy_comparable_count,
            "policy_adjusted_topic_match_rate": _rate(topic_count, policy_comparable_count),
            "candidate_selection_recall_rate": _rate(topic_count, candidate_count),
            "selected_count": selected_count,
            "selection_precision_rate": _rate(topic_count, selected_count),
            "end_to_end_match_rate": _rate(topic_count, total),
            "candidate_missing_count": missing_count,
        },
        "category_metrics": category_rows,
        "mismatch_reasons": [
            {
                "key": "recovered_collection",
                "label": "날짜 범위에서 보완 확보",
                "count": recovered_count,
                "description": "과거 날짜 재검색에서는 빠졌지만 원문 보존 후 현재 날짜 범위의 후보로 확인된 기사입니다.",
            },
            {
                "key": "candidate_missing",
                "label": "후보 미확보",
                "count": missing_count,
                "description": "원문은 DB에 보존되어 있지만 실제 작성일이 과거 메일의 날짜 범위 밖이어서 해당 날짜 후보에서 확인되지 않은 기사입니다.",
            },
            {
                "key": "policy_excluded",
                "label": "AI·메일 정책 제외",
                "count": policy_excluded_count,
                "description": "후보에는 있었지만 AI 대표 기사 선정, 현재 제외 기준 또는 메일 수량 정책에 따라 선택되지 않은 기사입니다.",
            },
        ],
        "match_method_counts": dict(method_counts),
        "status_counts": dict(status_counts),
        "lowest_match_dates": lowest_dates,
        "methodology": {
            "archive_stored": "비교 대상 과거 원문이 현재 DB에 보존된 비율",
            "automatic_collection": "현재 검색 공급자가 과거 날짜를 다시 검색했을 때 원본 기사를 찾은 비율로, 실시간 수집률과는 다릅니다.",
            "candidate_recall": "메일 발송일의 현재 업무일 날짜 규칙 안에서 후보로 확인된 과거 원본의 비율",
            "url_match": "정규화한 원문 URL이 동일한 기사만 집계",
            "exact_match": "URL 또는 정규화 제목이 동일한 기사 집계",
            "topic_match": "정확 일치와 동일 주제의 다른 대표 매체 기사를 함께 집계",
            "policy_adjusted_match": "날짜 범위 후보로 확보된 과거 기사 중 AI가 과거 홍보처와 같은 URL 또는 주제를 선택한 비율",
            "selection_precision": "서버가 실제 선택한 기사 중 과거 홍보처 선택과 URL 또는 주제가 일치한 비율",
            "end_to_end_match": "과거 홍보처 원본 전체 중 현재 시스템이 같은 URL 또는 주제를 최종 선택한 비율",
        },
    }


class HongboEvaluationService:
    def __init__(
        self,
        comparison_path: Path = DEFAULT_COMPARISON_PATH,
        archive_path: Path = DEFAULT_ARCHIVE_PATH,
    ):
        self.comparison_path = comparison_path
        self.archive_path = archive_path

    def load(self) -> dict:
        if not self.comparison_path.exists():
            return {
                "available": False,
                "message": "홍보처 원본 메일 비교 결과가 아직 생성되지 않았습니다.",
                "metrics": {},
                "category_metrics": [],
                "mismatch_reasons": [],
                "lowest_match_dates": [],
            }
        payload = json.loads(self.comparison_path.read_text(encoding="utf-8"))
        archive_stored_count = None
        if self.archive_path.exists():
            archive_payload = json.loads(self.archive_path.read_text(encoding="utf-8"))
            archive_stored_count = int(archive_payload.get("unique_article_count") or 0)
        result = build_hongbo_evaluation(payload, archive_stored_count=archive_stored_count)
        result["source_updated_at"] = self.comparison_path.stat().st_mtime
        return result
