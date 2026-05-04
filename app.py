"""Celestial Arc — Main Flask Application (refactored)."""
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

from ai_client import openai_guru_reply
from database import init_db, migrate_db, save_report, fetch_report_by_public_id, fetch_report_row, save_chat_message, get_chat_history
from geo import photon_search, timeapi_timezone_name
from security import register_security, ensure_csrf, client_ip
from services.analysis_service import (
    compute_hybrid_big_three, build_blueprint, build_prediction,
    simulate_palm_analysis, zodiac_sign, moon_sign, ascendant_sign,
    build_report_html
)
from services.storage_service import upload_palm_image, delete_file
from services.auth_service import optional_auth, require_auth
from vedic_engine import build_vedic_bundle, format_guru_context, get_horoscope_for_sign, generate_kundli_chart_from_birth

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
    return datetime.strptime(time_str, "%H:%M").time()

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ───────────────────────────────────────────────────────────

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
        "- \"personality\": 2-3 sentences about their deep nature based on Sun, Moon, Lagna, and Nakshatra.\n"
        "- \"career\": 2-3 sentences analyzing the 10th house, Saturn, and Mercury.\n"
        "- \"love\": 2-3 sentences on relationships based on the 7th house, Venus, and Moon.\n"
        "- \"future\": 2-3 sentences predicting the overarching life trajectory and karmic goals.\n"
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
    try:
        reply = openai_guru_reply(system_prompt, chart_data)
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
        kundli_image_path = upload_palm_image(file_bytes, kundli_file.filename)

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
        profile = {
            "zodiac": zodiac_sign(parsed_date),
            "moon_sign": moon_sign(parsed_date),
            "ascendant": ascendant_sign(parsed_time, birth_place),
        }
        chart_debug["fallback"] = "legacy_approx"

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

    report_html = build_report_html(full_name, profile, sections, palm_text)
    created_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    report_extras = json.dumps({
        "blueprint": blueprint, "vedic": vedic_structured, "vedic_sections": vedic_sections,
        "kundli_image_path": kundli_image_path, "kundli_notes": kundli_notes,
        "hybrid_chart": hybrid_details, "chart_debug": chart_debug,
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
        "palm_disclaimer": "AI-simulated palm reading — for entertainment purposes only" if palm_text else None,
        "ai_chat_available": bool(os.environ.get("GROQ_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()),
    })


@app.route("/api/config", methods=["GET"])
def api_config():
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    return jsonify({
        "ai_chat": bool(groq_key or openai_key),
        "provider": "groq" if groq_key else ("openai" if openai_key else "none"),
    })


@app.route("/api/ai/status", methods=["GET"])
def api_ai_status():
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    provider = "groq" if groq_key else ("openai" if openai_key else "none")
    enabled = bool(groq_key or openai_key)
    if not enabled:
        return jsonify({"success": True, "enabled": False, "provider": "none"})
    probe = openai_guru_reply("You are a diagnostics endpoint. Reply with exactly: OK", "OK")
    return jsonify({"success": True, "enabled": True, "provider": provider, "ok": bool(probe)})


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

    # Support both public_id (UUID) and legacy integer id
    row = None
    try:
        rid = int(report_id)
        row = fetch_report_row(rid)
    except (TypeError, ValueError):
        row = fetch_report_by_public_id(str(report_id))

    if row is None:
        return jsonify({"success": False, "error": "Report not found."}), 404

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
        report_excerpts = "\n".join([
            f"Personality: {_chat_text_clip(merged_sections.get('personality'))}",
            f"Career: {_chat_text_clip(merged_sections.get('career'))}",
            f"Future: {_chat_text_clip(merged_sections.get('future'))}",
            f"Love: {_chat_text_clip(merged_sections.get('love'))}",
            f"Strengths: {_chat_text_clip(merged_sections.get('strengths'), 600)}",
            f"Weaknesses: {_chat_text_clip(merged_sections.get('weaknesses'), 600)}",
            f"Wellness: {_chat_text_clip(merged_sections.get('wellness'), 600)}",
            f"Compatibility: {_chat_text_clip(merged_sections.get('compatibility'), 600)}",
            f"Seasonal Energy: {_chat_text_clip(merged_sections.get('seasonal_energy'), 600)}",
            f"Dasha Timing: {_chat_text_clip(merged_sections.get('vimshottari_timing'), 600)}",
            f"Rahu-Ketu: {_chat_text_clip(merged_sections.get('rahu_ketu'), 600)}",
            f"Remedies: {_chat_text_clip(merged_sections.get('remedies_lifestyle'), 600)}",
        ])
        system = (
            "You are Guru Arya — a 30-year experienced Vedic astrologer. "
            "Your job is to provide accurate, personal, and clear Vedic readings. "
            "You strictly follow the Vedic Lahiri Ayanamsa sidereal system.\n\n"
            "LANGUAGE RULES:\n- ALWAYS speak in simple, plain English. No Hindi or Hinglish.\n"
            "- Address the user by name when natural.\n\n"
            "STRICT RULES:\n- ONLY use Vedic (Jyotish) astrology. NO Western astrology.\n"
            "- ONLY use provided chart data — do not guess or invent.\n"
            "- NO generic horoscope lines — every answer MUST be specific to this person's chart.\n"
            "- NEVER break character or say 'As an AI'. You ARE Guru Arya.\n\n"
            "RESPONSE FORMAT:\n"
            "1. For greetings: reply naturally and wait for their question.\n"
            "2. For astrology questions use 4 parts:\n"
            "   **[Direct Answer]** — clear answer to their question.\n"
            "   **[The 'Why']** — specific planets, houses, dasha causing it.\n"
            "   **[Timing]** — timeframe based on Mahadasha/Antardasha.\n"
            "   **[Advice]** — 1-2 practical lines.\n\n"
            "Keep answers between 150-350 words."
        )
        user_blob = f"CHART CONTEXT:\n{ctx}\n\nREPORT EXCERPTS:\n{report_excerpts}\n\n{row['full_name']}'s QUESTION:\n{message}"

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
os.makedirs(INSTANCE_DIR, exist_ok=True)
validate_startup_config()
init_db()
migrate_db()

# ── Daily horoscope email scheduler ──────────────────────────────────
import atexit
from services.scheduler_service import init_scheduler, shutdown_scheduler
init_scheduler(app)
atexit.register(shutdown_scheduler)


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
