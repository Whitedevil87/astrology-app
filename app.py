import json
import logging
import os
import sqlite3
import math
import secrets
import time as time_mod
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, time, timezone
from html import escape
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, render_template, request, session

from database import init_db, migrate_db, get_connection, save_report, fetch_report_row
from geo import photon_search, timeapi_timezone_name
from services.analysis_service import (
    compute_hybrid_big_three, build_blueprint, build_prediction, 
    simulate_palm_analysis, zodiac_sign, moon_sign, ascendant_sign,
    build_report_html
)
from dotenv import load_dotenv
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Try importing Groq client (recommended way)
try:
    from groq import Groq
    import httpx
    GROQ_SDK_AVAILABLE = True
    HTTPX_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False
    HTTPX_AVAILABLE = False
    Groq = None  # type: ignore
    httpx = None  # type: ignore

OPENAI_AVAILABLE = True

from vedic_engine import build_vedic_bundle, format_guru_context, get_horoscope_for_sign, generate_kundli_chart_from_birth

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DATABASE_PATH = os.path.join(INSTANCE_DIR, "astrology.db")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=False)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Production security configurations
# Secure SECRET_KEY configuration
_SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not _SECRET_KEY:
    if os.environ.get("FLASK_ENV") == "production":
        logger.critical("❌ CRITICAL: SECRET_KEY environment variable is not set in production!")
        logger.critical("   This is a security vulnerability. Set SECRET_KEY env var before deploying.")
    else:
        logger.warning("⚠️ Using development SECRET_KEY fallback")
        _SECRET_KEY = "dev-key-change-in-production-UNSAFE"
app.config["SECRET_KEY"] = _SECRET_KEY

app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Disable secure cookies if running locally without HTTPS to allow CSRF sessions to persist
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("REQUIRE_HTTPS", "false").lower() in ("1", "true", "yes")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PREFERRED_URL_SCHEME"] = "https" if app.config["SESSION_COOKIE_SECURE"] else "http"

# Production hardening (safe defaults)
app.config["SESSION_COOKIE_NAME"] = os.environ.get("SESSION_COOKIE_NAME", "celestial_arc")
app.config["TEMPLATES_AUTO_RELOAD"] = app.config["DEBUG"]


@app.after_request
def add_security_headers(resp):
    """
    Add baseline security headers.
    Kept lightweight to avoid breaking the current inline/Tailwind CDN usage.
    """
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    # HSTS only when behind HTTPS (Render uses HTTPS). Safe if app is served over HTTPS.
    if not app.config["DEBUG"]:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    # Minimal CSP to avoid breaking Tailwind CDN and inline scripts in templates.
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "connect-src 'self' https://photon.komoot.io https://timeapi.io https://api.groq.com https://api.openai.com; "
        "base-uri 'self'; form-action 'self'"
    )
    if app.config["DEBUG"]:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp


# --- Basic request protections (CSRF + light rate limiting) ---
_RATE_BUCKETS: Dict[str, list[float]] = {}


def _client_ip() -> str:
    # Render sets X-Forwarded-For. We only need a best-effort IP for rate limiting.
    fwd = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return fwd or (request.remote_addr or "unknown")


def _rate_limit(key: str, limit: int, window_s: int) -> bool:
    """Return True if allowed, False if rate-limited."""
    now = time_mod.time()
    bucket = _RATE_BUCKETS.get(key, [])
    cutoff = now - window_s
    bucket = [t for t in bucket if t >= cutoff]
    if len(bucket) >= limit:
        _RATE_BUCKETS[key] = bucket
        return False
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket
    return True


def _ensure_csrf() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return str(token)


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"ok": True})


@app.route("/api/csrf", methods=["GET"])
def api_csrf():
    return jsonify({"success": True, "csrf_token": _ensure_csrf()})


