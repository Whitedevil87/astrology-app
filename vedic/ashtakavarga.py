"""
vedic/ashtakavarga.py
─────────────────────
Complete Ashtakavarga system for Vedic astrology.

Implements:
  • Bhinnashtakavarga  — each planet's 8-source benefic-point grid
  • Sarvashtakavarga   — total benefic points per sign (all planets summed)
  • Kaksha division    — 8 sub-divisions (3°45' each) per sign
  • Strength scoring   — sign & house-wise benefic tally
  • Interpretation     — transit quality, dasha strength, life-area scoring

Reference: Brihat Parashara Hora Shastra — Ashtakavarga chapters.

Public API
──────────
    compute_ashtakavarga(planet_houses)          → dict
    sarvashtakavarga(bhinna)                     → dict[sign→int]
    ashtakavarga_report(planet_houses, lagna)    → dict
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Any

ZODIAC = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# ── Ashtakavarga Tables (BPHS standard) ──────────────────────────────
# For each planet, benefic houses counted from EACH of 8 reference points
# (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Lagna).
# Table format: planet → [benefic_house_offsets_from_reference]
# Reference order: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Lagna

_ASHTAK_TABLES: Dict[str, List[List[int]]] = {
    "Sun": [
        [1, 2, 4, 7, 8, 9, 10, 11],        # from Sun
        [3, 6, 10, 11],                      # from Moon
        [1, 2, 4, 7, 8, 9, 10, 11],         # from Mars
        [3, 5, 6, 9, 10, 11, 12],           # from Mercury
        [5, 6, 9, 11],                       # from Jupiter
        [6, 7, 12],                          # from Venus
        [1, 2, 4, 7, 8, 9, 10, 11],         # from Saturn
        [3, 4, 6, 10, 11, 12],              # from Lagna
    ],
    "Moon": [
        [3, 6, 7, 8, 10, 11],               # from Sun
        [1, 3, 6, 7, 10, 11],              # from Moon
        [2, 3, 5, 6, 9, 10, 11],           # from Mars
        [1, 3, 4, 5, 7, 8, 10, 11],        # from Mercury
        [1, 4, 7, 8, 10, 11, 12],          # from Jupiter
        [3, 4, 5, 7, 9, 10, 11],           # from Venus
        [3, 5, 6, 11],                      # from Saturn
        [3, 6, 10, 11],                     # from Lagna
    ],
    "Mars": [
        [3, 5, 6, 10, 11],                  # from Sun
        [3, 6, 11],                         # from Moon
        [1, 2, 4, 7, 8, 10, 11],           # from Mars
        [3, 5, 6, 11],                      # from Mercury
        [6, 10, 11, 12],                    # from Jupiter
        [6, 8, 11, 12],                     # from Venus
        [1, 4, 7, 8, 9, 10, 11],           # from Saturn
        [1, 3, 6, 10, 11],                  # from Lagna
    ],
    "Mercury": [
        [5, 6, 9, 11, 12],                  # from Sun
        [2, 4, 6, 8, 10, 11],              # from Moon
        [1, 2, 4, 7, 8, 9, 10, 11],        # from Mars
        [1, 3, 5, 6, 9, 10, 11, 12],       # from Mercury
        [6, 8, 11, 12],                     # from Jupiter
        [1, 2, 3, 4, 5, 8, 9, 11],         # from Venus
        [1, 2, 4, 7, 8, 9, 10, 11],        # from Saturn
        [1, 2, 4, 6, 8, 10, 11],           # from Lagna
    ],
    "Jupiter": [
        [1, 2, 3, 4, 7, 8, 9, 10, 11],     # from Sun
        [2, 5, 7, 9, 11],                   # from Moon
        [1, 2, 4, 7, 8, 10, 11],           # from Mars
        [1, 2, 4, 5, 6, 9, 10, 11],        # from Mercury
        [1, 2, 3, 4, 7, 8, 10, 11],        # from Jupiter
        [2, 5, 6, 9, 10, 11],              # from Venus
        [3, 5, 6, 12],                      # from Saturn
        [1, 2, 4, 5, 6, 7, 9, 10, 11],     # from Lagna
    ],
    "Venus": [
        [8, 11, 12],                        # from Sun
        [1, 2, 3, 4, 5, 8, 9, 11, 12],     # from Moon
        [3, 4, 6, 9, 11, 12],              # from Mars
        [3, 5, 6, 9, 11],                   # from Mercury
        [5, 8, 9, 10, 11],                  # from Jupiter
        [1, 2, 3, 4, 5, 8, 9, 10, 11],     # from Venus
        [3, 4, 5, 8, 9, 10, 11],           # from Saturn
        [1, 2, 3, 4, 5, 8, 9, 11],         # from Lagna
    ],
    "Saturn": [
        [1, 2, 4, 7, 8, 10, 11],           # from Sun
        [3, 6, 11],                         # from Moon
        [3, 5, 6, 10, 11, 12],             # from Mars
        [6, 9, 11, 12],                     # from Mercury
        [5, 6, 11, 12],                     # from Jupiter
        [6, 11, 12],                        # from Venus
        [3, 5, 6, 11],                      # from Saturn
        [1, 3, 4, 6, 10, 11],              # from Lagna
    ],
}

# Reference points order (index 0-7 in table above)
_REF_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]

# ── Core calculation ─────────────────────────────────────────────────

def _sign_index(sign: str) -> int:
    return ZODIAC.index(sign) if sign in ZODIAC else 0


def _house_from_offset(base_sign: int, offset: int) -> int:
    """1-based house at offset steps from base (offset=1 means same sign)."""
    return (base_sign + offset - 1) % 12


def compute_bhinna_ashtakavarga(
    planet_signs: Dict[str, str],
    lagna_sign: str,
) -> Dict[str, List[int]]:
    """
    Compute Bhinnashtakavarga for all 7 classical planets.

    Parameters
    ----------
    planet_signs : dict of planet → sign name (sidereal)
    lagna_sign   : Ascendant sign

    Returns
    -------
    dict of planet_name → list[12] of benefic points per sign (0–8)
    """
    result: Dict[str, List[int]] = {}

    for planet, table in _ASHTAK_TABLES.items():
        points = [0] * 12  # one slot per zodiac sign

        for ref_idx, ref_name in enumerate(_REF_ORDER):
            # Determine reference sign index
            if ref_name == "Lagna":
                ref_sign_idx = _sign_index(lagna_sign)
            else:
                ref_sign = planet_signs.get(ref_name)
                if ref_sign is None:
                    continue
                ref_sign_idx = _sign_index(ref_sign)

            # Mark benefic signs for this reference point
            benefic_offsets = table[ref_idx]
            for offset in benefic_offsets:
                benefic_sign = _house_from_offset(ref_sign_idx, offset)
                points[benefic_sign] += 1

        result[planet] = points

    return result


def compute_sarvashtakavarga(
    bhinna: Dict[str, List[int]],
) -> List[int]:
    """
    Sarvashtakavarga: sum of all 7 planet bhinnashtakavarga per sign.
    Returns list[12] of total benefic points per sign (0–56).
    """
    total = [0] * 12
    for planet_points in bhinna.values():
        for i, pts in enumerate(planet_points):
            total[i] += pts
    return total


def ashtakavarga_report(
    planet_signs: Dict[str, str],
    lagna_sign: str,
    moon_sign: str,
) -> Dict[str, Any]:
    """
    Full Ashtakavarga analysis with interpretation.

    Returns
    -------
    {
      "bhinna": {planet: [12 scores]},
      "sarva":  [12 scores],
      "sign_analysis": {sign: {points, strength, transit_quality}},
      "life_areas": {house_num: {score, prediction}},
      "strongest_signs": [...],
      "weakest_signs": [...],
      "total_score": int,
      "interpretation": str,
    }
    """
    bhinna = compute_bhinna_ashtakavarga(planet_signs, lagna_sign)
    sarva  = compute_sarvashtakavarga(bhinna)

    lagna_idx = _sign_index(lagna_sign)

    # Per-sign analysis
    sign_analysis: Dict[str, Any] = {}
    for i, sign in enumerate(ZODIAC):
        pts = sarva[i]
        house_num = (i - lagna_idx) % 12 + 1

        if pts >= 30:
            strength = "Strong"
            transit_q = "Excellent — highly favorable for activities related to this house"
        elif pts >= 25:
            strength = "Good"
            transit_q = "Good — generally positive results when planets transit here"
        elif pts >= 20:
            strength = "Average"
            transit_q = "Mixed — moderate results, depends on planet and dasha"
        else:
            strength = "Weak"
            transit_q = "Challenging — extra care needed when planets transit here"

        sign_analysis[sign] = {
            "points": pts,
            "house": house_num,
            "strength": strength,
            "transit_quality": transit_q,
        }

    # Life area scores (houses 1-12)
    life_areas = _compute_life_areas(sarva, lagna_idx)

    # Rankings
    sorted_signs = sorted(ZODIAC, key=lambda s: sarva[_sign_index(s)], reverse=True)
    strongest = [(s, sarva[_sign_index(s)]) for s in sorted_signs[:3]]
    weakest   = [(s, sarva[_sign_index(s)]) for s in sorted_signs[-3:]]

    total_score = sum(sarva)
    avg = total_score / 12

    # Per-planet benefic totals
    planet_totals = {p: sum(pts) for p, pts in bhinna.items()}

    interpretation = _interpret_sarva(avg, strongest, weakest, moon_sign, lagna_sign)

    # Jupiter's Bhinnashtakavarga for transit quality
    jupiter_bhinna = bhinna.get("Jupiter", [0]*12)
    saturn_bhinna  = bhinna.get("Saturn", [0]*12)

    return {
        "bhinna": bhinna,
        "sarva": sarva,
        "sign_analysis": sign_analysis,
        "life_areas": life_areas,
        "strongest_signs": strongest,
        "weakest_signs": weakest,
        "total_score": total_score,
        "average_per_sign": round(avg, 1),
        "planet_totals": planet_totals,
        "jupiter_transit_scores": {ZODIAC[i]: jupiter_bhinna[i] for i in range(12)},
        "saturn_transit_scores":  {ZODIAC[i]: saturn_bhinna[i]  for i in range(12)},
        "interpretation": interpretation,
    }


# ── Life Area Scoring ────────────────────────────────────────────────

_HOUSE_THEMES = {
    1:  ("Self & Health",       "personality, vitality, general wellbeing"),
    2:  ("Wealth & Family",     "accumulated wealth, speech, early family"),
    3:  ("Courage & Siblings",  "younger siblings, short travel, communication skills"),
    4:  ("Home & Happiness",    "mother, property, vehicles, inner peace"),
    5:  ("Children & Intellect","children, education, past-life merit, speculation"),
    6:  ("Enemies & Health",    "debts, diseases, service, competition"),
    7:  ("Marriage & Business", "spouse quality, partnerships, foreign travel"),
    8:  ("Longevity & Secrets", "lifespan, hidden income, research, in-laws"),
    9:  ("Luck & Dharma",       "fortune, father, religion, higher learning"),
    10: ("Career & Status",     "profession, authority, government, reputation"),
    11: ("Income & Gains",      "profits, elder siblings, fulfillment of desires"),
    12: ("Losses & Liberation", "foreign lands, spirituality, hospital expenses"),
}


def _compute_life_areas(sarva: List[int], lagna_idx: int) -> Dict[int, Any]:
    areas: Dict[int, Any] = {}
    for house in range(1, 13):
        sign_idx = (lagna_idx + house - 1) % 12
        pts = sarva[sign_idx]
        name, desc = _HOUSE_THEMES[house]

        if pts >= 30:
            pred = f"Strong house ({pts} pts) — this life area brings natural success and support."
        elif pts >= 25:
            pred = f"Good house ({pts} pts) — generally positive outcomes in {desc}."
        elif pts >= 20:
            pred = f"Average house ({pts} pts) — mixed results; effort brings moderate gains."
        else:
            pred = f"Challenging house ({pts} pts) — difficulties in {desc}; remedies help."

        areas[house] = {
            "name": name,
            "description": desc,
            "points": pts,
            "prediction": pred,
        }
    return areas


# ── Interpretation text ──────────────────────────────────────────────

def _interpret_sarva(
    avg: float,
    strongest: List[Tuple],
    weakest: List[Tuple],
    moon_sign: str,
    lagna_sign: str,
) -> str:
    lines: List[str] = []

    if avg >= 28:
        lines.append(
            "Your Sarvashtakavarga average is exceptionally high — the chart carries strong cosmic support. "
            "Most life areas are well-resourced and planetary transits will generally bring positive results."
        )
    elif avg >= 25:
        lines.append(
            "Your Sarvashtakavarga average is above average — the chart is well-balanced with good overall support. "
            "You have natural resilience and most major transits will be manageable."
        )
    elif avg >= 22:
        lines.append(
            "Your Sarvashtakavarga average is moderate — the chart has a mix of strong and weak areas. "
            "Focus on leveraging your strong houses and be mindful during transits through weak ones."
        )
    else:
        lines.append(
            "Your Sarvashtakavarga average suggests a more challenging configuration overall. "
            "This points to a life of effort-based achievement — rewards come through persistence. "
            "Remedies and mindful timing of major decisions are especially valuable."
        )

    if strongest:
        s_names = ", ".join(f"{s[0]} ({s[1]} pts)" for s in strongest[:2])
        lines.append(f"Strongest signs: {s_names} — planet transits here bring peak opportunity.")

    if weakest:
        w_names = ", ".join(f"{s[0]} ({s[1]} pts)" for s in weakest[:2])
        lines.append(f"Weaker signs: {w_names} — be cautious during Saturn/Rahu transits here.")

    return " ".join(lines)


# ── Kaksha (sub-division) analysis ──────────────────────────────────

_KAKSHA_LORDS = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon", "Lagna"]


def kaksha_lord(longitude_in_sign: float) -> str:
    """
    Return the Kaksha (8th sub-division) lord for a planet's
    position within its sign (0–30°).
    Each kaksha = 3°45' = 3.75°
    """
    kaksha_num = int(longitude_in_sign / 3.75) % 8
    return _KAKSHA_LORDS[kaksha_num]


def transit_kaksha_quality(
    transiting_planet: str,
    natal_sign_points: int,
    kaksha_planet: str,
    bhinna_planet_points: Dict[str, List[int]],
    transit_sign: str,
) -> str:
    """
    Assess quality of a transit using Kaksha Pravesh method.
    A transit is favorable if the Kaksha lord has a benefic point
    in the Bhinnashtakavarga of the transiting planet.
    """
    sign_idx = ZODIAC.index(transit_sign) if transit_sign in ZODIAC else 0
    planet_bhinna = bhinna_planet_points.get(transiting_planet, [0]*12)
    planet_pts = planet_bhinna[sign_idx]

    kaksha_bhinna = bhinna_planet_points.get(kaksha_planet, [0]*12)
    kaksha_pts = kaksha_bhinna[sign_idx]

    if planet_pts >= 4 and kaksha_pts >= 4:
        return "Excellent — double benefic confirmation"
    elif planet_pts >= 4:
        return "Good — favorable transit"
    elif planet_pts >= 3:
        return "Moderate — mixed results"
    else:
        return "Challenging — unfavorable transit, consider timing"
