"""Celestial Arc — Main Flask Application (refactored)."""
import concurrent.futures
import json
import logging
import os
import secrets
import uuid
from datetime import date, datetime, time, timezone
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, render_template, request, session
from dotenv import load_dotenv
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.ai_client import openai_guru_reply
from database import init_db, migrate_db, save_report, fetch_report_by_public_id, save_chat_message, get_chat_history
from utils.geo import photon_search, timeapi_timezone_name
from security import register_security, ensure_csrf, client_ip
from services.analysis_service import (
    compute_hybrid_big_three, build_blueprint, build_prediction,
    simulate_palm_analysis, zodiac_sign, moon_sign, ascendant_sign,
    western_zodiac_sign,
    build_report_html, build_report_html_v2,
    compute_full_dasha, compute_birth_panchanga,
    compute_ashtakavarga, compute_compatibility,
)
from services.storage_service import upload_palm_image, upload_kundli_image, delete_file
from services.auth_service import optional_auth, require_auth
from utils.vedic_engine import build_vedic_bundle, format_guru_context, get_horoscope_for_sign, generate_kundli_chart_from_birth

load_dotenv()

# ── Structured logging + Sentry ──────────────────────────────────────
from logging_config import setup_logging, setup_sentry
setup_logging()
setup_sentry()
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=False)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# ── Configuration ────────────────────────────────────────────────────
from config import configure_app, validate_startup_config
configure_app(app)

# ── Security (headers, rate limiting, CSRF) ──────────────────────────
register_security(app)

# ── Register blueprints ──────────────────────────────────────────────
from blueprints.auth import auth_bp
from blueprints.compatibility import compat_bp
app.register_blueprint(auth_bp)
app.register_blueprint(compat_bp)


# ── Helper functions ─────────────────────────────────────────────────

def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()

def parse_time(time_str: str) -> time:
    time_str = (time_str or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time format: {time_str!r}")

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ───────────────────────────────────────────────────────────
@app.route("/api/debug-swisseph")
def debug_swisseph():
    try:
        import swisseph as swe

        return {
            "installed": True,
            "version": swe.version(),
            "ephe_path": swe.get_ephe_path()
        }
    except Exception as e:
        return {
            "installed": False,
            "error": str(e)
        }, 500
@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"ok": True})

@app.route("/api/csrf", methods=["GET"])
def api_csrf():
    return jsonify({"success": True, "csrf_token": ensure_csrf()})

@app.route("/landing")
def landing():
    return render_template("landing.html")

@app.route("/")
def index():
    return render_template("landing.html")

@app.route("/app")
def app_view():
    return render_template("index.html")

@app.route("/horoscope")
def horoscope_view():
    return render_template("horoscope.html")

@app.route("/dashboard")
def dashboard_view():
    return render_template("dashboard.html")

@app.route("/login")
def login_view():
    return render_template("login.html")


@app.route("/api/places", methods=["GET"])
def api_places():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"success": True, "places": []})
    places = photon_search(q, limit=7)
    return jsonify({"success": True, "places": places})