@app.before_request
def protect_requests():
    # Rate limiting for expensive endpoints
    ip = _client_ip()
    if request.path == "/api/analyze" and request.method == "POST":
        if not _rate_limit(f"{ip}:analyze", limit=20, window_s=60):
            return jsonify({"success": False, "error": "Too many requests. Please wait a minute and try again."}), 429
    if request.path == "/api/chat" and request.method == "POST":
        if not _rate_limit(f"{ip}:chat", limit=40, window_s=60):
            return jsonify({"success": False, "error": "Too many chat messages. Please slow down."}), 429
    if request.path == "/api/places" and request.method == "GET":
        if not _rate_limit(f"{ip}:places", limit=60, window_s=60):
            return jsonify({"success": False, "places": []}), 429

    # CSRF protection for browser-origin POSTs
    if request.method == "POST" and request.path in {"/api/analyze", "/api/chat"}:
        expected = session.get("csrf_token")
        provided = (request.headers.get("X-CSRF-Token") or "").strip()
        if not expected:
            _ensure_csrf()
            expected = session.get("csrf_token")
        if not provided or provided != expected:
            return jsonify({"success": False, "error": "CSRF token missing/invalid. Refresh the page and try again."}), 403




def ensure_directories() -> None:
    """Create required folders if missing."""
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        logger.info("Directories ensured: %s, %s", INSTANCE_DIR, UPLOAD_DIR)
    except OSError as e:
        logger.error("Failed to create directories: %s", e)
        raise


def parse_date(date_str: str) -> date:
    """Parse date from YYYY-MM-DD string."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def parse_time(time_str: str) -> time:
    """Parse time from HH:MM string."""
    return datetime.strptime(time_str, "%H:%M").time()


def allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def make_upload_filename(filename: str) -> str:
    """Generate a secure, random filename while preserving the extension."""
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else "bin"
    return f"{uuid.uuid4().hex}.{ext}"


def openai_guru_reply(system: str, user: str) -> Optional[str]:
    """
    Optional cloud AI — uses Groq (recommended) or OpenAI for chat completions.
    
    Groq is preferred (free tier, fast): set GROQ_API_KEY and GROQ_MODEL.
    Falls back to OpenAI if Groq not available: set OPENAI_API_KEY.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    
    logger.info(f"Chat attempt: groq_key_set={bool(groq_key)}, openai_key_set={bool(openai_key)}")
    
    # Try Groq first (recommended)
    if groq_key and GROQ_SDK_AVAILABLE:
        return _groq_chat(system, user, groq_key)
    elif groq_key and not GROQ_SDK_AVAILABLE:
        logger.warning("⚠️  Groq key set but groq SDK not available. Install: pip install groq")
        return _groq_http_fallback(system, user, groq_key)
    
    # Fall back to OpenAI
    if openai_key:
        return _openai_chat(system, user, openai_key)
    
    # No API available
    logger.error("❌ No API key available (GROQ_API_KEY or OPENAI_API_KEY not set)")
    return None


