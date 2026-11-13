"""Structured JSON logging with request correlation IDs for PIIS."""

from __future__ import annotations

import contextvars
from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any, Dict, Optional
import uuid

# Context variable storing the active request/investigation correlation ID
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="SYSTEM"
)


def get_correlation_id() -> str:
    """Return the current correlation ID."""
    return correlation_id_ctx.get()


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """Set or generate a new correlation ID for the active context."""
    cid = corr_id or f"corr-{uuid.uuid4().hex[:12]}"
    correlation_id_ctx.set(cid)
    return cid


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects containing correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": get_correlation_id(),
            "message": record.getMessage(),
        }

        # Include extra fields if provided
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_entry.update(record.extra_fields)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configure root logger with structured JSON formatting."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicate lines
    root.handlers = [handler]
