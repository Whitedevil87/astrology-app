"""
Vedic astrology engine — Lahiri sidereal system (traditional Vedic standard).
Whole-sign houses, Vimshottari Dasha from Moon Nakshatra,
sidereal planet positions via Swiss Ephemeris when available.

Integrates:
    - vedic.vargas     (Layer 3 — Divisional charts)
    - vedic.strength   (Layer 5 — Shadbala + Ashtakavarga)
    - vedic.yogas      (Layer 6 — Classical yoga detection)
    - vedic.transits   (Layer 7 — Gochara & Sade Sati)
"""

from __future__ import annotations

import logging
import re
import math
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime, date, time as dt_time

from utils.astrology_math import lahiri_ayanamsa, _norm360 as _math_norm360
from utils.astrology_constants import (
    NAKSHATRA_DATA, VIMSHOTTARI_ORDER, VIMSHOTTARI_PERIODS,
    VIMSHOTTARI_TOTAL_YEARS,
)

logger = logging.getLogger(__name__)

try:
    from skyfield.api import Astrometric, load, wgs84
    from skyfield.magnitudelib import phase_angle
    SKYFIELD_AVAILABLE = True
except ImportError:
    SKYFIELD_AVAILABLE = False

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

HOUSE_MEANINGS = {
    1: "Self, body, temperament, life direction (Lagna)",
    2: "Wealth, speech, family, values (Dhana)",
    3: "Siblings, courage, short journeys, skills (Sahaj)",
    4: "Home, mother, comfort, roots (Sukha)",
    5: "Children, creativity, romance, intellect (Putra)",
    6: "Health, service, debts, competition (Ari)",
    7: "Marriage, partnerships, contracts (Yuvati)",
    8: "Transformations, shared resources, longevity (Randhra)",
    9: "Dharma, higher learning, luck, guru (Bhagya)",
    10: "Career, status, authority, reputation (Karma)",
    11: "Gains, friends, aspirations, income (Labha)",
    12: "Moksha, losses, foreign lands, liberation (Vyaya)",
}

VIMSHOTTARI_LORDS = VIMSHOTTARI_ORDER


def _sign_index(sign: str) -> int:
    return ZODIAC_ORDER.index(sign) if sign in ZODIAC_ORDER else 0


def _whole_sign_house(planet_sign: str, lagna_sign: str) -> int:
    """Whole-sign house: lagna sign is house 1."""
    p = _sign_index(planet_sign)
    l = _sign_index(lagna_sign)
    return (p - l) % 12 + 1


def _norm360(x: float) -> float:
    x = x % 360.0
    return x + 360.0 if x < 0 else x


