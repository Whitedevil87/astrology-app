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
from dotenv import load_dotenv
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Try importing Groq client (recommended way)
try:
    from groq import Groq
    GROQ_SDK_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False

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
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
app.config["SESSION_COOKIE_SECURE"] = not app.config["DEBUG"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PREFERRED_URL_SCHEME"] = "https" if not app.config["DEBUG"] else "http"

# Production hardening (safe defaults)
app.config["SESSION_COOKIE_NAME"] = os.environ.get("SESSION_COOKIE_NAME", "celestial_arc")
app.config["TEMPLATES_AUTO_RELOAD"] = False


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

PHOTON_BASE_URL = os.environ.get("PHOTON_BASE_URL", "https://photon.komoot.io/api/").strip()
TIMEAPI_BASE_URL = os.environ.get("TIMEAPI_BASE_URL", "https://timeapi.io/api/v1").strip()


def ensure_directories() -> None:
    """Create required folders if missing."""
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        logger.info("Directories ensured: %s, %s", INSTANCE_DIR, UPLOAD_DIR)
    except OSError as e:
        logger.error("Failed to create directories: %s", e)
        raise


def get_connection() -> sqlite3.Connection:
    """Return SQLite connection with dict-like rows."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def http_get_json(url: str, timeout: int = 12) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CelestialArc/1.0 (Flask; local educational app)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def photon_search(q: str, limit: int = 7) -> list[Dict[str, Any]]:
    query = (q or "").strip()
    if not query:
        return []
    url = f"{PHOTON_BASE_URL}?q={urllib.parse.quote(query)}&limit={int(limit)}&lang=en"
    try:
        data = http_get_json(url, timeout=10)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return []
    features = data.get("features") or []
    out: list[Dict[str, Any]] = []
    for feat in features[:limit]:
        try:
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = (geom.get("coordinates") or [None, None])
            lon = float(coords[0])
            lat = float(coords[1])
            name = props.get("name") or ""
            city = props.get("city") or ""
            state = props.get("state") or props.get("region") or ""
            country = props.get("country") or ""
            parts = [p for p in (name, city, state, country) if isinstance(p, str) and p.strip()]
            label = ", ".join(dict.fromkeys(parts))[:140]
            if not label:
                continue
            out.append({"label": label, "lat": lat, "lon": lon})
        except (TypeError, ValueError):
            continue
    return out


def timeapi_timezone_name(lat: float, lon: float) -> Optional[str]:
    """
    Resolve an IANA timezone name from coordinates.
    Uses timeapi.io which does not require an API key.
    """
    url = (
        f"{TIMEAPI_BASE_URL}/timezone/coordinate"
        f"?latitude={urllib.parse.quote(str(lat))}&longitude={urllib.parse.quote(str(lon))}"
    )
    try:
        data = http_get_json(url, timeout=10)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    tz = data.get("timeZone") or data.get("timezone") or data.get("time_zone")
    return str(tz).strip() if tz else None


def _deg_to_rad(x: float) -> float:
    return x * math.pi / 180.0


def _rad_to_deg(x: float) -> float:
    return x * 180.0 / math.pi


def _norm360(x: float) -> float:
    x = x % 360.0
    return x + 360.0 if x < 0 else x


def _norm24(x: float) -> float:
    x = x % 24.0
    return x + 24.0 if x < 0 else x


def julian_day(dt_utc: datetime) -> float:
    """Julian day for UTC datetime (proleptic Gregorian)."""
    if dt_utc.tzinfo is None:
        raise ValueError("dt_utc must be timezone-aware")
    dt = dt_utc.astimezone(timezone.utc)
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
    return float(jd)


def sun_ecliptic_longitude_deg(jd: float) -> float:
    """
    Approximate apparent ecliptic longitude of the Sun (degrees).
    Low/medium precision but good enough for sign.
    """
    n = jd - 2451545.0
    L = _norm360(280.460 + 0.9856474 * n)
    g = _norm360(357.528 + 0.9856003 * n)
    lam = L + 1.915 * math.sin(_deg_to_rad(g)) + 0.020 * math.sin(_deg_to_rad(2 * g))
    return _norm360(lam)


def moon_ecliptic_longitude_deg(jd: float) -> float:
    """
    Very simplified Moon longitude (degrees).
    This is not ephemeris-grade, but much more meaningful than day-of-year buckets.
    """
    n = jd - 2451545.0
    L0 = _norm360(218.316 + 13.176396 * n)  # mean longitude
    Mm = _norm360(134.963 + 13.064993 * n)  # mean anomaly
    Ms = _norm360(357.529 + 0.9856003 * n)  # sun mean anomaly
    D = _norm360(297.850 + 12.190749 * n)   # elongation
    # main periodic terms (truncated)
    lam = (
        L0
        + 6.289 * math.sin(_deg_to_rad(Mm))
        + 1.274 * math.sin(_deg_to_rad(2 * D - Mm))
        + 0.658 * math.sin(_deg_to_rad(2 * D))
        + 0.214 * math.sin(_deg_to_rad(2 * Mm))
        - 0.186 * math.sin(_deg_to_rad(Ms))
    )
    return _norm360(lam)


def gmst_hours(jd: float) -> float:
    """Greenwich mean sidereal time in hours."""
    T = (jd - 2451545.0) / 36525.0
    gmst = 6.697374558 + 2400.051336 * T + 0.000025862 * T * T
    # add rotation since 0h UT
    frac_day = (jd + 0.5) % 1.0
    gmst += 24.06570982441908 * frac_day
    return _norm24(gmst)


def ascendant_longitude_deg(jd: float, lat_deg: float, lon_deg: float) -> float:
    """
    Approximate Ascendant ecliptic longitude (degrees) from JD + coordinates.
    Uses LST and obliquity; sufficient for asc sign.
    """
    eps = _deg_to_rad(23.439291)  # obliquity (approx)
    lat = _deg_to_rad(lat_deg)
    lst = _deg_to_rad(_norm360((gmst_hours(jd) * 15.0) + lon_deg))
    # Formula for ascendant longitude (Meeus-like)
    num = math.sin(lst) * math.cos(eps) - math.tan(lat) * math.sin(eps)
    den = math.cos(lst)
    lam = math.atan2(num, den)
    return _norm360(_rad_to_deg(lam))


def sign_from_longitude(lon_deg: float) -> str:
    idx = int(_norm360(lon_deg) // 30)
    return ZODIAC_ORDER[idx]


def compute_hybrid_big_three(
    birth_date: date,
    birth_time: time,
    birth_place: str,
    lat: float,
    lon: float,
    tz_name: str,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    tz = ZoneInfo(tz_name)
    dt_local = datetime(
        birth_date.year,
        birth_date.month,
        birth_date.day,
        birth_time.hour,
        birth_time.minute,
        tzinfo=tz,
    )
    dt_utc = dt_local.astimezone(timezone.utc)
    jd = julian_day(dt_utc)
    sun_lon = sun_ecliptic_longitude_deg(jd)
    moon_lon = moon_ecliptic_longitude_deg(jd)
    asc_lon = ascendant_longitude_deg(jd, lat, lon)
    profile = {
        "zodiac": sign_from_longitude(sun_lon),
        "moon_sign": sign_from_longitude(moon_lon),
        "ascendant": sign_from_longitude(asc_lon),
    }
    details = {
        "method": "hybrid_approx",
        "place_input": birth_place,
        "lat": lat,
        "lon": lon,
        "tz": tz_name,
        "local_datetime": dt_local.isoformat(),
        "utc_datetime": dt_utc.isoformat(),
        "jd": jd,
        "sun_lon_deg": sun_lon,
        "moon_lon_deg": moon_lon,
        "asc_lon_deg": asc_lon,
    }
    return profile, details


def init_db() -> None:
    """Initialize reports table for saved predictions."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            birth_time TEXT NOT NULL,
            birth_place TEXT NOT NULL,
            palm_enabled INTEGER NOT NULL DEFAULT 0,
            hand_choice TEXT,
            palm_image_path TEXT,
            zodiac TEXT NOT NULL,
            moon_sign TEXT NOT NULL,
            ascendant TEXT NOT NULL,
            personality TEXT NOT NULL,
            career TEXT NOT NULL,
            love_life TEXT NOT NULL,
            future_outlook TEXT NOT NULL,
            strengths TEXT,
            weaknesses TEXT,
            wellness TEXT,
            compatibility TEXT,
            seasonal_energy TEXT,
            palm_analysis TEXT,
            report_html TEXT NOT NULL,
            report_extras TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def migrate_db() -> None:
    """Add new columns for older SQLite files (idempotent)."""
    conn = get_connection()
    cursor = conn.execute("PRAGMA table_info(reports)")
    columns = {row[1] for row in cursor.fetchall()}
    for name, definition in (
        ("strengths", "TEXT"),
        ("weaknesses", "TEXT"),
        ("wellness", "TEXT"),
        ("compatibility", "TEXT"),
        ("seasonal_energy", "TEXT"),
        ("report_extras", "TEXT"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {name} {definition}")
    conn.commit()
    conn.close()


def allowed_file(filename: str) -> bool:
    """Validate file extension for palm uploads."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def make_upload_filename(original_name: str) -> str:
    """Generate safe unique upload filename."""
    ext = original_name.rsplit(".", 1)[1].lower()
    return f"{uuid.uuid4().hex}.{ext}"


def parse_date(date_value: str):
    return datetime.strptime(date_value, "%Y-%m-%d").date()


def parse_time(time_value: str):
    return datetime.strptime(time_value, "%H:%M").time()


def zodiac_sign(birth_date) -> str:
    month, day = birth_date.month, birth_date.day
    if (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "Capricorn"
    if (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "Aquarius"
    if (month == 2 and day >= 19) or (month == 3 and day <= 20):
        return "Pisces"
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "Aries"
    if (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "Taurus"
    if (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "Gemini"
    if (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return "Cancer"
    if (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "Leo"
    if (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "Virgo"
    if (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return "Libra"
    if (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return "Scorpio"
    return "Sagittarius"


def moon_sign(birth_date) -> str:
    """Approximation based on day of year."""
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    day_of_year = birth_date.timetuple().tm_yday
    return signs[(day_of_year // 30) % len(signs)]


def ascendant_sign(birth_time, birth_place: str) -> str:
    """Simple ascendant approximation from time + place text."""
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    place_score = sum(ord(ch) for ch in birth_place.lower() if ch.isalpha())
    time_bucket = birth_time.hour * 2 + (1 if birth_time.minute >= 30 else 0)
    return signs[(place_score + time_bucket) % len(signs)]


PERSONALITY_RULES = {
    "Aries": "bold, energetic, action-driven",
    "Taurus": "steady, grounded, loyal",
    "Gemini": "curious, social, quick-minded",
    "Cancer": "protective, intuitive, empathetic",
    "Leo": "charismatic, proud, heart-led",
    "Virgo": "analytical, practical, detail-focused",
    "Libra": "harmonious, diplomatic, refined",
    "Scorpio": "intense, strategic, emotionally deep",
    "Sagittarius": "optimistic, adventurous, philosophical",
    "Capricorn": "disciplined, responsible, ambitious",
    "Aquarius": "independent, inventive, visionary",
    "Pisces": "imaginative, sensitive, spiritually tuned",
}


CAREER_RULES = {
    "Aries": "leadership, startups, athletics, emergency response",
    "Taurus": "finance, design, architecture, food or luxury industries",
    "Gemini": "media, sales, teaching, communications, product roles",
    "Cancer": "counseling, hospitality, healthcare, caregiving fields",
    "Leo": "public leadership, entertainment, branding, entrepreneurship",
    "Virgo": "analysis, engineering, medicine, operations excellence",
    "Libra": "law, diplomacy, design, client-facing strategy",
    "Scorpio": "research, psychology, cybersecurity, investigative work",
    "Sagittarius": "travel, higher education, publishing, consulting",
    "Capricorn": "management, government, finance, long-term planning",
    "Aquarius": "technology, innovation labs, social impact, science",
    "Pisces": "arts, healing, storytelling, spiritual guidance",
}

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

ZODIAC_META: Dict[str, Dict[str, str]] = {
    # Use explicit \uXXXX escapes to avoid Windows encoding/codepage corruption.
    "Aries": {"element": "Fire", "modality": "Cardinal", "ruler": "Mars", "glyph": "\u2648"},
    "Taurus": {"element": "Earth", "modality": "Fixed", "ruler": "Venus", "glyph": "\u2649"},
    "Gemini": {"element": "Air", "modality": "Mutable", "ruler": "Mercury", "glyph": "\u264A"},
    "Cancer": {"element": "Water", "modality": "Cardinal", "ruler": "Moon", "glyph": "\u264B"},
    "Leo": {"element": "Fire", "modality": "Fixed", "ruler": "Sun", "glyph": "\u264C"},
    "Virgo": {"element": "Earth", "modality": "Mutable", "ruler": "Mercury", "glyph": "\u264D"},
    "Libra": {"element": "Air", "modality": "Cardinal", "ruler": "Venus", "glyph": "\u264E"},
    "Scorpio": {"element": "Water", "modality": "Fixed", "ruler": "Pluto", "glyph": "\u264F"},
    "Sagittarius": {"element": "Fire", "modality": "Mutable", "ruler": "Jupiter", "glyph": "\u2650"},
    "Capricorn": {"element": "Earth", "modality": "Cardinal", "ruler": "Saturn", "glyph": "\u2651"},
    "Aquarius": {"element": "Air", "modality": "Fixed", "ruler": "Uranus", "glyph": "\u2652"},
    "Pisces": {"element": "Water", "modality": "Mutable", "ruler": "Neptune", "glyph": "\u2653"},
}

STRENGTH_BLURBS = {
    "Aries": "Courageous initiative, honest drive, and the ability to start what others only dream about.",
    "Taurus": "Patient endurance, loyal devotion, and a gift for building lasting security and beauty.",
    "Gemini": "Quick learning, witty communication, and versatile problem-solving under pressure.",
    "Cancer": "Protective intuition, deep empathy, and emotional intelligence that nurtures others.",
    "Leo": "Generous warmth, creative confidence, and natural leadership that uplifts a room.",
    "Virgo": "Precision, helpfulness, and sharp improvement skills that turn chaos into order.",
    "Libra": "Diplomatic grace, aesthetic taste, and peacemaking that restores balance.",
    "Scorpio": "Emotional courage, strategic focus, and transformative insight into hidden motives.",
    "Sagittarius": "Optimistic vision, honest philosophy, and fearless exploration of new horizons.",
    "Capricorn": "Discipline, integrity, and long-game ambition that climbs with quiet strength.",
    "Aquarius": "Original thinking, humanitarian ideals, and inventive solutions ahead of the curve.",
    "Pisces": "Compassion, imagination, and spiritual sensitivity that heals through understanding.",
}

WEAKNESS_BLURBS = {
    "Aries": "Impatience, sharp reactions, or moving too fast before listening to quieter signals.",
    "Taurus": "Stubborn resistance to change, over-attachment to comfort, or delayed adaptation.",
    "Gemini": "Scattered focus, nervous overthinking, or difficulty sitting with one deep decision.",
    "Cancer": "Mood swings, retreat under stress, or taking feedback more personally than intended.",
    "Leo": "Pride wounds, spotlight hunger, or mistaking loyalty for unlimited attention.",
    "Virgo": "Self-criticism, worry loops, or perfect standards that delay necessary action.",
    "Libra": "People-pleasing, indecision, or avoiding hard truths to keep harmony at all costs.",
    "Scorpio": "Intensity that overwhelms others, secrecy, or control instincts during vulnerability.",
    "Sagittarius": "Over-promising, blunt honesty, or restlessness that disrupts steady progress.",
    "Capricorn": "Workaholic tendencies, emotional reserve, or fear of imperfection slowing joy.",
    "Aquarius": "Detached coolness, unpredictability, or idealism that forgets tender human needs.",
    "Pisces": "Escapism, porous boundaries, or absorbing other people's moods too easily.",
}

LUCKY_DAYS = {
    "Aries": "Tuesday",
    "Taurus": "Friday",
    "Gemini": "Wednesday",
    "Cancer": "Monday",
    "Leo": "Sunday",
    "Virgo": "Wednesday",
    "Libra": "Friday",
    "Scorpio": "Tuesday",
    "Sagittarius": "Thursday",
    "Capricorn": "Saturday",
    "Aquarius": "Saturday",
    "Pisces": "Thursday",
}

ELEMENT_COLORS = {
    "Fire": "Gold & crimson",
    "Earth": "Forest green & clay",
    "Air": "Sky blue & silver",
    "Water": "Indigo & sea glass",
}


def _sign_index(sign: str) -> int:
    return ZODIAC_ORDER.index(sign) if sign in ZODIAC_ORDER else 0


def harmony_matches(zodiac: str) -> str:
    """Light element-based compatibility hint (entertainment)."""
    meta = ZODIAC_META.get(zodiac, ZODIAC_META["Aries"])
    element = meta["element"]
    same_element = [s for s in ZODIAC_ORDER if ZODIAC_META[s]["element"] == element and s != zodiac]
    complementary = {
        "Fire": ["Air"],
        "Air": ["Fire"],
        "Water": ["Earth"],
        "Earth": ["Water"],
    }
    other_el = complementary.get(element, ["Air"])
    bridge = [s for s in ZODIAC_ORDER if ZODIAC_META[s]["element"] in other_el][:4]
    pool = list(dict.fromkeys(same_element[:2] + bridge))
    return ", ".join(pool[:3])


def growth_matches(zodiac: str) -> str:
    """Signs that can feel challenging but catalyze growth."""
    idx = _sign_index(zodiac)
    square_a = ZODIAC_ORDER[(idx + 3) % 12]
    square_b = ZODIAC_ORDER[(idx + 9) % 12]
    return f"{square_a}, {square_b}"


def seasonal_transit_note(now: datetime, sun_sign: str) -> str:
    """Seasonal flavor from calendar month (rule-based, not real ephemeris)."""
    month = now.month
    seasons = {
        12: "Winter quiet invites planning; review what you want before the next surge.",
        1: "A reset favors fresh systems—small rituals now compound through spring.",
        2: "Patience deepens intuition; notice messages in dreams and synchronicities.",
        3: "Momentum returns; say yes to learning curves you can practice in public.",
        4: "Stability season: nurture your body, budget, and consistent allies.",
        5: "Social sparks return—networking and storytelling open doors faster than perfection.",
        6: "Home and heart take priority; protect your peace like infrastructure.",
        7: "Creative risk is supported; let yourself be seen without endless rehearsal.",
        8: "Refinement pays off—edit, simplify, polish what already works.",
        9: "Partnerships clarify; negotiate kindly but keep your standards clean.",
        10: "Transformation asks honesty; release control where trust works better.",
        11: "Expansion calls—study ideas, travel plans, and mentors can reroute you.",
    }
    base = seasons.get(month, seasons[6])
    return f"As a {sun_sign}, {base} Timing improves when action matches emotional truth."


def build_blueprint(zodiac: str, moon: str, asc: str, birth_date) -> Dict[str, Any]:
    """Structured chart highlights for UI chips and quick reference."""
    meta = ZODIAC_META.get(zodiac, ZODIAC_META["Aries"])
    lucky_number = (birth_date.day * 11 + birth_date.month * 13 + birth_date.year) % 88 + 3
    element = meta["element"]
    return {
        "glyph": meta["glyph"],
        "sun_sign": zodiac,
        "element": element,
        "modality": meta["modality"],
        "ruling_planet": meta["ruler"],
        "lucky_number": lucky_number,
        "lucky_day": LUCKY_DAYS.get(zodiac, "Thursday"),
        "lucky_color": ELEMENT_COLORS.get(element, "Amethyst & silver"),
        "moon_sign": moon,
        "ascendant": asc,
        "best_matches": harmony_matches(zodiac),
        "growth_signs": growth_matches(zodiac),
        "energy_focus": f"{meta['ruler']}-styled drive with {element.lower()} element steadiness",
    }


def simulate_palm_analysis(hand_choice: str) -> str:
    """Fake palm interpretation for engaging experience."""
    hand_label = "left hand" if hand_choice == "left" else "right hand"
    line_strength = "strong and etched" if hand_choice == "right" else "soft but deep"
    return (
        f"Your {hand_label} shows {line_strength} life and heart lines. This pattern suggests emotional wisdom, "
        "strong resilience after setbacks, and a tendency to trust intuition before logic. "
        "A slight curve near the fate line indicates a meaningful career pivot that becomes your turning point."
    )


def build_prediction(
    full_name: str,
    birth_place: str,
    profile: Dict[str, str],
    palm_text: Optional[str],
    birth_date,
    now: datetime,
    blueprint: Dict[str, Any],
) -> Dict[str, str]:
    """Rich, rule-based sections that feel like a full astrology reading."""
    z = profile["zodiac"]
    m = profile["moon_sign"]
    a = profile["ascendant"]
    meta = ZODIAC_META.get(z, ZODIAC_META["Aries"])
    element = meta["element"]

    personality = (
        f"{full_name}, the veil lifts on a signature that is unmistakably {z} {blueprint['glyph']}: "
        f"{PERSONALITY_RULES.get(z, 'a rare blend of fire and wisdom')}. "
        f"Your emotional story is painted by a {m} Moon—this is how you nurture, remember, and heal. "
        f"Rising as {a}, you broadcast a first impression that can charm rooms, test boundaries, or quietly command respect—"
        "often before you say a single polished sentence."
    )

    career = (
        f"Your vocational compass tilts toward arenas tied to {CAREER_RULES.get(z, 'strategy and craft')}. "
        f"The {element.lower()} element in your Sun wants work with tangible impact; your {m} Moon needs meaning, not only metrics. "
        f"With {a} on the ascendant, leadership shows up through presence, pacing, and the story you tell about your mission. "
        f"Places and networks echoing the spirit of {birth_place} can act like catalysts when you are ready to claim the next level."
    )

    love = (
        f"In love, your {m} Moon asks for emotional fluency: safe words, loyal gestures, and a partner who does not vanish when feelings intensify. "
        f"Your {z} Sun brings heat, sincerity, and non-negotiable self-respect. "
        f"{a} rising adds charisma in early attraction, but your real bond blooms when someone proves steadiness over performance. "
        f"Harmonious archetypes to explore: {blueprint['best_matches']}. Growth-oriented tension may arrive with {blueprint['growth_signs']}—"
        "not punishment, but accelerators that sharpen clarity."
    )

    future = (
        f"The path ahead favors showing up as the whole version of yourself—not only the convenient one. "
        f"The triad of {z}, {m}, and {a} suggests a destiny that rewards courage, compassionate boundaries, and a willingness to reroute when intuition whispers 'not this.' "
        f"Lucky threads this year: lean into {blueprint['lucky_day']} energy, {blueprint['lucky_color']} tones as mindful cues, and the number {blueprint['lucky_number']} as a playful synchronicity anchor."
    )
    if palm_text:
        future += (
            " The palm layer adds a tactile prophecy: destiny here moves through your hands—what you build, touch, and repair becomes part of the spell."
        )

    strengths = STRENGTH_BLURBS.get(z, STRENGTH_BLURBS["Aries"])
    weaknesses = WEAKNESS_BLURBS.get(z, WEAKNESS_BLURBS["Aries"])

    wellness = (
        f"Wellness for {z} thrives when the {element.lower()} element is honored. "
        f"Ground glittering stress with breathwork, walking rhythm, or a creative outlet that cannot be graded. "
        f"Your {m} Moon may store tension in the body like memory—prioritize sleep sanctuaries and emotional debriefs with people who feel safe."
    )

    compatibility = (
        f"Compatibility snapshot: your Sun seeks playmates of the mind and heart who match your tempo. "
        f"Easy resonance often appears with {blueprint['best_matches']}, while {blueprint['growth_signs']} may teach lessons about compromise, trust, and bold honesty. "
        f"Remember: astrology highlights tendencies, not verdicts—choose kindness and curiosity over fatalism."
    )

    seasonal_energy = seasonal_transit_note(now, z)

    return {
        "personality": personality,
        "career": career,
        "love": love,
        "future": future,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "wellness": wellness,
        "compatibility": compatibility,
        "seasonal_energy": seasonal_energy,
    }


def build_report_html(name: str, profile: Dict[str, str], sections: Dict[str, str], palm_text: Optional[str]) -> str:
    """Return safe HTML used for print and archival views."""
    palm_block = ""
    if palm_text:
        palm_block = (
            '<article class="report-section-card">'
            '<div class="report-section-heading"><span class="report-icon">\u270B</span><h3>Palm Reading Insight</h3></div>'
            f"<p class='report-copy'>{escape(palm_text)}</p>"
            "</article>"
        )

    def block(icon: str, title: str, key: str) -> str:
        body = escape(sections.get(key, ""))
        return (
            '<article class="report-section-card">'
            f'<div class="report-section-heading"><span class="report-icon">{icon}</span><h3>{escape(title)}</h3></div>'
            f"<p class='report-copy'>{body}</p>"
            "</article>"
        )

    html_parts = [
        f"<h2 class='report-title'>{escape(name)} — Cosmic Brief</h2>",
        f"<p class='report-meta'>Sun {escape(profile['zodiac'])} · Moon {escape(profile['moon_sign'])} · Asc {escape(profile['ascendant'])}</p>",
        block("\u2726", "Personality Analysis", "personality"),
        block("\u2726", "Career Path", "career"),
        block("\u2726", "Love & Relationships", "love"),
        block("\u2726", "Future Outlook", "future"),
        block("\u2600", "Core Strengths", "strengths"),
        block("\u263D", "Growth Edges", "weaknesses"),
        block("\u2727", "Wellness & Rhythm", "wellness"),
        block("\u2665", "Compatibility Notes", "compatibility"),
        block("\u25CE", "Seasonal Energy & Timing", "seasonal_energy"),
        block("\u2726", "Kundli & chart layer", "kundli_layer"),
        block("\u2726", "Houses (whole-sign demo)", "vedic_houses"),
        block("\u2726", "Rahu & Ketu", "rahu_ketu"),
        block("\u2726", "Dasha / dosha snapshot", "vimshottari_timing"),
        block("\u2726", "Remedies & ethical lifestyle", "remedies_lifestyle"),
        palm_block,
    ]
    # Strip any non-printable control chars that can appear from copy/paste or encoding issues.
    rendered = "".join(html_parts)
    rendered = "".join(ch for ch in rendered if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return rendered


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
    try:
        model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.1-8b-instant"
        logger.info(f"🔄 Using Groq SDK with model '{model}'")
        
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model,
            temperature=0.65,
            max_tokens=900,
        )
        
        result = chat_completion.choices[0].message.content.strip()
        logger.info(f"✅ Groq chat success ({len(result)} chars)")
        return result
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        # Parse error details
        if "401" in error_msg or "Unauthorized" in error_msg:
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
        model = os.environ.get("GROQ_MODEL", "").strip() or "llama-3.1-8b-instant"
        logger.info(f"🔄 Using Groq HTTP fallback with model '{model}'")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.65,
            "max_tokens": 900,
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
            "temperature": 0.65,
            "max_tokens": 900,
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


def fetch_report_row(report_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    return row


def save_report(payload: Dict) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO reports (
            full_name, birth_date, birth_time, birth_place, palm_enabled, hand_choice, palm_image_path,
            zodiac, moon_sign, ascendant, personality, career, love_life, future_outlook,
            strengths, weaknesses, wellness, compatibility, seasonal_energy,
            palm_analysis, report_html, report_extras, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["full_name"],
            payload["birth_date"],
            payload["birth_time"],
            payload["birth_place"],
            payload["palm_enabled"],
            payload["hand_choice"],
            payload["palm_image_path"],
            payload["profile"]["zodiac"],
            payload["profile"]["moon_sign"],
            payload["profile"]["ascendant"],
            payload["sections"]["personality"],
            payload["sections"]["career"],
            payload["sections"]["love"],
            payload["sections"]["future"],
            payload["sections"]["strengths"],
            payload["sections"]["weaknesses"],
            payload["sections"]["wellness"],
            payload["sections"]["compatibility"],
            payload["sections"]["seasonal_energy"],
            payload["palm_analysis"],
            payload["report_html"],
            payload["report_extras"],
            payload["created_at"],
        ),
    )
    conn.commit()
    report_id = cursor.lastrowid or 0
    conn.close()
    return report_id


@app.route("/landing")
def landing():
    """Serve the futuristic landing page."""
    return render_template("landing.html")


@app.route("/")
def index():
    """Serve the futuristic landing page as home."""
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

    now = datetime.utcnow()
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


@app.route("/api/debug/chat-config", methods=["GET"])
def debug_chat_config():
    """Debug endpoint to check chat configuration. Redacts sensitive values."""
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    groq_model = os.environ.get("GROQ_MODEL", "").strip()
    openai_model = os.environ.get("OPENAI_MODEL", "").strip()
    
    def redact(key: str) -> str:
        if not key:
            return "[NOT SET]"
        if len(key) < 10:
            return f"[TOO SHORT: {len(key)} chars]"
        return f"[SET: {key[:10]}...{key[-5:]}]"
    
    return jsonify({
        "groq": {
            "api_key": redact(groq_key),
            "model": groq_model or "[DEFAULT: llama-3.1-8b-instant]",
            "endpoint": "https://api.groq.com/openai/v1",
            "status": "✅ READY" if groq_key and groq_model else "❌ MISSING"
        },
        "openai": {
            "api_key": redact(openai_key),
            "model": openai_model or "[DEFAULT: gpt-4o-mini]",
            "endpoint": "https://api.openai.com/v1",
            "status": "✅ READY" if openai_key else "❌ MISSING"
        },
        "active_provider": "Groq" if groq_key else ("OpenAI" if openai_key else "NONE"),
        "custom_base_url": os.environ.get("AI_CHAT_BASE_URL", "[NOT SET]"),
        "openai_available_flag": OPENAI_AVAILABLE,
        "recommendations": [
            "Ensure GROQ_API_KEY is set on Render" if not groq_key else "✅ GROQ_API_KEY is set",
            "Set GROQ_MODEL to 'llama-3.1-8b-instant'" if not groq_model else f"✅ GROQ_MODEL = {groq_model}",
            "API key must be at least 20 characters" if groq_key and len(groq_key) < 20 else "✅ API key length OK"
        ]
    })


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
        system = (
            "You are a compassionate, accurate Vedic-inspired astrologer chat guide. "
            "Use the structured CONTEXT; do not invent precise astronomical facts not in context. "
            "Refuse medical/legal claims; encourage professional human advice. "
            "Tone: warm, mystical, empowering."
        )
        user_blob = f"CONTEXT:\n{ctx}\n\nUSER QUESTION:\n{message}"
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

        return jsonify(
            {
                "success": True,
                "reply": ai_reply,
                "source": "ai",
            }
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {type(e).__name__}: {e}")
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