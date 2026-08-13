"""
app/error_reporter.py -- Structured Error Capture & Crash Reporting
====================================================================

Initialise Sentry if SENTRY_DSN is configured; otherwise write crash
reports to a local `crashes/` directory as JSON files.

Usage (called once in create_app()):
    from app.error_reporter import init as init_error_reporter
    init_error_reporter(app)
"""

from __future__ import annotations

import json
import logging
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_SENTRY_INITIALISED = False


def init(app) -> None:
    """
    Initialise error reporting. Called from create_app() after the Flask
    app is configured.

    Priority:
      1. Sentry SDK (if SENTRY_DSN is set and sentry_sdk is installed)
      2. Local JSON crash file reporter (always available as fallback)
    """
    global _SENTRY_INITIALISED

    sentry_dsn = app.config.get("SENTRY_DSN") or _env_sentry_dsn()
    telemetry = app.config.get("TELEMETRY_ENABLED", False)

    if sentry_dsn and telemetry:
        _init_sentry(app, sentry_dsn)
    else:
        logger.info("[ERROR_REPORTER] Sentry not enabled -- using local crash file reporter.")

    # Always install the unhandled exception hook for local crash files
    _install_excepthook()


def _env_sentry_dsn() -> str:
    """Read SENTRY_DSN from config.py or environment."""
    import os
    try:
        import config as _cfg
        return getattr(_cfg, "SENTRY_DSN", "") or os.environ.get("SENTRY_DSN", "")
    except Exception:
        return os.environ.get("SENTRY_DSN", "")


def _init_sentry(app, dsn: str) -> None:
    """Attempt to initialise the Sentry SDK."""
    global _SENTRY_INITIALISED
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                FlaskIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            traces_sample_rate=0.0,   # No performance tracing — privacy first
            send_default_pii=False,   # Never send PII to Sentry
            environment="production",
        )
        _SENTRY_INITIALISED = True
        logger.info("[ERROR_REPORTER] Sentry initialised (send_default_pii=False).")
    except ImportError:
        logger.warning("[ERROR_REPORTER] sentry-sdk not installed -- falling back to local crash files.")
    except Exception as exc:
        logger.warning("[ERROR_REPORTER] Sentry init failed: %s", exc)


def _crashes_dir() -> Path:
    """Return the path to the local crash report directory."""
    try:
        from src.common import data_path
        crashes = data_path("logs") / "crashes"
    except Exception:
        crashes = Path("crashes")
    crashes.mkdir(parents=True, exist_ok=True)
    return crashes


def write_crash_report(exc_type, exc_value, exc_tb) -> Path | None:
    """
    Write a structured JSON crash report to the crashes/ directory.

    Returns the path of the written file, or None on failure.
    """
    try:
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        report = {
            "timestamp": ts,
            "exception_type": exc_type.__name__ if exc_type else "Unknown",
            "exception_value": str(exc_value),
            "traceback": traceback.format_exception(exc_type, exc_value, exc_tb),
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.machine(),
        }
        path = _crashes_dir() / f"crash_{ts}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.error("[ERROR_REPORTER] Crash report written: %s", path)
        return path
    except Exception as inner:
        logger.error("[ERROR_REPORTER] Failed to write crash report: %s", inner)
        return None


def _install_excepthook() -> None:
    """Replace sys.excepthook with one that writes a local crash file."""
    original_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        if not issubclass(exc_type, KeyboardInterrupt):
            write_crash_report(exc_type, exc_value, exc_tb)
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
    logger.debug("[ERROR_REPORTER] sys.excepthook installed.")