def generate_dynamic_report_cards(full_name, profile, vedic_structured, vedic_sections):
    """Generate personalized Vedic reading cards via LLM."""
    system_prompt = (
        "You are an expert Vedic astrologer generating a highly personalized astrology report. "
        "You MUST return the output as a valid, raw JSON object exactly matching the keys provided. "
        "Do NOT wrap the JSON in markdown code blocks (like ```json ... ```). Just return the raw JSON object.\n\n"
        "REQUIRED KEYS:\n"
        "- \"personality\": 2-3 sentences about their deep nature based on Sun, Moon, Lagna, Nakshatra, and active Yogas.\n"
        "- \"career\": 2-3 sentences analyzing the 10th house, Saturn, Mercury, and Dashamsha (D10).\n"
        "- \"love\": 2-3 sentences on relationships based on the 7th house, Venus, Moon, and Navamsa (D9).\n"
        "- \"future\": 2-3 sentences predicting trajectory using Dasha + Transit confidence score.\n"
        "- \"strengths\": 1-2 sentences on their strongest astrological assets.\n"
        "- \"weaknesses\": 1-2 sentences on challenges and how to overcome them.\n"
        "- \"wellness\": 1-2 sentences on health based on the 6th/8th house and Moon.\n"
        "- \"compatibility\": 1-2 sentences on what energy matches them best.\n"
        "- \"seasonal_energy\": 1-2 sentences on their current Dasha/Antardasha timing.\n\n"
        "RULES:\n"
        "- Write in beautiful, simple, plain English (NO Hinglish).\n"
        "- Be deeply personalized. Explicitly mention their specific planets and houses.\n"
        "- Be empowering but honest.\n"
        "- Address them directly by name if appropriate.\n"
        "- The JSON must be valid and parseable by Python's json.loads()."
    )
    chart_data = (
        f"USER: {full_name}\n"
        f"BIG THREE: Sun in {profile.get('zodiac')}, Moon in {profile.get('moon_sign')}, Ascendant in {profile.get('ascendant')}\n"
        f"DASHAS: {vedic_structured.get('mahadasha')} Mahadasha, {vedic_structured.get('antardasha_demo')} Antardasha\n"
        f"NAKSHATRA: {vedic_structured.get('nakshatra')} (Lord: {vedic_structured.get('nakshatra_lord')})\n"
        f"DOSHAS: {', '.join(vedic_structured.get('dosha_flags', []))}\n"
        f"HOUSES:\n{vedic_sections.get('vedic_houses')}\n\nGenerate the JSON report for this person."
    )
    def _call():
        return openai_guru_reply(system_prompt, chart_data, max_tokens=1500)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call)
            reply = future.result(timeout=15)  # 15-second hard timeout
        if not reply:
            return None
        reply = reply.strip()
        if reply.startswith("```json"):
            reply = reply[7:]
        if reply.startswith("```"):
            reply = reply[3:]
        if reply.endswith("```"):
            reply = reply[:-3]
        cards = json.loads(reply.strip())
        required_keys = ["personality", "career", "love", "future", "strengths", "weaknesses", "wellness", "compatibility", "seasonal_energy"]
        for key in required_keys:
            if key not in cards:
                return None
        return cards
    except concurrent.futures.TimeoutError:
        logger.warning("Dynamic report card generation timed out after 15s — using static fallback")
        return None
    except Exception as e:
        logger.error(f"Failed to generate dynamic cards: {e}")
        return None


