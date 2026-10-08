"""Structured logging setup for AskMyData.

Development: plain human-readable text.
Production:  JSON lines for log aggregation (CloudWatch, GCP, Datadog).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    app_env = os.getenv("APP_ENV", "development")
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    if app_env == "production":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    root = logging.getLogger()
    root.setLevel(log_level)
    # Avoid duplicate handlers if called multiple times
    root.handlers.clear()
    root.addHandler(handler)