def _groq_chat(system: str, user: str, api_key: str) -> Optional[str]:
    """Use official Groq Python SDK (recommended way)."""
    if not GROQ_SDK_AVAILABLE or Groq is None:
        logger.warning("⚠️ Groq SDK not available, falling back to HTTP")
        return _groq_http_fallback(system, user, api_key)
    
    try:
        model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"
        logger.info(f"🔄 Using Groq SDK with model '{model}'")
        
        # Create explicit httpx client without proxy to avoid environment variable conflicts
        # This prevents "TypeError: Client.__init__() got an unexpected keyword argument 'proxies'"
        if HTTPX_AVAILABLE:
            try:
                # Create httpx client without allowing environment proxies
                http_client = httpx.Client(trust_env=False)
                client = Groq(api_key=api_key, http_client=http_client)
            except Exception as httpx_err:
                # Fallback if explicit http_client fails
                logger.warning(f"⚠️ Could not create explicit httpx client: {httpx_err}. Retrying without it.")
                client = Groq(api_key=api_key)
        else:
            client = Groq(api_key=api_key)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model,
            temperature=0.78,
            max_tokens=1800,
        )
        
        result = chat_completion.choices[0].message.content.strip()
        logger.info(f"✅ Groq chat success ({len(result)} chars)")
        return result
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        # Parse error details
        if "model_decommissioned" in error_msg:
            logger.error(f"❌ Model Decommissioned from Groq - Update GROQ_MODEL env var")
            logger.error(f"   Current model may be deprecated. Visit: https://console.groq.com/docs/deprecations")
            logger.error(f"   Try: GROQ_MODEL=llama-3.1-8b-instant or llama-3.3-70b-versatile")
        elif "401" in error_msg or "Unauthorized" in error_msg:
            logger.error(f"❌ 401 Unauthorized from Groq - Invalid API key")
        elif "403" in error_msg or "Forbidden" in error_msg or "1010" in error_msg:
            logger.error(f"❌ 403 Forbidden/1010 from Groq - Check API key permissions or try new key")
        elif "429" in error_msg or "Rate limit" in error_msg:
            logger.error(f"❌ 429 Rate Limited from Groq - Wait before retrying")
        elif "ConnectTimeout" in error_type or "ReadTimeout" in error_type:
            logger.error(f"❌ Timeout from Groq (60s) - Network issue or service slow")
        else:
            logger.error(f"❌ Groq error: {error_type}: {error_msg[:300]}")
        
        return None


