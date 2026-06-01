"""Quick verification of the sidereal engine + service imports."""
import datetime as dt
from utils.astrology_math import (
    julian_day, sun_sidereal_longitude_deg, moon_sidereal_longitude_deg,
    lahiri_ayanamsa, nakshatra_index, nakshatra_pada, ascendant_sidereal_longitude_deg,
)
from utils.astrology_constants import ZODIAC_ORDER, NAKSHATRA_DATA

def sign(lon):
    return ZODIAC_ORDER[int(lon // 30) % 12]

print("=" * 60)
print("VEDIC ENGINE VERIFICATION (Lahiri Sidereal)")
print("=" * 60)

tests = [
    (1995, 8, 10, "Aug 10 (Western=Leo)"),
    (1995, 8, 20, "Aug 20 (Western=Leo)"),
    (1995, 9, 5,  "Sep 05 (Western=Virgo)"),
    (2000, 10, 15,"Oct 15 (Western=Libra)"),
    (1990, 1, 15, "Jan 15 (Western=Capricorn)"),
    (2000, 7, 25, "Jul 25 (Western=Leo)"),
]

for y, m, d, label in tests:
    utc = dt.datetime(y, m, d, 12, 0, tzinfo=dt.timezone.utc)
    jd = julian_day(utc)
    sun_lon = sun_sidereal_longitude_deg(jd)
    moon_lon = moon_sidereal_longitude_deg(jd)
    nak_idx = nakshatra_index(moon_lon)
    nak = NAKSHATRA_DATA[nak_idx]
    print(f"\n{label}:")
    print(f"  Ayanamsa: {lahiri_ayanamsa(jd):.3f} deg")
    print(f"  Sun:  {sun_lon:.2f} deg -> {sign(sun_lon)}")
    print(f"  Moon: {moon_lon:.2f} deg -> {sign(moon_lon)}")
    print(f"  Nakshatra: {nak['name']} (lord: {nak['lord']}, pada: {nakshatra_pada(moon_lon)})")

# Test ascendant (Delhi, noon)
print("\n" + "=" * 60)
print("ASCENDANT TEST (Delhi 28.6N, 77.2E)")
utc = dt.datetime(1995, 8, 10, 6, 30, tzinfo=dt.timezone.utc)  # noon IST
jd = julian_day(utc)
asc_lon = ascendant_sidereal_longitude_deg(jd, 28.6, 77.2)
print(f"  Asc: {asc_lon:.2f} deg -> {sign(asc_lon)}")

# Test service imports
print("\n" + "=" * 60)
print("SERVICE IMPORT TEST")
try:
    from services.analysis_service import zodiac_sign, compute_hybrid_big_three, build_blueprint
    print("  analysis_service: OK")
except Exception as e:
    print(f"  analysis_service: FAIL - {e}")

try:
    from utils.vedic_engine import build_vedic_bundle, format_guru_context, compute_vimshottari_dasha
    print("  vedic_engine: OK")

    # Test Vimshottari
    moon_lon = moon_sidereal_longitude_deg(julian_day(dt.datetime(1995, 8, 10, 6, 30, tzinfo=dt.timezone.utc)))
    md, ad, left = compute_vimshottari_dasha(moon_lon, dt.date(1995, 8, 10))
    print(f"  Vimshottari: MD={md}, AD={ad}, years_left={left:.1f}")
except Exception as e:
    print(f"  vedic_engine: FAIL - {e}")

print("\n" + "=" * 60)
print("Fallback zodiac_sign test (no coordinates):")
from services.analysis_service import zodiac_sign
for m, d, label in [(8, 10, "Aug10"), (8, 20, "Aug20"), (10, 15, "Oct15"), (1, 15, "Jan15")]:
    s = zodiac_sign(dt.date(2000, m, d))
    print(f"  {label} -> {s}")
print("DONE")
