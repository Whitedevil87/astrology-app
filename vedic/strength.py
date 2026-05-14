"""
Layer 5 — Planetary Strength: Shadbala & Ashtakavarga.

Shadbala (six-fold strength) components:
    1. Sthana Bala  — Positional strength (exaltation, own sign, etc.)
    2. Dig Bala     — Directional strength (planet in its strong direction)
    3. Kala Bala    — Temporal strength (day/night, hora, month lords)
    4. Cheshta Bala — Motional strength (retrograde/direct/stationary)
    5. Naisargika Bala — Natural strength (fixed hierarchy)
    6. Drik Bala    — Aspectual strength (benefic/malefic aspects)

Ashtakavarga:
    Benefic points (bindus) per planet per house from 8 sources
    (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Lagna).

Reference: BPHS, Jataka Parijata, Uttara Kalamrita.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# ── Sign properties ─────────────────────────────────────────────────

_SIGN_IDX = {s: i for i, s in enumerate(ZODIAC_ORDER)}

# Planet rulerships (traditional Vedic — no outer planets)
SIGN_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

# Exaltation signs and exact degrees
EXALTATION = {
    "Sun": ("Aries", 10), "Moon": ("Taurus", 3), "Mars": ("Capricorn", 28),
    "Mercury": ("Virgo", 15), "Jupiter": ("Cancer", 5), "Venus": ("Pisces", 27),
    "Saturn": ("Libra", 20), "Rahu": ("Taurus", 20), "Ketu": ("Scorpio", 20),
}

# Debilitation = 180° from exaltation
DEBILITATION = {
    "Sun": "Libra", "Moon": "Scorpio", "Mars": "Cancer",
    "Mercury": "Pisces", "Jupiter": "Capricorn", "Venus": "Virgo",
    "Saturn": "Aries", "Rahu": "Scorpio", "Ketu": "Taurus",
}

# Moola Trikona signs and degree ranges
MOOLA_TRIKONA = {
    "Sun": ("Leo", 0, 20), "Moon": ("Taurus", 3, 30), "Mars": ("Aries", 0, 12),
    "Mercury": ("Virgo", 16, 20), "Jupiter": ("Sagittarius", 0, 10),
    "Venus": ("Libra", 0, 15), "Saturn": ("Aquarius", 0, 20),
}

# Own signs (each planet owns 1–2 signs)
OWN_SIGNS = {
    "Sun": ["Leo"], "Moon": ["Cancer"], "Mars": ["Aries", "Scorpio"],
    "Mercury": ["Gemini", "Virgo"], "Jupiter": ["Sagittarius", "Pisces"],
    "Venus": ["Taurus", "Libra"], "Saturn": ["Capricorn", "Aquarius"],
    "Rahu": ["Aquarius"], "Ketu": ["Scorpio"],
}

# Friendship table (natural)
_FRIENDS = {
    "Sun": {"Moon", "Mars", "Jupiter"},
    "Moon": {"Sun", "Mercury"},
    "Mars": {"Sun", "Moon", "Jupiter"},
    "Mercury": {"Sun", "Venus"},
    "Jupiter": {"Sun", "Moon", "Mars"},
    "Venus": {"Mercury", "Saturn"},
    "Saturn": {"Mercury", "Venus"},
    "Rahu": {"Mercury", "Venus", "Saturn"},
    "Ketu": {"Mars", "Jupiter"},
}

_ENEMIES = {
    "Sun": {"Venus", "Saturn"},
    "Moon": set(),
    "Mars": {"Mercury"},
    "Mercury": {"Moon"},
    "Jupiter": {"Mercury", "Venus"},
    "Venus": {"Sun", "Moon"},
    "Saturn": {"Sun", "Moon", "Mars"},
    "Rahu": {"Sun", "Moon", "Mars"},
    "Ketu": {"Mercury", "Venus"},
}

# Benefic / Malefic classification
NATURAL_BENEFICS = {"Jupiter", "Venus", "Moon", "Mercury"}
NATURAL_MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}


def _sign_index(sign: str) -> int:
    return _SIGN_IDX.get(sign, 0)


# ====================================================================
# 1. STHANA BALA — Positional Strength
# ====================================================================

def sthana_bala(planet: str, sign: str, degree_in_sign: float = 15.0) -> float:
    """
    Positional strength of a planet in a sign.

    Returns strength in shashtiamsas (0–60 scale):
        Exaltation:     60
        Moola Trikona:  45
        Own sign:       30
        Friend's sign:  22.5
        Neutral:        15
        Enemy's sign:   7.5
        Debilitation:   3.75 (0 at exact debil. degree)
    """
    if planet in ("Rahu", "Ketu"):
        # Nodes get simplified scoring
        if EXALTATION.get(planet, ("", 0))[0] == sign:
            return 50.0
        if DEBILITATION.get(planet) == sign:
            return 5.0
        return 25.0

    # Check exaltation
    exalt_sign, exalt_deg = EXALTATION.get(planet, ("", 0))
    if sign == exalt_sign:
        # Uccha Bala: proportional to distance from debilitation point
        debil_sign = DEBILITATION.get(planet, "")
        return 60.0

    # Check debilitation
    if sign == DEBILITATION.get(planet, ""):
        return 3.75

    # Check Moola Trikona
    mt = MOOLA_TRIKONA.get(planet)
    if mt and sign == mt[0] and mt[1] <= degree_in_sign <= mt[2]:
        return 45.0

    # Check own sign
    if sign in OWN_SIGNS.get(planet, []):
        return 30.0

    # Check friendship
    ruler = SIGN_RULERS.get(sign, "")
    if ruler in _FRIENDS.get(planet, set()):
        return 22.5
    if ruler in _ENEMIES.get(planet, set()):
        return 7.5

    # Neutral
    return 15.0


# ====================================================================
# 2. DIG BALA — Directional Strength
# ====================================================================

# Planets are strongest in specific houses (directions)
_DIG_BALA_HOUSE = {
    "Sun": 10, "Mars": 10,          # Zenith (South) — 10th house
    "Jupiter": 1, "Mercury": 1,     # East — 1st house (Lagna)
    "Moon": 4, "Venus": 4,          # Nadir (North) — 4th house
    "Saturn": 7,                     # West — 7th house
}


def dig_bala(planet: str, house: int) -> float:
    """
    Directional strength based on planet's house position.

    Returns 0–60 shashtiamsas.
    Maximum (60) when planet is in its strongest house.
    Minimum (0) when planet is in the opposite house.
    Linear interpolation between.
    """
    best_house = _DIG_BALA_HOUSE.get(planet)
    if best_house is None:
        return 30.0  # Rahu/Ketu — neutral dig bala

    # Distance in houses (0–6 scale, since opposite = 6 houses away)
    diff = abs(house - best_house)
    if diff > 6:
        diff = 12 - diff
    # 0 houses away = 60, 6 houses away = 0
    return 60.0 * (1 - diff / 6.0)


# ====================================================================
# 3. KALA BALA — Temporal Strength (Simplified)
# ====================================================================

def kala_bala(planet: str, is_day_birth: bool) -> float:
    """
    Simplified temporal strength.

    Day births strengthen: Sun, Jupiter, Venus
    Night births strengthen: Moon, Mars, Saturn
    Mercury is always strong (ubhayachari).

    Returns 0–60 shashtiamsas.
    """
    day_strong = {"Sun", "Jupiter", "Venus"}
    night_strong = {"Moon", "Mars", "Saturn"}

    if planet == "Mercury":
        return 45.0  # Always moderately strong

    if planet in day_strong:
        return 50.0 if is_day_birth else 15.0
    if planet in night_strong:
        return 50.0 if not is_day_birth else 15.0

    return 30.0  # Rahu, Ketu


# ====================================================================
# 4. CHESHTA BALA — Motional Strength (Simplified)
# ====================================================================

def cheshta_bala(planet: str, is_retrograde: bool = False) -> float:
    """
    Motional strength — retrograde planets are considered strong (60),
    direct planets get moderate (30), Sun/Moon are always direct (30).
    """
    if planet in ("Sun", "Moon", "Rahu", "Ketu"):
        return 30.0  # Never retrograde
    return 60.0 if is_retrograde else 30.0


# ====================================================================
# 5. NAISARGIKA BALA — Natural Strength (Fixed)
# ====================================================================

# Traditional fixed natural strength values (shashtiamsas)
NAISARGIKA_VALUES = {
    "Sun": 60.0, "Moon": 51.43, "Mars": 17.14, "Mercury": 25.71,
    "Jupiter": 34.29, "Venus": 42.86, "Saturn": 8.57,
    "Rahu": 12.0, "Ketu": 8.0,
}


def naisargika_bala(planet: str) -> float:
    """Natural/inherent strength — fixed values from tradition."""
    return NAISARGIKA_VALUES.get(planet, 15.0)


# ====================================================================
# 6. DRIK BALA — Aspectual Strength (Simplified)
# ====================================================================

def drik_bala(
    planet: str,
    planet_house: int,
    all_planet_houses: Dict[str, int],
) -> float:
    """
    Simplified aspectual strength based on benefic/malefic aspects.
    Benefic aspects increase strength, malefic aspects decrease it.

    Returns -30 to +30 shashtiamsas (centered at 0).
    """
    score = 0.0
    for other_planet, other_house in all_planet_houses.items():
        if other_planet == planet:
            continue
        diff = (other_house - planet_house) % 12
        # Full aspects: 7th house from any planet
        # Special aspects: Jupiter (5,9), Mars (4,8), Saturn (3,10)
        is_aspecting = False
        if diff == 6:  # 7th aspect (all planets)
            is_aspecting = True
        elif other_planet == "Jupiter" and diff in (4, 8):
            is_aspecting = True
        elif other_planet == "Mars" and diff in (3, 7):
            is_aspecting = True
        elif other_planet == "Saturn" and diff in (2, 9):
            is_aspecting = True

        if is_aspecting:
            if other_planet in NATURAL_BENEFICS:
                score += 7.5
            elif other_planet in NATURAL_MALEFICS:
                score -= 7.5

    return max(-30.0, min(30.0, score))


# ====================================================================
# COMBINED SHADBALA
# ====================================================================

def compute_shadbala(
    planet: str,
    sign: str,
    house: int,
    degree_in_sign: float,
    is_day_birth: bool,
    is_retrograde: bool,
    all_planet_houses: Dict[str, int],
) -> Dict[str, float]:
    """
    Compute all 6 components of Shadbala for a planet.

    Returns dict with individual components and total.
    """
    sb = sthana_bala(planet, sign, degree_in_sign)
    db = dig_bala(planet, house)
    kb = kala_bala(planet, is_day_birth)
    cb = cheshta_bala(planet, is_retrograde)
    nb = naisargika_bala(planet)
    drk = drik_bala(planet, house, all_planet_houses)

    total = sb + db + kb + cb + nb + max(0, drk)

    return {
        "sthana_bala": round(sb, 2),
        "dig_bala": round(db, 2),
        "kala_bala": round(kb, 2),
        "cheshta_bala": round(cb, 2),
        "naisargika_bala": round(nb, 2),
        "drik_bala": round(drk, 2),
        "total": round(total, 2),
        "is_strong": total >= 150.0,  # Minimum required Shadbala for strength
    }


def compute_all_shadbala(
    planet_signs: Dict[str, str],
    planet_houses: Dict[str, int],
    planet_degrees: Dict[str, float],
    is_day_birth: bool = True,
    retrograde_planets: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Compute Shadbala for all planets.

    Parameters
    ----------
    planet_signs   : planet → zodiac sign (e.g. {"Sun": "Leo"})
    planet_houses  : planet → house number (1–12)
    planet_degrees : planet → degree within sign (0–30)
    is_day_birth   : True if born between sunrise and sunset
    retrograde_planets : list of retrograde planet names
    """
    retros = set(retrograde_planets or [])
    result: Dict[str, Dict[str, float]] = {}
    for planet in planet_signs:
        result[planet] = compute_shadbala(
            planet=planet,
            sign=planet_signs[planet],
            house=planet_houses.get(planet, 1),
            degree_in_sign=planet_degrees.get(planet, 15.0),
            is_day_birth=is_day_birth,
            is_retrograde=planet in retros,
            all_planet_houses=planet_houses,
        )
    return result


