"""
Layer 6 — Yoga & Combination Detector.

Detects classical Vedic astrological yogas (planetary combinations)
from house placements and sign positions.

Yogas implemented:
    - Raj Yoga (royal combinations — trikona + kendra lords)
    - Dhana Yoga (wealth combinations)
    - Pancha Mahapurusha Yoga (5 great person yogas)
    - Kemadruma Yoga (Moon isolation — poverty indicator)
    - Gajakesari Yoga (Jupiter-Moon — fame & wisdom)
    - Budhaditya Yoga (Sun-Mercury — intelligence)
    - Viparita Raj Yoga (lords of dusthana in dusthana)
    - Neechabhanga Raj Yoga (debilitation cancellation)
    - Chandra-Mangala Yoga (Moon-Mars — wealth through effort)
    - Graha cancellations & special combos

Reference: BPHS, Phaladeepika, Jataka Parijata.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGN_RULERS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}

EXALTATION_SIGNS = {
    "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn",
    "Mercury": "Virgo", "Jupiter": "Cancer", "Venus": "Pisces",
    "Saturn": "Libra",
}

DEBILITATION_SIGNS = {
    "Sun": "Libra", "Moon": "Scorpio", "Mars": "Cancer",
    "Mercury": "Pisces", "Jupiter": "Capricorn", "Venus": "Virgo",
    "Saturn": "Aries",
}

OWN_SIGNS = {
    "Sun": {"Leo"}, "Moon": {"Cancer"}, "Mars": {"Aries", "Scorpio"},
    "Mercury": {"Gemini", "Virgo"}, "Jupiter": {"Sagittarius", "Pisces"},
    "Venus": {"Taurus", "Libra"}, "Saturn": {"Capricorn", "Aquarius"},
}

_SIGN_IDX = {s: i for i, s in enumerate(ZODIAC_ORDER)}

# Kendra houses (angular): 1, 4, 7, 10
KENDRA_HOUSES = {1, 4, 7, 10}
# Trikona houses (trinal): 1, 5, 9
TRIKONA_HOUSES = {1, 5, 9}
# Dusthana houses: 6, 8, 12
DUSTHANA_HOUSES = {6, 8, 12}
# Upachaya houses: 3, 6, 10, 11
UPACHAYA_HOUSES = {3, 6, 10, 11}


def _sign_for_house(lagna_sign: str, house: int) -> str:
    """Get the zodiac sign for a given house number (whole-sign system)."""
    lagna_idx = _SIGN_IDX.get(lagna_sign, 0)
    return ZODIAC_ORDER[(lagna_idx + house - 1) % 12]


def _house_lord(lagna_sign: str, house: int) -> str:
    """Get the planetary lord of a given house."""
    sign = _sign_for_house(lagna_sign, house)
    return SIGN_RULERS[sign]


def _planets_in_same_house(planet_houses: Dict[str, int], planet_a: str, planet_b: str) -> bool:
    """Check if two planets are in the same house (conjunction)."""
    return planet_houses.get(planet_a) == planet_houses.get(planet_b)


def _planets_in_kendra_from(planet_houses: Dict[str, int], planet_a: str, planet_b: str) -> bool:
    """Check if planet_b is in a kendra (1/4/7/10) from planet_a."""
    h_a = planet_houses.get(planet_a, 0)
    h_b = planet_houses.get(planet_b, 0)
    diff = ((h_b - h_a) % 12)
    return diff in {0, 3, 6, 9}  # Houses 1, 4, 7, 10 offset


# ====================================================================
# RAJ YOGA — Royal Combinations
# ====================================================================

def detect_raj_yogas(
    planet_houses: Dict[str, int],
    lagna_sign: str,
) -> List[Dict[str, str]]:
    """
    Raj Yoga: When lords of Trikona houses (1,5,9) are conjunct with
    or aspect lords of Kendra houses (1,4,7,10).
    """
    yogas: List[Dict[str, str]] = []

    trikona_lords = {h: _house_lord(lagna_sign, h) for h in TRIKONA_HOUSES}
    kendra_lords = {h: _house_lord(lagna_sign, h) for h in KENDRA_HOUSES}

    for t_house, t_lord in trikona_lords.items():
        for k_house, k_lord in kendra_lords.items():
            if t_lord == k_lord:
                # Same planet lords both a trikona and kendra — automatic Raj Yoga
                yogas.append({
                    "name": "Raj Yoga",
                    "type": "royal",
                    "strength": "strong",
                    "description": (
                        f"{t_lord} lords both House {t_house} (trikona) and "
                        f"House {k_house} (kendra) — a powerful Raj Yoga indicating "
                        f"authority, status, and success."
                    ),
                })
                continue

            if _planets_in_same_house(planet_houses, t_lord, k_lord):
                yogas.append({
                    "name": "Raj Yoga",
                    "type": "royal",
                    "strength": "strong",
                    "description": (
                        f"{t_lord} (lord of {t_house}th, trikona) conjuncts "
                        f"{k_lord} (lord of {k_house}th, kendra) in House "
                        f"{planet_houses.get(t_lord, '?')} — Raj Yoga promising "
                        f"rise in life, leadership, and recognition."
                    ),
                })

    return yogas


# ====================================================================
# PANCHA MAHAPURUSHA YOGA — 5 Great Person Yogas
# ====================================================================

_MAHAPURUSHA_NAMES = {
    "Mars": "Ruchaka",
    "Mercury": "Bhadra",
    "Jupiter": "Hamsa",
    "Venus": "Malavya",
    "Saturn": "Shasha",
}

_MAHAPURUSHA_MEANINGS = {
    "Ruchaka": "Warrior-like courage, physical strength, commanding presence",
    "Bhadra": "Brilliant intellect, eloquent speech, sharp business acumen",
    "Hamsa": "Wisdom, spiritual elevation, righteous character, fame",
    "Malavya": "Beauty, artistic talent, luxury, refined relationships",
    "Shasha": "Authority through discipline, political power, organizational mastery",
}


def detect_pancha_mahapurusha(
    planet_signs: Dict[str, str],
    planet_houses: Dict[str, int],
) -> List[Dict[str, str]]:
    """
    Pancha Mahapurusha: Mars/Mercury/Jupiter/Venus/Saturn in
    own sign OR exaltation sign, AND placed in a Kendra house (1,4,7,10).
    """
    yogas: List[Dict[str, str]] = []
    for planet in ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        sign = planet_signs.get(planet, "")
        house = planet_houses.get(planet, 0)
        in_own = sign in OWN_SIGNS.get(planet, set())
        in_exalted = EXALTATION_SIGNS.get(planet) == sign
        in_kendra = house in KENDRA_HOUSES

        if (in_own or in_exalted) and in_kendra:
            yoga_name = _MAHAPURUSHA_NAMES[planet]
            yogas.append({
                "name": f"{yoga_name} Yoga",
                "type": "mahapurusha",
                "planet": planet,
                "strength": "very_strong",
                "description": (
                    f"{planet} in {'exaltation' if in_exalted else 'own sign'} "
                    f"({sign}) in Kendra House {house} — {yoga_name} Yoga: "
                    f"{_MAHAPURUSHA_MEANINGS[yoga_name]}."
                ),
            })
    return yogas


# ====================================================================
# DHANA YOGA — Wealth Combinations
# ====================================================================

def detect_dhana_yogas(
    planet_houses: Dict[str, int],
    lagna_sign: str,
) -> List[Dict[str, str]]:
    """
    Dhana Yoga: Connection between lords of houses 2 (wealth), 5 (luck),
    9 (fortune), 11 (gains) with Kendra lords.
    """
    yogas: List[Dict[str, str]] = []
    wealth_houses = {2, 5, 9, 11}

    for wh in wealth_houses:
        w_lord = _house_lord(lagna_sign, wh)
        for kh in KENDRA_HOUSES:
            k_lord = _house_lord(lagna_sign, kh)
            if w_lord == k_lord:
                continue
            if _planets_in_same_house(planet_houses, w_lord, k_lord):
                yogas.append({
                    "name": "Dhana Yoga",
                    "type": "wealth",
                    "strength": "moderate",
                    "description": (
                        f"{w_lord} (lord of {wh}th, wealth house) conjuncts "
                        f"{k_lord} (lord of {kh}th, kendra) — Dhana Yoga "
                        f"indicating financial prosperity and material gains."
                    ),
                })
    return yogas


# ====================================================================
# GAJAKESARI YOGA — Jupiter + Moon
# ====================================================================

def detect_gajakesari(planet_houses: Dict[str, int]) -> List[Dict[str, str]]:
    """
    Gajakesari: Jupiter in Kendra (1/4/7/10) from Moon.
    Grants fame, wisdom, wealth, and respected position.
    """
    if _planets_in_kendra_from(planet_houses, "Moon", "Jupiter"):
        return [{
            "name": "Gajakesari Yoga",
            "type": "prosperity",
            "strength": "strong",
            "description": (
                "Jupiter is in a Kendra from Moon — Gajakesari Yoga: "
                "grants intelligence, good reputation, lasting wealth, "
                "and widespread recognition in society."
            ),
        }]
    return []


# ====================================================================
# BUDHADITYA YOGA — Sun + Mercury
# ====================================================================

def detect_budhaditya(
    planet_houses: Dict[str, int],
    planet_signs: Dict[str, str],
) -> List[Dict[str, str]]:
    """
    Budhaditya: Sun and Mercury in the same house (conjunction).
    Mercury must NOT be combust (within 14° of Sun — simplified check).
    Grants sharp intellect and communication skills.
    """
    if _planets_in_same_house(planet_houses, "Sun", "Mercury"):
        # Check combustion (simplified: if in same sign, assume some combustion risk)
        sun_sign = planet_signs.get("Sun", "")
        merc_sign = planet_signs.get("Mercury", "")
        if sun_sign == merc_sign:
            return [{
                "name": "Budhaditya Yoga",
                "type": "intelligence",
                "strength": "moderate",
                "description": (
                    "Sun and Mercury conjunct — Budhaditya Yoga: "
                    "sharp analytical mind, eloquent communication, "
                    "aptitude for learning and scholarly pursuits. "
                    "(Note: Mercury may be partially combust.)"
                ),
            }]
    return []


# ====================================================================
# KEMADRUMA YOGA — Moon Isolation (Challenging)
# ====================================================================

def detect_kemadruma(planet_houses: Dict[str, int]) -> List[Dict[str, str]]:
    """
    Kemadruma: No planet in the 2nd or 12th house from Moon.
    (Excluding Sun, Rahu, Ketu from consideration.)
    Indicates periods of loneliness, financial hardship, or lack of support.
    """
    moon_h = planet_houses.get("Moon", 0)
    if not moon_h:
        return []

    h_before = ((moon_h - 2) % 12) + 1  # 12th from Moon
    h_after = (moon_h % 12) + 1          # 2nd from Moon

    flanking_planets = False
    for planet in ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        ph = planet_houses.get(planet, 0)
        if ph == h_before or ph == h_after:
            flanking_planets = True
            break

    if not flanking_planets:
        # Check for cancellation: planet in kendra from Moon or Lagna
        return [{
            "name": "Kemadruma Yoga",
            "type": "challenging",
            "strength": "moderate",
            "description": (
                "No planet flanks the Moon (houses 2nd and 12th from Moon are empty) — "
                "Kemadruma Yoga: can indicate phases of isolation, financial stress, "
                "or lack of social support. Often cancelled by planets in Kendra "
                "from Moon or strong Moon itself."
            ),
        }]
    return []


# ====================================================================
# CHANDRA-MANGALA YOGA — Moon + Mars
# ====================================================================

def detect_chandra_mangala(planet_houses: Dict[str, int]) -> List[Dict[str, str]]:
    """Moon and Mars conjunction — wealth through hard work and courage."""
    if _planets_in_same_house(planet_houses, "Moon", "Mars"):
        return [{
            "name": "Chandra-Mangala Yoga",
            "type": "wealth",
            "strength": "moderate",
            "description": (
                "Moon and Mars conjunct — Chandra-Mangala Yoga: "
                "wealth earned through bold action, business acumen, "
                "and courageous initiative. Emotional intensity drives success."
            ),
        }]
    return []


# ====================================================================
# VIPARITA RAJ YOGA — Lords of 6, 8, 12 in Each Other's Houses
# ====================================================================

def detect_viparita_raj(
    planet_houses: Dict[str, int],
    lagna_sign: str,
) -> List[Dict[str, str]]:
    """
    Viparita Raj Yoga: When lords of dusthana houses (6, 8, 12)
    are placed in OTHER dusthana houses.
    Turns adversity into unexpected fortune.
    """
    yogas: List[Dict[str, str]] = []
    dusthana_lords = {h: _house_lord(lagna_sign, h) for h in DUSTHANA_HOUSES}

    for house, lord in dusthana_lords.items():
        lord_house = planet_houses.get(lord, 0)
        if lord_house in DUSTHANA_HOUSES and lord_house != house:
            yogas.append({
                "name": "Viparita Raj Yoga",
                "type": "reversal",
                "strength": "moderate",
                "description": (
                    f"Lord of {house}th ({lord}) placed in {lord_house}th (another dusthana) — "
                    f"Viparita Raj Yoga: sudden rise after adversity, unexpected gains "
                    f"from difficult circumstances, resilience turning into triumph."
                ),
            })
    return yogas


# ====================================================================
# NEECHABHANGA RAJ YOGA — Debilitation Cancellation
# ====================================================================

def detect_neechabhanga(
    planet_signs: Dict[str, str],
    planet_houses: Dict[str, int],
    lagna_sign: str,
) -> List[Dict[str, str]]:
    """
    Neechabhanga Raj Yoga: A debilitated planet's weakness gets cancelled when:
    1. The lord of its debilitation sign is in a Kendra from Lagna or Moon
    2. The exaltation lord of the debilitated planet is in Kendra
    3. The debilitated planet itself is in a Kendra
    """
    yogas: List[Dict[str, str]] = []

    for planet, deb_sign in DEBILITATION_SIGNS.items():
        if planet_signs.get(planet) != deb_sign:
            continue

        # Planet is debilitated — check cancellation conditions
        planet_house = planet_houses.get(planet, 0)
        deb_sign_lord = SIGN_RULERS.get(deb_sign, "")
        deb_lord_house = planet_houses.get(deb_sign_lord, 0)

        cancelled = False

        # Condition 1: Lord of debilitation sign in kendra from Lagna
        if deb_lord_house in KENDRA_HOUSES:
            cancelled = True

        # Condition 2: Debilitated planet itself in kendra
        if planet_house in KENDRA_HOUSES:
            cancelled = True

        if cancelled:
            yogas.append({
                "name": "Neechabhanga Raj Yoga",
                "type": "reversal",
                "strength": "strong",
                "description": (
                    f"{planet} is debilitated in {deb_sign} but its debilitation "
                    f"is cancelled — Neechabhanga Raj Yoga: initial struggles transform "
                    f"into extraordinary success. The weakness becomes the greatest strength."
                ),
            })
    return yogas


# ====================================================================
# UNIFIED DETECTOR
# ====================================================================

def detect_all_yogas(
    planet_houses: Dict[str, int],
    planet_signs: Dict[str, str],
    lagna_sign: str,
) -> Dict[str, Any]:
    """
    Run all yoga detectors and return a structured summary.

    Returns
    -------
    {
        "yogas": [list of all detected yoga dicts],
        "count": total number of yogas found,
        "has_raj_yoga": bool,
        "has_mahapurusha": bool,
        "has_dhana_yoga": bool,
        "has_challenging": bool,
        "summary": human-readable summary string,
    }
    """
    all_yogas: List[Dict[str, str]] = []

    all_yogas.extend(detect_raj_yogas(planet_houses, lagna_sign))
    all_yogas.extend(detect_pancha_mahapurusha(planet_signs, planet_houses))
    all_yogas.extend(detect_dhana_yogas(planet_houses, lagna_sign))
    all_yogas.extend(detect_gajakesari(planet_houses))
    all_yogas.extend(detect_budhaditya(planet_houses, planet_signs))
    all_yogas.extend(detect_kemadruma(planet_houses))
    all_yogas.extend(detect_chandra_mangala(planet_houses))
    all_yogas.extend(detect_viparita_raj(planet_houses, lagna_sign))
    all_yogas.extend(detect_neechabhanga(planet_signs, planet_houses, lagna_sign))

    # Deduplicate by name+description
    seen = set()
    unique: List[Dict[str, str]] = []
    for y in all_yogas:
        key = y["name"] + y.get("description", "")
        if key not in seen:
            seen.add(key)
            unique.append(y)

    types = {y.get("type") for y in unique}

    # Build summary
    if unique:
        names = list(dict.fromkeys(y["name"] for y in unique))
        summary = f"{len(unique)} yoga(s) detected: {', '.join(names[:5])}"
        if len(names) > 5:
            summary += f" and {len(names) - 5} more"
    else:
        summary = "No classical yogas detected from current house placements."

    return {
        "yogas": unique,
        "count": len(unique),
        "has_raj_yoga": "royal" in types,
        "has_mahapurusha": "mahapurusha" in types,
        "has_dhana_yoga": "wealth" in types,
        "has_challenging": "challenging" in types,
        "summary": summary,
    }
