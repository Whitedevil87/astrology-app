import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DATABASE_PATH = os.path.join(INSTANCE_DIR, "astrology.db")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

PHOTON_BASE_URL = os.environ.get("PHOTON_BASE_URL", "https://photon.komoot.io/api/").strip()
TIMEAPI_BASE_URL = os.environ.get("TIMEAPI_BASE_URL", "https://timeapi.io/api/v1").strip()


def configure_app(app):
    app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        if os.environ.get("FLASK_ENV") == "production":
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
    app.config["TEMPLATES_AUTO_RELOAD"] = False

    return app