# ====================================================================
# ASHTAKAVARGA
# ====================================================================

# Benefic positions from each planet (traditional tables)
# Format: planet → list of house offsets (from that planet's position)
# where that planet contributes a bindu (benefic point)

_ASHTAKAVARGA_TABLE = {
    "Sun": {
        "Sun": [1, 2, 4, 7, 8, 9, 10, 11],
        "Moon": [3, 6, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [5, 6, 9, 11],
        "Venus": [6, 7, 12],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [3, 4, 6, 10, 11, 12],
    },
    "Moon": {
        "Sun": [3, 6, 7, 8, 10, 11],
        "Moon": [1, 3, 6, 7, 10, 11],
        "Mars": [2, 3, 5, 6, 9, 10, 11],
        "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
        "Jupiter": [1, 4, 7, 8, 10, 11, 12],
        "Venus": [3, 4, 5, 7, 9, 10, 11],
        "Saturn": [3, 5, 6, 11],
        "Lagna": [3, 6, 10, 11],
    },
    "Mars": {
        "Sun": [3, 5, 6, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [3, 5, 6, 11],
        "Jupiter": [6, 10, 11, 12],
        "Venus": [6, 8, 11, 12],
        "Saturn": [1, 4, 7, 8, 9, 10, 11],
        "Lagna": [1, 3, 6, 10, 11],
    },
    "Mercury": {
        "Sun": [5, 6, 9, 11, 12],
        "Moon": [2, 4, 6, 8, 10, 11],
        "Mars": [1, 2, 4, 7, 8, 9, 10, 11],
        "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
        "Jupiter": [6, 8, 11, 12],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
        "Saturn": [1, 2, 4, 7, 8, 9, 10, 11],
        "Lagna": [1, 2, 4, 6, 8, 10, 11],
    },
    "Jupiter": {
        "Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11],
        "Moon": [2, 5, 7, 9, 11],
        "Mars": [1, 2, 4, 7, 8, 10, 11],
        "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
        "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11],
        "Venus": [2, 5, 6, 9, 10, 11],
        "Saturn": [3, 5, 6, 12],
        "Lagna": [1, 2, 4, 5, 6, 7, 9, 10, 11],
    },
    "Venus": {
        "Sun": [8, 11, 12],
        "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
        "Mars": [3, 5, 6, 9, 11, 12],
        "Mercury": [3, 5, 6, 9, 11],
        "Jupiter": [5, 8, 9, 10, 11],
        "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
        "Saturn": [3, 4, 5, 8, 9, 10, 11],
        "Lagna": [1, 2, 3, 4, 5, 8, 9, 11],
    },
    "Saturn": {
        "Sun": [1, 2, 4, 7, 8, 10, 11],
        "Moon": [3, 6, 11],
        "Mars": [3, 5, 6, 10, 11, 12],
        "Mercury": [6, 8, 9, 10, 11, 12],
        "Jupiter": [5, 6, 11, 12],
        "Venus": [6, 11, 12],
        "Saturn": [3, 5, 6, 11],
        "Lagna": [1, 3, 4, 6, 10, 11],
    },
}


def compute_ashtakavarga(
    planet_houses: Dict[str, int],
    lagna_house: int = 1,
) -> Dict[str, Dict[int, int]]:
    """
    Compute Ashtakavarga bindus (benefic points) for each planet in each house.

    Parameters
    ----------
    planet_houses : planet → house number (1–12)
    lagna_house   : Lagna house number (always 1 in whole-sign)

    Returns
    -------
    dict[planet][house_number] = bindu_count (0–8)
    """
    result: Dict[str, Dict[int, int]] = {}

    for target_planet in _ASHTAKAVARGA_TABLE:
        house_bindus: Dict[int, int] = {h: 0 for h in range(1, 13)}

        for source, offsets in _ASHTAKAVARGA_TABLE[target_planet].items():
            if source == "Lagna":
                source_house = lagna_house
            else:
                source_house = planet_houses.get(source, 1)

            for offset in offsets:
                target_house = ((source_house - 1 + offset - 1) % 12) + 1
                house_bindus[target_house] += 1

        result[target_planet] = house_bindus

    return result


def sarvashtakavarga(planet_houses: Dict[str, int], lagna_house: int = 1) -> Dict[int, int]:
    """
    Sarvashtakavarga (SAV): Sum of all planets' bindus per house.

    Returns dict[house_number] = total_bindus (0–56 theoretical max).
    Houses with 28+ are strong; below 25 are weak.
    """
    all_av = compute_ashtakavarga(planet_houses, lagna_house)
    sav: Dict[int, int] = {h: 0 for h in range(1, 13)}
    for planet_av in all_av.values():
        for house, bindus in planet_av.items():
            sav[house] += bindus
    return sav


def planet_strength_summary(
    planet_signs: Dict[str, str],
    planet_houses: Dict[str, int],
    planet_degrees: Dict[str, float],
    is_day_birth: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """
    Combined strength summary: Shadbala + Ashtakavarga bindus for each planet.
    """
    shadbala = compute_all_shadbala(planet_signs, planet_houses, planet_degrees, is_day_birth)
    av = compute_ashtakavarga(planet_houses)

    summary: Dict[str, Dict[str, Any]] = {}
    for planet in planet_signs:
        sb = shadbala.get(planet, {})
        planet_house = planet_houses.get(planet, 1)
        planet_bindus = av.get(planet, {}).get(planet_house, 0)

        # Determine dignity
        sign = planet_signs[planet]
        if EXALTATION.get(planet, ("", 0))[0] == sign:
            dignity = "Exalted"
        elif DEBILITATION.get(planet) == sign:
            dignity = "Debilitated"
        elif sign in OWN_SIGNS.get(planet, []):
            dignity = "Own Sign"
        elif MOOLA_TRIKONA.get(planet, ("", 0, 0))[0] == sign:
            dignity = "Moola Trikona"
        else:
            ruler = SIGN_RULERS.get(sign, "")
            if ruler in _FRIENDS.get(planet, set()):
                dignity = "Friend's Sign"
            elif ruler in _ENEMIES.get(planet, set()):
                dignity = "Enemy's Sign"
            else:
                dignity = "Neutral"

        summary[planet] = {
            "dignity": dignity,
            "shadbala_total": sb.get("total", 0),
            "is_strong": sb.get("is_strong", False),
            "ashtakavarga_bindus": planet_bindus,
            "components": sb,
        }
    return summary
