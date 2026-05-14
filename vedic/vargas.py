"""
Layer 3 — Divisional Charts (Vargas).

Implements all 16 primary Varga charts from D1 (Rashi) to D60 (Shashtiamsha).
Each function takes a sidereal longitude and returns the Varga sign.

Reference: Brihat Parashara Hora Shastra (BPHS) chapters on Varga division.

Public API
----------
    varga_sign(longitude, division)            -> str
    compute_all_vargas(planet_longitudes)       -> dict[str, dict[int, str]]
    navamsa_sign(longitude)                    -> str   (D9 shortcut)
    dashamsha_sign(longitude)                  -> str   (D10 shortcut)
"""

from __future__ import annotations

from typing import Dict, List

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# ── Utility ─────────────────────────────────────────────────────────

def _norm360(x: float) -> float:
    x = x % 360.0
    return x + 360.0 if x < 0 else x


def _sign_index(lon: float) -> int:
    """0-based sign index from longitude."""
    return int(_norm360(lon) // 30) % 12


def _sign_name(idx: int) -> str:
    return ZODIAC_ORDER[idx % 12]


def _degree_in_sign(lon: float) -> float:
    """Degree within the current sign (0–30)."""
    return _norm360(lon) % 30.0


# ── Generic equal-division Varga ────────────────────────────────────

def _equal_varga(lon: float, divisions: int) -> int:
    """
    For equal-division Vargas (D2, D3, D4, D7, D10, D12, D16, D20, D24, D27, D40, D45, D60):
    Divide each sign into `divisions` equal parts. The resulting part number
    maps to a sign counting from the base sign.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part_span = 30.0 / divisions
    part = int(deg / part_span)
    # Standard Parashara rule: count from the sign itself
    return (sign_idx + part) % 12


# ── D1: Rashi (Identity — the sign itself) ──────────────────────────

def d1_sign(lon: float) -> str:
    """D1 Rashi chart — the natal sign."""
    return _sign_name(_sign_index(lon))


# ── D2: Hora (Wealth) ───────────────────────────────────────────────

def d2_sign(lon: float) -> str:
    """
    D2 Hora: Each sign split into 2 halves (15° each).
    Odd signs: first half → Leo, second half → Cancer.
    Even signs: first half → Cancer, second half → Leo.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    is_odd = (sign_idx % 2 == 0)  # 0-indexed: Aries=0 (odd sign)
    if is_odd:
        return "Leo" if deg < 15.0 else "Cancer"
    else:
        return "Cancer" if deg < 15.0 else "Leo"


# ── D3: Drekkana (Siblings, courage) ────────────────────────────────

def d3_sign(lon: float) -> str:
    """
    D3 Drekkana: Each sign into 3 parts (10° each).
    Part 1 → same sign, Part 2 → 5th from it, Part 3 → 9th from it.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    if deg < 10.0:
        return _sign_name(sign_idx)
    elif deg < 20.0:
        return _sign_name(sign_idx + 4)
    else:
        return _sign_name(sign_idx + 8)


# ── D4: Chaturthamsha (Fortune, property) ───────────────────────────

def d4_sign(lon: float) -> str:
    """D4: 4 equal parts (7.5° each), counted from the sign."""
    return _sign_name(_equal_varga(lon, 4))


# ── D7: Saptamsha (Children, progeny) ───────────────────────────────

def d7_sign(lon: float) -> str:
    """
    D7 Saptamsha: 7 equal parts (4.2857° each).
    Odd signs: count from the sign itself.
    Even signs: count from the 7th sign.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part_span = 30.0 / 7
    part = int(deg / part_span)
    if sign_idx % 2 == 0:  # Odd sign (0-indexed)
        return _sign_name(sign_idx + part)
    else:  # Even sign
        return _sign_name(sign_idx + 6 + part)


# ── D9: Navamsa (Marriage, dharma, spiritual life) — MOST IMPORTANT ─

def d9_sign(lon: float) -> str:
    """
    D9 Navamsa: 9 equal parts (3.333° each).
    Fire signs start from Aries, Earth from Capricorn,
    Air from Libra, Water from Cancer.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part_span = 30.0 / 9
    part = int(deg / part_span)

    # Starting sign based on element (triplicity)
    element_starts = {
        0: 0,   # Fire (Aries, Leo, Sagittarius) → start from Aries
        1: 9,   # Earth (Taurus, Virgo, Capricorn) → start from Capricorn
        2: 6,   # Air (Gemini, Libra, Aquarius) → start from Libra
        3: 3,   # Water (Cancer, Scorpio, Pisces) → start from Cancer
    }
    element = sign_idx % 4  # Fire=0, Earth=1, Air=2, Water=3
    # But the element grouping in Jyotish by triplicities:
    # Fire signs: indices 0,4,8 (Aries, Leo, Sag)
    # Earth signs: indices 1,5,9 (Taurus, Virgo, Cap)
    # Air signs: indices 2,6,10 (Gemini, Libra, Aquarius)
    # Water signs: indices 3,7,11 (Cancer, Scorpio, Pisces)
    element_group = sign_idx % 4
    start = element_starts[element_group]

    navamsa_idx = (start + (sign_idx // 4) * 9 + part) % 12
    # Simpler standard formula: absolute navamsa from 0° Aries
    abs_lon = _norm360(lon)
    navamsa_num = int(abs_lon / (30.0 / 9))  # 0-based navamsa number out of 108
    return _sign_name(navamsa_num % 12)


def navamsa_sign(lon: float) -> str:
    """Alias for d9_sign — the Navamsa chart sign."""
    return d9_sign(lon)


# ── D10: Dashamsha (Career, profession) ─────────────────────────────

def d10_sign(lon: float) -> str:
    """
    D10 Dashamsha: 10 equal parts (3° each).
    Odd signs: count from the sign itself.
    Even signs: count from the 9th sign.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part_span = 30.0 / 10
    part = int(deg / part_span)
    if sign_idx % 2 == 0:  # Odd sign
        return _sign_name(sign_idx + part)
    else:  # Even sign
        return _sign_name(sign_idx + 8 + part)


def dashamsha_sign(lon: float) -> str:
    """Alias for d10_sign — the Dashamsha chart sign."""
    return d10_sign(lon)


# ── D12: Dvadashamsha (Parents) ─────────────────────────────────────

def d12_sign(lon: float) -> str:
    """D12: 12 equal parts (2.5° each), counted from the sign."""
    return _sign_name(_equal_varga(lon, 12))


# ── D16: Shodashamsha (Vehicles, comforts) ──────────────────────────

def d16_sign(lon: float) -> str:
    """
    D16 Shodashamsha: 16 equal parts (1.875° each).
    Movable signs start from Aries, Fixed from Leo,
    Dual from Sagittarius.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part = int(deg / (30.0 / 16))
    modality = sign_idx % 3  # 0=Cardinal, 1=Fixed, 2=Mutable
    starts = {0: 0, 1: 4, 2: 8}  # Aries, Leo, Sagittarius
    return _sign_name(starts[modality] + part)


# ── D20: Vimshamsha (Spiritual progress) ────────────────────────────

def d20_sign(lon: float) -> str:
    """
    D20 Vimshamsha: 20 parts (1.5° each).
    Movable → Aries, Fixed → Sagittarius, Dual → Leo.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part = int(deg / (30.0 / 20))
    modality = sign_idx % 3
    starts = {0: 0, 1: 8, 2: 4}
    return _sign_name(starts[modality] + part)


# ── D24: Chaturvimshamsha (Education, learning) ─────────────────────

def d24_sign(lon: float) -> str:
    """
    D24: 24 parts (1.25° each).
    Odd signs start from Leo, Even signs from Cancer.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part = int(deg / (30.0 / 24))
    start = 4 if (sign_idx % 2 == 0) else 3  # Leo=4, Cancer=3
    return _sign_name(start + part)


# ── D27: Saptavimshamsha / Bhamsha (Strength, prowess) ──────────────

def d27_sign(lon: float) -> str:
    """
    D27 Bhamsha: 27 parts (1.111° each).
    Fire signs start from Aries, Earth from Cancer,
    Air from Libra, Water from Capricorn.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part = int(deg / (30.0 / 27))
    element = sign_idx % 4
    starts = {0: 0, 1: 3, 2: 6, 3: 9}
    return _sign_name(starts[element] + part)


# ── D30: Trimshamsha (Misfortune, evil) ─────────────────────────────

def d30_sign(lon: float) -> str:
    """
    D30 Trimshamsha: Unequal divisions within each sign.
    Odd signs: Mars(5°), Saturn(5°), Jupiter(8°), Mercury(7°), Venus(5°)
    Even signs: Venus(5°), Mercury(7°), Jupiter(8°), Saturn(5°), Mars(5°)
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)

    if sign_idx % 2 == 0:  # Odd sign
        spans = [(5, "Aries"), (5, "Aquarius"), (8, "Sagittarius"),
                 (7, "Gemini"), (5, "Libra")]
    else:  # Even sign
        spans = [(5, "Taurus"), (7, "Virgo"), (8, "Pisces"),
                 (5, "Capricorn"), (5, "Scorpio")]

    accum = 0.0
    for span_deg, sign in spans:
        accum += span_deg
        if deg < accum:
            return sign
    return spans[-1][1]


# ── D40: Khavedamsha (Auspicious/inauspicious effects) ──────────────

def d40_sign(lon: float) -> str:
    """D40: 40 parts (0.75° each). Odd signs from Aries, Even from Libra."""
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part = int(deg / (30.0 / 40))
    start = 0 if (sign_idx % 2 == 0) else 6
    return _sign_name(start + part)


# ── D45: Akshavedamsha (General indications) ────────────────────────

def d45_sign(lon: float) -> str:
    """
    D45: 45 parts (0.667° each).
    Movable → Aries, Fixed → Leo, Dual → Sagittarius.
    """
    sign_idx = _sign_index(lon)
    deg = _degree_in_sign(lon)
    part = int(deg / (30.0 / 45))
    modality = sign_idx % 3
    starts = {0: 0, 1: 4, 2: 8}
    return _sign_name(starts[modality] + part)


# ── D60: Shashtiamsha (Past life karma — most subtle) ───────────────

def d60_sign(lon: float) -> str:
    """D60: 60 parts (0.5° each), counted from the sign."""
    return _sign_name(_equal_varga(lon, 60))


# ── Unified Varga computation ───────────────────────────────────────

VARGA_FUNCTIONS = {
    1: d1_sign, 2: d2_sign, 3: d3_sign, 4: d4_sign,
    7: d7_sign, 9: d9_sign, 10: d10_sign, 12: d12_sign,
    16: d16_sign, 20: d20_sign, 24: d24_sign, 27: d27_sign,
    30: d30_sign, 40: d40_sign, 45: d45_sign, 60: d60_sign,
}

VARGA_NAMES = {
    1: "Rashi", 2: "Hora", 3: "Drekkana", 4: "Chaturthamsha",
    7: "Saptamsha", 9: "Navamsa", 10: "Dashamsha", 12: "Dvadashamsha",
    16: "Shodashamsha", 20: "Vimshamsha", 24: "Chaturvimshamsha",
    27: "Bhamsha", 30: "Trimshamsha", 40: "Khavedamsha",
    45: "Akshavedamsha", 60: "Shashtiamsha",
}

VARGA_THEMES = {
    1: "Overall life & body",
    2: "Wealth & financial sustenance",
    3: "Siblings, courage, & short journeys",
    4: "Fortune, property, & fixed assets",
    7: "Children & progeny",
    9: "Marriage, dharma, & spiritual path",
    10: "Career, profession, & public status",
    12: "Parents & ancestral legacy",
    16: "Vehicles, comforts, & luxuries",
    20: "Spiritual progress & worship",
    24: "Education, learning, & knowledge",
    27: "Physical strength & prowess",
    30: "Misfortune, suffering, & evil",
    40: "Auspicious / inauspicious effects",
    45: "General indications & character",
    60: "Past life karma & subtle destiny",
}


def varga_sign(lon: float, division: int) -> str:
    """Compute the Varga sign for any supported division."""
    func = VARGA_FUNCTIONS.get(division)
    if func is None:
        raise ValueError(f"Unsupported Varga division: D{division}")
    return func(lon)


def compute_all_vargas(
    planet_longitudes: Dict[str, float],
    divisions: List[int] | None = None,
) -> Dict[str, Dict[int, str]]:
    """
    Compute Varga signs for all planets across specified divisions.

    Parameters
    ----------
    planet_longitudes : dict mapping planet name → sidereal longitude
    divisions         : list of Varga divisions to compute (default: all 16)

    Returns
    -------
    dict[planet_name][division] = sign_name
    """
    if divisions is None:
        divisions = list(VARGA_FUNCTIONS.keys())

    result: Dict[str, Dict[int, str]] = {}
    for planet, lon in planet_longitudes.items():
        result[planet] = {}
        for div in divisions:
            func = VARGA_FUNCTIONS.get(div)
            if func:
                result[planet][div] = func(lon)
    return result


def compute_key_vargas(planet_longitudes: Dict[str, float]) -> Dict[str, Dict[str, str]]:
    """
    Compute only the most important Vargas (D1, D9, D10) for all planets.
    Returns a more readable format.
    """
    result: Dict[str, Dict[str, str]] = {}
    for planet, lon in planet_longitudes.items():
        result[planet] = {
            "rashi": d1_sign(lon),
            "navamsa": d9_sign(lon),
            "dashamsha": d10_sign(lon),
        }
    return result