def _groq_http_fallback(system: str, user: str, api_key: str) -> Optional[str]:
    """Fallback to raw HTTP if groq SDK not installed."""
    try:
        model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"
        logger.info(f"🔄 Using Groq HTTP fallback with model '{model}'")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.78,
            "max_tokens": 1800,
        }
        
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            response_text = resp.read().decode("utf-8", errors="replace")
            data = json.loads(response_text)
        
        if "choices" not in data or not data["choices"]:
            logger.error(f"❌ Invalid Groq response structure: {response_text[:300]}")
            return None
        
        result = str(data["choices"][0]["message"]["content"]).strip()
        logger.info(f"✅ Groq HTTP fallback success ({len(result)} chars)")
        return result
        
    except urllib.error.HTTPError as e:
        status_code = e.code
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")
        except:
            pass
        
        if status_code == 401:
            logger.error(f"❌ 401 Unauthorized from Groq - Invalid API key")
        elif status_code == 403:
            logger.error(f"❌ 403 Forbidden from Groq - Check API key permissions")
            if error_body:
                logger.error(f"   Response: {error_body[:200]}")
        elif status_code == 429:
            logger.error(f"❌ 429 Rate Limited from Groq")
        else:
            logger.error(f"❌ HTTP {status_code} from Groq")
        
        return None
        
    except (urllib.error.URLError, TimeoutError) as e:
        logger.error(f"❌ Groq connection error: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"❌ Groq response parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected Groq error: {type(e).__name__}: {e}")
        return None


def _openai_chat(system: str, user: str, api_key: str) -> Optional[str]:
    """Use OpenAI API as fallback."""
    try:
        model = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
        logger.info(f"🔄 Using OpenAI with model '{model}'")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.78,
            "max_tokens": 1800,
        }
        
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        
        result = str(data["choices"][0]["message"]["content"]).strip()
        logger.info(f"✅ OpenAI chat success ({len(result)} chars)")
        return result
        
    except urllib.error.HTTPError as e:
        if e.code == 401:
            logger.error(f"❌ 401 Unauthorized from OpenAI - Invalid API key")
        elif e.code == 429:
            logger.error(f"❌ 429 Rate Limited from OpenAI")
        else:
            logger.error(f"❌ HTTP {e.code} from OpenAI")
        return None
        
    except (urllib.error.URLError, TimeoutError) as e:
        logger.error(f"❌ OpenAI connection error: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"❌ OpenAI response parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected OpenAI error: {type(e).__name__}: {e}")
        return None


@app.route("/api/ai/status", methods=["GET"])
def api_ai_status():
    """
    Lightweight health check for AI provider connectivity.
    Does NOT return any secrets.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    provider = "groq" if groq_key else ("openai" if openai_key else "none")
    model = (
        os.environ.get("GROQ_MODEL", "").strip()
        if provider == "groq"
        else os.environ.get("OPENAI_MODEL", "").strip()
    )
    enabled = bool(groq_key or openai_key)
    if not enabled:
        return jsonify({"success": True, "enabled": False, "provider": "none"})

    # Make a tiny request through the same code path used by /api/chat.
    probe = openai_guru_reply(
        system="You are a diagnostics endpoint. Reply with exactly: OK",
        user="OK",
    )
    return jsonify(
        {
            "success": True,
            "enabled": True,
            "provider": provider,
            "model": model or None,
            "ok": bool(probe),
        }
    )




@app.route("/landing")
def landing():
    """Serve the landing page."""
    return render_template("landing.html")


@app.route("/")
def index():
    """Serve the landing page as home."""
    return render_template("landing.html")


@app.route("/app")
def app_view():
    """Serve the main astrology app."""
    return render_template("index.html")


@app.route("/horoscope")
def horoscope_view():
    """Serve the daily horoscope page."""
    return render_template("horoscope.html")


@app.route("/api/places", methods=["GET"])
def api_places():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"success": True, "places": []})
    places = photon_search(q, limit=7)
    return jsonify({"success": True, "places": places})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """Validate strict flow inputs and generate report."""
    try:
        full_name = request.form.get("full_name", "").strip()
        birth_date_raw = request.form.get("birth_date", "").strip()
        birth_time_raw = request.form.get("birth_time", "").strip()
        birth_place = request.form.get("birth_place", "").strip()
        place_lat_raw = (request.form.get("place_lat") or "").strip()
        place_lon_raw = (request.form.get("place_lon") or "").strip()
        place_label = (request.form.get("place_label") or "").strip()
        place_tz = (request.form.get("place_tz") or "").strip()
        palm_enabled_raw = request.form.get("palm_enabled", "no").strip().lower()
        palm_enabled = palm_enabled_raw == "yes"
        hand_choice = request.form.get("hand_choice", "").strip().lower()
        palm_image = request.files.get("palm_image")
        kundli_notes = request.form.get("kundli_notes", "").strip()
        kundli_file = request.files.get("kundli_chart")

        missing = []
        if not full_name:
            missing.append("full_name")
        if not birth_date_raw:
            missing.append("birth_date")
        if not birth_time_raw:
            missing.append("birth_time")
        if not birth_place:
            missing.append("birth_place")
        if missing:
            return jsonify({"success": False, "error": "Please fill all required fields.", "missing_fields": missing}), 400

        try:
            parsed_date = parse_date(birth_date_raw)
            parsed_time = parse_time(birth_time_raw)
        except ValueError as e:
            logger.warning("Date/time parsing error for user %s: %s", full_name, e)
            return jsonify({"success": False, "error": "Date or time format is invalid."}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Date or time format is invalid."}), 400

    palm_image_path = None
    palm_text = None
    if palm_enabled:
        if hand_choice not in {"left", "right"}:
            return jsonify({"success": False, "error": "Please choose left or right hand for palm reading."}), 400
        if palm_image and palm_image.filename:
            if not allowed_file(palm_image.filename):
                return jsonify({"success": False, "error": "Palm image must be png, jpg, jpeg, or webp."}), 400
            filename = make_upload_filename(palm_image.filename)
            saved_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            palm_image.save(saved_path)
            palm_image_path = os.path.join("uploads", filename).replace("\\", "/")
            palm_text = simulate_palm_analysis(hand_choice)

    kundli_image_path = None
    if kundli_file and kundli_file.filename:
        if not allowed_file(kundli_file.filename):
            return jsonify({"success": False, "error": "Kundli image must be png, jpg, jpeg, or webp."}), 400
        filename = make_upload_filename(kundli_file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        kundli_file.save(save_path)
        kundli_image_path = os.path.join("uploads", filename).replace("\\", "/")

    # Hybrid chart: resolve place -> lat/lon + timezone name, then compute Big Three.
    chart_debug: Dict[str, Any] = {"place_autocomplete_used": bool(place_lat_raw and place_lon_raw)}
    lat = None
    lon = None
    if place_lat_raw and place_lon_raw:
        try:
            lat = float(place_lat_raw)
            lon = float(place_lon_raw)
        except ValueError:
            lat = None
            lon = None

    if lat is None or lon is None:
        places = photon_search(place_label or birth_place, limit=1)
        if places:
            lat = float(places[0]["lat"])
            lon = float(places[0]["lon"])
            chart_debug["geocoded_label"] = places[0].get("label")
        else:
            chart_debug["geocode_failed"] = True

    tz_name = place_tz or None
    if tz_name is None and lat is not None and lon is not None:
        tz_name = timeapi_timezone_name(lat, lon)
        if tz_name:
            chart_debug["tz_resolved_by"] = "timeapi"

    profile = None
    hybrid_details: Dict[str, Any] = {}
    if lat is not None and lon is not None and tz_name:
        try:
            profile, hybrid_details = compute_hybrid_big_three(
                parsed_date, parsed_time, birth_place, lat, lon, tz_name
            )
        except ZoneInfoNotFoundError:
            chart_debug["tz_invalid"] = tz_name
            profile = None
        except Exception as e:
            chart_debug["hybrid_error"] = str(e)
            profile = None

    if profile is None:
        # Fallback to previous approximation if hybrid computation unavailable.
        profile = {
            "zodiac": zodiac_sign(parsed_date),
            "moon_sign": moon_sign(parsed_date),
            "ascendant": ascendant_sign(parsed_time, birth_place),
        }
        chart_debug["fallback"] = "legacy_approx"

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # Python 3.12+ compatible
    blueprint = build_blueprint(profile["zodiac"], profile["moon_sign"], profile["ascendant"], parsed_date)
    sections = build_prediction(
        full_name,
        birth_place,
        profile,
        palm_text,
        parsed_date,
        now,
        blueprint,
    )
    vedic_sections, vedic_structured = build_vedic_bundle(
        profile["ascendant"],
        profile["zodiac"],
        profile["moon_sign"],
        parsed_date,
        parsed_time,
        birth_place,
        kundli_notes,
        bool(kundli_image_path),
        hybrid_details,
    )
    sections.update(vedic_sections)

    report_html = build_report_html(full_name, profile, sections, palm_text)
    created_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    report_extras = json.dumps(
        {
            "blueprint": blueprint,
            "vedic": vedic_structured,
            "vedic_sections": vedic_sections,
            "kundli_image_path": kundli_image_path,
            "kundli_notes": kundli_notes,
            "hybrid_chart": hybrid_details,
            "chart_debug": chart_debug,
        },
        ensure_ascii=True,
    )

    report_id = save_report(
        {
            "full_name": full_name,
            "birth_date": birth_date_raw,
            "birth_time": birth_time_raw,
            "birth_place": birth_place,
            "palm_enabled": 1 if palm_enabled else 0,
            "hand_choice": hand_choice if palm_enabled else None,
            "palm_image_path": palm_image_path,
            "profile": profile,
            "sections": sections,
            "palm_analysis": palm_text,
            "report_html": report_html,
            "report_extras": report_extras,
            "created_at": created_at,
        }
    )

    return jsonify(
        {
            "success": True,
            "report_id": report_id,
            "profile": profile,
            "blueprint": blueprint,
            "vedic": vedic_structured,
            "sections": sections,
            "palm_analysis": palm_text,
            "report_html": report_html,
            "created_at": created_at,
            "ai_chat_available": bool(
                os.environ.get("GROQ_API_KEY", "").strip()
                or os.environ.get("OPENAI_API_KEY", "").strip()
            ),
        }
    )


@app.route("/api/config", methods=["GET"])
def api_config():
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    key = groq_key or openai_key
    return jsonify(
        {
            "ai_chat": bool(key),
            "provider": "groq" if groq_key else ("openai" if openai_key else "none"),
            "hint": "Chat requires GROQ_API_KEY (recommended) or OPENAI_API_KEY to be set.",
        }
    )


# SECURITY: Debug endpoint removed to prevent information disclosure
# This endpoint was leaking API key patterns (first 10 + last 5 characters)
# If you need configuration debugging, access Render dashboard directly


def _chat_text_clip(text: Optional[str], max_len: int = 900) -> str:
    """Single-line excerpt for LLM context (keeps prompts bounded)."""
    if not text:
        return ""
    t = " ".join(str(text).split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


@app.route("/api/chat", methods=["POST"])
def api_chat():
    payload = request.get_json(force=True, silent=True) or {}
    report_id = payload.get("report_id")
    message = (payload.get("message") or "").strip()
    if not report_id or not message:
        return jsonify({"success": False, "error": "report_id and message are required."}), 400

    try:
        rid = int(report_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid report_id."}), 400

    row = fetch_report_row(rid)
    if row is None:
        return jsonify({"success": False, "error": "Report not found."}), 404

    extras: Dict[str, Any] = {}
    if row["report_extras"]:
        try:
            extras = json.loads(row["report_extras"])
        except json.JSONDecodeError:
            extras = {}

    blueprint = extras.get("blueprint") or {}
    vedic = extras.get("vedic") or {}
    vedic_sections = extras.get("vedic_sections") or {}

    profile = {
        "zodiac": row["zodiac"],
        "moon_sign": row["moon_sign"],
        "ascendant": row["ascendant"],
    }
    merged_sections: Dict[str, str] = {
        "personality": row["personality"],
        "career": row["career"],
        "love": row["love_life"],
        "future": row["future_outlook"],
        "strengths": row["strengths"] or "",
        "weaknesses": row["weaknesses"] or "",
        "wellness": row["wellness"] or "",
        "compatibility": row["compatibility"] or "",
        "seasonal_energy": row["seasonal_energy"] or "",
    }
    merged_sections.update({k: str(v) for k, v in vedic_sections.items()})

    # Check if API is available (Groq or OpenAI)
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    
    if not (groq_key or openai_key):
        logger.error("❌ Chat API called but NO API keys configured")
        logger.error("   Missing: GROQ_API_KEY and OPENAI_API_KEY")
        return jsonify({
            "success": False,
            "error": "Chat service is offline. Configure GROQ_API_KEY or OPENAI_API_KEY to enable chat."
        }), 503
    
    logger.info(f"📨 Chat message received for report {rid} - Provider: {'Groq' if groq_key else 'OpenAI'}")
    
    try:
        ctx = format_guru_context(row["full_name"], profile, vedic, blueprint)
        report_excerpts = "\n".join(
            [
                f"Personality (deep reading): {_chat_text_clip(merged_sections.get('personality'), 900)}",
                f"Career Path (full reading): {_chat_text_clip(merged_sections.get('career'), 900)}",
                f"Future Outlook (full reading): {_chat_text_clip(merged_sections.get('future'), 900)}",
                f"Love & Relationships (full reading): {_chat_text_clip(merged_sections.get('love'), 900)}",
                f"Core Strengths: {_chat_text_clip(merged_sections.get('strengths'), 600)}",
                f"Growth Edges: {_chat_text_clip(merged_sections.get('weaknesses'), 600)}",
                f"Wellness & Rhythm: {_chat_text_clip(merged_sections.get('wellness'), 600)}",
                f"Compatibility Notes: {_chat_text_clip(merged_sections.get('compatibility'), 600)}",
                f"Seasonal / Transit Energy: {_chat_text_clip(merged_sections.get('seasonal_energy'), 600)}",
                f"Dasha / Dosha Timing: {_chat_text_clip(merged_sections.get('vimshottari_timing'), 600)}",
                f"Rahu-Ketu Axis: {_chat_text_clip(merged_sections.get('rahu_ketu'), 600)}",
                f"Remedies & Lifestyle: {_chat_text_clip(merged_sections.get('remedies_lifestyle'), 600)}",
            ]
        )
        system = (
            "You are Guru Arya — a deeply wise, warm, and uncannily perceptive Vedic astrologer with 30 years of experience. "
            "You have the rare gift of making ancient cosmic wisdom feel immediate, personal, and alive. "
            "You speak like a trusted mentor who truly SEES the person in front of them — not a textbook or a robot.\n\n"
            "YOUR PERSONALITY:\n"
            "- You are compassionate but never vague. You give SPECIFIC, actionable guidance grounded in the chart.\n"
            "- You weave planetary positions naturally into conversation — like a doctor reading an X-ray, you explain what you see and what it means for THEM.\n"
            "- You use vivid metaphors and poetic language that makes astrology feel magical, not mechanical.\n"
            "- You occasionally say something so precisely accurate about their inner life that it gives them chills.\n"
            "- You balance honesty with kindness — you don't hide challenges, but you always show the path through.\n"
            "- You address them by name when it feels natural.\n\n"
            "YOUR EXPERTISE:\n"
            "- You read the FULL chart: Sun sign personality, Moon sign emotional nature, Ascendant social mask, and all planetary house placements.\n"
            "- For CAREER questions: deeply analyze 10th house (reputation/career), 6th house (daily work/obstacles), 2nd/11th (income), "
            "Saturn (discipline/delays), Jupiter (expansion/luck), and the current Mahadasha lord's influence. Be specific about timing windows and what actions to take.\n"
            "- For LOVE questions: analyze 7th house (partnerships), Venus (romance/beauty), Moon (emotional needs), and 5th house (romance/creativity). "
            "Describe what kind of partner suits them and when love energy peaks.\n"
            "- For TIMING questions: use Mahadasha/Antardasha periods, planetary transits, and seasonal energy to give conditional timing windows. "
            "Never give exact dates as guarantees, but give meaningful windows like 'the next 3-4 months carry strong Jupiter support for new beginnings.'\n"
            "- For HEALTH/WELLNESS: connect planetary influences to physical and mental patterns. Give practical lifestyle advice rooted in the chart.\n\n"
            "RESPONSE STYLE:\n"
            "- Open with something that shows you understand their specific situation — reference their chart placements directly.\n"
            "- Give 2-3 layers of insight: the surface answer, the deeper pattern, and the soul-level lesson.\n"
            "- End with one concrete action step or reflection prompt they can use TODAY.\n"
            "- Use markdown formatting: **bold** for key insights, occasional *italics* for poetic emphasis.\n"
            "- Keep responses between 150-400 words — substantial enough to impress, concise enough to respect their time.\n"
            "- NEVER say 'as an AI' or break character. You ARE Guru Arya. You've been reading charts for decades.\n\n"
            "CRITICAL RULES:\n"
            "- ONLY use information from the CONTEXT and REPORT EXCERPTS provided. Never invent chart details.\n"
            "- Stay on topic. Career questions get career answers. Love questions get love answers. Don't cross-pollinate unless relevant.\n"
            "- If you genuinely cannot answer something from the chart data, say so honestly and suggest what additional information would help.\n"
            "- Always maintain a tone that is authoritative yet warm — like a wise elder who genuinely cares about the questioner's wellbeing."
        )
        user_blob = (
            f"CHART CONTEXT:\n{ctx}\n\nFULL REPORT EXCERPTS (this person's complete reading):\n{report_excerpts}\n\n"
            f"{row['full_name']}'s QUESTION:\n{message}"
        )
        logger.info(f"   Calling AI endpoint...")
        ai_reply = openai_guru_reply(system, user_blob)
        
        if ai_reply is None:
            logger.error(f"❌ AI chat returned None for report {rid}")
            return jsonify({
                "success": False,
                "error": "Chat service failed to generate response. Check Render logs for details."
            }), 503

        logger.info(f"✅ Chat response generated ({len(ai_reply)} chars)")
        return jsonify(
            {
                "success": True,
                "reply": ai_reply,
                "source": "ai",
            }
        )
    except Exception as e:
        logger.error(f"❌ Chat endpoint error: {type(e).__name__}: {e}")
        return jsonify({
            "success": False,
            "error": "An error occurred while processing your message."
        }), 500


@app.route("/api/locations", methods=["GET"])
def api_locations():
    """Legacy location autocomplete (disabled by default)."""
    # This endpoint is not used by the current UI (we use /api/places).
    # Keep it disabled unless explicitly configured.
    geonames_user = os.environ.get("GEONAMES_USERNAME", "").strip()
    if not geonames_user:
        return jsonify({"success": False, "error": "Disabled"}), 404

    query = request.args.get("query", "").strip()
    if len(query) < 2:
        return jsonify({"success": False, "locations": []}), 400
    
    try:
        # Using geonames API (free tier)
        params = {
            "name_startsWith": query,
            "featureClass": "P",  # Only cities/places
            "maxRows": 10,
            "username": geonames_user,
        }
        url = "http://api.geonames.org/searchJSON"
        
        # Create a request with timeout
        req = urllib.request.Request(f"{url}?{'&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in params.items()])}", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        locations = []
        if "geonames" in data:
            for place in data["geonames"][:10]:
                locations.append({
                    "name": f"{place.get('name', '')}, {place.get('adminName1', '')}, {place.get('countryName', '')}",
                    "lat": place.get("lat"),
                    "lng": place.get("lng"),
                })
        
        return jsonify({"success": True, "locations": locations})
    except Exception as e:
        logger.warning(f"Location search failed: {e}")
        return jsonify({"success": False, "locations": []})


@app.route("/api/horoscope", methods=["GET"])
def api_horoscope():
    """Get horoscope for a zodiac sign."""
    sign = request.args.get("sign", "").strip().capitalize()
    valid_signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    
    if sign not in valid_signs:
        return jsonify({"success": False, "error": "Invalid zodiac sign"}), 400
    
    # This would fetch from vedic engine or saved horoscopes
    horoscope = get_horoscope_for_sign(sign)
    
    return jsonify({
        "success": True,
        "sign": sign,
        "horoscope": horoscope
    })


@app.route("/api/kundli-chart", methods=["POST"])
def api_kundli_chart():
    """Generate Kundli chart from birth data."""
    payload = request.get_json(force=True, silent=True) or {}
    birth_date = payload.get("birth_date", "").strip()
    birth_time = payload.get("birth_time", "").strip()
    birth_place = payload.get("birth_place", "").strip()
    
    if not birth_date or not birth_time:
        return jsonify({"success": False, "error": "birth_date and birth_time required"}), 400
    
    try:
        # Try to get coordinates for birthplace (simplified - just use None for now)
        # In production, you'd use a geolocation API
        result = generate_kundli_chart_from_birth(birth_date, birth_time)
        
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Kundli chart generation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


ensure_directories()
init_db()
migrate_db()


@app.before_request
def log_request():
    """Log incoming requests (production debugging)."""
    if app.config.get("DEBUG"):
        logger.debug("Request: %s %s", request.method, request.path)


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"success": False, "error": "Bad request"}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    logger.error("Server error: %s", e)
    return jsonify({"success": False, "error": "Internal server error"}), 500


if __name__ == "__main__":
    # Development server configuration
    # For production, use: gunicorn -w 4 -b 0.0.0.0:5000 app:app
    
    _host = os.environ.get("FLASK_HOST", "0.0.0.0")
    _port = int(os.environ.get("FLASK_PORT", "5000"))
    _debug = app.config["DEBUG"]
    
    logger.info("Starting Flask application...")
    logger.info("Debug mode: %s", _debug)
    logger.info("Listening on %s:%d", _host, _port)
    
    app.run(host=_host, port=_port, debug=_debug, threaded=True)
