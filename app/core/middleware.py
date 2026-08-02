import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_SLOW_REQUESTS,
    request_route,
)


logger = logging.getLogger(__name__)
SLOW_REQUEST_THRESHOLD_MS = 750


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
        started_at = time.perf_counter()
        method = request.method
        should_measure = request.url.path != "/metrics"
        if should_measure:
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()

        response = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_seconds = max(0.0, time.perf_counter() - started_at)
            duration_ms = duration_seconds * 1000
            route = request_route(request)

            if response is not None:
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"
                response.headers["Server-Timing"] = f'app;dur={duration_ms:.1f}'

            if should_measure:
                HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()
                HTTP_REQUESTS.labels(method=method, route=route, status=str(status_code)).inc()
                HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(duration_seconds)

                if duration_ms >= SLOW_REQUEST_THRESHOLD_MS:
                    HTTP_SLOW_REQUESTS.labels(method=method, route=route).inc()
                    logger.warning(
                        "slow request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
                        method,
                        request.url.path,
                        status_code,
                        duration_ms,
                        request_id,
                    )
