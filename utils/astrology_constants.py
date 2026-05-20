"""
Celestial Arc — Vedic astrology constants and reference data.
All rulers follow traditional Vedic (Jyotish) assignments — no outer planets.
"""

from typing import Dict, List, Any

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# ── Vedic Zodiac Meta (traditional rulers only) ─────────────────────

ZODIAC_META: Dict[str, Dict[str, str]] = {
    "Aries":       {"element": "Fire",  "modality": "Cardinal", "ruler": "Mars",    "glyph": "\u2648"},
    "Taurus":      {"element": "Earth", "modality": "Fixed",    "ruler": "Venus",   "glyph": "\u2649"},
    "Gemini":      {"element": "Air",   "modality": "Mutable",  "ruler": "Mercury", "glyph": "\u264A"},
    "Cancer":      {"element": "Water", "modality": "Cardinal", "ruler": "Moon",    "glyph": "\u264B"},
    "Leo":         {"element": "Fire",  "modality": "Fixed",    "ruler": "Sun",     "glyph": "\u264C"},
    "Virgo":       {"element": "Earth", "modality": "Mutable",  "ruler": "Mercury", "glyph": "\u264D"},
    "Libra":       {"element": "Air",   "modality": "Cardinal", "ruler": "Venus",   "glyph": "\u264E"},
    "Scorpio":     {"element": "Water", "modality": "Fixed",    "ruler": "Mars",    "glyph": "\u264F"},
    "Sagittarius": {"element": "Fire",  "modality": "Mutable",  "ruler": "Jupiter", "glyph": "\u2650"},
    "Capricorn":   {"element": "Earth", "modality": "Cardinal", "ruler": "Saturn",  "glyph": "\u2651"},
    "Aquarius":    {"element": "Air",   "modality": "Fixed",    "ruler": "Saturn",  "glyph": "\u2652"},
    "Pisces":      {"element": "Water", "modality": "Mutable",  "ruler": "Jupiter", "glyph": "\u2653"},
}

# ── Personality (Simple English + light Hinglish) ────────────────────

PERSONALITY_RULES = {
    "Aries":       "bold and action-oriented — always the first to step forward",
    "Taurus":      "steady, grounded, and loyal — a symbol of patience and stability",
    "Gemini":      "curious, social, and quick-minded — eager to learn about everything",
    "Cancer":      "protective, intuitive, and empathetic — deeply cares for loved ones",
    "Leo":         "charismatic, proud, and heart-led — a natural leader who inspires everyone",
    "Virgo":       "analytical, practical, and detail-focused — always follows the path of perfection",
    "Libra":       "harmonious, diplomatic, and refined — loves balance and beauty",
    "Scorpio":     "intense, strategic, and emotionally deep — incredibly strong from within",
    "Sagittarius": "optimistic, adventurous, and philosophical — explores new horizons",
    "Capricorn":   "disciplined, responsible, and ambitious — slow but powerful growth",
    "Aquarius":    "independent, inventive, and visionary — possesses a unique way of thinking",
    "Pisces":      "imaginative, sensitive, and spiritually tuned — a creative and intuitive soul",
}

CAREER_RULES = {
    "Aries":       "leadership, startups, athletics, emergency response",
    "Taurus":      "finance, design, real estate, food or luxury industries",
    "Gemini":      "media, sales, teaching, communications, writing roles",
    "Cancer":      "counseling, hospitality, healthcare, caregiving fields",
    "Leo":         "public leadership, entertainment, branding, entrepreneurship",
    "Virgo":       "analysis, engineering, medicine, operations excellence",
    "Libra":       "law, diplomacy, design, client-facing strategy",
    "Scorpio":     "research, psychology, investigation, occult sciences",
    "Sagittarius": "travel, higher education, publishing, consulting",
    "Capricorn":   "management, government, finance, long-term planning",
    "Aquarius":    "technology, innovation, social impact, science",
    "Pisces":      "arts, healing, storytelling, spiritual guidance",
}

STRENGTH_BLURBS = {
    "Aries":       "Courageous initiative, honest drive — takes action on what they believe in.",
    "Taurus":      "Patient endurance, loyal devotion — stands firm even in difficult times.",
    "Gemini":      "Quick learning, witty communication — can handle any situation with ease.",
    "Cancer":      "Protective intuition, deep empathy — will do anything for their loved ones.",
    "Leo":         "Generous warmth, creative confidence — a natural-born leader.",
    "Virgo":       "Precision, helpfulness — turns chaos into perfect order.",
    "Libra":       "Diplomatic grace, aesthetic taste — brings balance wherever they go.",
    "Scorpio":     "Emotional courage, strategic focus — never afraid of challenges.",
    "Sagittarius": "Optimistic vision, honest philosophy — finds victory beyond fear.",
    "Capricorn":   "Discipline, integrity — achieves the top through quiet, hard work.",
    "Aquarius":    "Original thinking, humanitarian ideals — thinks completely out of the box.",
    "Pisces":      "Compassion, imagination — understands others deeply from the heart.",
}

WEAKNESS_BLURBS = {
    "Aries":       "Impatience, sharp reactions — sometimes speaks without thinking.",
    "Taurus":      "Stubborn nature, slow to change — finds it difficult to leave their comfort zone.",
    "Gemini":      "Scattered focus, overthinking — needs to learn to concentrate on one task.",
    "Cancer":      "Mood swings, over-sensitive — tends to take small things to heart.",
    "Leo":         "Pride, spotlight hunger — ego can occasionally take over.",
    "Virgo":       "Self-criticism, worry loops — the quest for perfection can halt progress.",
    "Libra":       "People-pleasing, indecision — forgets themselves while trying to keep everyone happy.",
    "Scorpio":     "Intensity, secrecy — prone to trust issues and controlling habits.",
    "Sagittarius": "Over-promising, blunt honesty — needs to filter their words sometimes.",
    "Capricorn":   "Workaholic, emotionally reserved — should learn to share their feelings more.",
    "Aquarius":    "Detached nature, unpredictable — occasionally struggles to form emotional connections.",
    "Pisces":      "Escapism, porous boundaries — absorbs the stress and problems of others.",
}

