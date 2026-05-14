"""
Layer 7 — Transit & Gochara Engine.

Computes live planetary positions and compares them against the natal chart
to produce transit analysis including:
    - Sade Sati status (Saturn's 7.5-year transit over Moon)
    - Ashtama Shani (Saturn in 8th from natal Moon)
    - Jupiter transit analysis
    - Gochara (transit) benefic/malefic assessment per house
    - Current Dasha + Transit confluence for prediction confidence

Reference: Phaladeepika, BPHS transit chapters, Brihat Jataka.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from astrology_math import julian_day, _norm360

logger = logging.getLogger(__name__)

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

_SIGN_IDX = {s: i for i, s in enumerate(ZODIAC_ORDER)}

# Average transit duration per planet (approximate)
_TRANSIT_DURATIONS = {
    "Sun": "~1 month per sign",
    "Moon": "~2.25 days per sign",
    "Mars": "~45 days per sign",
    "Mercury": "~25 days per sign",
    "Jupiter": "~13 months per sign",
    "Venus": "~25 days per sign",
    "Saturn": "~2.5 years per sign",
    "Rahu": "~18 months per sign (retrograde)",
    "Ketu": "~18 months per sign (retrograde)",
}

# Gochara: Houses where transiting planets give good/bad results
# From Moon sign (Vedic transit reference point)
_GOCHARA_GOOD_HOUSES = {
    "Sun": {3, 6, 10, 11},
    "Moon": {1, 3, 6, 7, 10, 11},
    "Mars": {3, 6, 11},
    "Mercury": {2, 4, 6, 8, 10, 11},
    "Jupiter": {2, 5, 7, 9, 11},
    "Venus": {1, 2, 3, 4, 5, 8, 9, 11, 12},
    "Saturn": {3, 6, 11},
    "Rahu": {3, 6, 10, 11},
    "Ketu": {3, 6, 11},
}


def _sign_distance(from_sign: str, to_sign: str) -> int:
    """
    House distance from from_sign to to_sign (1-based).
    If same sign → 1, next sign → 2, etc.
    """
    f = _SIGN_IDX.get(from_sign, 0)
    t = _SIGN_IDX.get(to_sign, 0)
    return ((t - f) % 12) + 1


def _sign_from_longitude(lon: float) -> str:
    return ZODIAC_ORDER[int(_norm360(lon) // 30) % 12]


# ====================================================================
# CURRENT PLANET POSITIONS
# ====================================================================

def current_planet_positions(
    jd_now: Optional[float] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Get current sidereal positions of all 9 Vedic planets.

    Returns dict[planet] = {"longitude": float, "sign": str, "degree": float}
    """
    if jd_now is None:
        now = datetime.now(timezone.utc)
        jd_now = julian_day(now)

    # Try precision engine first
    try:
        from vedic.swisseph_engine import get_all_planet_longitudes, sign_from_longitude
        longitudes = get_all_planet_longitudes(jd_now, sidereal=True)
        result = {}
        for planet, lon in longitudes.items():
            result[planet] = {
                "longitude": round(lon, 4),
                "sign": sign_from_longitude(lon),
                "degree_in_sign": round(lon % 30, 2),
            }
        return result
    except Exception as exc:
        logger.warning("Transit position calculation error: %s — using fallback", exc)

    # Fallback: use basic math engine
    from vedic_engine import _get_planet_lon, _sign_from_longitude
    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
    result = {}
    for planet in planets:
        try:
            lon = _get_planet_lon(jd_now, planet)
            result[planet] = {
                "longitude": round(lon, 4),
                "sign": _sign_from_longitude(lon),
                "degree_in_sign": round(lon % 30, 2),
            }
        except Exception:
            pass
    return result


# ====================================================================
# SADE SATI — Saturn's 7.5-Year Transit
# ====================================================================

