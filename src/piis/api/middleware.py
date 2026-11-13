"""FastAPI middleware for request correlation, latency tracking, and security headers."""

from __future__ import annotations

import logging
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from piis.observability.logging import set_correlation_id

logger = logging.getLogger("piis.api.access")


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware extracting or generating X-Correlation-ID for every incoming request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        corr_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
        active_corr_id = set_correlation_id(corr_id)

        start_time = time.time()
        response: Response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000.0

        # Inject correlation ID into response headers
        response.headers["X-Correlation-ID"] = active_corr_id

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        # Log access event
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({duration_ms:.1f}ms)",
            extra={"extra_fields": {
                "http_method": request.method,
                "http_path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }},
        )

        return response
