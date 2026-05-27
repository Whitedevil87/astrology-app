"""
Centralised configuration for Celestial Arc.

Reads environment variables and exposes them as module-level constants.
All other modules should import from here — never read os.environ directly.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# ── Database ──────────────────────────────────────────────────────────
# PostgreSQL via Supabase (production) — falls back to SQLite (local dev)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_FALLBACK_PATH = os.path.join(INSTANCE_DIR, "astrology.db")

# ── Supabase ──────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# ── Upstash Redis (rate limiting) ─────────────────────────────────────
UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()

# ── External APIs ─────────────────────────────────────────────────────
PHOTON_BASE_URL = os.environ.get("PHOTON_BASE_URL", "https://photon.komoot.io/api/").strip()
TIMEAPI_BASE_URL = os.environ.get("TIMEAPI_BASE_URL", "https://timeapi.io/api/v1").strip()

# ── AI Providers ──────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"

# ── Email ─────────────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@celestialarc.com").strip()

# ── Monitoring ────────────────────────────────────────────────────────
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()

# ── Astrology ─────────────────────────────────────────────────────────
# Lahiri matches AstroSage / mainstream Indian Vedic software defaults.
AYANAMSA = os.environ.get("AYANAMSA", "lahiri").strip().lower()

# ── Feature Flags ─────────────────────────────────────────────────────
ENABLE_PALM_VISION = os.environ.get("ENABLE_PALM_VISION", "false").lower() in ("1", "true", "yes")
ENABLE_PHONE_OTP = os.environ.get("ENABLE_PHONE_OTP", "false").lower() in ("1", "true", "yes")

# ── Flask ─────────────────────────────────────────────────────────────
FLASK_ENV = os.environ.get("FLASK_ENV", "development").strip()
IS_PRODUCTION = FLASK_ENV == "production"


def configure_app(app):
    """Apply configuration to a Flask app instance."""
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

    # Secret key
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        if IS_PRODUCTION:
            logger.critical("❌ CRITICAL: SECRET_KEY environment variable is not set in production!")
            logger.critical("   This is a security vulnerability. Set SECRET_KEY env var before deploying.")
        else:
            logger.warning("⚠️ Using development SECRET_KEY fallback")
            secret_key = "dev-key-change-in-production-UNSAFE"

    app.config["SECRET_KEY"] = secret_key
    app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("REQUIRE_HTTPS", "false").lower() in ("1", "true", "yes")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PREFERRED_URL_SCHEME"] = "https" if app.config["SESSION_COOKIE_SECURE"] else "http"
    app.config["SESSION_COOKIE_NAME"] = os.environ.get("SESSION_COOKIE_NAME", "celestial_arc")
    app.config["TEMPLATES_AUTO_RELOAD"] = app.config["DEBUG"]
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    return app


def validate_startup_config():
    """Log warnings for non-default or missing configuration at startup."""
    if PHOTON_BASE_URL != "https://photon.komoot.io/api/":
        logger.warning(f"⚠️ PHOTON_BASE_URL overridden: {PHOTON_BASE_URL}")
    if TIMEAPI_BASE_URL != "https://timeapi.io/api/v1":
        logger.warning(f"⚠️ TIMEAPI_BASE_URL overridden: {TIMEAPI_BASE_URL}")

    if not DATABASE_URL:
        logger.warning("⚠️ DATABASE_URL not set — using SQLite fallback (not suitable for production)")
    if not SUPABASE_URL:
        logger.warning("SUPABASE_URL not set - Supabase Auth and Storage disabled")
    if not UPSTASH_REDIS_REST_URL:
        logger.warning("UPSTASH_REDIS_REST_URL not set - using in-memory rate limiting (resets on restart)")
    if not GROQ_API_KEY and not OPENAI_API_KEY:
        logger.warning("No AI provider configured - Guru Arya chat will be unavailable")
    if SENTRY_DSN:
        logger.info("Sentry error tracking enabled")
    if RESEND_API_KEY:
        logger.info("Email sending enabled via Resend")
