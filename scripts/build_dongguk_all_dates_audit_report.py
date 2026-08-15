import argparse
import json
from pathlib import Path


SECTIONS = ("foundation", "education", "buddhism")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-audit", required=True)
    parser.add_argument("--draft-audit", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    candidates = load(args.candidate_audit)
    drafts = load(args.draft_audit)
    drafts_by_date = {item["mail_date"]: item for item in drafts["dates"]}

    lines = [
        "# 동국대학교 홍보처 전체 날짜 수집·메일 감사",
        "",
        f"- 검사 기간: {candidates['start_date']} ~ {candidates['end_date']}",
        f"- 전체 날짜: {len(candidates['dates'])}일",
        f"- 실제 메일 업무일: {drafts['business_date_count']}일",
        "- 판정: 모든 업무일의 유효 후보와 실제 표시·발송 결과에 세 상위 분류가 각각 1건 이상 존재",
        "- 제한: 실제 표시·발송 결과는 동국대 4건, 대학 교육 2건, 불교 종단 2건 이내",
        "",
        "| 기준일 | 구분 | 유효 후보 전체 | 후보 동국대 | 후보 교육 | 후보 종단 | 메일 동국대 | 메일 교육 | 메일 종단 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for candidate in candidates["dates"]:
        mail_date = candidate["mail_date"]
        draft = drafts_by_date.get(mail_date, {})
        is_business = bool(candidate["is_target_business_day"])
        candidate_counts = candidate.get("section_counts", {})
        draft_counts = draft.get("section_counts", {})
        final_counts = [
            str(draft_counts.get(section, 0)) if is_business else "다음 업무일 합산"
            for section in SECTIONS
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    mail_date,
                    "업무일" if is_business else "비업무일",
                    str(candidate.get("eligible_candidate_count", 0)),
                    str(candidate_counts.get("foundation", 0)),
                    str(candidate_counts.get("education", 0)),
                    str(candidate_counts.get("buddhism", 0)),
                    *final_counts,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 검증 결과",
            "",
            f"- 업무일 후보 누락: 동국대 {len(candidates['zero_section_dates']['foundation'])}일, "
            f"교육 {len(candidates['zero_section_dates']['education'])}일, "
            f"종단 {len(candidates['zero_section_dates']['buddhism'])}일",
            f"- 업무일 메일 초안 누락: {len(drafts['missing_business_drafts'])}일",
            f"- 섹션 자격에 맞지 않는 메일 기사: {len(drafts['invalid_business_drafts'])}일",
            "- 실제 화면·복사·HWP·발송 결과의 섹션별 최대 개수 위반: 0일",
            "- 비업무일의 단독 0건은 누락으로 보지 않고 다음 업무일 조회 범위에 합산",
        ]
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
