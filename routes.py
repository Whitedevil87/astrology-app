import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict
from zoneinfo import ZoneInfoNotFoundError

from flask import jsonify, render_template, request

from ai_client import openai_guru_reply
from database import fetch_report_row, save_report
from feature_flags import get_public_feature_flags, is_ai_oracle_allowed
from geo import photon_search, timeapi_timezone_name
from helpers import (
    ascendant_sign,
    allowed_file,
    build_blueprint,
    build_prediction,
    build_report_html,
    compute_hybrid_big_three,
    make_upload_filename,
    moon_sign,
    parse_date,
    parse_time,
    simulate_palm_analysis,
    zodiac_sign,
)
from life_scores import compute_life_scores
from personalization import build_personalization
from vedic_engine import build_vedic_bundle, format_guru_context, get_horoscope_for_sign, generate_kundli_chart_from_birth


def register_routes(app):
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

    @app.route("/api/places", methods=["GET"])
    def api_places():
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"success": True, "places": []})
        places = photon_search(q, limit=7)
        return jsonify({"success": True, "places": places})

    @app.route("/api/analyze", methods=["POST"])
    def analyze():
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

            parsed_date = parse_date(birth_date_raw)
            parsed_time = parse_time(birth_time_raw)
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
            profile = {
                "zodiac": zodiac_sign(parsed_date),
                "moon_sign": moon_sign(parsed_date),
                "ascendant": ascendant_sign(parsed_time, birth_place),
            }
            chart_debug["fallback"] = "legacy_approx"

        now = datetime.now(timezone.utc).replace(tzinfo=None)
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

        feature_flags = get_public_feature_flags()
        personalization = build_personalization(
            full_name,
            profile,
            blueprint,
            vedic_structured,
            hybrid_details,
            now,
            feature_flags,
        )

        report_html = build_report_html(full_name, profile, sections, palm_text)
        created_at = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        life_scores = compute_life_scores(profile, blueprint)
        report_extras = json.dumps(
            {
                "blueprint": blueprint,
                "vedic": vedic_structured,
                "vedic_sections": vedic_sections,
                "kundli_image_path": kundli_image_path,
                "kundli_notes": kundli_notes,
                "hybrid_chart": hybrid_details,
                "chart_debug": chart_debug,
                "personalization": personalization,
                "life_scores": life_scores,
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
                "personalization": personalization,
                "hybrid_chart": hybrid_details,
                "life_scores": life_scores,
                "flags": feature_flags,
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
        payload = {
            "ai_chat": bool(key),
            "provider": "groq" if groq_key else ("openai" if openai_key else "none"),
            "hint": "Chat requires GROQ_API_KEY (recommended) or OPENAI_API_KEY to be set.",
        }
        payload.update(get_public_feature_flags())
        return jsonify(payload)

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

        if not is_ai_oracle_allowed():
            return jsonify(
                {
                    "success": False,
                    "error": "AI Oracle is temporarily paused. You can still read your saved report on screen.",
                }
            ), 403

        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not (groq_key or openai_key):
            return jsonify({
                "success": False,
                "error": "Chat service is offline. Configure GROQ_API_KEY or OPENAI_API_KEY to enable chat.",
            }), 503

        ctx = format_guru_context(row["full_name"], profile, vedic, blueprint)
        personalization = extras.get("personalization") if isinstance(extras, dict) else {}
        first_name = ""
        if isinstance(personalization, dict):
            first_name = str(personalization.get("first_name") or "").strip()
        if not first_name:
            first_name = (row["full_name"] or "Friend").split()[0]

        system = (
            "You are a premium personal cosmic guide (warm, precise, cinematic language—never generic horoscope spam). "
            f"Address the querent as {first_name} occasionally (not every sentence). "
            "Ground every claim in the CONTEXT: Big Three, houses, dasha/dosha flags, blueprint, palm layer if present. "
            "Offer specific reflections, 2–3 actionable micro-rituals, and one clarifying question to deepen the loop. "
            "If asked for exact dates of life events, give symbolic timing windows and decision cues—avoid false certainty. "
            "If the question is outside astrology/palmistry/cosmic self-development, decline kindly in character. "
            "Keep responses tight: 120–220 words unless the user asks for depth."
        )
        user_blob = f"CONTEXT:\n{ctx}\n\nUSER QUESTION:\n{message}"
        ai_reply = openai_guru_reply(system, user_blob)
        if ai_reply is None:
            return jsonify({
                "success": False,
                "error": "Chat service failed to generate response. Check Render logs for details.",
            }), 503

        return jsonify({"success": True, "reply": ai_reply, "source": "ai"})

    @app.route("/api/locations", methods=["GET"])
    def api_locations():
        geonames_user = os.environ.get("GEONAMES_USERNAME", "").strip()
        if not geonames_user:
            return jsonify({"success": False, "error": "Disabled"}), 404

        query = request.args.get("query", "").strip()
        if len(query) < 2:
            return jsonify({"success": False, "locations": []}), 400

        try:
            params = {
                "name_startsWith": query,
                "featureClass": "P",
                "maxRows": 10,
                "username": geonames_user,
            }
            url = "http://api.geonames.org/searchJSON"
            req = urllib.request.Request(
                f"{url}?{'&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in params.items()])}",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))

            locations = []
            if "geonames" in data:
                for place in data["geonames"][:10]:
                    locations.append({
                        "name": f"{place.get('name', '')}, {place.get('adminName1', '')}, {place.get('countryName', '')}",
                        "lat": place.get("lat"),
                        "lng": place.get("lng"),
                    })

            return jsonify({"success": True, "locations": locations})
        except Exception:
            return jsonify({"success": False, "locations": []})

    @app.route("/api/horoscope", methods=["GET"])
    def api_horoscope():
        sign = request.args.get("sign", "").strip().capitalize()
        valid_signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
        if sign not in valid_signs:
            return jsonify({"success": False, "error": "Invalid zodiac sign"}), 400

        horoscope = get_horoscope_for_sign(sign)
        return jsonify({"success": True, "sign": sign, "horoscope": horoscope})

    @app.route("/api/kundli-chart", methods=["POST"])
    def api_kundli_chart():
        payload = request.get_json(force=True, silent=True) or {}
        birth_date = payload.get("birth_date", "").strip()
        birth_time = payload.get("birth_time", "").strip()
        birth_place = payload.get("birth_place", "").strip()

        if not birth_date or not birth_time:
            return jsonify({"success": False, "error": "birth_date and birth_time required"}), 400

        try:
            result = generate_kundli_chart_from_birth(birth_date, birth_time)
            if result.get("success"):
                return jsonify(result)
            return jsonify(result), 400
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"success": False, "error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"success": False, "error": "Internal server error"}), 500

    return app
