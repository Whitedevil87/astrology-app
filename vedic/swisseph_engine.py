"""
Layer 1 — High-precision astronomical engine.

Wraps the Swiss Ephemeris (pyswisseph) library for arc-second accuracy.
Falls back gracefully to the existing astrology_math.py if swisseph is
not installed (pip install pyswisseph).

Public API
----------
    get_planet_longitude(jd, planet, sidereal=True) -> float
    get_all_planet_longitudes(jd, sidereal=True)    -> dict[str, float]
    get_ayanamsa(jd, aya_type="lahiri")             -> float
    get_ascendant(jd, lat, lon, sidereal=True)       -> float
    SWISSEPH_AVAILABLE                                -> bool
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── Try importing pyswisseph ────────────────────────────────────────
try:
    import swisseph as swe

    # Set Lahiri (Chitrapaksha) as default ayanamsa
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    SWISSEPH_AVAILABLE = True
    logger.info("Swiss Ephemeris (pyswisseph) loaded — high-precision mode active")
except ImportError:
    swe = None  # type: ignore[assignment]
    SWISSEPH_AVAILABLE = False
    logger.warning(
        "pyswisseph not installed — falling back to approximate math engine. "
        "Install with: pip install pyswisseph"
    )

# ── Fallback imports ────────────────────────────────────────────────
from utils.astrology_math import (
    lahiri_ayanamsa as _fallback_ayanamsa,
    sun_tropical_longitude_deg as _fb_sun_trop,
    moon_tropical_longitude_deg as _fb_moon_trop,
    ascendant_tropical_longitude_deg as _fb_asc_trop,
    _norm360,
)
# vedic_engine import is deferred to avoid circular imports

# ── Planet ID mapping (swisseph constants) ──────────────────────────
_SWE_PLANETS: Dict[str, int] = {}
if SWISSEPH_AVAILABLE:
    _SWE_PLANETS = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
        "Rahu": swe.MEAN_NODE,  # Mean Rahu (North Node)
    }

# Supported ayanamsa types
_AYA_MODES: Dict[str, int] = {}
if SWISSEPH_AVAILABLE:
    _AYA_MODES = {
        "lahiri": swe.SIDM_LAHIRI,
        "kp": swe.SIDM_KRISHNAMURTI,
        "raman": swe.SIDM_RAMAN,
        "yukteshwar": swe.SIDM_YUKTESHWAR,
    }

ALL_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]


# ── Ayanamsa ────────────────────────────────────────────────────────

def get_ayanamsa(jd: float, aya_type: str = "lahiri") -> float:
    """Return ayanamsa in degrees for the given Julian Day."""
    if SWISSEPH_AVAILABLE:
        mode = _AYA_MODES.get(aya_type.lower(), swe.SIDM_LAHIRI)
        swe.set_sid_mode(mode)
        return swe.get_ayanamsa_ut(jd)
    return _fallback_ayanamsa(jd)


# ── Single planet longitude ────────────────────────────────────────

def get_planet_longitude(
    jd: float,
    planet: str,
    sidereal: bool = True,
    aya_type: str = "lahiri",
) -> float:
    """
    Compute ecliptic longitude for a single planet.

    Parameters
    ----------
    jd       : Julian Day (UT)
    planet   : One of ALL_PLANETS
    sidereal : If True, subtract ayanamsa (Vedic). If False, return tropical.
    aya_type : Ayanamsa system — "lahiri", "kp", "raman", "yukteshwar"

    Returns
    -------
    Longitude in degrees [0, 360)
    """
    trop = _tropical_longitude(jd, planet)
    if not sidereal:
        return trop
    aya = get_ayanamsa(jd, aya_type)
    return _norm360(trop - aya)


def _tropical_longitude(jd: float, planet: str) -> float:
    """Tropical ecliptic longitude — uses swisseph if available, else fallback."""
    # Ketu is always 180° from Rahu
    if planet == "Ketu":
        rahu_lon = _tropical_longitude(jd, "Rahu")
        return _norm360(rahu_lon + 180.0)

    if SWISSEPH_AVAILABLE and planet in _SWE_PLANETS:
        try:
            flags = swe.FLG_SWIEPH | swe.FLG_SPEED
            result = swe.calc_ut(jd, _SWE_PLANETS[planet], flags)
            return _norm360(result[0][0])
        except Exception as exc:
            logger.warning("swisseph calc failed for %s: %s — using fallback", planet, exc)

    # ── Fallback to custom math ─────────────────────────────────
    if planet == "Sun":
        return _fb_sun_trop(jd)
    if planet == "Moon":
        return _fb_moon_trop(jd)
    # Lazy import to avoid circular dependency
    from utils.vedic_engine import _get_planet_lon_tropical
    return _get_planet_lon_tropical(jd, planet)


# ── All planet longitudes at once ──────────────────────────────────

def get_all_planet_longitudes(
    jd: float,
    sidereal: bool = True,
    aya_type: str = "lahiri",
) -> Dict[str, float]:
    """Return dict of planet_name → longitude for all 9 Vedic planets."""
    aya = get_ayanamsa(jd, aya_type) if sidereal else 0.0
    result: Dict[str, float] = {}
    for planet in ALL_PLANETS:
        trop = _tropical_longitude(jd, planet)
        lon = _norm360(trop - aya) if sidereal else trop
        result[planet] = lon
    return result


# ── Ascendant ──────────────────────────────────────────────────────

def get_ascendant(
    jd: float,
    lat: float,
    lon: float,
    sidereal: bool = True,
    aya_type: str = "lahiri",
) -> float:
    """Compute the Ascendant (Lagna) longitude."""
    if SWISSEPH_AVAILABLE:
        try:
            # swe.houses_ex returns (cusps_tuple, ascmc_tuple)
            mode = _AYA_MODES.get(aya_type.lower(), swe.SIDM_LAHIRI)
            swe.set_sid_mode(mode)
            flags = swe.FLG_SIDEREAL if sidereal else 0
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b"P", flags)
            return _norm360(ascmc[0])
        except Exception as exc:
            logger.warning("swisseph houses_ex failed: %s — using fallback", exc)

    # Fallback
    trop_asc = _fb_asc_trop(jd, lat, lon)
    if sidereal:
        aya = get_ayanamsa(jd, aya_type)
        return _norm360(trop_asc - aya)
    return trop_asc


# ── House cusps (Placidus) ──────────────────────────────────────────

def get_house_cusps(
    jd: float,
    lat: float,
    lon: float,
    system: str = "P",
    sidereal: bool = True,
    aya_type: str = "lahiri",
) -> Dict[int, float]:
    """
    Compute house cusps using the specified house system.

    Parameters
    ----------
    system : "P" = Placidus, "W" = Whole Sign, "K" = Koch, "E" = Equal
    """
    if SWISSEPH_AVAILABLE:
        try:
            mode = _AYA_MODES.get(aya_type.lower(), swe.SIDM_LAHIRI)
            swe.set_sid_mode(mode)
            flags = swe.FLG_SIDEREAL if sidereal else 0
            cusps, ascmc = swe.houses_ex(jd, lat, lon, system.encode(), flags)
            # cusps is a tuple of 13 values: cusps[0] is unused, cusps[1]–cusps[12] are houses 1–12
            return {i: _norm360(cusps[i]) for i in range(1, 13)}
        except Exception as exc:
            logger.warning("swisseph house cusps failed: %s — using whole sign fallback", exc)

    # Whole Sign fallback: Ascendant sign = House 1 start
    asc_lon = get_ascendant(jd, lat, lon, sidereal, aya_type)
    asc_sign_start = (int(asc_lon) // 30) * 30
    return {i: _norm360(asc_sign_start + (i - 1) * 30) for i in range(1, 13)}


# ── Convenience: sign from longitude ────────────────────────────────

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def sign_from_longitude(lon: float) -> str:
    """Zodiac sign from longitude in degrees."""
    return ZODIAC_ORDER[int(_norm360(lon) // 30) % 12]
