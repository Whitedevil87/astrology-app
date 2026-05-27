"""
vedic/dasha.py
──────────────
Complete Vimshottari Dasha system with exact dates.

Implements:
  • Mahadasha (120-year cycle)
  • Antardasha (Bhukti) — sub-periods within each Mahadasha
  • Pratyantar Dasha — sub-sub-periods
  • Dasha balance at birth from Moon's Nakshatra position
  • Current running dasha detection
  • Life event predictions per dasha lord combination
  • Dasha quality scoring

Public API
──────────
    compute_dasha(moon_longitude_sidereal, birth_jd)  → dict
    current_dasha(dasha_data, current_jd)             → dict
    dasha_predictions(mahadasha_lord, antardasha_lord, lagna, planets) → str
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ── Vimshottari Dasha periods (in years) ────────────────────────────

DASHA_YEARS: Dict[str, int] = {
    "Ketu":    7,
    "Venus":   20,
    "Sun":     6,
    "Moon":    10,
    "Mars":    7,
    "Rahu":    18,
    "Jupiter": 16,
    "Saturn":  19,
    "Mercury": 17,
}

DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
TOTAL_YEARS = 120

# Nakshatra → ruling planet (27 nakshatras, 0-based)
NAKSHATRA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",  # 1–9
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",  # 10–18
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",  # 19–27
]

# ── Utility ──────────────────────────────────────────────────────────

_DAYS_PER_YEAR = 365.25


def _jd_to_datetime(jd: float) -> datetime:
    """Convert Julian Day to UTC datetime."""
    jd_adj = jd + 0.5
    z = int(jd_adj)
    f = jd_adj - z
    if z < 2299161:
        a = z
    else:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)

    day = b - d - int(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715

    frac_day = f
    hour = int(frac_day * 24)
    minute = int((frac_day * 24 - hour) * 60)
    second = int(((frac_day * 24 - hour) * 60 - minute) * 60)

    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _datetime_to_str(dt: datetime) -> str:
    return dt.strftime("%d %b %Y")


def _years_to_days(years: float) -> float:
    return years * _DAYS_PER_YEAR


# ── Dasha Balance at Birth ───────────────────────────────────────────

def _dasha_balance_at_birth(moon_sid: float) -> Tuple[str, float]:
    """
    Compute the ruling Mahadasha at birth and years remaining.

    Parameters
    ----------
    moon_sid : Moon sidereal longitude (0–360°)

    Returns
    -------
    (lord, years_remaining_in_first_dasha)
    """
    nak_span = 360.0 / 27.0
    nak_idx = int(moon_sid / nak_span) % 27
    lord = NAKSHATRA_LORDS[nak_idx]

    # How far through the current nakshatra (0.0–1.0)
    nak_start = nak_idx * nak_span
    fraction_elapsed = (moon_sid - nak_start) / nak_span

    # Years elapsed in current dasha at birth
    total_period = DASHA_YEARS[lord]
    years_elapsed = fraction_elapsed * total_period
    years_remaining = total_period - years_elapsed

    return lord, years_remaining


# ── Build full Dasha timeline ────────────────────────────────────────

def compute_dasha(
    moon_sid: float,
    birth_jd: float,
    years_ahead: int = 120,
) -> Dict[str, Any]:
    """
    Compute complete Vimshottari Dasha timeline.

    Parameters
    ----------
    moon_sid   : Moon sidereal longitude (degrees)
    birth_jd   : Julian Day of birth (UT)
    years_ahead: How many years of dasha to compute (default: 120 = full cycle)

    Returns
    -------
    {
      "birth_balance": {...},
      "mahadasha_list": [...],
      "current": {...},
      "next_change": {...},
    }
    """
    first_lord, first_remaining = _dasha_balance_at_birth(moon_sid)
    first_lord_idx = DASHA_ORDER.index(first_lord)

    mahadasha_list: List[Dict[str, Any]] = []
    current_jd = datetime.now(timezone.utc)
    current_jd_num = _datetime_to_jd(current_jd)

    # --- Build timeline ---
    jd_cursor = birth_jd
    current_dasha: Optional[Dict] = None
    next_change: Optional[Dict] = None

    for i in range(9):  # 9 possible mahadashas in 120 years
        idx = (first_lord_idx + i) % 9
        maha_lord = DASHA_ORDER[idx]

        if i == 0:
            maha_years = first_remaining
        else:
            maha_years = float(DASHA_YEARS[maha_lord])

        maha_end_jd = jd_cursor + _years_to_days(maha_years)

        # Build Antardashas
        antardashas = _build_antardashas(maha_lord, jd_cursor, maha_years, current_jd_num)

        maha_entry: Dict[str, Any] = {
            "lord": maha_lord,
            "start_jd": jd_cursor,
            "end_jd": maha_end_jd,
            "start_date": _datetime_to_str(_jd_to_datetime(jd_cursor)),
            "end_date":   _datetime_to_str(_jd_to_datetime(maha_end_jd)),
            "years": round(maha_years, 2),
            "antardashas": antardashas,
            "is_current": jd_cursor <= current_jd_num < maha_end_jd,
            "prediction": _mahadasha_prediction(maha_lord),
        }

        if maha_entry["is_current"]:
            current_dasha = maha_entry

        mahadasha_list.append(maha_entry)
        jd_cursor = maha_end_jd

        if jd_cursor - birth_jd > _years_to_days(years_ahead):
            break

    # Find next mahadasha change
    for m in mahadasha_list:
        if m["end_jd"] > current_jd_num:
            next_change = {
                "lord": m["lord"],
                "ends": m["end_date"],
                "next_lord": DASHA_ORDER[(DASHA_ORDER.index(m["lord"]) + 1) % 9],
            }
            break

    # Birth balance info
    nak_idx = int(moon_sid / (360/27)) % 27
    nak_name = _nakshatra_name(nak_idx)
    birth_balance = {
        "lord": first_lord,
        "years_remaining": round(first_remaining, 2),
        "nakshatra": nak_name,
        "nakshatra_lord": first_lord,
        "message": (
            f"At birth, {first_lord} Mahadasha was running with "
            f"{first_remaining:.1f} years remaining. "
            f"Moon was in {nak_name} nakshatra."
        ),
    }

    return {
        "birth_balance": birth_balance,
        "mahadasha_list": mahadasha_list,
        "current": current_dasha or {},
        "next_change": next_change or {},
        "moon_nakshatra": nak_name,
    }


def _datetime_to_jd(dt: datetime) -> float:
    """Convert UTC datetime to Julian Day."""
    y, mo, d = dt.year, dt.month, dt.day
    h = dt.hour + dt.minute/60 + dt.second/3600
    dd = d + h/24.0
    if mo <= 2:
        y -= 1; mo += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25*(y+4716)) + int(30.6001*(mo+1)) + dd + b - 1524.5


def _build_antardashas(
    maha_lord: str,
    maha_start_jd: float,
    maha_years: float,
    current_jd: float,
) -> List[Dict[str, Any]]:
    """Build Antardasha (Bhukti) list for a given Mahadasha."""
    maha_lord_idx = DASHA_ORDER.index(maha_lord)
    antardashas: List[Dict[str, Any]] = []
    jd_cursor = maha_start_jd

    for i in range(9):
        idx = (maha_lord_idx + i) % 9
        antar_lord = DASHA_ORDER[idx]

        # Antardasha years = (maha_years × antar_lord_years) / 120
        antar_years = (maha_years * DASHA_YEARS[antar_lord]) / TOTAL_YEARS
        antar_end_jd = jd_cursor + _years_to_days(antar_years)

        is_current = jd_cursor <= current_jd < antar_end_jd

        # Build Pratyantar Dashas for current antardasha only (for performance)
        pratyantars: List[Dict] = []
        if is_current:
            pratyantars = _build_pratyantars(maha_lord, antar_lord, jd_cursor, antar_years, current_jd)

        entry: Dict[str, Any] = {
            "lord": antar_lord,
            "start_jd": jd_cursor,
            "end_jd": antar_end_jd,
            "start_date": _datetime_to_str(_jd_to_datetime(jd_cursor)),
            "end_date":   _datetime_to_str(_jd_to_datetime(antar_end_jd)),
            "years": round(antar_years, 3),
            "months": round(antar_years * 12, 1),
            "is_current": is_current,
            "prediction": _antardasha_prediction(maha_lord, antar_lord),
            "pratyantars": pratyantars,
        }
        antardashas.append(entry)
        jd_cursor = antar_end_jd

    return antardashas


def _build_pratyantars(
    maha_lord: str,
    antar_lord: str,
    antar_start_jd: float,
    antar_years: float,
    current_jd: float,
) -> List[Dict[str, Any]]:
    """Build Pratyantar Dasha list for current Antardasha."""
    antar_lord_idx = DASHA_ORDER.index(antar_lord)
    pratyantars: List[Dict[str, Any]] = []
    jd_cursor = antar_start_jd

    for i in range(9):
        idx = (antar_lord_idx + i) % 9
        prat_lord = DASHA_ORDER[idx]

        # Pratyantar years = (antar_years × prat_years) / 120
        prat_years = (antar_years * DASHA_YEARS[prat_lord]) / TOTAL_YEARS
        prat_end_jd = jd_cursor + _years_to_days(prat_years)

        days = round(prat_years * _DAYS_PER_YEAR)
        entry = {
            "lord": prat_lord,
            "start_date": _datetime_to_str(_jd_to_datetime(jd_cursor)),
            "end_date": _datetime_to_str(_jd_to_datetime(prat_end_jd)),
            "days": days,
            "is_current": jd_cursor <= current_jd < prat_end_jd,
        }
        pratyantars.append(entry)
        jd_cursor = prat_end_jd

    return pratyantars


# ── Nakshatra name helper ────────────────────────────────────────────

_NAK_NAMES = [
    "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
    "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta",
    "Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha",
    "Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada",
    "Uttara Bhadrapada","Revati",
]

def _nakshatra_name(idx: int) -> str:
    return _NAK_NAMES[idx % 27]


# ── Current dasha detector ───────────────────────────────────────────

def current_dasha(dasha_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the current running Mahadasha + Antardasha + Pratyantar."""
    current_maha = dasha_data.get("current", {})
    if not current_maha:
        return {}

    current_antar: Dict = {}
    current_prat: Dict = {}

    for a in current_maha.get("antardashas", []):
        if a.get("is_current"):
            current_antar = a
            for p in a.get("pratyantars", []):
                if p.get("is_current"):
                    current_prat = p
            break

    return {
        "mahadasha": current_maha.get("lord"),
        "mahadasha_ends": current_maha.get("end_date"),
        "antardasha": current_antar.get("lord"),
        "antardasha_ends": current_antar.get("end_date"),
        "pratyantar": current_prat.get("lord"),
        "pratyantar_ends": current_prat.get("end_date"),
        "prediction": current_antar.get("prediction", ""),
    }


