import argparse
import csv
import json
import re
import struct
import zipfile
import zlib
from collections import defaultdict
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from olefile import OleFileIO


SECTION_PATTERNS = (
    ("foundation", re.compile(r"^\s*동국대\s*\[?\s*법인\s*/\s*건학위[^\n]*관련\s*기사\s*$", re.I)),
    ("education", re.compile(r"^\s*대학\s*\[?\s*교육[^\n]*관련\s*기사\s*$", re.I)),
    (
        "buddhism",
        re.compile(r"^\s*(?:불교\s*\[?\s*종단|종단\s*\[?\s*불교)[^\n]*관련\s*기사\s*$", re.I),
    ),
)
SECTION_LABELS = {
    "foundation": "동국대 [법인/건학위]",
    "education": "대학 [교육]",
    "buddhism": "불교 [종단]",
}
ARTICLE_RE = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*(.+?)\s*$")
URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", re.I)
DATE_RE = re.compile(r"\((\d{6})\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract article lists from Hongbo HWP/HWPX daily mails.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _clean_hwp_record_text(value: str) -> str:
    return "".join(character for character in value if ord(character) >= 32 or character in "\t\n")


def read_hwp_preview(path: Path) -> str:
    with OleFileIO(str(path)) as ole:
        header = ole.openstream("FileHeader").read()
        compressed = bool(struct.unpack_from("<I", header, 36)[0] & 1)
        section_names = sorted(
            item for item in ole.listdir() if len(item) == 2 and item[0] == "BodyText" and item[1].startswith("Section")
        )
        paragraphs = []
        for section_name in section_names:
            data = ole.openstream(section_name).read()
            if compressed:
                data = zlib.decompress(data, -15)
            offset = 0
            while offset + 4 <= len(data):
                record_header = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                tag_id = record_header & 0x3FF
                size = (record_header >> 20) & 0xFFF
                if size == 0xFFF:
                    if offset + 4 > len(data):
                        break
                    size = struct.unpack_from("<I", data, offset)[0]
                    offset += 4
                payload = data[offset : offset + size]
                offset += size
                if tag_id == 67:
                    paragraphs.append(_clean_hwp_record_text(payload.decode("utf-16le", errors="ignore")))
        if paragraphs:
            return "\n".join(paragraphs)
        if ole.exists("PrvText"):
            return ole.openstream("PrvText").read().decode("utf-16le", errors="ignore")
        raise ValueError("HWP body and preview text streams are missing")


def read_hwpx_preview(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        section_names = sorted(
            name for name in archive.namelist() if re.fullmatch(r"Contents/section\d+\.xml", name)
        )
        paragraphs = []
        for name in section_names:
            xml = archive.read(name).decode("utf-8", errors="ignore")
            for paragraph in re.findall(r"<[^:>]*:?p(?:\s[^>]*)?>(.*?)</[^:>]*:?p>", xml, re.S):
                text_parts = re.findall(r"<[^:>]*:?t(?:\s[^>]*)?>(.*?)</[^:>]*:?t>", paragraph, re.S)
                text = "".join(re.sub(r"<[^>]+>", "", part) for part in text_parts)
                if text:
                    paragraphs.append(text)
        if paragraphs:
            return "\n".join(paragraphs)
        data = archive.read("Preview/PrvText.txt")
        return data.decode("utf-8", errors="ignore")


def document_date(path: Path) -> str:
    match = DATE_RE.search(path.name)
    if not match:
        raise ValueError("Date not found in filename")
    return datetime.strptime(match.group(1), "%y%m%d").date().isoformat()


def clean_line(value: str) -> str:
    value = unescape(value).replace("<><>", " ").replace("<>", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def canonical_url(value: str) -> str:
    raw = value.strip().rstrip(".,;)")
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


def split_title_source(value: str) -> tuple[str, str | None, bool]:
    value = clean_line(value)
    syndicated = bool(re.search(r"\s+외\s*$", value))
    value = re.sub(r"\s+외\s*$", "", value).strip()
    match = re.search(r"\s*\[([^\[\]]+)\]\s*$", value)
    if not match:
        return value, None, syndicated
    source = clean_line(match.group(1))
    if re.search(r"\s+외$", source):
        syndicated = True
        source = re.sub(r"\s+외$", "", source).strip()
    title = value[: match.start()].strip()
    return title, source, syndicated


def parse_document(path: Path) -> dict:
    mail_date = document_date(path)
    text = read_hwp_preview(path) if path.suffix.lower() == ".hwp" else read_hwpx_preview(path)
    lines = [clean_line(line) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line]

    articles = []
    section = None
    current = None
    pending_number = None
    for line in lines:
        section_match = next((key for key, pattern in SECTION_PATTERNS if pattern.search(line)), None)
        if section_match:
            section = section_match
            current = None
            pending_number = None
            continue
        number_only = re.fullmatch(r"\s*(\d{1,3})\s*[.)]\s*", line)
        if section and number_only:
            pending_number = int(number_only.group(1))
            current = None
            continue
        article_match = ARTICLE_RE.match(line)
        if section and article_match:
            title, source, syndicated = split_title_source(article_match.group(2))
            current = {
                "mail_date": mail_date,
                "section": section,
                "section_label": SECTION_LABELS[section],
                "number": int(article_match.group(1)),
                "title": title,
                "source": source,
                "is_syndicated": syndicated,
                "urls": [],
                "related_sources": [],
                "document": str(path),
            }
            articles.append(current)
            pending_number = None
            continue
        if section and pending_number is not None and not URL_RE.search(line):
            title, source, syndicated = split_title_source(line)
            current = {
                "mail_date": mail_date,
                "section": section,
                "section_label": SECTION_LABELS[section],
                "number": pending_number,
                "title": title,
                "source": source,
                "is_syndicated": syndicated,
                "urls": [],
                "related_sources": [],
                "document": str(path),
            }
            articles.append(current)
            pending_number = None
            continue
        if current:
            urls = URL_RE.findall(line)
            for url in urls:
                cleaned_url = url.rstrip(".,;)")
                if cleaned_url not in current["urls"]:
                    current["urls"].append(cleaned_url)
            source_match = re.search(r"\[([^\[\]]+)\]\s*$", line)
            if urls and source_match:
                related_source = clean_line(source_match.group(1))
                if related_source and related_source not in current["related_sources"]:
                    current["related_sources"].append(related_source)

    for article in articles:
        article["canonical_urls"] = [canonical_url(url) for url in article["urls"]]
        article["is_syndicated"] = article["is_syndicated"] or len(article["urls"]) > 1
    return {
        "mail_date": mail_date,
        "document": str(path),
        "extension": path.suffix.lower(),
        "article_count": len(articles),
        "section_counts": {
            key: sum(article["section"] == key for article in articles) for key in SECTION_LABELS
        },
        "articles": articles,
    }


def article_identity(article: dict) -> str:
    if article["canonical_urls"]:
        return "url:" + article["canonical_urls"][0]
    title = re.sub(r"[^0-9a-z가-힣]", "", article["title"].lower())
    return f"title:{article['section']}:{title}"


def choose_document_versions(documents: list[dict]) -> tuple[dict, list[dict]]:
    ordered = sorted(
        documents,
        key=lambda item: (
            item["article_count"],
            sum(len(article["urls"]) for article in item["articles"]),
            item["extension"] == ".hwpx",
            Path(item["document"]).stat().st_mtime,
        ),
        reverse=True,
    )
    chosen = json.loads(json.dumps(ordered[0], ensure_ascii=False))
    known = {article_identity(article) for article in chosen["articles"]}
    merged_count = 0
    for candidate in ordered[1:]:
        for article in candidate["articles"]:
            identity = article_identity(article)
            if identity in known:
                continue
            chosen["articles"].append(article)
            known.add(identity)
            merged_count += 1
    chosen["articles"].sort(key=lambda item: (list(SECTION_LABELS).index(item["section"]), item["number"]))
    chosen["article_count"] = len(chosen["articles"])
    chosen["section_counts"] = {
        key: sum(article["section"] == key for article in chosen["articles"]) for key in SECTION_LABELS
    }
    chosen["source_documents"] = [item["document"] for item in ordered]
    chosen["merged_from_alternate_count"] = merged_count
    return chosen, ordered[1:]


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(
        path for path in args.input_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".hwp", ".hwpx"}
    )
    parsed = []
    errors = []
    for path in paths:
        try:
            parsed.append(parse_document(path))
        except Exception as exc:
            errors.append({"document": str(path), "error": str(exc)})

    by_date = defaultdict(list)
    for document in parsed:
        by_date[document["mail_date"]].append(document)
    chosen_by_date = {}
    duplicate_documents = []
    for mail_date, documents in sorted(by_date.items()):
        chosen, duplicates = choose_document_versions(documents)
        chosen_by_date[mail_date] = chosen
        duplicate_documents.extend(
            {
                "mail_date": mail_date,
                "chosen_document": chosen["document"],
                "duplicate_document": item["document"],
                "chosen_count": chosen["article_count"],
                "duplicate_count": item["article_count"],
            }
            for item in duplicates
        )

    payload = {
        "input_document_count": len(paths),
        "parsed_document_count": len(parsed),
        "unique_mail_date_count": len(chosen_by_date),
        "article_count": sum(item["article_count"] for item in chosen_by_date.values()),
        "dates": chosen_by_date,
        "duplicate_documents": duplicate_documents,
        "errors": errors,
    }
    json_path = args.output_dir / "original_mail_articles.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = args.output_dir / "original_mail_articles.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "mail_date", "section_label", "number", "title", "source", "is_syndicated", "urls", "document"
            ],
        )
        writer.writeheader()
        for mail_date, document in chosen_by_date.items():
            for article in document["articles"]:
                writer.writerow(
                    {
                        "mail_date": mail_date,
                        "section_label": article["section_label"],
                        "number": article["number"],
                        "title": article["title"],
                        "source": article["source"] or "",
                        "is_syndicated": article["is_syndicated"],
                        "urls": "\n".join(article["urls"]),
                        "document": article["document"],
                    }
                )
    print(json.dumps({
        "json": str(json_path),
        "csv": str(csv_path),
        "input_documents": len(paths),
        "parsed_documents": len(parsed),
        "unique_dates": len(chosen_by_date),
        "articles": payload["article_count"],
        "duplicates": len(duplicate_documents),
        "errors": errors,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
