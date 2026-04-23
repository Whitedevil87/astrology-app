import math
from datetime import datetime, timezone

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

def sun_ecliptic_longitude_deg(jd: float) -> float:
    """
    Approximate apparent ecliptic longitude of the Sun (degrees).
    Low/medium precision but good enough for sign.
    """
    n = jd - 2451545.0
    L = _norm360(280.460 + 0.9856474 * n)
    g = _norm360(357.528 + 0.9856003 * n)
    lam = L + 1.915 * math.sin(_deg_to_rad(g)) + 0.020 * math.sin(_deg_to_rad(2 * g))
    return _norm360(lam)

def moon_ecliptic_longitude_deg(jd: float) -> float:
    """
    Very simplified Moon longitude (degrees).
    This is not ephemeris-grade, but much more meaningful than day-of-year buckets.
    """
    n = jd - 2451545.0
    L0 = _norm360(218.316 + 13.176396 * n)  # mean longitude
    Mm = _norm360(134.963 + 13.064993 * n)  # mean anomaly
    Ms = _norm360(357.529 + 0.9856003 * n)  # sun mean anomaly
    D = _norm360(297.850 + 12.190749 * n)   # elongation
    # main periodic terms (truncated)
    lam = (
        L0
        + 6.289 * math.sin(_deg_to_rad(Mm))
        + 1.274 * math.sin(_deg_to_rad(2 * D - Mm))
        + 0.658 * math.sin(_deg_to_rad(2 * D))
        + 0.214 * math.sin(_deg_to_rad(2 * Mm))
        - 0.186 * math.sin(_deg_to_rad(Ms))
    )
    return _norm360(lam)

def gmst_hours(jd: float) -> float:
    """Greenwich mean sidereal time in hours."""
    T = (jd - 2451545.0) / 36525.0
    gmst = 6.697374558 + 2400.051336 * T + 0.000025862 * T * T
    # add rotation since 0h UT
    frac_day = (jd + 0.5) % 1.0
    gmst += 24.06570982441908 * frac_day
    return _norm24(gmst)

def ascendant_longitude_deg(jd: float, lat_deg: float, lon_deg: float) -> float:
    """
    Approximate Ascendant ecliptic longitude (degrees) from JD + coordinates.
    Uses LST and obliquity; sufficient for asc sign.
    """
    eps = _deg_to_rad(23.439291)  # obliquity (approx)
    lat = _deg_to_rad(lat_deg)
    lst = _deg_to_rad(_norm360((gmst_hours(jd) * 15.0) + lon_deg))
    # Formula for ascendant longitude (Meeus-like)
    num = math.sin(lst) * math.cos(eps) - math.tan(lat) * math.sin(eps)
    den = math.cos(lst)
    lam = math.atan2(num, den)
    return _norm360(_rad_to_deg(lam))
