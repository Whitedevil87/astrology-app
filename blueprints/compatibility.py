"""Compatibility / Synastry blueprint — /api/compatibility."""
import logging
from flask import Blueprint, jsonify, request
from services.analysis_service import (
    zodiac_sign, moon_sign, ascendant_sign,
    compute_hybrid_big_three, harmony_matches, growth_matches
)
from services.auth_service import optional_auth
from geo import photon_search, timeapi_timezone_name
from ai_client import openai_guru_reply
from datetime import datetime

logger = logging.getLogger(__name__)
compat_bp = Blueprint("compatibility", __name__, url_prefix="/api")

# Vedic Guna Milan / Ashtakoot point system (simplified)
_GUNA_ASPECTS = {
    "Varna": 1, "Vashya": 2, "Tara": 3, "Yoni": 4,
    "Graha Maitri": 5, "Gana": 6, "Bhakoot": 7, "Nadi": 8,
}

_ELEMENT_COMPAT = {
    ("Fire", "Fire"): 7, ("Fire", "Air"): 8, ("Fire", "Earth"): 4, ("Fire", "Water"): 3,
    ("Air", "Air"): 7, ("Air", "Earth"): 4, ("Air", "Water"): 5,
    ("Earth", "Earth"): 7, ("Earth", "Water"): 8,
    ("Water", "Water"): 7,
}

_ZODIAC_ELEMENTS = {
    "Aries": "Fire", "Taurus": "Earth", "Gemini": "Air", "Cancer": "Water",
    "Leo": "Fire", "Virgo": "Earth", "Libra": "Air", "Scorpio": "Water",
    "Sagittarius": "Fire", "Capricorn": "Earth", "Aquarius": "Air", "Pisces": "Water",
}


def _element_score(sign1: str, sign2: str) -> int:
    e1, e2 = _ZODIAC_ELEMENTS.get(sign1, "Fire"), _ZODIAC_ELEMENTS.get(sign2, "Fire")
    key = (e1, e2) if (e1, e2) in _ELEMENT_COMPAT else (e2, e1)
    return _ELEMENT_COMPAT.get(key, 5)


def _compute_guna_score(profile1: dict, profile2: dict) -> dict:
    """Simplified Ashtakoot Guna Milan scoring."""
    sun_score = _element_score(profile1["zodiac"], profile2["zodiac"])
    moon_score = _element_score(profile1["moon_sign"], profile2["moon_sign"])
    asc_score = _element_score(profile1["ascendant"], profile2["ascendant"])

    total = sun_score + moon_score + asc_score
    max_possible = 24
    percentage = round((total / max_possible) * 100)

    if percentage >= 75:
        verdict = "Excellent cosmic compatibility — a powerful connection across all layers."
    elif percentage >= 55:
        verdict = "Good compatibility — natural harmony with a few growth edges to navigate."
    elif percentage >= 35:
        verdict = "Moderate compatibility — differences can spark growth if approached with awareness."
    else:
        verdict = "Challenging match — significant differences that require patience and understanding."

    return {
        "sun_harmony": sun_score,
        "moon_harmony": moon_score,
        "ascendant_harmony": asc_score,
        "total_score": total,
        "max_score": max_possible,
        "percentage": percentage,
        "verdict": verdict,
    }


@compat_bp.route("/compatibility", methods=["POST"])
@optional_auth
def api_compatibility():
    payload = request.get_json(force=True, silent=True) or {}

    # Person 1 (the logged-in user or manually entered)
    p1 = payload.get("person1", {})
    p2 = payload.get("person2", {})

    for label, person in [("person1", p1), ("person2", p2)]:
        if not person.get("birth_date") or not person.get("birth_time"):
            return jsonify({"success": False, "error": f"{label}: birth_date and birth_time required"}), 400

    profiles = {}
    for label, person in [("person1", p1), ("person2", p2)]:
        try:
            bd = datetime.strptime(person["birth_date"], "%Y-%m-%d").date()
            bt = datetime.strptime(person["birth_time"], "%H:%M").time()
        except ValueError:
            return jsonify({"success": False, "error": f"{label}: invalid date/time format"}), 400

        birth_place = person.get("birth_place", "Unknown")
        lat = person.get("lat")
        lon = person.get("lon")
        tz = person.get("tz")

        # Try geocoding if no coords
        if lat is None or lon is None:
            places = photon_search(birth_place, limit=1)
            if places:
                lat, lon = places[0]["lat"], places[0]["lon"]

        if tz is None and lat is not None and lon is not None:
            tz = timeapi_timezone_name(lat, lon)

        profile = None
        if lat is not None and lon is not None and tz:
            try:
                profile, _ = compute_hybrid_big_three(bd, bt, birth_place, lat, lon, tz)
            except Exception:
                pass

        if profile is None:
            profile = {
                "zodiac": zodiac_sign(bd),
                "moon_sign": moon_sign(bd),
                "ascendant": ascendant_sign(bt, birth_place),
            }

        profiles[label] = {**profile, "name": person.get("name", label), "birth_date": person["birth_date"]}

    # Compute scores
    guna = _compute_guna_score(profiles["person1"], profiles["person2"])

    # Optionally generate AI analysis
    ai_analysis = None
    try:
        system = (
            "You are a Vedic astrology compatibility expert. Analyze the compatibility between two people "
            "based on their Sun, Moon, and Ascendant signs. Be specific, insightful, and balanced. "
            "Mention both strengths and challenges. Use plain English. Keep it under 200 words."
        )
        user_msg = (
            f"Person 1 ({profiles['person1']['name']}): Sun={profiles['person1']['zodiac']}, "
            f"Moon={profiles['person1']['moon_sign']}, Asc={profiles['person1']['ascendant']}\n"
            f"Person 2 ({profiles['person2']['name']}): Sun={profiles['person2']['zodiac']}, "
            f"Moon={profiles['person2']['moon_sign']}, Asc={profiles['person2']['ascendant']}\n"
            f"Guna score: {guna['percentage']}%\n"
            "Provide a detailed compatibility reading."
        )
        ai_analysis = openai_guru_reply(system, user_msg)
    except Exception as e:
        logger.warning(f"AI compatibility analysis failed: {e}")

    return jsonify({
        "success": True,
        "person1": profiles["person1"],
        "person2": profiles["person2"],
        "guna_score": guna,
        "ai_analysis": ai_analysis,
        "best_matches_p1": harmony_matches(profiles["person1"]["zodiac"]),
        "best_matches_p2": harmony_matches(profiles["person2"]["zodiac"]),
    })