def _sign_from_longitude(lon_deg: float) -> str:
    idx = int(_norm360(lon_deg) // 30)
    return ZODIAC_ORDER[idx]


def _get_planet_lon(jd: float, planet: str) -> float:
    """Sidereal longitude (Lahiri) — Swiss Ephemeris when available."""
    try:
        from vedic.swisseph_engine import SWISSEPH_AVAILABLE, get_planet_longitude
        if SWISSEPH_AVAILABLE:
            return get_planet_longitude(jd, planet, sidereal=True, aya_type="lahiri")
    except Exception:
        pass
    tropical = _get_planet_lon_tropical(jd, planet)
    return _norm360(tropical - lahiri_ayanamsa(jd))


def _get_planet_lon_tropical(jd: float, planet: str) -> float:
    """Compute tropical longitude for a planet."""
    T = (jd - 2451545.0) / 36525.0
    if planet == 'Rahu':
        omega = 125.04452 - 1934.136261 * T + 0.0020708 * T * T
        return _norm360(omega)
    if planet == 'Ketu':
        omega = 125.04452 - 1934.136261 * T + 0.0020708 * T * T
        return _norm360(omega + 180.0)

    if planet == 'Mercury':
        L = 252.250 + 149472.674 * T
        M = 174.795 + 149472.674 * T
        M_rad = math.radians(_norm360(M))
        C = 23.69 * math.sin(M_rad) + 3.47 * math.sin(2*M_rad)
    elif planet == 'Venus':
        L = 181.980 + 58517.816 * T
        M = 50.416 + 58517.816 * T
        M_rad = math.radians(_norm360(M))
        C = 0.77 * math.sin(M_rad) + 0.01 * math.sin(2*M_rad)
    elif planet == 'Mars':
        L = 355.433 + 19140.299 * T
        M = 19.373 + 19140.299 * T
        M_rad = math.radians(_norm360(M))
        C = 10.69 * math.sin(M_rad) + 0.62 * math.sin(2*M_rad)
    elif planet == 'Jupiter':
        L = 34.351 + 3034.906 * T
        M = 20.020 + 3034.906 * T
        M_rad = math.radians(_norm360(M))
        C = 5.55 * math.sin(M_rad) + 0.17 * math.sin(2*M_rad)
    elif planet == 'Saturn':
        L = 50.077 + 1222.114 * T
        M = 317.021 + 1222.114 * T
        M_rad = math.radians(_norm360(M))
        C = 6.36 * math.sin(M_rad) + 0.22 * math.sin(2*M_rad)
    else:
        return 0.0

    return _norm360(L + C)


# ── Proper Vimshottari Dasha from Moon Nakshatra ─────────────────────

def compute_vimshottari_dasha(moon_sid_lon: float, birth_date, current_date=None):
    """
    Compute current Mahadasha, Antardasha, and Pratyantardasha from Moon's
    sidereal longitude.

    Returns (mahadasha_lord, antardasha_lord, pratyantardasha_lord, years_left_in_md).
    """
    if current_date is None:
        current_date = datetime.now().date()

    nak_span = 360.0 / 27.0  # 13.3333 deg
    lon = _norm360(moon_sid_lon)
    nak_idx = int(lon / nak_span) % 27
    nak_data = NAKSHATRA_DATA[nak_idx]
    nak_lord = nak_data["lord"]

    # Fraction of Nakshatra already traversed at birth
    nak_start = nak_idx * nak_span
    frac_traversed = (lon - nak_start) / nak_span

    # Remaining years of birth Nakshatra lord's dasha
    lord_period = VIMSHOTTARI_PERIODS[nak_lord]
    remaining_years = lord_period * (1.0 - frac_traversed)

    # Find the lord's position in Vimshottari sequence
    lord_seq_idx = VIMSHOTTARI_ORDER.index(nak_lord)

    # Calculate age
    if isinstance(birth_date, datetime):
        bd = birth_date.date()
    elif isinstance(birth_date, date):
        bd = birth_date
    else:
        bd = date.today()

    if isinstance(current_date, datetime):
        cd = current_date.date() if hasattr(current_date, 'date') else current_date
    else:
        cd = current_date

    age_years = (cd - bd).days / 365.25

    # Walk through dasha sequence to find current Mahadasha
    elapsed = 0.0
    md_lord = nak_lord
    md_start_age = 0.0

    if age_years < remaining_years:
        md_lord = nak_lord
        md_start_age = 0.0
    else:
        elapsed = remaining_years
        for i in range(1, 10):
            next_lord = VIMSHOTTARI_ORDER[(lord_seq_idx + i) % 9]
            next_period = VIMSHOTTARI_PERIODS[next_lord]
            if elapsed + next_period > age_years:
                md_lord = next_lord
                md_start_age = elapsed
                break
            elapsed += next_period
        else:
            md_lord = nak_lord
            md_start_age = 0.0

    # ── Antardasha within Mahadasha ──
    md_period = VIMSHOTTARI_PERIODS[md_lord]
    time_in_md = age_years - md_start_age
    md_seq_idx = VIMSHOTTARI_ORDER.index(md_lord)

    ad_elapsed = 0.0
    ad_lord = md_lord
    ad_start_in_md = 0.0
    ad_period_actual = 0.0
    for i in range(9):
        ad_candidate = VIMSHOTTARI_ORDER[(md_seq_idx + i) % 9]
        ad_period = md_period * VIMSHOTTARI_PERIODS[ad_candidate] / VIMSHOTTARI_TOTAL_YEARS
        if ad_elapsed + ad_period > time_in_md:
            ad_lord = ad_candidate
            ad_start_in_md = ad_elapsed
            ad_period_actual = ad_period
            break
        ad_elapsed += ad_period
    else:
        ad_lord = md_lord
        ad_period_actual = md_period * VIMSHOTTARI_PERIODS[md_lord] / VIMSHOTTARI_TOTAL_YEARS

    # ── Pratyantardasha within Antardasha ──
    time_in_ad = time_in_md - ad_start_in_md
    ad_seq_idx = VIMSHOTTARI_ORDER.index(ad_lord)

    pd_lord = ad_lord
    pd_elapsed = 0.0
    for j in range(9):
        pd_candidate = VIMSHOTTARI_ORDER[(ad_seq_idx + j) % 9]
        pd_period = ad_period_actual * VIMSHOTTARI_PERIODS[pd_candidate] / VIMSHOTTARI_TOTAL_YEARS
        if pd_elapsed + pd_period > time_in_ad:
            pd_lord = pd_candidate
            break
        pd_elapsed += pd_period

    years_left = md_period - time_in_md

    return md_lord, ad_lord, pd_lord, max(0, years_left)


def _ketu_from_rahu(rahu_house: int) -> int:
    return (rahu_house - 1 + 6) % 12 + 1


def _clamp_house(n: int) -> int:
    n = int(n)
    if n < 1:
        return 1
    if n > 12:
        return 12
    return n


def parse_kundli_notes(text: str) -> Dict[str, int]:
    """Extract planet→house numbers from free text (user pasted from software)."""
    if not text:
        return {}
    t = text.lower()
    out: Dict[str, int] = {}
    patterns = [
        ("rahu", "rahu_house"),
        ("ketu", "ketu_house"),
        ("mars", "mars_house"),
        ("mangal", "mars_house"),
        ("moon", "moon_house"),
        ("sun", "sun_house"),
        ("mercury", "mercury_house"),
        ("budh", "mercury_house"),
        ("venus", "venus_house"),
        ("shukra", "venus_house"),
        ("jupiter", "jupiter_house"),
        ("guru", "jupiter_house"),
        ("saturn", "saturn_house"),
        ("shani", "saturn_house"),
    ]
    for key, field in patterns:
        match = re.search(rf"{key}\s*(?:in|house|:)?\s*(\d{{1,2}})", t)
        if match:
            out[field] = _clamp_house(int(match.group(1)))
    return out


def _pseudo_seed(birth_date, birth_time, birth_place: str) -> int:
    return (
        birth_date.year * 5023
        + birth_date.month * 271
        + birth_date.day * 97
        + birth_time.hour * 13
        + birth_time.minute * 3
        + sum(ord(c) for c in birth_place[:24])
    ) & 0xFFFFFFFF


def compute_dosha_flags(mars_house: int, rahu_house: int, ketu_house: int) -> List[str]:
    flags: List[str] = []
    if mars_house in {1, 2, 4, 7, 8, 12}:
        flags.append(
            "Manglik / Kuja dosha (Mars in a sensitive marriage/self house — verify with full chart matching)"
        )
    folk = (rahu_house * 5 + ketu_house * 11 + mars_house * 3) % 13
    if folk == 0:
        flags.append(
            "Some traditional checklists may mention Kaal Sarp–style node emphasis — confirm with software + a human astrologer; avoid fear-based labels."
        )
    return flags


def build_remedy_text(flags: List[str], rahu_house: int, ketu_house: int, mahadasha: str) -> str:
    lines: List[str] = []
    lines.append(
        "These are gentle, generic practices often discussed in tradition — not medical advice. "
        "For serious decisions (marriage timing, legal, health), consult a qualified human astrologer and professionals."
    )
    if any("Manglik" in f for f in flags):
        lines.append(
            "Manglik considerations: steady Hanuman worship on Tuesdays, ethical martial discipline (sport/service), "
            "avoid impulsive conflict in partnerships; some families do matching — modern couples often focus on maturity and communication."
        )
    if any("Kaal Sarp" in f for f in flags):
        lines.append(
            "Rahu–Ketu axis remedies (popular lore): disciplined meditation, ethical living (no shortcuts), "
            "Rudra japam or Vishnu sahasranama if it resonates with your lineage — choose what your teacher recommends."
        )
    lines.append(
        f"Rahu in house {rahu_house}: reduce chaotic scrolling, commit to one skill, beware glamour and sudden shortcuts."
    )
    lines.append(
        f"Ketu in house {ketu_house}: simplify attachments here, trust intuition, study spiritual frameworks without dogma."
    )
    lines.append(
        f"Mahadasha flavor ({mahadasha}): align activities with this planet’s dignity in your real chart; "
        "use this demo period as a journaling lens, not a contract with fate."
    )
    return " ".join(lines)


def build_vedic_bundle(
    lagna_sign: str,
    sun_sign: str,
    moon_sign: str,
    birth_date,
    birth_time,
    birth_place: str,
    kundli_notes: str,
    has_kundli_image: bool,
    hybrid_details: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Returns (sections dict for report, structured vedic dict for chat/JSON).
    """
    seed = _pseudo_seed(birth_date, birth_time, birth_place)
    overrides = parse_kundli_notes(kundli_notes)

    jd = hybrid_details.get("jd") if hybrid_details else None

    if jd is not None:
        # High precision calculation using true math engine
        sun_h = overrides.get("sun_house") or _whole_sign_house(sun_sign, lagna_sign)
        moon_h = overrides.get("moon_house") or _whole_sign_house(moon_sign, lagna_sign)
        mars_sign = _sign_from_longitude(_get_planet_lon(jd, "Mars"))
        mars_h = overrides.get("mars_house") or _whole_sign_house(mars_sign, lagna_sign)
        mercury_sign = _sign_from_longitude(_get_planet_lon(jd, "Mercury"))
        mercury_h = overrides.get("mercury_house") or _whole_sign_house(mercury_sign, lagna_sign)
        venus_sign = _sign_from_longitude(_get_planet_lon(jd, "Venus"))
        venus_h = overrides.get("venus_house") or _whole_sign_house(venus_sign, lagna_sign)
        jupiter_sign = _sign_from_longitude(_get_planet_lon(jd, "Jupiter"))
        jupiter_h = overrides.get("jupiter_house") or _whole_sign_house(jupiter_sign, lagna_sign)
        saturn_sign = _sign_from_longitude(_get_planet_lon(jd, "Saturn"))
        saturn_h = overrides.get("saturn_house") or _whole_sign_house(saturn_sign, lagna_sign)
        rahu_sign = _sign_from_longitude(_get_planet_lon(jd, "Rahu"))
        ketu_sign = _sign_from_longitude(_get_planet_lon(jd, "Ketu"))
        rahu_h = overrides.get("rahu_house") or _whole_sign_house(rahu_sign, lagna_sign)
        ketu_h = overrides.get("ketu_house") or _whole_sign_house(ketu_sign, lagna_sign)
        house_msg = "Lahiri sidereal positions (Swiss Ephemeris) with whole-sign houses."
    else:
        # Fallback pseudo-seed logic
        sun_h = overrides.get("sun_house") or _whole_sign_house(sun_sign, lagna_sign)
        moon_h = overrides.get("moon_house") or _whole_sign_house(moon_sign, lagna_sign)
        mars_h = overrides.get("mars_house") or _clamp_house((seed % 12) + 1)
        rahu_o = overrides.get("rahu_house")
        ketu_o = overrides.get("ketu_house")
        if rahu_o is not None and ketu_o is not None:
            rahu_h = _clamp_house(rahu_o)
            ketu_h = _clamp_house(ketu_o)
        elif rahu_o is not None:
            rahu_h = _clamp_house(rahu_o)
            ketu_h = _ketu_from_rahu(rahu_h)
        elif ketu_o is not None:
            ketu_h = _clamp_house(ketu_o)
            rahu_h = _ketu_from_rahu(ketu_h)
        else:
            rahu_h = _clamp_house((((seed // 9) + 10) % 12) + 1)
            ketu_h = _ketu_from_rahu(rahu_h)
        mercury_h = overrides.get("mercury_house") or _clamp_house((seed // 3 % 12) + 1)
        venus_h = overrides.get("venus_house") or _clamp_house((seed // 5 % 12) + 1)
        jupiter_h = overrides.get("jupiter_house") or _clamp_house((seed // 7 % 12) + 1)
        saturn_h = overrides.get("saturn_house") or _clamp_house((seed // 11 % 12) + 1)
        house_msg = "Approximate positions; provide exact birth place and time for Lahiri precision."

    # ── Proper Vimshottari Dasha from Moon Nakshatra ──
    moon_lon = hybrid_details.get("moon_lon_deg") if hybrid_details else None
    nak_name = (hybrid_details or {}).get("nakshatra", "")
    nak_lord = (hybrid_details or {}).get("nakshatra_lord", "")
    nak_pada = (hybrid_details or {}).get("nakshatra_pada", 0)

    mahadasha = ""
    antar = ""
    pratyantardasha = ""
    if moon_lon is not None and jd is not None:
        try:
            from vedic.dasha import compute_dasha, current_dasha as _cur_dasha
            _dasha = compute_dasha(moon_lon, jd)
            _cur = _cur_dasha(_dasha)
            mahadasha = _cur.get("mahadasha") or ""
            antar = _cur.get("antardasha") or ""
            pratyantardasha = _cur.get("pratyantar") or ""
            if not nak_name:
                nak_name = _dasha.get("moon_nakshatra", {}).get("name", nak_name)
            if not nak_lord:
                nak_lord = _dasha.get("moon_nakshatra", {}).get("lord", nak_lord)
        except Exception as e:
            logger.warning("JD-based dasha failed, using age-walk fallback: %s", e)
            mahadasha, antar, pratyantardasha, _md_left = compute_vimshottari_dasha(moon_lon, birth_date)
    elif moon_lon is not None:
        mahadasha, antar, pratyantardasha, _md_left = compute_vimshottari_dasha(moon_lon, birth_date)
    else:
        day_of_year = birth_date.timetuple().tm_yday
        approx_nak_idx = (day_of_year * 27 // 365) % 27
        nak_lord_fb = NAKSHATRA_DATA[approx_nak_idx]["lord"]
        lord_idx = VIMSHOTTARI_ORDER.index(nak_lord_fb)
        mahadasha = nak_lord_fb
        antar = VIMSHOTTARI_ORDER[(lord_idx + 1) % 9]
        pratyantardasha = VIMSHOTTARI_ORDER[(lord_idx + 2) % 9]

    flags = compute_dosha_flags(mars_h, rahu_h, ketu_h)
    remedies = build_remedy_text(flags, rahu_h, ketu_h, mahadasha)

    # ── Build planet data structures for new modules ──
    planet_houses: Dict[str, int] = {
        "Sun": sun_h, "Moon": moon_h, "Mars": mars_h,
        "Mercury": mercury_h, "Venus": venus_h, "Jupiter": jupiter_h,
        "Saturn": saturn_h, "Rahu": rahu_h, "Ketu": ketu_h,
    }
    planet_signs: Dict[str, str] = {
        "Sun": sun_sign, "Moon": moon_sign,
    }
    planet_degrees: Dict[str, float] = {}

    # Fill in planet signs from longitudes if available
    if jd is not None:
        precomputed = (hybrid_details or {}).get("planet_longitudes") or {}
        for p in ["Mars", "Mercury", "Venus", "Jupiter", "Saturn", "Rahu", "Ketu"]:
            lon = precomputed.get(p) or _get_planet_lon(jd, p)
            planet_signs[p] = _sign_from_longitude(lon)
            planet_degrees[p] = lon % 30.0
        if moon_lon is not None:
            planet_degrees["Moon"] = moon_lon % 30.0
    else:
        # Approximate signs from house placement (fallback)
        for p, h in planet_houses.items():
            if p not in planet_signs:
                lagna_idx = ZODIAC_ORDER.index(lagna_sign) if lagna_sign in ZODIAC_ORDER else 0
                planet_signs[p] = ZODIAC_ORDER[(lagna_idx + h - 1) % 12]

    # ── Layer 3: Divisional Charts (Vargas) ──
    vargas_data: Dict[str, Any] = {}
    try:
        from vedic.vargas import compute_key_vargas
        if jd is not None:
            precomputed = (hybrid_details or {}).get("planet_longitudes") or {}
            planet_lons = {
                p: precomputed.get(p) or _get_planet_lon(jd, p)
                for p in ["Sun", "Moon", "Mars", "Mercury", "Venus", "Jupiter", "Saturn", "Rahu", "Ketu"]
            }
            vargas_data = compute_key_vargas(planet_lons)
    except Exception as e:
        logger.warning("Varga computation skipped: %s", e)

    # ── Layer 5: Planetary Strength ──
    strength_data: Dict[str, Any] = {}
    try:
        from vedic.strength import planet_strength_summary
        strength_data = planet_strength_summary(
            planet_signs, planet_houses, planet_degrees,
            is_day_birth=(birth_time.hour >= 6 and birth_time.hour < 18),
        )
    except Exception as e:
        logger.warning("Strength computation skipped: %s", e)

    # ── Layer 6: Yoga Detection ──
    yoga_data: Dict[str, Any] = {}
    try:
        from vedic.yogas import detect_all_yogas
        yoga_data = detect_all_yogas(planet_houses, planet_signs, lagna_sign)
    except Exception as e:
        logger.warning("Yoga detection skipped: %s", e)

    # ── Layer 7: Transit & Gochara ──
    transit_data: Dict[str, Any] = {}
    try:
        from vedic.transits import gochara_report, prediction_confidence
        transit_data = gochara_report(moon_sign, lagna_sign)
        # Layer 8: Dasha + Transit confidence
        sade_sati = transit_data.get("sade_sati", {})
        jupiter_tr = transit_data.get("jupiter_transit", {})
        confidence = prediction_confidence(
            mahadasha, antar,
            transit_data.get("transit_score", 50),
            sade_sati.get("active", False),
            jupiter_tr.get("quality", "mixed"),
        )
        transit_data["prediction_confidence"] = confidence
    except Exception as e:
        logger.warning("Transit computation skipped: %s", e)

    house_lines = [
        f"Lagna ({lagna_sign}) occupies House 1 — {HOUSE_MEANINGS[1]}",
        f"Engine: {house_msg}",
        f"Sun ({sun_sign}) → House {sun_h}: {HOUSE_MEANINGS.get(sun_h, '')}",
        f"Moon ({moon_sign}) → House {moon_h}: {HOUSE_MEANINGS.get(moon_h, '')}",
        f"Mars → House {mars_h}: {HOUSE_MEANINGS.get(mars_h, '')}",
        f"Mercury → House {mercury_h}",
        f"Venus → House {venus_h}",
        f"Jupiter → House {jupiter_h}",
        f"Saturn → House {saturn_h}",
    ]

    upload_note = (
        "You attached a chart image — stored for your records. "
        "Local mode does not OCR the pixels; paste key houses in the notes box for software-grade alignment. "
        "Optional: set OPENAI_API_KEY on the server to enable cloud AI interpretation."
        if has_kundli_image
        else "No chart image uploaded — house numbers below blend whole-sign logic with your notes (if any)."
    )
    if kundli_notes.strip():
        upload_note += " Your pasted notes override automatic house guesses where detected."

    rahu_blurb = (
        f"Rahu in House {rahu_h}: obsessions, sudden opportunities, foreigners/tech themes — channels through {HOUSE_MEANINGS.get(rahu_h, '')}. "
        "Mature Rahu chooses ethical ambition, one ruthless cut of distraction, and structured learning."
    )
    ketu_blurb = (
        f"Ketu in House {ketu_h}: detachment and insight where you over-identify — {HOUSE_MEANINGS.get(ketu_h, '')}. "
        "Healthy Ketu prefers simplicity, mastery without applause, and spiritual skepticism that still respects kindness."
    )

    dasha_blurb = (
        f"Vimshottari Dasha: {mahadasha} Mahadasha → {antar} Antardasha → {pratyantardasha} Pratyantardasha. "
        "These three layers of timing shape your current life themes."
    )

    dosha_blurb = (
        "Dosha scan: " + ("; ".join(flags) if flags else "No major flag from Mars placement.")
    )

    # ── Yoga section text ──
    yoga_blurb = ""
    if yoga_data.get("yogas"):
        yoga_lines = [f"Yogas detected ({yoga_data['count']}):"]
        for y in yoga_data["yogas"][:6]:
            yoga_lines.append(f"• {y['name']}: {y['description']}")
        yoga_blurb = " ".join(yoga_lines)
    else:
        yoga_blurb = "No classical yogas detected from current house placements."

    # ── Transit section text ──
    transit_blurb = ""
    if transit_data:
        sade = transit_data.get("sade_sati", {})
        conf = transit_data.get("prediction_confidence", {})
        transit_blurb = (
            f"Transit Score: {transit_data.get('transit_score', '?')}% favorable. "
            f"Sade Sati: {sade.get('phase_name', 'N/A')}. "
            f"{transit_data.get('overall_description', '')} "
            f"Prediction Confidence: {conf.get('score', '?')}% — {conf.get('description', '')}"
        )

    # ── Strength section text ──
    strength_blurb = ""
    if strength_data:
        strong = [p for p, d in strength_data.items() if d.get("is_strong")]
        dignity_list = [f"{p}: {d.get('dignity', '?')}" for p, d in strength_data.items() if p not in ("Rahu", "Ketu")]
        strength_blurb = (
            f"Strong planets: {', '.join(strong) if strong else 'None above threshold'}. "
            f"Dignities — {'; '.join(dignity_list[:5])}."
        )

    structured: Dict[str, Any] = {
        "lagna_sign": lagna_sign,
        "houses": {
            "sun": sun_h, "moon": moon_h, "mars": mars_h,
            "rahu": rahu_h, "ketu": ketu_h,
            "mercury": mercury_h, "venus": venus_h,
            "jupiter": jupiter_h, "saturn": saturn_h,
        },
        "planet_signs": planet_signs,
        "mahadasha": mahadasha,
        "antardasha_demo": antar,
        "pratyantardasha": pratyantardasha,
        "nakshatra": nak_name,
        "nakshatra_lord": nak_lord,
        "nakshatra_pada": nak_pada,
        "dosha_flags": flags,
        "yogas": yoga_data,
        "transits": transit_data,
        "strength": strength_data,
        "vargas": vargas_data,
        "has_kundli_image": has_kundli_image,
        "notes_used": bool(kundli_notes.strip()),
    }

    sections = {
        "kundli_layer": upload_note,
        "vedic_houses": " \n".join(house_lines),
        "rahu_ketu": rahu_blurb + " " + ketu_blurb,
        "vimshottari_timing": dasha_blurb + " " + dosha_blurb,
        "remedies_lifestyle": remedies,
        "yogas": yoga_blurb,
        "transits": transit_blurb,
        "planet_strength": strength_blurb,
    }
    return sections, structured


def _planets_in_house(houses: Dict[str, Any], house_num: int) -> str:
    if not houses:
        return "(no house table)"
    hits = [name for name, hn in houses.items() if hn == house_num]
    return ", ".join(hits) if hits else "(none listed in this house)"


def format_guru_context(name: str, profile: Dict[str, str], vedic: Dict[str, Any], blueprint: Dict[str, Any]) -> str:
    """Rich Vedic astrological context for the Guru Arya AI persona (Lahiri sidereal)."""
    h = vedic.get("houses") or {}
    career_hint = ""
    if blueprint:
        career_hint = (
            f"Blueprint cues — energy focus: {blueprint.get('energy_focus', 'n/a')}; "
            f"ruling planet: {blueprint.get('ruling_planet', 'n/a')}; "
            f"element: {blueprint.get('element', 'n/a')}; modality: {blueprint.get('modality', 'n/a')}; "
            f"lucky day: {blueprint.get('lucky_day', 'n/a')}; lucky color: {blueprint.get('lucky_color', 'n/a')}; "
            f"lucky number: {blueprint.get('lucky_number', 'n/a')}.\n"
            f"Best compatibility matches: {blueprint.get('best_matches', 'n/a')}. "
            f"Growth-tension signs: {blueprint.get('growth_signs', 'n/a')}.\n"
        )

    dosha_info = vedic.get('dosha_flags') or ['none flagged']
    mahadasha = vedic.get('mahadasha', 'unknown')
    antardasha = vedic.get('antardasha_demo', 'unknown')
    pratyantardasha = vedic.get('pratyantardasha', 'unknown')
    nakshatra = vedic.get('nakshatra', 'unknown')
    nak_lord = vedic.get('nakshatra_lord', 'unknown')
    nak_pada = vedic.get('nakshatra_pada', 0)

    # Yoga summary for context
    yoga_info = vedic.get('yogas', {})
    yoga_summary = yoga_info.get('summary', 'Not computed') if yoga_info else 'Not computed'

    # Transit summary
    transit_info = vedic.get('transits', {})
    sade_sati_phase = transit_info.get('sade_sati', {}).get('phase_name', 'N/A') if transit_info else 'N/A'
    transit_score = transit_info.get('transit_score', '?') if transit_info else '?'
    confidence = transit_info.get('prediction_confidence', {}).get('score', '?') if transit_info else '?'

    # Strength summary
    strength_info = vedic.get('strength', {})
    strength_lines = ""
    if strength_info:
        for p, data in list(strength_info.items())[:7]:
            dignity = data.get('dignity', '?')
            strong = "✓" if data.get('is_strong') else "✗"
            strength_lines += f"  {p}: {dignity} (strong={strong})\n"

    # Navamsa (D9) for marriage/dharma context
    vargas_info = vedic.get('vargas', {})
    navamsa_lines = ""
    if vargas_info:
        for p, v in vargas_info.items():
            nav = v.get('navamsa', '?')
            navamsa_lines += f"  {p}: D9={nav}\n"

    return (
        f"Querent: {name}.\n"
        f"SYSTEM: Lahiri Sidereal Vedic Astrology (Swiss Ephemeris). All positions are sidereal.\n\n"
        f"Sun Rashi: {profile.get('zodiac')} (aatma, ego, life purpose).\n"
        f"Moon Rashi: {profile.get('moon_sign')} (mann, emotions, subconscious patterns).\n"
        f"Lagna (Ascendant): {profile.get('ascendant')} (shareer, first impression, physical constitution).\n"
        f"Moon Nakshatra: {nakshatra} (lord: {nak_lord}, pada: {nak_pada}).\n\n"
        f"{career_hint}"
        f"PLANETARY HOUSE PLACEMENTS (Whole-Sign, 1-12):\n"
        f"  Sun → House {h.get('sun', '?')} | Moon → House {h.get('moon', '?')} | Mars → House {h.get('mars', '?')}\n"
        f"  Mercury → House {h.get('mercury', '?')} | Venus → House {h.get('venus', '?')} | Jupiter → House {h.get('jupiter', '?')}\n"
        f"  Saturn → House {h.get('saturn', '?')} | Rahu → House {h.get('rahu', '?')} | Ketu → House {h.get('ketu', '?')}\n\n"
        f"PLANETARY DIGNITY & STRENGTH:\n{strength_lines}\n"
        f"NAVAMSA CHART (D9 — Marriage & Dharma):\n{navamsa_lines}\n"
        f"KEY HOUSE ANALYSIS:\n"
        f"  1st (Lagna/Self): Lagna in {profile.get('ascendant')}.\n"
        f"  4th (Sukha/Home/Mother) hosts: {_planets_in_house(h, 4)}.\n"
        f"  5th (Putra/Romance/Creativity) hosts: {_planets_in_house(h, 5)}.\n"
        f"  7th (Yuvati/Marriage/Partners) hosts: {_planets_in_house(h, 7)}.\n"
        f"  10th (Karma/Career/Status) hosts: {_planets_in_house(h, 10)}.\n"
        f"  11th (Labha/Gains/Income) hosts: {_planets_in_house(h, 11)}.\n\n"
        f"YOGAS: {yoga_summary}\n\n"
        f"DASHA TIMING (Vimshottari from Moon Nakshatra):\n"
        f"  Mahadasha: {mahadasha} | Antardasha: {antardasha} | Pratyantardasha: {pratyantardasha}\n"
        f"  Dosha flags: {', '.join(dosha_info)}.\n\n"
        f"CURRENT TRANSITS:\n"
        f"  Transit Score: {transit_score}% favorable | Sade Sati: {sade_sati_phase}\n"
        f"  Prediction Confidence: {confidence}%\n\n"
        "INTERPRETATION RULES (STRICT):\n"
        "- ONLY use Vedic (Jyotish) astrology. NO Western astrology references.\n"
        "- Use ONLY the data provided above. Do NOT guess or hallucinate.\n"
        "- Always mention specific planet + house + dasha when giving reasons.\n"
        "- Reference yogas and planetary dignity when relevant.\n"
        "- For timing questions, cite Dasha + Transit confluence.\n"
    )


def guru_reply_rule_based(message: str, ctx: str, vedic: Dict[str, Any], sections: Dict[str, str]) -> str:
    """Keyword routing over precomputed sections (works offline)."""
    m = message.lower()
    chunks: List[str] = []

    if any(k in m for k in ("rahu", "ketu", "snake", "axis")):
        chunks.append(sections.get("rahu_ketu", ""))
    if any(k in m for k in ("marriage", "love", "spouse", "7th", "partner")):
        chunks.append(
            "Partnership lens: the 7th house and Venus timing matter. "
            + sections.get("compatibility", "")
        )
    if any(
        k in m
        for k in (
            "career",
            "job",
            "jobs",
            "employ",
            "unemploy",
            "salary",
            "work",
            "office",
            "hiring",
            "interview",
            "money",
            "10th",
            "business",
        )
    ):
        chunks.append(sections.get("career", ""))
        chunks.append(sections.get("future", ""))
    if any(k in m for k in ("dasha", "mahadasha", "antar", "timing", "when")):
        chunks.append(sections.get("vimshottari_timing", ""))
    if any(k in m for k in ("remedy", "puja", "mantra", "dosha", "afflicted", "problem")):
        chunks.append(sections.get("remedies_lifestyle", ""))
    if any(k in m for k in ("house", "kundli", "chart", "lagna", "asc")):
        chunks.append(sections.get("vedic_houses", ""))

    if not chunks:
        chunks.append(
            "Sit quietly with this chart snapshot: compare what you feel true in your body versus what fear says. "
            "Astrology is a mirror: use it for meaning-making, not for shrinking your agency.\n\n"
            + ctx
        )

    tail = (
        "\n\n— If you want tighter accuracy, paste planet-wise house numbers from your kundli software into the notes field and regenerate."
    )
    text = "\n\n".join(c for c in chunks if c).strip()
    return text + tail


def get_horoscope_for_sign(sign: str) -> str:
    """Generate daily horoscope for a zodiac sign."""
    horoscopes = {
        "Aries": "Mars empowers your initiative today. Channel boldness into a worthwhile goal. Relationship insights emerge in evening hours. Lucky color: Red.",
        "Taurus": "Venus aligns with stability. Focus on building long-term value. Friends bring good news. Financial prudence pays off. Lucky color: Green.",
        "Gemini": "Mercury energizes communication. Speak your truth; others listen. Creative solutions emerge. Avoid overcommitting. Lucky color: Yellow.",
        "Cancer": "Moon's influence deepens introspection. Home and family matters gain clarity. Trust your intuition. Self-care is not indulgence. Lucky color: Silver.",
        "Leo": "Sun radiates confidence and joy. Express yourself authentically. Romance or creative breakthrough possible. Lead with heart. Lucky color: Gold.",
        "Virgo": "Mercury brings analytical clarity. Details matter; organization pays off. Domestic matters settle. Health improves with attention. Lucky color: Green.",
        "Libra": "Venus graces social and romantic realms. Charm opens doors. Creative projects flourish. Balance work and pleasure. Lucky color: Pink.",
        "Scorpio": "Pluto's intensity fuels transformation. Resources align in your favor. Home feels secure. Intuitive power peaks. Lucky color: Black.",
        "Sagittarius": "Jupiter expands horizons. Communication flows; travel beckons. New ideas take root. Adventure calls. Lucky color: Purple.",
        "Capricorn": "Saturn brings solid progress. Finances strengthen. Patience and planning reap rewards. Foundation solidifies. Lucky color: Brown.",
        "Aquarius": "Uranus sparks innovation. Social connections deepen. Unexpected opportunities arise. Embrace uniqueness. Lucky color: Blue.",
        "Pisces": "Neptune softens the day. Spirituality calls; meditation helps. Compassion flows naturally. Rest as needed. Lucky color: Teal.",
    }
    return horoscopes.get(sign, "The stars guide your path. Trust the unfolding of your cosmic blueprint.")


def generate_kundli_svg(
    zodiac: str,
    moon_sign: str,
    ascendant: str,
    planets: Dict[str, Any],
) -> str:
    """Generate a basic SVG Kundli/birth chart diagram."""
    width, height = 600, 600
    cx, cy = width / 2, height / 2
    radius = 200
    
    # SVG header
    svg = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
    svg += '<defs>'
    svg += '<style>'
    svg += 'text { font-family: Arial, sans-serif; font-size: 12px; fill: #333; }'
    svg += '.house-label { font-weight: bold; font-size: 14px; }'
    svg += '.planet-label { font-size: 11px; fill: #0066cc; font-weight: bold; }'
    svg += '.zodiac-label { font-size: 10px; fill: #666; }'
    svg += '</style>'
    svg += '</defs>'
    
    # Background circle
    svg += f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="#fff9f0" stroke="#8b7355" stroke-width="2"/>'
    
    # 12 houses (lines from center)
    for i in range(12):
        angle = (i * 30) * math.pi / 180
        x1, y1 = cx, cy
        x2 = cx + radius * math.cos(angle)
        y2 = cy + radius * math.sin(angle)
        svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#ccc" stroke-width="1"/>'
    
    # House numbers (1-12 arranged in circle)
    house_labels = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
    for i, label in enumerate(house_labels):
        angle = (i * 30 + 15) * math.pi / 180
        x = cx + (radius * 0.85) * math.cos(angle)
        y = cy + (radius * 0.85) * math.sin(angle)
        svg += f'<text x="{x}" y="{y}" text-anchor="middle" class="house-label">{label}</text>'
    
    # Zodiac signs in each house sector
    zodiac_glyphs = {
        "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
        "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
        "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
    }
    
    lagna_idx = ZODIAC_ORDER.index(ascendant) if ascendant in ZODIAC_ORDER else 0
    for i in range(12):
        sign_idx = (lagna_idx + i) % 12
        sign = ZODIAC_ORDER[sign_idx]
        glyph = zodiac_glyphs.get(sign, "?")
        angle = (i * 30 + 5) * math.pi / 180
        x = cx + (radius * 0.60) * math.cos(angle)
        y = cy + (radius * 0.60) * math.sin(angle)
        svg += f'<text x="{x}" y="{y}" text-anchor="middle" class="zodiac-label">{glyph}</text>'
    
    # Display key planets in chart center
    planet_text = f"☉ Sun: {zodiac}"
    moon_text = f"☽ Moon: {moon_sign}"
    asc_text = f"Asc: {ascendant}"
    
    svg += f'<text x="{cx}" y="{cy - 20}" text-anchor="middle" class="planet-label">{planet_text}</text>'
    svg += f'<text x="{cx}" y="{cy}" text-anchor="middle" class="planet-label">{moon_text}</text>'
    svg += f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" class="planet-label">{asc_text}</text>'
    
    # Outer circle
    svg += f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#8b7355" stroke-width="2"/>'
    
    svg += '</svg>'
    return svg


def generate_kundli_chart_from_birth(
    birth_date: str,
    birth_time: str,
    birth_place_lat: Optional[float] = None,
    birth_place_lon: Optional[float] = None,
    tz_offset_hours: float = 5.5,  # Default IST; pass correct offset for other timezones
) -> Dict[str, Any]:
    """
    Generate Kundli chart data from birth information.
    Returns dictionary with zodiac, moon_sign, ascendant, and SVG chart.

    Parameters
    ----------
    birth_date       : "YYYY-MM-DD" string (local date at birth)
    birth_time       : "HH:MM" or "HH:MM:SS" string (local time at birth)
    birth_place_lat  : Latitude of birth place
    birth_place_lon  : Longitude of birth place
    tz_offset_hours  : UTC offset in hours (e.g. IST=5.5, EST=-5, GMT=0)
                       IMPORTANT: pass the correct offset — default is IST (5.5)
    """
    if not SKYFIELD_AVAILABLE:
        return {
            "success": False,
            "message": "Skyfield not available for chart generation",
        }

    try:
        import math as _math
        from utils.astrology_math import (
            julian_day as _jd_func,
            ascendant_tropical_longitude_deg as _asc_trop_func,
            moon_tropical_longitude_deg as _moon_trop_func,
            sun_tropical_longitude_deg as _sun_trop_func,
            lahiri_ayanamsa as _aya_func,
            _norm360 as _n360,
        )
        from datetime import timezone as _tz, timedelta as _td

        # Parse birth date and time as LOCAL time
        birth_dt = datetime.fromisoformat(f"{birth_date}T{birth_time}")

        # Convert local → UTC using the provided offset
        utc_offset = _td(hours=tz_offset_hours)
        local_tz = _tz(utc_offset)
        birth_dt_local = birth_dt.replace(tzinfo=local_tz)
        birth_dt_utc = birth_dt_local.astimezone(_tz.utc)

        # Julian Day in UT
        from utils.astrology_math import julian_day as _jd_calc
        jd = _jd_calc(birth_dt_utc)

        _lon = birth_place_lon if birth_place_lon is not None else 91.0
        _lat = birth_place_lat if birth_place_lat is not None else 26.0

        # --- Accurate planetary positions ---
        aya = _aya_func(jd)

        # Sun sidereal longitude
        sun_trop = _sun_trop_func(jd)
        sun_sid = _n360(sun_trop - aya)
        zodiac = ZODIAC_ORDER[int(sun_sid / 30) % 12]

        # Moon sidereal longitude (25-term formula)
        moon_trop = _moon_trop_func(jd)
        moon_sid = _n360(moon_trop - aya)
        moon_sign = ZODIAC_ORDER[int(moon_sid / 30) % 12]

        # Ascendant — uses corrected quadrant formula
        asc_trop = _asc_trop_func(jd, _lat, _lon)
        asc_sid = _n360(asc_trop - aya)
        ascendant = ZODIAC_ORDER[int(asc_sid / 30) % 12]

        # Generate SVG
        svg = generate_kundli_svg(zodiac, moon_sign, ascendant, {})

        return {
            "success": True,
            "zodiac": zodiac,
            "moon_sign": moon_sign,
            "ascendant": ascendant,
            "chart_svg": svg,
            "jd": jd,
            "sun_lon": sun_sid,
            "moon_lon": moon_sid,
            "asc_lon": asc_sid,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Chart generation error: {str(e)}",
        }