def sade_sati_status(natal_moon_sign: str, current_saturn_sign: str) -> Dict[str, Any]:
    """
    Check Sade Sati status.

    Sade Sati occurs when Saturn transits:
        - 12th from Moon sign (rising phase — 2.5 years)
        - The Moon sign itself (peak phase — 2.5 years)
        - 2nd from Moon sign (setting phase — 2.5 years)

    Returns dict with status, phase, and description.
    """
    distance = _sign_distance(natal_moon_sign, current_saturn_sign)

    if distance == 12:  # 12th from Moon
        return {
            "active": True,
            "phase": "rising",
            "phase_name": "First Phase (12th from Moon)",
            "severity": "moderate",
            "description": (
                f"Saturn transiting {current_saturn_sign} (12th from your Moon in {natal_moon_sign}) — "
                "Sade Sati Rising Phase: expenses may increase, sleep disturbances possible. "
                "Focus on savings, spiritual practice, and patience. This is the beginning of "
                "Saturn's karmic lessons."
            ),
        }
    elif distance == 1:  # Same sign as Moon
        return {
            "active": True,
            "phase": "peak",
            "phase_name": "Peak Phase (Over Moon Sign)",
            "severity": "strong",
            "description": (
                f"Saturn transiting {current_saturn_sign} (directly over your Moon in {natal_moon_sign}) — "
                "Sade Sati Peak Phase: the most intense period. Emotional pressure, career changes, "
                "and relationship tests. This is Saturn demanding authenticity — strip away what's "
                "not truly you. Hard work and discipline are your best remedies."
            ),
        }
    elif distance == 2:  # 2nd from Moon
        return {
            "active": True,
            "phase": "setting",
            "phase_name": "Final Phase (2nd from Moon)",
            "severity": "moderate",
            "description": (
                f"Saturn transiting {current_saturn_sign} (2nd from your Moon in {natal_moon_sign}) — "
                "Sade Sati Setting Phase: financial pressures easing, family matters settling. "
                "The lessons learned are solidifying. Stay disciplined — relief is approaching."
            ),
        }
    else:
        return {
            "active": False,
            "phase": "none",
            "phase_name": "Not Active",
            "severity": "none",
            "description": (
                f"Saturn in {current_saturn_sign} — Sade Sati is NOT active for your Moon sign "
                f"({natal_moon_sign}). Saturn's karmic lessons are focused elsewhere."
            ),
        }


# ====================================================================
# ASHTAMA SHANI — Saturn in 8th from Moon
# ====================================================================

def ashtama_shani_status(natal_moon_sign: str, current_saturn_sign: str) -> Dict[str, Any]:
    """
    Ashtama Shani: Saturn transiting the 8th house from natal Moon.
    A difficult transit bringing sudden changes, obstacles, and health concerns.
    """
    distance = _sign_distance(natal_moon_sign, current_saturn_sign)

    if distance == 8:
        return {
            "active": True,
            "description": (
                f"Saturn in {current_saturn_sign} (8th from your Moon in {natal_moon_sign}) — "
                "Ashtama Shani active: period of transformation and hidden challenges. "
                "Health needs attention, avoid risky ventures. Focus on inner strength "
                "and preventive care. This transit ultimately builds resilience."
            ),
        }
    return {
        "active": False,
        "description": "Ashtama Shani is not active.",
    }


# ====================================================================
# JUPITER TRANSIT ANALYSIS
# ====================================================================

def jupiter_transit_analysis(
    natal_moon_sign: str,
    current_jupiter_sign: str,
    natal_lagna_sign: str,
) -> Dict[str, Any]:
    """
    Jupiter transit assessment from Moon and Lagna.
    Jupiter is the greatest benefic — its transit through favorable houses
    brings growth, wisdom, and prosperity.
    """
    from_moon = _sign_distance(natal_moon_sign, current_jupiter_sign)
    from_lagna = _sign_distance(natal_lagna_sign, current_jupiter_sign)

    good_from_moon = from_moon in _GOCHARA_GOOD_HOUSES.get("Jupiter", set())
    good_from_lagna = from_lagna in {1, 2, 5, 7, 9, 11}

    if good_from_moon and good_from_lagna:
        quality = "excellent"
        desc = (
            f"Jupiter transiting {current_jupiter_sign} — {from_moon}th from Moon, "
            f"{from_lagna}th from Lagna. Doubly auspicious: expect expansion in career, "
            "knowledge, relationships, and spiritual growth. Best time for important decisions."
        )
    elif good_from_moon:
        quality = "favorable"
        desc = (
            f"Jupiter transiting {current_jupiter_sign} — favorable from Moon ({from_moon}th). "
            "Emotional wisdom increases, good for learning and relationships. "
            "Some challenges from Lagna perspective — balance optimism with caution."
        )
    elif good_from_lagna:
        quality = "mixed"
        desc = (
            f"Jupiter transiting {current_jupiter_sign} — favorable from Lagna ({from_lagna}th) "
            f"but challenging from Moon ({from_moon}th). External opportunities present "
            "but inner peace requires effort. Focus on practical growth."
        )
    else:
        quality = "challenging"
        desc = (
            f"Jupiter transiting {current_jupiter_sign} — {from_moon}th from Moon, "
            f"{from_lagna}th from Lagna. Jupiter's blessings are muted this period. "
            "Focus on consolidation rather than expansion. Inner growth over outer pursuit."
        )

    return {
        "current_sign": current_jupiter_sign,
        "house_from_moon": from_moon,
        "house_from_lagna": from_lagna,
        "quality": quality,
        "description": desc,
    }


