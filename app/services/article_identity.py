import hashlib
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_KEYS = {
    "cp", "from", "gclid", "fbclid", "influxdiv", "medium", "ncid", "ocid", "ref",
    "source", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
}
ARTICLE_ID_KEYS = ("arcid", "idxno", "no", "article_id", "articleid", "aid", "id")


def normalize_article_title(value: str | None, publisher: str | None = None) -> str:
    title = re.sub(r"<[^>]+>", " ", value or "")
    title = re.sub(r"\s*[-|]\s*(?:네이버\s*뉴스|구글\s*뉴스|뉴스)\s*$", "", title, flags=re.I)
    if publisher:
        title = re.sub(rf"\s*[-|]\s*{re.escape(publisher.strip())}\s*$", "", title, flags=re.I)
    return re.sub(r"[^0-9a-z가-힣]+", "", title.casefold())


def normalize_publisher(value: str | None) -> str:
    publisher = re.sub(r"\s+", " ", value or "").strip().casefold()
    publisher = re.sub(r"^(?:미래를 보는 창\s*[-|]\s*)", "", publisher)
    return re.sub(r"\s*(?:뉴스)?\s*$", "", publisher)


def canonicalize_article_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.split("#", 1)[0].rstrip("/").casefold()
    host = (parts.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]
    path = re.sub(r"/+", "/", parts.path or "/")
    path = re.sub(r"/(?:amp|mobile)/", "/", path, flags=re.I)
    path = re.sub(r"view_amp(?=\.)", "view", path, flags=re.I)
    query_items = [(key.casefold(), val) for key, val in parse_qsl(parts.query, keep_blank_values=False)]
    query = dict(query_items)

    # Publisher article IDs are stable across AMP/mobile/search-provider URL variants.
    stable = [(key, query[key]) for key in ARTICLE_ID_KEYS if query.get(key)]
    if stable:
        query_items = stable
    else:
        query_items = [(key, val) for key, val in query_items if key not in TRACKING_QUERY_KEYS and not key.startswith("utm_")]
    query_items.sort()
    return urlunsplit(("https", host, path.rstrip("/") or "/", urlencode(query_items), ""))


def normalized_content(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"[^0-9a-z가-힣]+", "", text.casefold())


def content_fingerprint(value: str | None) -> str | None:
    normalized = normalized_content(value)
    if len(normalized) < 120:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_same_publisher_article(
    *,
    left_title: str | None,
    left_publisher: str | None,
    left_content: str | None,
    left_url: str | None,
    right_title: str | None,
    right_publisher: str | None,
    right_content: str | None,
    right_url: str | None,
) -> bool:
    left_canonical_url = canonicalize_article_url(left_url)
    right_canonical_url = canonicalize_article_url(right_url)
    if left_canonical_url and left_canonical_url == right_canonical_url:
        return True
    if normalize_publisher(left_publisher) != normalize_publisher(right_publisher):
        return False
    left_title_key = normalize_article_title(left_title, left_publisher)
    right_title_key = normalize_article_title(right_title, right_publisher)
    if left_title_key and right_title_key and SequenceMatcher(None, left_title_key, right_title_key).ratio() >= 0.9:
        return True
    left_body = normalized_content(left_content)
    right_body = normalized_content(right_content)
    return bool(
        len(left_body) >= 200
        and len(right_body) >= 200
        and SequenceMatcher(None, left_body[:4000], right_body[:4000]).ratio() >= 0.94
    )
