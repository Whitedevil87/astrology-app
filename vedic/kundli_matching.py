"""
vedic/kundli_matching.py
─────────────────────────
Complete Kundli Matching (Ashtakoot Milan) — 36-point Guna system.

Implements all 8 Kootas:
  1. Varna        — 1 point   (spiritual/caste compatibility)
  2. Vasya        — 2 points  (dominance/attraction)
  3. Tara         — 3 points  (birth star compatibility)
  4. Yoni         — 4 points  (sexual/biological compatibility)
  5. Graha Maitri — 5 points  (planetary friendship)
  6. Gana         — 6 points  (temperament)
  7. Bhakut       — 7 points  (relationship/health)
  8. Nadi         — 8 points  (health and progeny)

Also includes:
  • Mangal Dosha analysis (with exceptions)
  • Rajju & Vedha dosha
  • Overall compatibility verdict
  • Detailed interpretation per koota

Public API
──────────
    compute_guna_milan(boy_moon_sid, girl_moon_sid) → dict
    check_mangal_dosha(planet_houses)              → dict
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

# ── Nakshatra data ───────────────────────────────────────────────────

NAKSHATRA_NAMES = [
    "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
    "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta",
    "Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha",
    "Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada",
    "Uttara Bhadrapada","Revati",
]

# ── 1. VARNA (1 point) ───────────────────────────────────────────────
# 4 varnas: Brahmin(4) > Kshatriya(3) > Vaishya(2) > Shudra(1)

NAK_VARNA = [
    "Shudra","Shudra","Brahmin","Vaishya","Shudra","Shudra","Brahmin",
    "Kshatriya","Brahmin","Shudra","Vaishya","Brahmin","Vaishya",
    "Shudra","Shudra","Shudra","Kshatriya","Kshatriya","Brahmin","Brahmin",
    "Vaishya","Brahmin","Shudra","Vaishya","Brahmin","Kshatriya","Brahmin",
]

VARNA_SCORE = {"Brahmin": 4, "Kshatriya": 3, "Vaishya": 2, "Shudra": 1}

def _varna_score(boy_nak: int, girl_nak: int) -> Tuple[float, str]:
    bv = NAK_VARNA[boy_nak]
    gv = NAK_VARNA[girl_nak]
    bs, gs = VARNA_SCORE[bv], VARNA_SCORE[gv]
    # Boy's varna >= girl's varna → full point; else 0
    pts = 1.0 if bs >= gs else 0.0
    return pts, f"Boy: {bv}, Girl: {gv}"

# ── 2. VASYA (2 points) ──────────────────────────────────────────────
# Vasya groups: Chatushpada, Manava, Jalchar, Vanchar, Keeta

SIGN_VASYA = {
    "Aries": "Chatushpada", "Taurus": "Chatushpada",
    "Gemini": "Manava", "Cancer": "Jalchar",
    "Leo": "Vanchar", "Virgo": "Manava",
    "Libra": "Manava", "Scorpio": "Keeta",
    "Sagittarius": "Chatushpada", "Capricorn": "Jalchar",
    "Aquarius": "Manava", "Pisces": "Jalchar",
}

ZODIAC = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
          "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]

_VASYA_DOMINANCE: Dict[str, List[str]] = {
    "Chatushpada": ["Manava"],
    "Manava":      ["Chatushpada"],
    "Vanchar":     ["Chatushpada"],
    "Jalchar":     ["Vanchar"],
    "Keeta":       ["Jalchar"],
}

_VASYA_MUTUAL = {
    ("Manava", "Chatushpada"), ("Chatushpada", "Manava"),
    ("Chatushpada", "Vanchar"), ("Vanchar", "Chatushpada"),
}

def _vasya_score(boy_sign_idx: int, girl_sign_idx: int) -> Tuple[float, str]:
    bs = ZODIAC[boy_sign_idx]
    gs = ZODIAC[girl_sign_idx]
    bv = SIGN_VASYA[bs]
    gv = SIGN_VASYA[gs]
    if bv == gv:
        pts, note = 2.0, "Same Vasya group — very compatible"
    elif gv in _VASYA_DOMINANCE.get(bv, []):
        pts, note = 2.0, f"Boy ({bv}) dominates Girl ({gv}) — full points"
    elif bv in _VASYA_DOMINANCE.get(gv, []):
        pts, note = 0.5, f"Girl ({gv}) dominates Boy ({bv}) — partial"
    else:
        pts, note = 0.0, f"No Vasya relation: Boy ({bv}), Girl ({gv})"
    return pts, note

# ── 3. TARA (3 points) ───────────────────────────────────────────────

def _tara_score(boy_nak: int, girl_nak: int) -> Tuple[float, str]:
    """
    Count girl's nakshatra from boy's, divide by 9, check remainder.
    Auspicious remainders: 1,2,4,6,8 → 1.5 points each (max 3 for both directions)
    """
    _AUS = {1, 2, 4, 6, 8}
    def _tara(from_nak: int, to_nak: int) -> float:
        count = (to_nak - from_nak) % 27 + 1
        rem = ((count - 1) % 9) + 1
        return 1.5 if rem in _AUS else 0.0

    b_to_g = _tara(boy_nak, girl_nak)
    g_to_b = _tara(girl_nak, boy_nak)
    pts = b_to_g + g_to_b
    return pts, f"Boy→Girl: {b_to_g:.1f}, Girl→Boy: {g_to_b:.1f}"

# ── 4. YONI (4 points) ───────────────────────────────────────────────

NAK_YONI = [
    "Ashwa","Gaja","Mesha","Sarpa","Sarpa","Shwan","Marjara","Mesha","Marjara",
    "Mushaka","Gau","Gau","Mahisha","Vyaghra","Mahisha","Vyaghra","Mrig","Mrig",
    "Shwan","Vanara","Nakula","Vanara","Simha","Ashwa","Simha","Gaja","Gaja",
]

_YONI_ENEMY: Dict[str, str] = {
    "Ashwa": "Mahisha", "Mahisha": "Ashwa",
    "Gaja":  "Simha",   "Simha":   "Gaja",
    "Mesha": "Vanara",  "Vanara":  "Mesha",
    "Sarpa": "Nakula",  "Nakula":  "Sarpa",
    "Shwan": "Mrig",    "Mrig":    "Shwan",
    "Marjara":"Mushaka","Mushaka": "Marjara",
    "Gau":   "Vyaghra", "Vyaghra": "Gau",
    "Ashwa": "Mahisha",
}

_YONI_FRIENDLY: Dict[str, List[str]] = {
    "Ashwa": ["Ashwa"], "Gaja": ["Gaja"], "Mesha": ["Mesha"],
    "Sarpa": ["Sarpa"], "Shwan": ["Shwan"], "Marjara": ["Marjara"],
    "Gau": ["Gau"], "Mahisha": ["Mahisha"], "Vyaghra": ["Vyaghra"],
    "Mrig": ["Mrig"], "Vanara": ["Vanara"], "Nakula": ["Nakula"],
    "Simha": ["Simha"], "Mushaka": ["Mushaka"],
}

def _yoni_score(boy_nak: int, girl_nak: int) -> Tuple[float, str]:
    by, gy = NAK_YONI[boy_nak], NAK_YONI[girl_nak]
    if by == gy:
        return 4.0, f"Same Yoni ({by}) — maximum sexual compatibility"
    elif _YONI_ENEMY.get(by) == gy or _YONI_ENEMY.get(gy) == by:
        return 0.0, f"Enemy Yoni ({by} vs {gy}) — challenging"
    else:
        return 2.0, f"Neutral Yoni ({by} vs {gy}) — moderate"

# ── 5. GRAHA MAITRI (5 points) ───────────────────────────────────────

SIGN_LORD = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

_PLANET_FRIENDS: Dict[str, List[str]] = {
    "Sun":     ["Moon", "Mars", "Jupiter"],
    "Moon":    ["Sun", "Mercury"],
    "Mars":    ["Sun", "Moon", "Jupiter"],
    "Mercury": ["Sun", "Venus"],
    "Jupiter": ["Sun", "Moon", "Mars"],
    "Venus":   ["Mercury", "Saturn"],
    "Saturn":  ["Mercury", "Venus"],
    "Rahu":    ["Venus", "Saturn", "Mercury"],
    "Ketu":    ["Mars", "Venus", "Saturn"],
}

_PLANET_ENEMIES: Dict[str, List[str]] = {
    "Sun":     ["Venus", "Saturn"],
    "Moon":    ["Saturn"],
    "Mars":    ["Mercury"],
    "Mercury": ["Moon"],
    "Jupiter": ["Mercury", "Venus"],
    "Venus":   ["Sun", "Moon"],
    "Saturn":  ["Sun", "Moon", "Mars"],
}

def _planet_relation(p1: str, p2: str) -> str:
    if p1 == p2:
        return "same"
    friends = _PLANET_FRIENDS.get(p1, [])
    enemies = _PLANET_ENEMIES.get(p1, [])
    if p2 in friends:
        return "friend"
    elif p2 in enemies:
        return "enemy"
    return "neutral"

def _graha_maitri_score(boy_sign_idx: int, girl_sign_idx: int) -> Tuple[float, str]:
    bl = SIGN_LORD[ZODIAC[boy_sign_idx]]
    gl = SIGN_LORD[ZODIAC[girl_sign_idx]]

    b_to_g = _planet_relation(bl, gl)
    g_to_b = _planet_relation(gl, bl)

    if b_to_g == "same":
        return 5.0, f"Same lord ({bl}) — perfect Graha Maitri"
    elif b_to_g == "friend" and g_to_b == "friend":
        return 5.0, f"{bl} and {gl} are mutual friends — excellent"
    elif b_to_g == "friend" and g_to_b == "neutral":
        return 4.0, f"{bl} friendly to {gl} (neutral returned)"
    elif b_to_g == "neutral" and g_to_b == "friend":
        return 4.0, f"{gl} friendly to {bl} (neutral returned)"
    elif b_to_g == "neutral" and g_to_b == "neutral":
        return 3.0, f"Both {bl} and {gl} neutral to each other"
    elif b_to_g == "friend" and g_to_b == "enemy":
        return 1.0, f"{bl} friendly but {gl} hostile"
    elif b_to_g == "enemy" and g_to_b == "friend":
        return 1.0, f"{gl} friendly but {bl} hostile"
    elif b_to_g == "enemy" and g_to_b == "neutral":
        return 0.5, f"{bl} hostile to {gl}"
    elif b_to_g == "neutral" and g_to_b == "enemy":
        return 0.5, f"{gl} hostile to {bl}"
    else:
        return 0.0, f"{bl} and {gl} are mutual enemies — incompatible"

# ── 6. GANA (6 points) ───────────────────────────────────────────────
# 3 Ganas: Deva (divine), Manushya (human), Rakshasa (demonic)

NAK_GANA = [
    "Deva","Manushya","Rakshasa","Manushya","Deva","Manushya","Deva","Deva","Rakshasa",
    "Rakshasa","Manushya","Manushya","Deva","Rakshasa","Deva","Rakshasa","Deva","Rakshasa",
    "Rakshasa","Manushya","Manushya","Deva","Rakshasa","Deva","Manushya","Manushya","Deva",
]

_GANA_SCORES: Dict[Tuple[str,str], float] = {
    ("Deva",     "Deva"):     6.0,
    ("Manushya", "Manushya"): 6.0,
    ("Rakshasa", "Rakshasa"): 6.0,
    ("Deva",     "Manushya"): 5.0,
    ("Manushya", "Deva"):     5.0,
    ("Manushya", "Rakshasa"): 1.0,
    ("Rakshasa", "Manushya"): 1.0,
    ("Deva",     "Rakshasa"): 0.0,
    ("Rakshasa", "Deva"):     0.0,
}

def _gana_score(boy_nak: int, girl_nak: int) -> Tuple[float, str]:
    bg, gg = NAK_GANA[boy_nak], NAK_GANA[girl_nak]
    pts = _GANA_SCORES.get((bg, gg), 0.0)
    if pts == 6.0:
        note = f"Same Gana ({bg}) — excellent temperament match"
    elif pts >= 5.0:
        note = f"Compatible Ganas ({bg} & {gg}) — good"
    elif pts == 1.0:
        note = f"Challenging Ganas ({bg} & {gg}) — requires understanding"
    else:
        note = f"Incompatible Ganas ({bg} & {gg}) — significant temperament clash"
    return pts, note

# ── 7. BHAKUT (7 points) ─────────────────────────────────────────────

def _bhakut_score(boy_sign_idx: int, girl_sign_idx: int) -> Tuple[float, str]:
    """
    Compute the sign-to-sign relationship.
    Inauspicious: 6-8, 5-9, 3-11, 12-2 (and reverses)
    """
    diff = (girl_sign_idx - boy_sign_idx) % 12 + 1
    rev_diff = (boy_sign_idx - girl_sign_idx) % 12 + 1

    inauspicious_pairs = {(6,8),(8,6),(5,9),(9,5),(3,11),(11,3),(2,12),(12,2)}
    pair = (diff, rev_diff)

    if diff == 1:  # Same sign
        return 7.0, "Same Moon sign — perfect Bhakut"
    elif pair in inauspicious_pairs:
        return 0.0, f"Bhakut dosha ({diff}-{rev_diff} pattern) — relationship and health challenges"
    else:
        return 7.0, f"Bhakut compatible ({diff}-{rev_diff}) — positive"

# ── 8. NADI (8 points) ───────────────────────────────────────────────
# 3 Nadis: Adi (Vata), Madhya (Pitta), Antya (Kapha)

NAK_NADI = [
    "Adi","Madhya","Antya","Antya","Madhya","Adi","Adi","Madhya","Antya",
    "Antya","Madhya","Adi","Adi","Madhya","Antya","Antya","Madhya","Adi",
    "Adi","Madhya","Antya","Antya","Madhya","Adi","Adi","Madhya","Antya",
]

def _nadi_score(boy_nak: int, girl_nak: int) -> Tuple[float, str]:
    bn, gn = NAK_NADI[boy_nak], NAK_NADI[girl_nak]
    if bn == gn:
        return 0.0, (
            f"Nadi Dosha! Both have {bn} Nadi — health issues and progeny problems possible. "
            "Consider remedies."
        )
    return 8.0, f"Boy: {bn} Nadi, Girl: {gn} Nadi — compatible, no Nadi dosha"

# ── Rajju Dosha ──────────────────────────────────────────────────────

NAK_RAJJU = [
    "Siro","Kanta","Udara","Nabi","Nabi","Kanta","Pada","Pada","Kanta",
    "Siro","Siro","Nabi","Udara","Udara","Nabi","Siro","Kanta","Pada",
    "Pada","Kanta","Siro","Siro","Nabi","Udara","Udara","Nabi","Kanta",
]

def _rajju_check(boy_nak: int, girl_nak: int) -> Dict[str, Any]:
    br, gr = NAK_RAJJU[boy_nak], NAK_RAJJU[girl_nak]
    has_dosha = br == gr
    return {
        "has_dosha": has_dosha,
        "boy_rajju": br,
        "girl_rajju": gr,
        "severity": {
            "Pada": "Moderate (affects longevity of husband)",
            "Udara": "Severe (affects children and prosperity)",
            "Nabi": "Moderate (affects children)",
            "Kanta": "Severe (affects longevity of wife)",
            "Siro": "Most Severe (affects both)",
        }.get(br, "") if has_dosha else "",
        "note": f"Rajju Dosha present ({br}) — consider remedies." if has_dosha else "No Rajju Dosha",
    }

# ── Vedha Dosha ──────────────────────────────────────────────────────

_VEDHA_PAIRS = {
    (0, 18), (1, 16), (2, 7), (3, 21), (4, 20), (5, 19),
    (6, 25), (7, 2),  (8, 24), (9, 22), (10, 22), (11, 25),
    (12, 23), (13, 17), (14, 15),
}

def _vedha_check(boy_nak: int, girl_nak: int) -> Dict[str, Any]:
    pair = (min(boy_nak, girl_nak), max(boy_nak, girl_nak))
    has_dosha = pair in _VEDHA_PAIRS
    return {
        "has_dosha": has_dosha,
        "note": "Vedha Dosha present — can create obstacles in married life. Remedies advised." if has_dosha else "No Vedha Dosha",
    }

# ── Main Guna Milan function ─────────────────────────────────────────

def compute_guna_milan(
    boy_moon_sid: float,
    girl_moon_sid: float,
) -> Dict[str, Any]:
    """
    Complete 36-point Ashtakoot Milan calculation.

    Parameters
    ----------
    boy_moon_sid  : Boy's sidereal Moon longitude (0–360°)
    girl_moon_sid : Girl's sidereal Moon longitude (0–360°)

    Returns
    -------
    Full compatibility report with scores, doshas, and interpretation.
    """
    nak_span = 360.0 / 27.0
    boy_nak  = int(boy_moon_sid  / nak_span) % 27
    girl_nak = int(girl_moon_sid / nak_span) % 27
    boy_sign  = int(boy_moon_sid  / 30) % 12
    girl_sign = int(girl_moon_sid / 30) % 12

    # ── Compute all 8 kootas ──
    v1_pts, v1_note = _varna_score(boy_nak, girl_nak)
    v2_pts, v2_note = _vasya_score(boy_sign, girl_sign)
    v3_pts, v3_note = _tara_score(boy_nak, girl_nak)
    v4_pts, v4_note = _yoni_score(boy_nak, girl_nak)
    v5_pts, v5_note = _graha_maitri_score(boy_sign, girl_sign)
    v6_pts, v6_note = _gana_score(boy_nak, girl_nak)
    v7_pts, v7_note = _bhakut_score(boy_sign, girl_sign)
    v8_pts, v8_note = _nadi_score(boy_nak, girl_nak)

    total = v1_pts + v2_pts + v3_pts + v4_pts + v5_pts + v6_pts + v7_pts + v8_pts
    percentage = round(total / 36 * 100, 1)

    # ── Doshas ──
    rajju = _rajju_check(boy_nak, girl_nak)
    vedha = _vedha_check(boy_nak, girl_nak)

    # ── Verdict ──
    verdict, verdict_detail = _compatibility_verdict(
        total, v8_pts, v7_pts, v6_pts, rajju["has_dosha"], vedha["has_dosha"]
    )

    kootas = [
        {"name": "Varna",        "max": 1,  "score": v1_pts, "note": v1_note},
        {"name": "Vasya",        "max": 2,  "score": v2_pts, "note": v2_note},
        {"name": "Tara",         "max": 3,  "score": v3_pts, "note": v3_note},
        {"name": "Yoni",         "max": 4,  "score": v4_pts, "note": v4_note},
        {"name": "Graha Maitri", "max": 5,  "score": v5_pts, "note": v5_note},
        {"name": "Gana",         "max": 6,  "score": v6_pts, "note": v6_note},
        {"name": "Bhakut",       "max": 7,  "score": v7_pts, "note": v7_note},
        {"name": "Nadi",         "max": 8,  "score": v8_pts, "note": v8_note},
    ]

    return {
        "boy_nakshatra":  NAKSHATRA_NAMES[boy_nak],
        "girl_nakshatra": NAKSHATRA_NAMES[girl_nak],
        "boy_moon_sign":  ZODIAC[boy_sign],
        "girl_moon_sign": ZODIAC[girl_sign],
        "kootas": kootas,
        "total_score": round(total, 1),
        "max_score": 36,
        "percentage": percentage,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "doshas": {
            "rajju": rajju,
            "vedha": vedha,
            "nadi_dosha": v8_pts == 0.0,
            "bhakut_dosha": v7_pts == 0.0,
            "gana_dosha": v6_pts == 0.0,
        },
        "marriage_recommendation": _marriage_recommendation(total, rajju["has_dosha"], v8_pts),
    }


def _compatibility_verdict(
    total: float, nadi: float, bhakut: float,
    gana: float, rajju: bool, vedha: bool,
) -> Tuple[str, str]:
    # Major dosha override
    if nadi == 0 and rajju:
        return "Needs Careful Consideration", (
            "Nadi Dosha AND Rajju Dosha both present — these are major compatibility concerns "
            "affecting health and longevity. Expert astrological consultation strongly recommended "
            "before proceeding. Remedies can help reduce the impact."
        )
    if nadi == 0:
        return "Moderate (Nadi Dosha)", (
            f"Total score {total:.0f}/36 — however Nadi Dosha is present which can affect "
            "health and children. Consider remedies. If other factors are strong, can proceed with caution."
        )
    if bhakut == 0:
        return "Moderate (Bhakut Dosha)", (
            f"Score {total:.0f}/36 with Bhakut Dosha — relationship dynamics and health may be "
            "affected. Exception rules should be checked by an astrologer."
        )

    if total >= 32:
        return "Excellent Match ⭐", (
            f"Outstanding compatibility of {total:.0f}/36 ({total/36*100:.0f}%) — "
            "this is a rare and highly auspicious match. Both partners will complement "
            "each other perfectly in all life areas. Highly recommended."
        )
    elif total >= 28:
        return "Very Good Match", (
            f"Strong compatibility of {total:.0f}/36 ({total/36*100:.0f}%) — "
            "a very good match with excellent prospects for a harmonious marriage. "
            "Minor areas of difference can be worked through with communication."
        )
    elif total >= 24:
        return "Good Match", (
            f"Good compatibility of {total:.0f}/36 ({total/36*100:.0f}%) — "
            "above the recommended threshold of 18. The couple can have a happy and "
            "fulfilling life with mutual understanding and effort."
        )
    elif total >= 18:
        return "Average Match", (
            f"Acceptable compatibility of {total:.0f}/36 ({total/36*100:.0f}%) — "
            "above the minimum threshold. Some areas will require conscious effort "
            "and adjustment. Not ideal but workable."
        )
    elif total >= 13:
        return "Below Average", (
            f"Compatibility of {total:.0f}/36 ({total/36*100:.0f}%) is below the recommended "
            "minimum of 18 points. Significant areas of incompatibility exist. "
            "Proceed only after careful astrological consultation."
        )
    else:
        return "Poor Match", (
            f"Low compatibility of {total:.0f}/36 ({total/36*100:.0f}%) — not recommended "
            "without thorough astrological analysis and remedial measures."
        )


def _marriage_recommendation(total: float, rajju: bool, nadi_pts: float) -> str:
    lines = []
    if total >= 28 and not rajju and nadi_pts > 0:
        lines.append("✅ Highly recommended for marriage — excellent Guna Milan score with no major doshas.")
    elif total >= 18 and nadi_pts > 0:
        lines.append("✅ Acceptable for marriage — meets the minimum threshold of 18 Gunas.")
    else:
        lines.append("⚠️ Consult an experienced astrologer before proceeding.")

    if rajju:
        lines.append("⚠️ Rajju Dosha present — Rajju Shanti puja recommended before marriage.")
    if nadi_pts == 0:
        lines.append("⚠️ Nadi Dosha present — Nadi Nivarana remedies (Go-Daan or Mahamrityunjaya Japa) advised.")

    return " ".join(lines)


# ── Mangal Dosha ─────────────────────────────────────────────────────

def check_mangal_dosha(
    planet_houses: Dict[str, int],
    lagna_sign: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check for Mangal Dosha (Kuja Dosha / Angaraka Dosha).

    Mars in houses 1, 2, 4, 7, 8, or 12 from Lagna, Moon, or Venus
    causes Mangal Dosha.

    Parameters
    ----------
    planet_houses : dict of planet → house number (1-based) from Lagna
    """
    mars_house = planet_houses.get("Mars")
    if mars_house is None:
        return {"has_dosha": False, "note": "Mars position unknown"}

    _MANGAL_HOUSES = {1, 2, 4, 7, 8, 12}
    has_dosha = mars_house in _MANGAL_HOUSES

    # Check exceptions
    exceptions = []

    # Exception 1: Mars in own sign (Aries, Scorpio) or exalted (Capricorn)
    mars_sign = planet_houses.get("Mars_sign", "")
    if mars_sign in {"Aries", "Scorpio", "Capricorn"}:
        exceptions.append(f"Mars in {mars_sign} — own/exaltation sign reduces Dosha")

    # Exception 2: Mars aspected by Jupiter
    jupiter_house = planet_houses.get("Jupiter", 0)
    if jupiter_house and abs(jupiter_house - mars_house) in {5, 7, 9}:
        exceptions.append("Jupiter aspects Mars — Dosha significantly reduced")

    # Exception 3: If both partners have Mangal Dosha, it cancels
    exceptions.append("Note: If both partners have Mangal Dosha, it cancels out")

    intensity = "High" if mars_house in {7, 8} else ("Moderate" if mars_house in {1, 2} else "Mild")

    return {
        "has_dosha": has_dosha,
        "mars_house": mars_house,
        "intensity": intensity if has_dosha else "None",
        "house_effect": {
            1:  "Affects personality and health of self",
            2:  "Affects wealth, family, and speech",
            4:  "Affects home, mother, domestic peace",
            7:  "Directly affects spouse — most impactful position",
            8:  "Affects longevity and in-laws",
            12: "Affects bed pleasures and foreign residence",
        }.get(mars_house, "") if has_dosha else "",
        "exceptions": exceptions,
        "remedy": (
            "Kumbh Vivah (ritual marriage to a tree or pot) before marriage, "
            "Mangal Shanti puja, and reciting Mangal Stotram on Tuesdays."
        ) if has_dosha and not exceptions else "No major remedy required",
        "note": (
            f"Mangal Dosha: Mars in House {mars_house} — {intensity} intensity. "
            + (f"Exceptions apply: {'; '.join(exceptions)}" if exceptions else "")
        ) if has_dosha else f"No Mangal Dosha — Mars in House {mars_house}",
    }
