from __future__ import annotations

import re
import time
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS = Counter(
    "news_http_requests_total",
    "Total HTTP requests handled by the News Intelligence API.",
    ("method", "route", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "news_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
    buckets=(0.025, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1, 2, 5, 10, 30, 60, 120),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "news_http_requests_in_progress",
    "HTTP requests currently being processed.",
    ("method",),
)
HTTP_SLOW_REQUESTS = Counter(
    "news_http_slow_requests_total",
    "HTTP requests slower than the configured slow request threshold.",
    ("method", "route"),
)

EXTERNAL_REQUESTS = Counter(
    "news_external_requests_total",
    "Calls from the main server to external services.",
    ("service", "operation", "status"),
)
EXTERNAL_REQUEST_DURATION = Histogram(
    "news_external_request_duration_seconds",
    "External service request duration in seconds.",
    ("service", "operation"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 240),
)

CRAWL_RUNS = Counter(
    "news_crawl_runs_total",
    "Completed crawl runs by trigger and result.",
    ("trigger", "status"),
)
CRAWL_RUN_DURATION = Histogram(
    "news_crawl_run_duration_seconds",
    "End-to-end crawl run duration in seconds.",
    ("trigger", "status"),
    buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200),
)
CRAWL_ARTICLES_PROCESSED = Counter(
    "news_crawl_articles_processed_total",
    "Articles processed by completed crawl runs.",
    ("trigger", "status"),
)
CRAWL_LAST_ARTICLE_COUNT = Gauge(
    "news_crawl_last_article_count",
    "Article count from the latest crawl run.",
    ("trigger",),
)
CRAWL_LAST_SUCCESS_TIMESTAMP = Gauge(
    "news_crawl_last_success_timestamp_seconds",
    "Unix timestamp of the latest completed or partial crawl run.",
    ("trigger",),
)


_DYNAMIC_SEGMENT = re.compile(r"/(?:\d+|[0-9a-f]{8}-[0-9a-f-]{27,})(?=/|$)", re.IGNORECASE)
_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def normalize_route(path: str) -> str:
    """Keep metric labels bounded when a request does not resolve to a route template."""
    normalized = _DYNAMIC_SEGMENT.sub("/{id}", path or "/")
    return normalized[:160] or "/"


def request_route(request: Any) -> str:
    route = request.scope.get("route") if getattr(request, "scope", None) else None
    route_path = getattr(route, "path", None)
    return normalize_route(route_path or getattr(request.url, "path", "/"))


def observe_external_request(
    *,
    service: str,
    operation: str,
    status: str,
    started_at: float,
) -> None:
    duration = max(0.0, time.perf_counter() - started_at)
    EXTERNAL_REQUESTS.labels(service=service, operation=operation, status=status).inc()
    EXTERNAL_REQUEST_DURATION.labels(service=service, operation=operation).observe(duration)


def track_crawl_run_metrics(func: _F) -> _F:
    @wraps(func)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        started_at = time.perf_counter()
        trigger = str(kwargs.get("trigger_type") or "manual")
        status = "failed"
        article_count = 0
        try:
            result = await func(*args, **kwargs)
            if isinstance(result, dict):
                status = str(result.get("status") or "completed").lower()
                article_count = max(0, int(result.get("crawl_count") or 0))
            else:
                status = "completed"
            return result
        finally:
            duration = max(0.0, time.perf_counter() - started_at)
            CRAWL_RUNS.labels(trigger=trigger, status=status).inc()
            CRAWL_RUN_DURATION.labels(trigger=trigger, status=status).observe(duration)
            CRAWL_ARTICLES_PROCESSED.labels(trigger=trigger, status=status).inc(article_count)
            CRAWL_LAST_ARTICLE_COUNT.labels(trigger=trigger).set(article_count)
            if status in {"completed", "partial"}:
                CRAWL_LAST_SUCCESS_TIMESTAMP.labels(trigger=trigger).set_to_current_time()

    return wrapped  # type: ignore[return-value]