@app.route("/api/analyze", methods=["POST"])
@optional_auth
def analyze():
    """Validate inputs and generate astrology report."""
    try:
        full_name = request.form.get("full_name", "").strip()
        birth_date_raw = request.form.get("birth_date", "").strip()
        birth_time_raw = request.form.get("birth_time", "").strip()
        birth_place = request.form.get("birth_place", "").strip()
        place_lat_raw = (request.form.get("place_lat") or "").strip()
        place_lon_raw = (request.form.get("place_lon") or "").strip()
        place_label = (request.form.get("place_label") or "").strip()
        place_tz = (request.form.get("place_tz") or "").strip()
        palm_enabled = request.form.get("palm_enabled", "no").strip().lower() == "yes"
        gender = request.form.get("gender", "").strip().lower()
        hand_choice = request.form.get("hand_choice", "").strip().lower()
        palm_image = request.files.get("palm_image")
        kundli_notes = request.form.get("kundli_notes", "").strip()
        kundli_file = request.files.get("kundli_chart")

        missing = []
        if not full_name: missing.append("full_name")
        if not birth_date_raw: missing.append("birth_date")
        if not birth_time_raw: missing.append("birth_time")
        if not birth_place: missing.append("birth_place")
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

    # ── Palm image handling (via Supabase Storage) ───────────────
    palm_image_path = None
    palm_text = None
    if palm_enabled:
        if hand_choice not in {"left", "right"}:
            return jsonify({"success": False, "error": "Please choose left or right hand for palm reading."}), 400
        if palm_image and palm_image.filename:
            if not allowed_file(palm_image.filename):
                return jsonify({"success": False, "error": "Palm image must be png, jpg, jpeg, or webp."}), 400
            file_bytes = palm_image.read()
            palm_image_path = upload_palm_image(file_bytes, palm_image.filename)
            palm_text = simulate_palm_analysis(hand_choice)

    # ── Kundli image ─────────────────────────────────────────────
    kundli_image_path = None
    if kundli_file and kundli_file.filename:
        if not allowed_file(kundli_file.filename):
            return jsonify({"success": False, "error": "Kundli image must be png, jpg, jpeg, or webp."}), 400
        file_bytes = kundli_file.read()
        # MAJOR-03: Use dedicated kundli-images bucket, not palm-images
        kundli_image_path = upload_kundli_image(file_bytes, kundli_file.filename)

    # ── Geocoding + timezone ─────────────────────────────────────
    chart_debug: Dict[str, Any] = {"place_autocomplete_used": bool(place_lat_raw and place_lon_raw)}
    lat, lon = None, None
    if place_lat_raw and place_lon_raw:
        try:
            lat, lon = float(place_lat_raw), float(place_lon_raw)
        except ValueError:
            lat, lon = None, None

    if lat is None or lon is None:
        places = photon_search(place_label or birth_place, limit=1)
        if places:
            lat, lon = float(places[0]["lat"]), float(places[0]["lon"])
            chart_debug["geocoded_label"] = places[0].get("label")
        else:
            chart_debug["geocode_failed"] = True

    tz_name = place_tz or None
    if tz_name is None and lat is not None and lon is not None:
        tz_name = timeapi_timezone_name(lat, lon)
        if tz_name:
            chart_debug["tz_resolved_by"] = "timeapi"

    # ── Compute chart ────────────────────────────────────────────
    profile = None
    hybrid_details: Dict[str, Any] = {}
    if lat is not None and lon is not None and tz_name:
        try:
            profile, hybrid_details = compute_hybrid_big_three(parsed_date, parsed_time, birth_place, lat, lon, tz_name)
        except ZoneInfoNotFoundError:
            chart_debug["tz_invalid"] = tz_name
        except Exception as e:
            chart_debug["hybrid_error"] = str(e)

    if profile is None:
        # NOTE: ascendant cannot be calculated without lat/lon/timezone
        # Sun & Moon signs use date-based fallback, ascendant shows Unknown
        profile = {
            "zodiac": zodiac_sign(parsed_date),
            "moon_sign": moon_sign(parsed_date),
            "ascendant": "Unknown (location required)",
        }
        chart_debug["fallback"] = "legacy_approx — ascendant unavailable without geocoding"

    # Always add the Western/tropical sign for comparison
    profile["western_zodiac"] = western_zodiac_sign(parsed_date)

    now = datetime.now(timezone.utc)
    blueprint = build_blueprint(profile["zodiac"], profile["moon_sign"], profile["ascendant"], parsed_date)

    vedic_sections, vedic_structured = build_vedic_bundle(
        profile["ascendant"], profile["zodiac"], profile["moon_sign"],
        parsed_date, parsed_time, birth_place, kundli_notes,
        bool(kundli_image_path), hybrid_details,
    )

    dynamic_cards = generate_dynamic_report_cards(full_name, profile, vedic_structured, vedic_sections)
    if dynamic_cards:
        sections = dynamic_cards
        logger.info("Successfully generated dynamic AI report cards")
    else:
        sections = build_prediction(full_name, birth_place, profile, palm_text, parsed_date, now, blueprint)
        logger.warning("Dynamic cards failed, falling back to static predictions")
    sections.update(vedic_sections)

    # ── New Features: Dasha, Panchanga, Ashtakavarga ─────────────────
    birth_jd    = hybrid_details.get("jd")
    moon_lon    = hybrid_details.get("moon_lon_deg")
    tz_offset   = hybrid_details.get("tz_offset_hours", 5.5)

    # Use birth-date offset (handles DST correctly; do not use datetime.now())
    if tz_name and tz_offset == 5.5:
        try:
            _tz = ZoneInfo(tz_name)
            _dt_local = datetime.combine(parsed_date, parsed_time, tzinfo=_tz)
            tz_offset = _dt_local.utcoffset().total_seconds() / 3600.0
        except Exception:
            tz_offset = 5.5

    dasha_data         = {}
    panchanga_data     = {}
    ashtakavarga_data  = {}

    if birth_jd and moon_lon is not None:
        try:
            dasha_data = compute_full_dasha(moon_lon, birth_jd)
        except Exception as e:
            logger.warning("Dasha computation failed: %s", e)
            dasha_data = {"error": str(e)}

        try:
            _lat = lat or 20.0
            _lon = lon or 78.0
            panchanga_data = compute_birth_panchanga(birth_jd, _lat, _lon, tz_offset)
        except Exception as e:
            logger.warning("Panchanga computation failed: %s", e)
            panchanga_data = {"error": str(e)}

        # Ashtakavarga needs all planet signs from vedic_structured
        try:
            _planet_signs = vedic_structured.get("planet_signs", {})
            if _planet_signs:
                ashtakavarga_data = compute_ashtakavarga(
                    _planet_signs,
                    profile.get("ascendant", "Aries"),
                    profile.get("moon_sign", "Aries"),
                )
        except Exception as e:
            logger.warning("Ashtakavarga computation failed: %s", e)
            ashtakavarga_data = {"error": str(e)}

    report_html = build_report_html_v2(
        full_name, profile, sections, palm_text,
        dasha_data or None,
        panchanga_data or None,
        ashtakavarga_data or None,
    )
    created_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.debug("Chart debug info: %s", chart_debug)  # Internal only — never sent to client
    report_extras = json.dumps({
        "blueprint": blueprint,
        "vedic": vedic_structured,
        "vedic_sections": vedic_sections,
        "kundli_image_path": kundli_image_path,
        "hybrid_chart": hybrid_details,
        "gender": gender,
        "dasha": dasha_data,
        "panchanga": panchanga_data,
        "ashtakavarga": ashtakavarga_data,
    }, ensure_ascii=True)

    user_id = getattr(request, "current_user", {}).get("id") if hasattr(request, "current_user") and request.current_user else None

    public_id = save_report({
        "full_name": full_name, "birth_date": birth_date_raw, "birth_time": birth_time_raw,
        "birth_place": birth_place, "palm_enabled": 1 if palm_enabled else 0,
        "hand_choice": hand_choice if palm_enabled else None,
        "palm_image_path": palm_image_path, "profile": profile, "sections": sections,
        "palm_analysis": palm_text, "report_html": report_html,
        "report_extras": report_extras, "created_at": created_at,
    }, user_id=user_id)

    return jsonify({
        "success": True, "report_id": public_id, "profile": profile,
        "blueprint": blueprint, "vedic": vedic_structured, "sections": sections,
        "palm_analysis": palm_text, "report_html": report_html, "created_at": created_at,
        "yogas": vedic_structured.get("yogas", {}),
        "transits": vedic_structured.get("transits", {}),
        "strength": vedic_structured.get("strength", {}),
        "dasha": dasha_data,
        "panchanga": panchanga_data,
        "ashtakavarga": ashtakavarga_data,
        "palm_disclaimer": "AI-simulated palm reading — for entertainment purposes only" if palm_text else None,
        "ai_chat_available": bool(os.environ.get("GROQ_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()),
    })


@app.route("/api/config", methods=["GET"])
def api_config():
    # CRITICAL-04: Only expose whether AI is available — never reveal provider name
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    return jsonify({
        "ai_chat": bool(groq_key or openai_key),
    })


# ── New Feature Endpoints ─────────────────────────────────────────────

@app.route("/api/dasha", methods=["POST"])
def api_dasha():
    """
    Get full Vimshottari Dasha timeline for a birth chart.
    Body: { "moon_lon": float, "birth_jd": float }
    """
    try:
        data = request.get_json(force=True) or {}
        moon_lon  = float(data.get("moon_lon", 0))
        birth_jd  = float(data.get("birth_jd", 0))
        if not birth_jd:
            return jsonify({"success": False, "error": "birth_jd required"}), 400
        result = compute_full_dasha(moon_lon, birth_jd)
        return jsonify({"success": True, "dasha": result})
    except Exception as e:
        logger.exception("Dasha API error")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/panchanga", methods=["POST"])
def api_panchanga():
    """
    Get Panchanga for any date/time/location.
    Body: { "jd": float, "lat": float, "lon": float, "tz_offset": float }
    OR:   { "date": "YYYY-MM-DD", "time": "HH:MM", "lat": float, "lon": float, "tz_offset": float }
    """
    try:
        data = request.get_json(force=True) or {}
        lat        = float(data.get("lat", 20.0))
        lon        = float(data.get("lon", 78.0))
        tz_offset  = float(data.get("tz_offset", 5.5))

        if "jd" in data:
            jd = float(data["jd"])
        else:
            # Build JD from date+time
            date_str = data.get("date", "")
            time_str = data.get("time", "00:00")
            if not date_str:
                return jsonify({"success": False, "error": "date or jd required"}), 400
            from utils.astrology_math import julian_day as _jd_func
            from datetime import timezone as _tz_mod, timedelta
            dt_local = datetime.fromisoformat(f"{date_str}T{time_str}")
            dt_utc   = dt_local.replace(tzinfo=_tz_mod(timedelta(hours=tz_offset))).astimezone(_tz_mod.utc)
            jd = _jd_func(dt_utc)

        result = compute_birth_panchanga(jd, lat, lon, tz_offset)
        return jsonify({"success": True, "panchanga": result})
    except Exception as e:
        logger.exception("Panchanga API error")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ashtakavarga", methods=["POST"])
def api_ashtakavarga():
    """
    Get Ashtakavarga for a birth chart.
    Body: { "planet_signs": {planet: sign}, "lagna": str, "moon_sign": str }
    """
    try:
        data = request.get_json(force=True) or {}
        planet_signs = data.get("planet_signs", {})
        lagna        = data.get("lagna", "Aries")
        moon_sign_v  = data.get("moon_sign", "Aries")
        if not planet_signs:
            return jsonify({"success": False, "error": "planet_signs required"}), 400
        result = compute_ashtakavarga(planet_signs, lagna, moon_sign_v)
        return jsonify({"success": True, "ashtakavarga": result})
    except Exception as e:
        logger.exception("Ashtakavarga API error")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/compatibility", methods=["POST"])
def api_compatibility():
    """
    Compute Kundli Matching (36-point Guna Milan) for two people.
    Body: {
        "person1_moon_lon": float,  (sidereal)
        "person2_moon_lon": float,  (sidereal)
        "person1_planet_houses": {planet: house_num},  (optional)
        "person2_planet_houses": {planet: house_num},  (optional)
    }
    """
    try:
        data = request.get_json(force=True) or {}
        p1_moon = float(data.get("person1_moon_lon", 0))
        p2_moon = float(data.get("person2_moon_lon", 0))
        p1_houses = data.get("person1_planet_houses")
        p2_houses = data.get("person2_planet_houses")
        result = compute_compatibility(p1_moon, p2_moon, p1_houses, p2_houses)
        return jsonify({"success": True, "compatibility": result})
    except Exception as e:
        logger.exception("Compatibility API error")
        return jsonify({"success": False, "error": str(e)}), 500


# /api/ai/status removed — CRITICAL-04: made live AI probe calls with no auth/rate-limiting


def _chat_text_clip(text: Optional[str], max_len: int = 900) -> str:
    if not text:
        return ""
    t = " ".join(str(text).split())
    return t if len(t) <= max_len else t[:max_len - 1] + "…"


@app.route("/api/chat", methods=["POST"])
@optional_auth
def api_chat():
    payload = request.get_json(force=True, silent=True) or {}
    report_id = payload.get("report_id")
    message = (payload.get("message") or "").strip()
    if not report_id or not message:
        return jsonify({"success": False, "error": "report_id and message are required."}), 400

    user_id = getattr(request, "current_user", {}).get("id") if hasattr(request, "current_user") and request.current_user else None

    # CRITICAL-01: Look up by public UUID or fallback to integer ID for legacy cached frontend states
    try:
        report_id_int = int(report_id)
        row = fetch_report_row(report_id_int)
    except ValueError:
        row = fetch_report_by_public_id(str(report_id), user_id=user_id)

    if row is None:
        return jsonify({"success": False, "error": "Report not found."}), 404

    # CRITICAL-02: Ownership check — block if user doesn't own this report
    if row.get("user_id") and row["user_id"] != user_id:
        return jsonify({"success": False, "error": "Report not found or unauthorized."}), 404

    extras: Dict[str, Any] = {}
    if row.get("report_extras"):
        try:
            extras = json.loads(row["report_extras"])
        except json.JSONDecodeError:
            extras = {}

    blueprint = extras.get("blueprint") or {}
    vedic = extras.get("vedic") or {}
    vedic_sections = extras.get("vedic_sections") or {}

    profile = {"zodiac": row["zodiac"], "moon_sign": row["moon_sign"], "ascendant": row["ascendant"]}
    merged_sections = {
        "personality": row["personality"], "career": row["career"],
        "love": row["love_life"], "future": row["future_outlook"],
        "strengths": row.get("strengths") or "", "weaknesses": row.get("weaknesses") or "",
        "wellness": row.get("wellness") or "", "compatibility": row.get("compatibility") or "",
        "seasonal_energy": row.get("seasonal_energy") or "",
    }
    merged_sections.update({k: str(v) for k, v in vedic_sections.items()})

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not (groq_key or openai_key):
        return jsonify({"success": False, "error": "Chat service is offline."}), 503

    try:
        ctx = format_guru_context(row["full_name"], profile, vedic, blueprint)
        
        # Dynamic context filtering based on question to reduce token bloat and latency
        ml = message.lower()
        excerpts_to_include = [f"Personality: {_chat_text_clip(merged_sections.get('personality'))}"]
        
        if any(w in ml for w in ['career', 'job', 'work', 'business', 'money', 'wealth']):
            excerpts_to_include.append(f"Career/Wealth: {_chat_text_clip(merged_sections.get('career'))}")
        if any(w in ml for w in ['love', 'marriage', 'partner', 'relationship', 'spouse']):
            excerpts_to_include.append(f"Love: {_chat_text_clip(merged_sections.get('love'))}")
            excerpts_to_include.append(f"Compatibility: {_chat_text_clip(merged_sections.get('compatibility'), 400)}")
        if any(w in ml for w in ['future', 'when', 'time', 'dasha', 'transit']):
            excerpts_to_include.append(f"Future: {_chat_text_clip(merged_sections.get('future'))}")
            excerpts_to_include.append(f"Dasha Timing: {_chat_text_clip(merged_sections.get('vimshottari_timing'), 400)}")
        if any(w in ml for w in ['health', 'wellness', 'sick', 'disease']):
            excerpts_to_include.append(f"Wellness: {_chat_text_clip(merged_sections.get('wellness'), 400)}")
        
        if len(excerpts_to_include) == 1: # Default if no keywords match
            excerpts_to_include.append(f"Future: {_chat_text_clip(merged_sections.get('future'))}")
            excerpts_to_include.append(f"Strengths: {_chat_text_clip(merged_sections.get('strengths'), 400)}")
            
        report_excerpts = "\n".join(excerpts_to_include)

        system = (
            "You are Guru Arya — a wise, warm Vedic astrologer. "
            "Speak like a trusted elder. Match the user's language (English/Hindi/Hinglish).\n\n"
            "RULES:\n"
            "- Greetings ('Hi'): Just say hello warmly, NO reading.\n"
            "- DIRECT answers first (Yes/No), then explain.\n"
            "- Mention specific planets, houses, dashas.\n"
            "- NO markdown headers or bullet points.\n"
            "- ONLY Vedic (Jyotish) astrology. Do NOT make up placements.\n"
            "- MAX 4 SENTENCES. Do not ramble. GET TO THE POINT."
        )
        user_blob = f"CHART:\n{ctx}\n\nEXCERPTS:\n{report_excerpts}\n\nQUESTION:\n{message}"

        ai_reply = openai_guru_reply(system, user_blob)
        if ai_reply is None:
            return jsonify({"success": False, "error": "Chat service failed to generate response."}), 503

        # Save chat messages
        report_public_id = row.get("public_id", str(report_id))
        user_id = getattr(request, "current_user", {}).get("id") if hasattr(request, "current_user") and request.current_user else None
        try:
            save_chat_message(user_id, report_public_id, "user", message)
            save_chat_message(user_id, report_public_id, "assistant", ai_reply)
        except Exception as e:
            logger.warning(f"Could not save chat message: {e}")

        return jsonify({"success": True, "reply": ai_reply, "source": "ai"})
    except Exception as e:
        logger.error(f"Chat endpoint error: {type(e).__name__}: {e}")
        return jsonify({"success": False, "error": "An error occurred while processing your message."}), 500


@app.route("/api/chat/history/<report_id>", methods=["GET"])
@optional_auth
def api_chat_history(report_id):
    messages = get_chat_history(report_id, limit=50)
    return jsonify({"success": True, "messages": messages})


@app.route("/api/horoscope", methods=["GET"])
def api_horoscope():
    sign = request.args.get("sign", "").strip().capitalize()
    valid_signs = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    if sign not in valid_signs:
        return jsonify({"success": False, "error": "Invalid zodiac sign"}), 400
    horoscope = get_horoscope_for_sign(sign)
    return jsonify({"success": True, "sign": sign, "horoscope": horoscope})


@app.route("/api/kundli-chart", methods=["POST"])
def api_kundli_chart():
    payload = request.get_json(force=True, silent=True) or {}
    birth_date = payload.get("birth_date", "").strip()
    birth_time = payload.get("birth_time", "").strip()
    if not birth_date or not birth_time:
        return jsonify({"success": False, "error": "birth_date and birth_time required"}), 400
    try:
        result = generate_kundli_chart_from_birth(birth_date, birth_time)
        return jsonify(result) if result.get("success") else (jsonify(result), 400)
    except Exception as e:
        logger.error(f"Kundli chart generation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/reports", methods=["GET"])
@require_auth
def api_list_reports():
    from database import list_user_reports
    page = request.args.get("page", 1, type=int)
    limit = min(request.args.get("limit", 20, type=int), 100)
    reports = list_user_reports(request.current_user["id"], page=page, limit=limit)
    return jsonify({"success": True, "reports": reports, "page": page, "limit": limit})


@app.route("/api/chats", methods=["GET"])
@require_auth
def api_list_chats():
    from database import list_user_chats
    limit = min(request.args.get("limit", 10, type=int), 50)
    chats = list_user_chats(request.current_user["id"], limit=limit)
    return jsonify({"success": True, "chats": chats})


@app.route("/api/reports/<public_id>", methods=["GET"])
@optional_auth
def api_get_report(public_id):
    user_id = request.current_user["id"] if hasattr(request, "current_user") and request.current_user else None
    row = fetch_report_by_public_id(public_id, user_id=user_id)
    if row is None:
        return jsonify({"success": False, "error": "Report not found"}), 404
    return jsonify({"success": True, "report": row})


@app.route("/api/reports/<public_id>", methods=["DELETE"])
@require_auth
def api_delete_report(public_id):
    from database import delete_report
    row = fetch_report_by_public_id(public_id, user_id=request.current_user["id"])
    if row is None:
        return jsonify({"success": False, "error": "Report not found"}), 404
    if row.get("palm_image_path"):
        delete_file(row["palm_image_path"])
    delete_report(public_id, user_id=request.current_user["id"])
    return jsonify({"success": True})


# ── Startup ──────────────────────────────────────────────────────────
try:
    os.makedirs(INSTANCE_DIR, exist_ok=True)
except OSError:
    pass  # Vercel has a read-only filesystem
validate_startup_config()
init_db()
migrate_db()

# ── Daily horoscope email scheduler ──────────────────────────────────
# MAJOR-04: Only start scheduler in one process — prevents 4x emails on Gunicorn multi-worker
# Set SCHEDULER_ENABLED=true in Render env vars on exactly one service instance.
import atexit
from services.scheduler_service import init_scheduler, shutdown_scheduler
if os.environ.get("SCHEDULER_ENABLED", "false").lower() == "true":
    init_scheduler(app)
    atexit.register(shutdown_scheduler)
else:
    logger.info("Scheduler disabled — set SCHEDULER_ENABLED=true on one worker to enable")


@app.before_request
def log_request():
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
    _host = os.environ.get("FLASK_HOST", "0.0.0.0")
    _port = int(os.environ.get("FLASK_PORT", "5000"))
    _debug = app.config["DEBUG"]
    logger.info("Starting on %s:%d (debug=%s)", _host, _port, _debug)
    app.run(host=_host, port=_port, debug=_debug, threaded=True)
