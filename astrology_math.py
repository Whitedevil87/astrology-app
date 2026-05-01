"""
Celestial Arc — Core astronomical math engine.

Uses KP (Krishnamurti Paddhati) Ayanamsa for sidereal calculations.
All public functions return SIDEREAL longitudes suitable for Vedic astrology.
"""

import math
from datetime import datetime, timezone

# ── Utility ──────────────────────────────────────────────────────────

def _deg_to_rad(x: float) -> float:
    return x * math.pi / 180.0

def _rad_to_deg(x: float) -> float:
    return x * 180.0 / math.pi

def _norm360(x: float) -> float:
    x = x % 360.0
    return x + 360.0 if x < 0 else x

def _norm24(x: float) -> float:
    x = x % 24.0
    return x + 24.0 if x < 0 else x

# ── Julian Day ───────────────────────────────────────────────────────

def julian_day(dt_utc: datetime) -> float:
    """Julian day for UTC datetime (proleptic Gregorian)."""
    if dt_utc.tzinfo is None:
        raise ValueError("dt_utc must be timezone-aware")
    dt = dt_utc.astimezone(timezone.utc)
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5
    return float(jd)

# ── Lahiri Ayanamsa ────────────────────────────────────────────────────

def lahiri_ayanamsa(jd: float) -> float:
    """
    Lahiri (Chitra Paksha) Ayanamsa in degrees.
    Approximate calculation based on J2000 epoch.
    At J2000.0 (JD 2451545.0), Lahiri Ayanamsa is approximately 23° 51' 11" (23.85305°).
    Annual precession is ~50.27 arcseconds.
    """
    years_from_2000 = (jd - 2451545.0) / 365.25
    ayanamsa = 23.85305 + (50.27 / 3600.0) * years_from_2000
    return ayanamsa

def tropical_to_sidereal(lon_tropical: float, jd: float) -> float:
    """Convert tropical ecliptic longitude to sidereal using Lahiri Ayanamsa."""
    return _norm360(lon_tropical - lahiri_ayanamsa(jd))


# ── Sun Position ─────────────────────────────────────────────────────

def sun_tropical_longitude_deg(jd: float) -> float:
    """
    Approximate apparent tropical ecliptic longitude of the Sun (degrees).
    Accuracy: ~0.5 deg — sufficient for rashi determination.
    """
    n = jd - 2451545.0
    L = _norm360(280.460 + 0.9856474 * n)
    g = _norm360(357.528 + 0.9856003 * n)
    g_rad = _deg_to_rad(g)
    lam = L + 1.915 * math.sin(g_rad) + 0.020 * math.sin(2 * g_rad)
    return _norm360(lam)

def sun_sidereal_longitude_deg(jd: float) -> float:
    """Sidereal Sun longitude (KP Ayanamsa)."""
    return tropical_to_sidereal(sun_tropical_longitude_deg(jd), jd)

# ── Moon Position ────────────────────────────────────────────────────

def moon_tropical_longitude_deg(jd: float) -> float:
    """
    Simplified Moon tropical longitude (degrees).
    Uses main Brown-theory periodic terms. Accuracy ~1-2 deg.
    """
    n = jd - 2451545.0
    L0 = _norm360(218.316 + 13.176396 * n)
    Mm = _norm360(134.963 + 13.064993 * n)
    Ms = _norm360(357.529 + 0.9856003 * n)
    D  = _norm360(297.850 + 12.190749 * n)
    F  = _norm360(93.272  + 13.229350 * n)
    lam = (
        L0
        + 6.289 * math.sin(_deg_to_rad(Mm))
        + 1.274 * math.sin(_deg_to_rad(2 * D - Mm))
        + 0.658 * math.sin(_deg_to_rad(2 * D))
        + 0.214 * math.sin(_deg_to_rad(2 * Mm))
        - 0.186 * math.sin(_deg_to_rad(Ms))
        - 0.114 * math.sin(_deg_to_rad(2 * F))
    )
    return _norm360(lam)

def moon_sidereal_longitude_deg(jd: float) -> float:
    """Sidereal Moon longitude (KP Ayanamsa)."""
    return tropical_to_sidereal(moon_tropical_longitude_deg(jd), jd)

# ── Sidereal Time & Ascendant ────────────────────────────────────────

def gmst_hours(jd: float) -> float:
    """Greenwich Mean Sidereal Time in hours."""
    T = (jd - 2451545.0) / 36525.0
    gmst = 6.697374558 + 2400.051336 * T + 0.000025862 * T * T
    frac_day = (jd + 0.5) % 1.0
    gmst += 24.06570982441908 * frac_day
    return _norm24(gmst)

def ascendant_tropical_longitude_deg(jd: float, lat_deg: float, lon_deg: float) -> float:
    """
    Tropical Ascendant ecliptic longitude (degrees).
    Standard formula: tan(ASC) = -cos(RAMC) / [sin(eps)*tan(lat) + cos(eps)*sin(RAMC)]
    """
    eps = _deg_to_rad(23.4393 - 0.0000004 * (jd - 2451545.0))
    lat = _deg_to_rad(lat_deg)
    ramc = _deg_to_rad(_norm360(gmst_hours(jd) * 15.0 + lon_deg))

    y_val = -math.cos(ramc)
    x_val = math.sin(eps) * math.tan(lat) + math.cos(eps) * math.sin(ramc)
    asc_rad = math.atan2(y_val, x_val)
    return _norm360(_rad_to_deg(asc_rad))

def ascendant_sidereal_longitude_deg(jd: float, lat_deg: float, lon_deg: float) -> float:
    """Sidereal Ascendant using KP Ayanamsa."""
    return tropical_to_sidereal(
        ascendant_tropical_longitude_deg(jd, lat_deg, lon_deg), jd
    )

# ── Backward-compat aliases (now return SIDEREAL) ────────────────────

def sun_ecliptic_longitude_deg(jd: float) -> float:
    """Returns sidereal Sun longitude (KP). Used by analysis_service."""
    return sun_sidereal_longitude_deg(jd)

def moon_ecliptic_longitude_deg(jd: float) -> float:
    """Returns sidereal Moon longitude (KP). Used by analysis_service."""
    return moon_sidereal_longitude_deg(jd)

def ascendant_longitude_deg(jd: float, lat_deg: float, lon_deg: float) -> float:
    """Returns sidereal Ascendant longitude (KP). Used by analysis_service."""
    return ascendant_sidereal_longitude_deg(jd, lat_deg, lon_deg)

# ── Nakshatra Computation ────────────────────────────────────────────

NAKSHATRA_SPAN_DEG = 360.0 / 27.0   # 13.3333 degrees per Nakshatra

def nakshatra_index(sidereal_lon: float) -> int:
    """0-based Nakshatra index from sidereal longitude (0 = Ashwini, 26 = Revati)."""
    return int(_norm360(sidereal_lon) / NAKSHATRA_SPAN_DEG) % 27

def nakshatra_fraction(sidereal_lon: float) -> float:
    """Fraction of current Nakshatra traversed (0.0 to ~1.0)."""
    lon = _norm360(sidereal_lon)
    start = (lon // NAKSHATRA_SPAN_DEG) * NAKSHATRA_SPAN_DEG
    return (lon - start) / NAKSHATRA_SPAN_DEG

def nakshatra_pada(sidereal_lon: float) -> int:
    """Pada (quarter) of the Nakshatra, 1 to 4."""
    frac = nakshatra_fraction(sidereal_lon)
    return min(int(frac * 4) + 1, 4)
