from typing import Dict

ZODIAC_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

ZODIAC_META: Dict[str, Dict[str, str]] = {
    "Aries": {"element": "Fire", "modality": "Cardinal", "ruler": "Mars", "glyph": "\u2648"},
    "Taurus": {"element": "Earth", "modality": "Fixed", "ruler": "Venus", "glyph": "\u2649"},
    "Gemini": {"element": "Air", "modality": "Mutable", "ruler": "Mercury", "glyph": "\u264A"},
    "Cancer": {"element": "Water", "modality": "Cardinal", "ruler": "Moon", "glyph": "\u264B"},
    "Leo": {"element": "Fire", "modality": "Fixed", "ruler": "Sun", "glyph": "\u264C"},
    "Virgo": {"element": "Earth", "modality": "Mutable", "ruler": "Mercury", "glyph": "\u264D"},
    "Libra": {"element": "Air", "modality": "Cardinal", "ruler": "Venus", "glyph": "\u264E"},
    "Scorpio": {"element": "Water", "modality": "Fixed", "ruler": "Pluto", "glyph": "\u264F"},
    "Sagittarius": {"element": "Fire", "modality": "Mutable", "ruler": "Jupiter", "glyph": "\u2650"},
    "Capricorn": {"element": "Earth", "modality": "Cardinal", "ruler": "Saturn", "glyph": "\u2651"},
    "Aquarius": {"element": "Air", "modality": "Fixed", "ruler": "Uranus", "glyph": "\u2652"},
    "Pisces": {"element": "Water", "modality": "Mutable", "ruler": "Neptune", "glyph": "\u2653"},
}

PERSONALITY_RULES = {
    "Aries": "bold, energetic, action-driven",
    "Taurus": "steady, grounded, loyal",
    "Gemini": "curious, social, quick-minded",
    "Cancer": "protective, intuitive, empathetic",
    "Leo": "charismatic, proud, heart-led",
    "Virgo": "analytical, practical, detail-focused",
    "Libra": "harmonious, diplomatic, refined",
    "Scorpio": "intense, strategic, emotionally deep",
    "Sagittarius": "optimistic, adventurous, philosophical",
    "Capricorn": "disciplined, responsible, ambitious",
    "Aquarius": "independent, inventive, visionary",
    "Pisces": "imaginative, sensitive, spiritually tuned",
}

CAREER_RULES = {
    "Aries": "leadership, startups, athletics, emergency response",
    "Taurus": "finance, design, architecture, food or luxury industries",
    "Gemini": "media, sales, teaching, communications, product roles",
    "Cancer": "counseling, hospitality, healthcare, caregiving fields",
    "Leo": "public leadership, entertainment, branding, entrepreneurship",
    "Virgo": "analysis, engineering, medicine, operations excellence",
    "Libra": "law, diplomacy, design, client-facing strategy",
    "Scorpio": "research, psychology, cybersecurity, investigative work",
    "Sagittarius": "travel, higher education, publishing, consulting",
    "Capricorn": "management, government, finance, long-term planning",
    "Aquarius": "technology, innovation labs, social impact, science",
    "Pisces": "arts, healing, storytelling, spiritual guidance",
}

STRENGTH_BLURBS = {
    "Aries": "Courageous initiative, honest drive, and the ability to start what others only dream about.",
    "Taurus": "Patient endurance, loyal devotion, and a gift for building lasting security and beauty.",
    "Gemini": "Quick learning, witty communication, and versatile problem-solving under pressure.",
    "Cancer": "Protective intuition, deep empathy, and emotional intelligence that nurtures others.",
    "Leo": "Generous warmth, creative confidence, and natural leadership that uplifts a room.",
    "Virgo": "Precision, helpfulness, and sharp improvement skills that turn chaos into order.",
    "Libra": "Diplomatic grace, aesthetic taste, and peacemaking that restores balance.",
    "Scorpio": "Emotional courage, strategic focus, and transformative insight into hidden motives.",
    "Sagittarius": "Optimistic vision, honest philosophy, and fearless exploration of new horizons.",
    "Capricorn": "Discipline, integrity, and long-game ambition that climbs with quiet strength.",
    "Aquarius": "Original thinking, humanitarian ideals, and inventive solutions ahead of the curve.",
    "Pisces": "Compassion, imagination, and spiritual sensitivity that heals through understanding.",
}

WEAKNESS_BLURBS = {
    "Aries": "Impatience, sharp reactions, or moving too fast before listening to quieter signals.",
    "Taurus": "Stubborn resistance to change, over-attachment to comfort, or delayed adaptation.",
    "Gemini": "Scattered focus, nervous overthinking, or difficulty sitting with one deep decision.",
    "Cancer": "Mood swings, retreat under stress, or taking feedback more personally than intended.",
    "Leo": "Pride wounds, spotlight hunger, or mistaking loyalty for unlimited attention.",
    "Virgo": "Self-criticism, worry loops, or perfect standards that delay necessary action.",
    "Libra": "People-pleasing, indecision, or avoiding hard truths to keep harmony at all costs.",
    "Scorpio": "Intensity that overwhelms others, secrecy, or control instincts during vulnerability.",
    "Sagittarius": "Over-promising, blunt honesty, or restlessness that disrupts steady progress.",
    "Capricorn": "Workaholic tendencies, emotional reserve, or fear of imperfection slowing joy.",
    "Aquarius": "Detached coolness, unpredictability, or idealism that forgets tender human needs.",
    "Pisces": "Escapism, porous boundaries, or absorbing other people's moods too easily.",
}

LUCKY_DAYS = {
    "Aries": "Tuesday",
    "Taurus": "Friday",
    "Gemini": "Wednesday",
    "Cancer": "Monday",
    "Leo": "Sunday",
    "Virgo": "Wednesday",
    "Libra": "Friday",
    "Scorpio": "Tuesday",
    "Sagittarius": "Thursday",
    "Capricorn": "Saturday",
    "Aquarius": "Saturday",
    "Pisces": "Thursday",
}

ELEMENT_COLORS = {
    "Fire": "Gold & crimson",
    "Earth": "Forest green & clay",
    "Air": "Sky blue & silver",
    "Water": "Indigo & sea glass",
}

HOUSE_MEANINGS = {
    1: "Self, body, temperament, life direction (Lagna)",
    2: "Wealth, speech, family, values",
    3: "Siblings, courage, short journeys, skills",
    4: "Home, mother, comfort, roots",
    5: "Children, creativity, romance, intellect",
    6: "Health, service, debts, competition",
    7: "Marriage, partnerships, contracts, public relations",
    8: "Transformations, shared resources, longevity",
    9: "Dharma, higher learning, luck, guru",
    10: "Career, status, authority, reputation",
    11: "Gains, friends, aspirations, income streams",
    12: "Moksha, losses, foreign lands, sleep, liberation themes",
}

VIMSHOTTARI_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]
