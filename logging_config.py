"""
Logging configuration for Celestial Arc.

- Production: JSON-formatted logs (machine-parseable)
- Development: Human-readable colored logs
- Sentry integration for error tracking
"""
import logging
import os
import sys


def setup_logging():
    """Configure structured logging for the application."""
    is_production = os.environ.get("FLASK_ENV") == "production"
    log_level = logging.INFO if is_production else logging.DEBUG

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    if is_production:
        # JSON logging for production (machine-parseable)
        try:
            from pythonjsonlogger import jsonlogger

            handler = logging.StreamHandler(sys.stdout)
            formatter = jsonlogger.JsonFormatter(
                fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
        except ImportError:
            # Fallback if python-json-logger not available
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
    else:
        # Human-readable for development
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)


def setup_sentry():
    """Initialize Sentry error tracking if DSN is configured."""
    sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not sentry_dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,  # 10% of transactions
            profiles_sample_rate=0.1,
            environment=os.environ.get("FLASK_ENV", "development"),
            send_default_pii=False,  # Don't send user PII
        )
        logging.getLogger(__name__).info("✅ Sentry error tracking initialized")
    except Exception as e:
        logging.getLogger(__name__).warning(f"⚠️ Sentry init failed: {e}")