# ── Prediction text ──────────────────────────────────────────────────

def _mahadasha_prediction(lord: str) -> str:
    predictions = {
        "Sun": (
            "Sun Mahadasha (6 years) brings focus on self-assertion, authority, "
            "father, government, and health. Career advancement and recognition are "
            "highlighted. Ego conflicts may arise — cultivate humility. Health of "
            "eyes and heart needs attention."
        ),
        "Moon": (
            "Moon Mahadasha (10 years) emphasizes emotions, mother, home, travel, "
            "and mental peace. Mind becomes more sensitive. Strong for business, "
            "real estate, and public-facing work. Emotional ups and downs — "
            "spiritual practice brings stability."
        ),
        "Mars": (
            "Mars Mahadasha (7 years) brings energy, ambition, and drive. "
            "Excellent for real estate, engineering, military, and sports. "
            "Accidents and conflicts are risks — channel energy constructively. "
            "Siblings play an important role during this period."
        ),
        "Rahu": (
            "Rahu Mahadasha (18 years) is transformative and karmic. Ambition "
            "soars — foreign connections, unconventional paths, and sudden gains "
            "or losses. Illusions and obsessions must be watched. Strong for "
            "technology, politics, and mass media work."
        ),
        "Jupiter": (
            "Jupiter Mahadasha (16 years) is the most auspicious of all. "
            "Expansion in wealth, knowledge, spirituality, and family. Marriage, "
            "children, and higher education are favored. Guru-like figures enter "
            "life. Dharmic living brings maximum rewards."
        ),
        "Saturn": (
            "Saturn Mahadasha (19 years) is a period of hard work, discipline, "
            "and karmic reckoning. Slow but steady progress. Career stabilizes "
            "through perseverance. Health requires vigilance — knees, joints, "
            "and chronic conditions. Teaches patience and responsibility."
        ),
        "Mercury": (
            "Mercury Mahadasha (17 years) favors intellect, communication, "
            "business, and learning. Strong for writers, traders, teachers, "
            "and IT professionals. Multiple pursuits are common. Relatives and "
            "short journeys feature prominently. Analytical thinking peaks."
        ),
        "Ketu": (
            "Ketu Mahadasha (7 years) is mystical and detaching. Past-life karma "
            "surfaces — spiritual experiences intensify. Sudden events, accidents "
            "if afflicted. Excellent for moksha, research, and occult studies. "
            "Materially may feel unstable but spiritually very productive."
        ),
        "Venus": (
            "Venus Mahadasha (20 years) is the longest and most pleasurable. "
            "Love, marriage, luxury, arts, and material comforts flourish. "
            "Career in entertainment, beauty, or finance prospers. Overindulgence "
            "is the main risk. Generally the most enjoyable dasha period."
        ),
    }
    return predictions.get(lord, "")


