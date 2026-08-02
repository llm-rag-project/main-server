import json
from pathlib import Path


INPUT_PATH = Path("/code/exports/dongguk_sheet_rows_latest.json")
OUT_DIR = Path("/code/exports/dongguk_sheet_tsv")
HEADERS = ["기준일", "포함여부", "순번", "섹션", "수집 출처", "제목", "발행일시", "URL", "수집풀"]


def clean_cell(value):
    text = "" if value is None else str(value)
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def normalize_section(row):
    section = row.get("섹션") or "미분류"
    title = row.get("제목") or ""
    pool = row.get("수집풀") or ""
    if section == "미분류" and ("동국" in title or pool in {"dongguk_core", "dongguk_media", "dongguk_keyword"}):
        return "동국대 [법인/건학위]"
    return section


def main():
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for mail_date, info in data["dates"].items():
        rows = [HEADERS]
        for row in info["rows"]:
            normalized = dict(row)
            normalized["섹션"] = normalize_section(normalized)
            rows.append([clean_cell(normalized.get(header)) for header in HEADERS])
        path = OUT_DIR / f"{mail_date}.tsv"
        path.write_text("\n".join("\t".join(map(clean_cell, row)) for row in rows), encoding="utf-8")
        print(f"{mail_date}\t{len(rows)}\t{path}")


if __name__ == "__main__":
    main()
