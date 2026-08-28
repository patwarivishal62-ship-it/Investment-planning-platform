"""Structured-ish logging helpers.

We log operational facts (duration, dataset used, method, candidate counts,
failures). We deliberately avoid logging user financial inputs.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

_CONFIGURED = False


def setup_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, (level or os.getenv("LOG_LEVEL", "INFO")).upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


@contextmanager
def log_duration(logger: logging.Logger, operation: str, **context):
    """Log how long an expensive quantitative operation took."""
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:  # pragma: no cover - re-raised
        logger.warning(
            "%s failed after %.3fs %s error=%s",
            operation,
            time.perf_counter() - started,
            _fmt(context),
            type(exc).__name__,
        )
        raise
    else:
        logger.info("%s completed in %.3fs %s", operation, time.perf_counter() - started, _fmt(context))


def _fmt(context: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in context.items())