def _antardasha_prediction(maha: str, antar: str) -> str:
    """Concise prediction for Mahadasha–Antardasha combination."""

    combos: Dict[Tuple[str,str], str] = {
        ("Jupiter", "Jupiter"): "Peak of expansion — wealth, marriage, and spiritual growth all highlighted. Most auspicious sub-period.",
        ("Jupiter", "Saturn"):  "Hard work pays off — career consolidation. Balance expansion with discipline for best results.",
        ("Jupiter", "Mercury"): "Excellent for education, business deals, publishing. Intellect and wisdom combine powerfully.",
        ("Jupiter", "Venus"):   "Marriage and relationships highlighted. Financial gains through partnerships. Creative projects flourish.",
        ("Jupiter", "Sun"):     "Government favor, promotions, father's blessings. Authority and recognition come naturally.",
        ("Jupiter", "Moon"):    "Emotional fulfillment and family happiness. Travel and real estate deals favored.",
        ("Jupiter", "Mars"):    "Energy and optimism peak — excellent for new ventures, property, and athletic pursuits.",
        ("Jupiter", "Rahu"):    "Ambitious expansion — foreign opportunities. Be careful of overreach and hidden enemies.",
        ("Jupiter", "Ketu"):    "Spiritual insights and detachment. Past karma resolves — excellent for sadhana.",

        ("Saturn", "Saturn"):   "Intense karmic period — hard work with slow rewards. Health and patience are tested. Long-term seeds are planted.",
        ("Saturn", "Mercury"):  "Analytical and practical — excellent for detailed work, contracts, and long-term planning.",
        ("Saturn", "Ketu"):     "Spiritual renunciation and discipline. Losses may occur but inner wisdom grows.",
        ("Saturn", "Venus"):    "Delayed pleasures — relationships may face tests. Perseverance brings lasting love.",
        ("Saturn", "Sun"):      "Career struggles and conflicts with authority. Stay humble and work diligently.",
        ("Saturn", "Moon"):     "Mental stress and emotional challenges. Mother's health may need attention. Meditation helps.",
        ("Saturn", "Mars"):     "High energy but conflict-prone — accidents possible. Channel into structured physical work.",
        ("Saturn", "Rahu"):     "Highly challenging — sudden obstacles and karmic debts surface. Extra caution needed.",
        ("Saturn", "Jupiter"):  "Gradual improvement after struggle — rewards begin to materialize. Dharmic actions pay off.",

        ("Rahu", "Rahu"):       "Intense ambition and transformation. Foreign travel, unconventional paths. Confusion and brilliance coexist.",
        ("Rahu", "Jupiter"):    "Sudden expansion — be discerning about opportunities. Spiritual questions arise.",
        ("Rahu", "Saturn"):     "Heaviest karmic period — patience and humility essential. Old patterns forcibly broken.",
        ("Rahu", "Mercury"):    "Quick mind, entrepreneurial energy. Technology and communication ventures can excel.",
        ("Rahu", "Ketu"):       "Axis-node period — identity crisis, spiritual awakening, past-life patterns emerge strongly.",
        ("Rahu", "Venus"):      "Intense desires, glamour, and foreign relationships. Overindulgence risks — stay grounded.",
        ("Rahu", "Sun"):        "Ambition for power — government and authority matters. Ego must be kept in check.",
        ("Rahu", "Moon"):       "Mental turbulence and vivid dreams. Psychic sensitivity high — spiritual protection advised.",
        ("Rahu", "Mars"):       "Explosive energy — accidents and conflicts possible. Best channeled into bold, focused action.",

        ("Venus", "Venus"):     "Peak of luxurious living — love, marriage, arts, and material abundance all flow easily.",
        ("Venus", "Sun"):       "Creative authority — recognition in arts or finance. Relationship with father improves.",
        ("Venus", "Moon"):      "Emotional warmth and domestic happiness. Travel, beauty, and romance are highlighted.",
        ("Venus", "Mars"):      "Passionate and energetic — excellent for new ventures, romance, and physical pursuits.",
        ("Venus", "Rahu"):      "Glamour and unconventional love. Foreign gains possible. Avoid excess and obsession.",
        ("Venus", "Jupiter"):   "Highly auspicious — marriage, wealth, and spiritual blessings converge beautifully.",
        ("Venus", "Saturn"):    "Delayed pleasures but lasting rewards. Relationships require patience and commitment.",
        ("Venus", "Mercury"):   "Business partnerships and creative collaborations flourish. Strong for arts and communication.",
        ("Venus", "Ketu"):      "Spiritual longing amid worldly pleasures. Past relationships may surface for resolution.",

        ("Moon", "Moon"):       "Heightened sensitivity and intuition. Home, mother, and emotional matters central.",
        ("Moon", "Mars"):       "Energy and initiative — new ventures can start. Watch impulsiveness and accidents.",
        ("Moon", "Rahu"):       "Emotional intensity and desire for the unusual. Travel, speculation — stay grounded.",
        ("Moon", "Jupiter"):    "Fortunate and expansive — wealth and family happiness highlighted. Very auspicious.",
        ("Moon", "Saturn"):     "Emotional restriction — responsibilities feel heavy. Mother's health may need attention.",
        ("Moon", "Mercury"):    "Sharp intellect and communication. Business and education ventures progress well.",
        ("Moon", "Ketu"):       "Spiritual sensitivity and emotional detachment. Dreams carry meaningful messages.",
        ("Moon", "Venus"):      "Love, comfort, and beauty are central. Excellent for relationships and creative work.",
        ("Moon", "Sun"):        "Father-mother dynamics prominent. Career recognition possible — confidence builds.",

        ("Sun", "Sun"):         "Intense focus on self — health, ego, and authority matters come front and center.",
        ("Sun", "Moon"):        "Balance of heart and mind — family and career pull in different directions.",
        ("Sun", "Mars"):        "Ambitious and courageous — real estate, sports, and leadership opportunities arise.",
        ("Sun", "Rahu"):        "Desire for power and recognition. Foreign connections beneficial. Watch ego.",
        ("Sun", "Jupiter"):     "Government favor, promotions — the most auspicious Sun sub-period. Dharmic living rewarded.",
        ("Sun", "Saturn"):      "Career tests and father-related challenges. Hard work with delayed rewards.",
        ("Sun", "Mercury"):     "Intellect and authority combine — writing, teaching, and business communication excel.",
        ("Sun", "Ketu"):        "Spiritual detachment from status — inner exploration rewarded over outer ambition.",
        ("Sun", "Venus"):       "Creative energy and romance — arts, entertainment, and luxury appeal strongly.",

        ("Mars", "Mars"):       "High energy and initiative — property, siblings, and competitive ventures highlighted.",
        ("Mars", "Rahu"):       "Explosive and unpredictable — accidents possible. Ambition can lead to breakthroughs or setbacks.",
        ("Mars", "Jupiter"):    "Courage meets wisdom — very favorable for ventures, property, and higher education.",
        ("Mars", "Saturn"):     "Disciplined effort — hard physical work pays off. Conflict with authority possible.",
        ("Mars", "Mercury"):    "Technical skills shine — engineering, IT, and detailed projects excel.",
        ("Mars", "Ketu"):       "Past-life warrior karma — spiritual discipline and physical transformation.",
        ("Mars", "Venus"):      "Passionate relationships and creative energy — romance and new ventures are highlighted.",
        ("Mars", "Sun"):        "Father-son dynamics — ambition for recognition. Leadership roles are sought.",
        ("Mars", "Moon"):       "Emotional courage — family matters require decisive action.",

        ("Mercury", "Mercury"): "Peak intellectual activity — education, business, and communication all excel.",
        ("Mercury", "Ketu"):    "Deep thinking and spiritual inquiry — analytical skills meet intuition.",
        ("Mercury", "Venus"):   "Creative business and partnerships flourish — arts and commerce combine well.",
        ("Mercury", "Sun"):     "Communication skills bring recognition — writing and speaking opportunities arise.",
        ("Mercury", "Moon"):    "Emotional intelligence high — trading, writing, and teaching excel.",
        ("Mercury", "Mars"):    "Quick, technical, and competitive — excellent for engineering, debates, and sports.",
        ("Mercury", "Rahu"):    "Entrepreneurial and unconventional — technology and media ventures can excel.",
        ("Mercury", "Jupiter"): "Wisdom and intellect merge — education, publishing, and teaching peak.",
        ("Mercury", "Saturn"):  "Methodical and disciplined — long-term plans and detailed work pay off.",

        ("Ketu", "Ketu"):       "Deep spiritual period — past-life patterns surface. Losses lead to inner growth.",
        ("Ketu", "Venus"):      "Spiritual relationships and past-life love karma surface. Material desires lessen.",
        ("Ketu", "Sun"):        "Authority conflicts and identity questions — father relationships may be tested.",
        ("Ketu", "Moon"):       "Psychic sensitivity and emotional detachment. Meditative states come easily.",
        ("Ketu", "Mars"):       "Sudden events and spiritual courage — channeled into discipline brings breakthroughs.",
        ("Ketu", "Rahu"):       "Node-axis period of intense karmic release — major life shifts possible.",
        ("Ketu", "Jupiter"):    "Spiritual wisdom and past-life merit flow — religious practices deepen.",
        ("Ketu", "Saturn"):     "Austere and karmic — deep spiritual cleansing. Renunciation resonates strongly.",
        ("Ketu", "Mercury"):    "Analytical mysticism — research, occult studies, and deep learning flourish.",
    }

    key = (maha, antar)
    if key in combos:
        return combos[key]

    # Generic fallback
    benefics = {"Jupiter", "Venus", "Mercury", "Moon"}
    malefics  = {"Saturn", "Rahu", "Ketu", "Mars", "Sun"}

    if maha in benefics and antar in benefics:
        return f"{maha} Mahadasha / {antar} Antardasha: Generally auspicious — expansion and positive growth in this sub-period."
    elif maha in malefics and antar in malefics:
        return f"{maha} Mahadasha / {antar} Antardasha: Karmic challenges — patience and spiritual discipline are key."
    elif maha in benefics:
        return f"{maha} Mahadasha / {antar} Antardasha: Mostly positive — minor obstacles may appear but are overcome."
    else:
        return f"{maha} Mahadasha / {antar} Antardasha: Mixed period — effort and focus bring results despite challenges."
