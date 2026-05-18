"""Structured logging setup for Investment OS.

Usage:
    from investment_os.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("sync complete", extra={"records": 42})

In development, logs are pretty-printed to stdout.
In production, logs are emitted as JSON (one object per line) for log aggregators.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

_CONFIGURED = False


def _configure(level: str = "DEBUG", *, json_output: bool = False) -> None:
    """Configure root logger once. Called by get_logger() on first use."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_output:
        handler.setFormatter(_JsonFormatter())
    else:
        fmt = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    # Remove any handlers added by third-party libs before ours
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("urllib3", "httpx", "httpcore", "hpack"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class _JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter — no extra deps, no orjson required."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = traceback.format_exception(*record.exc_info)
        # Merge any extra fields passed via `extra={}`
        skip = logging.LogRecord.__dict__.keys() | {"message", "asctime"}
        for k, v in record.__dict__.items():
            if k not in skip:
                payload[k] = v
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring root logger is configured first."""
    # Lazy import avoids circular import (config → logging → config)
    try:
        from investment_os.core.config import settings
        level = settings.log_level
        json_output = settings.is_production
    except Exception:
        level = "DEBUG"
        json_output = False

    _configure(level=level, json_output=json_output)
    return logging.getLogger(name)