# ====================================================================
# FULL GOCHARA REPORT
# ====================================================================

def gochara_report(
    natal_moon_sign: str,
    natal_lagna_sign: str,
    current_positions: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Complete transit (Gochara) report comparing current planet positions
    against the natal Moon sign.

    Returns structured analysis for all planets + special transits.
    """
    if current_positions is None:
        current_positions = current_planet_positions()

    planet_transits: Dict[str, Dict[str, Any]] = {}
    favorable_count = 0
    challenging_count = 0

    for planet in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        pos = current_positions.get(planet, {})
        current_sign = pos.get("sign", "Aries")
        house_from_moon = _sign_distance(natal_moon_sign, current_sign)

        good_houses = _GOCHARA_GOOD_HOUSES.get(planet, set())
        is_favorable = house_from_moon in good_houses

        if is_favorable:
            favorable_count += 1
        else:
            challenging_count += 1

        planet_transits[planet] = {
            "current_sign": current_sign,
            "degree": pos.get("degree_in_sign", 0),
            "house_from_moon": house_from_moon,
            "is_favorable": is_favorable,
            "transit_duration": _TRANSIT_DURATIONS.get(planet, "varies"),
        }

    # Special transit checks
    saturn_sign = current_positions.get("Saturn", {}).get("sign", "Aries")
    jupiter_sign = current_positions.get("Jupiter", {}).get("sign", "Aries")

    sade_sati = sade_sati_status(natal_moon_sign, saturn_sign)
    ashtama = ashtama_shani_status(natal_moon_sign, saturn_sign)
    jupiter = jupiter_transit_analysis(natal_moon_sign, jupiter_sign, natal_lagna_sign)

    # Overall transit score
    total = favorable_count + challenging_count
    score = round((favorable_count / total * 100) if total else 50)

    if score >= 65:
        overall = "favorable"
        overall_desc = "Majority of transits are supportive — a good period for initiative and growth."
    elif score >= 45:
        overall = "mixed"
        overall_desc = "Transits are mixed — balance bold moves with caution and patience."
    else:
        overall = "challenging"
        overall_desc = "Current transits demand patience and inner work — avoid major risks."

    return {
        "planet_transits": planet_transits,
        "sade_sati": sade_sati,
        "ashtama_shani": ashtama,
        "jupiter_transit": jupiter,
        "favorable_count": favorable_count,
        "challenging_count": challenging_count,
        "transit_score": score,
        "overall_quality": overall,
        "overall_description": overall_desc,
    }


# ====================================================================
# DASHA + TRANSIT CONFLUENCE (Prediction Confidence)
# ====================================================================

def prediction_confidence(
    mahadasha_lord: str,
    antardasha_lord: str,
    transit_score: int,
    has_sade_sati: bool,
    jupiter_quality: str,
) -> Dict[str, Any]:
    """
    Layer 8 helper: Compute prediction confidence by overlapping
    Dasha timing with current transits.

    The higher the confluence between favorable dashas and favorable
    transits, the more confident the prediction.
    """
    # Base confidence from transit score
    confidence = transit_score

    # Dasha lord quality adjustment
    benefic_lords = {"Jupiter", "Venus", "Moon", "Mercury"}
    malefic_lords = {"Saturn", "Mars", "Rahu", "Ketu", "Sun"}

    if mahadasha_lord in benefic_lords:
        confidence += 8
    elif mahadasha_lord in malefic_lords:
        confidence -= 5

    if antardasha_lord in benefic_lords:
        confidence += 5
    elif antardasha_lord in malefic_lords:
        confidence -= 3

    # Special transit adjustments
    if has_sade_sati:
        confidence -= 12

    if jupiter_quality == "excellent":
        confidence += 10
    elif jupiter_quality == "favorable":
        confidence += 5
    elif jupiter_quality == "challenging":
        confidence -= 5

    confidence = max(10, min(95, confidence))

    if confidence >= 70:
        outlook = "strongly_positive"
        desc = "Dasha and transits align well — high confidence in positive outcomes."
    elif confidence >= 50:
        outlook = "cautiously_positive"
        desc = "Mixed signals — good potential but effort and timing matter."
    elif confidence >= 35:
        outlook = "neutral"
        desc = "Balanced period — neither strongly favorable nor adverse."
    else:
        outlook = "challenging"
        desc = "Current cosmic configuration demands patience and inner work."

    return {
        "score": confidence,
        "outlook": outlook,
        "description": desc,
        "factors": {
            "transit_base": transit_score,
            "mahadasha_lord": mahadasha_lord,
            "antardasha_lord": antardasha_lord,
            "sade_sati_active": has_sade_sati,
            "jupiter_quality": jupiter_quality,
        },
    }