LUCKY_DAYS = {
    "Aries": "Tuesday", "Taurus": "Friday", "Gemini": "Wednesday",
    "Cancer": "Monday", "Leo": "Sunday", "Virgo": "Wednesday",
    "Libra": "Friday", "Scorpio": "Tuesday", "Sagittarius": "Thursday",
    "Capricorn": "Saturday", "Aquarius": "Saturday", "Pisces": "Thursday",
}

ELEMENT_COLORS = {
    "Fire": "Gold & crimson",
    "Earth": "Forest green & clay",
    "Air": "Sky blue & silver",
    "Water": "Indigo & sea glass",
}

# ── House Meanings (Vedic / Bhava) ───────────────────────────────────

HOUSE_MEANINGS = {
    1:  "Self, body, temperament, life direction (Lagna)",
    2:  "Wealth, speech, family, values (Dhana)",
    3:  "Siblings, courage, short journeys, skills (Sahaj)",
    4:  "Home, mother, comfort, roots (Sukha)",
    5:  "Children, creativity, romance, intellect (Putra)",
    6:  "Health, service, debts, competition (Ari)",
    7:  "Marriage, partnerships, contracts (Yuvati)",
    8:  "Transformations, shared resources, longevity (Randhra)",
    9:  "Dharma, higher learning, luck, guru (Bhagya)",
    10: "Career, status, authority, reputation (Karma)",
    11: "Gains, friends, aspirations, income (Labha)",
    12: "Moksha, losses, foreign lands, liberation (Vyaya)",
}

# ── Nakshatra Data (27 Nakshatras) ───────────────────────────────────

NAKSHATRA_DATA: List[Dict[str, Any]] = [
    {"name": "Ashwini",           "lord": "Ketu",    "meaning": "Swift healing, new beginnings"},
    {"name": "Bharani",           "lord": "Venus",   "meaning": "Transformation, creation, bearing"},
    {"name": "Krittika",          "lord": "Sun",     "meaning": "Purification, sharp will, fire"},
    {"name": "Rohini",            "lord": "Moon",    "meaning": "Growth, beauty, fertility"},
    {"name": "Mrigashira",        "lord": "Mars",    "meaning": "Seeking, curiosity, exploration"},
    {"name": "Ardra",             "lord": "Rahu",    "meaning": "Storm, renewal, deep intellect"},
    {"name": "Punarvasu",         "lord": "Jupiter", "meaning": "Return of light, wisdom restored"},
    {"name": "Pushya",            "lord": "Saturn",  "meaning": "Nourishment, dharma, protection"},
    {"name": "Ashlesha",          "lord": "Mercury", "meaning": "Serpent energy, hidden wisdom"},
    {"name": "Magha",             "lord": "Ketu",    "meaning": "Royalty, ancestors, authority"},
    {"name": "Purva Phalguni",    "lord": "Venus",   "meaning": "Enjoyment, creativity, love"},
    {"name": "Uttara Phalguni",   "lord": "Sun",     "meaning": "Patronage, contracts, duty"},
    {"name": "Hasta",             "lord": "Moon",    "meaning": "Skill, craftsmanship, healing"},
    {"name": "Chitra",            "lord": "Mars",    "meaning": "Brilliance, artistry, design"},
    {"name": "Swati",             "lord": "Rahu",    "meaning": "Independence, flexibility, trade"},
    {"name": "Vishakha",          "lord": "Jupiter", "meaning": "Purpose, determination, branching"},
    {"name": "Anuradha",          "lord": "Saturn",  "meaning": "Devotion, friendship, discipline"},
    {"name": "Jyeshtha",          "lord": "Mercury", "meaning": "Seniority, protection, authority"},
    {"name": "Moola",             "lord": "Ketu",    "meaning": "Root, investigation, uprooting"},
    {"name": "Purva Ashadha",     "lord": "Venus",   "meaning": "Invincibility, declaration"},
    {"name": "Uttara Ashadha",    "lord": "Sun",     "meaning": "Final victory, leadership, ethics"},
    {"name": "Shravana",          "lord": "Moon",    "meaning": "Learning, listening, connection"},
    {"name": "Dhanishta",         "lord": "Mars",    "meaning": "Wealth, rhythm, ambition"},
    {"name": "Shatabhisha",       "lord": "Rahu",    "meaning": "Hundred healers, mystery, solitude"},
    {"name": "Purva Bhadrapada",  "lord": "Jupiter", "meaning": "Intensity, burning transformation"},
    {"name": "Uttara Bhadrapada", "lord": "Saturn",  "meaning": "Depth, wisdom, cosmic serpent"},
    {"name": "Revati",            "lord": "Mercury", "meaning": "Wealth of journey, transcendence"},
]

# ── Vimshottari Dasha Periods (years) ────────────────────────────────

VIMSHOTTARI_ORDER = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]

VIMSHOTTARI_PERIODS: Dict[str, int] = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}

VIMSHOTTARI_TOTAL_YEARS = 120  # sum of all periods

# Legacy alias used by vedic_engine
VIMSHOTTARI_LORDS = VIMSHOTTARI_ORDER
