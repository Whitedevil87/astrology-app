"""
Centralised security module for Celestial Arc.

Handles:
- Rate limiting (Upstash Redis in production, in-memory fallback for dev)
- CSRF token management
- Security headers
- Client IP extraction
"""

import logging
import secrets
import time as time_mod
from typing import Dict, Optional, Tuple

from flask import Flask, jsonify, request, session

logger = logging.getLogger(__name__)

# ── Redis client (lazy-initialised) ──────────────────────────────────
_redis_client = None
_redis_init_attempted = False


def _get_redis():
    """Lazily initialise the Upstash Redis client. Returns None if unavailable."""
    global _redis_client, _redis_init_attempted
    if _redis_init_attempted:
        return _redis_client
    _redis_init_attempted = True
    try:
        from config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
        if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
            from upstash_redis import Redis
            _redis_client = Redis(
                url=UPSTASH_REDIS_REST_URL,
                token=UPSTASH_REDIS_REST_TOKEN,
                rest_retries=3,
                rest_retry_interval=1,
            )
            logger.info("✅ Upstash Redis connected for rate limiting")
        else:
            logger.warning("⚠️ Upstash Redis not configured — using in-memory rate limiting")
    except Exception as e:
        logger.warning(f"⚠️ Could not connect to Upstash Redis: {e} — falling back to in-memory")
        _redis_client = None
    return _redis_client


# ── In-memory fallback ───────────────────────────────────────────────
_RATE_BUCKETS: Dict[str, list] = {}
_LAST_CLEANUP: float = time_mod.time()
_CLEANUP_INTERVAL_S: int = 300


def _cleanup_stale_buckets() -> None:
    """Periodically remove expired keys from in-memory rate buckets."""
    global _LAST_CLEANUP
    now = time_mod.time()
    if now - _LAST_CLEANUP < _CLEANUP_INTERVAL_S:
        return
    _LAST_CLEANUP = now
    stale_keys = []
    for key, timestamps in _RATE_BUCKETS.items():
        window = 86400 if ":day" in key else 60
        cutoff = now - window
        live = [t for t in timestamps if t >= cutoff]
        if not live:
            stale_keys.append(key)
        else:
            _RATE_BUCKETS[key] = live
    for k in stale_keys:
        del _RATE_BUCKETS[k]
    if stale_keys:
        logger.debug(f"🧹 Rate-limiter cleanup: removed {len(stale_keys)} stale keys")


# ── Core rate limiting function ──────────────────────────────────────
def is_rate_limited(ip: str, action: str, limit: int, window_seconds: int) -> bool:
    """
    Check if a request should be rate-limited.

    Uses Upstash Redis if available, otherwise falls back to in-memory.
    Returns True if the request SHOULD be blocked.
    """
    redis = _get_redis()

    if redis is not None:
        # ── Redis path (production) ──────────────────────────────
        try:
            key = f"ratelimit:{action}:{ip}"
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, window_seconds)
            return count > limit
        except Exception as e:
            logger.warning(f"⚠️ Redis rate-limit error: {e} — falling back to in-memory")
            # Fall through to in-memory

    # ── In-memory path (local dev / Redis failure) ───────────────
    _cleanup_stale_buckets()
    now = time_mod.time()
    key = f"{ip}:{action}"
    bucket = _RATE_BUCKETS.get(key, [])
    cutoff = now - window_seconds
    bucket = [t for t in bucket if t >= cutoff]
    if len(bucket) >= limit:
        _RATE_BUCKETS[key] = bucket
        return True
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket
    return False


# ── Rate limit configuration ────────────────────────────────────────
# Format: (per-minute limit, per-day limit)
_LIMITS = {
    "analyze":   (5,  15),
    "chat":      (10, 50),
    "places":    (30, 500),
    "horoscope": (10, 100),
    "kundli":    (5,  20),
}

# Themed error messages
_RATE_MESSAGES = {
    "analyze":   "🪐 The celestial energies need a moment to realign. You've generated too many charts — please wait before trying again.",
    "chat":      "🔮 Guru Arya is meditating to channel deeper wisdom. Please wait a moment before sending another message.",
    "places":    None,  # Silent fail for autocomplete
    "horoscope": "⭐ The stars are aligning your horoscope. Please try again in a moment.",
    "kundli":    "🕉️ Your Kundli chart requires cosmic precision. Please wait before generating another.",
}

# Map of (path, method) → action name
_RATE_MAP = {
    ("/api/analyze", "POST"):           "analyze",
    ("/api/chat", "POST"):              "chat",
    ("/api/places", "GET"):             "places",
    ("/api/horoscope", "GET"):          "horoscope",
    ("/api/kundli-chart", "POST"):      "kundli",
    ("/api/compatibility", "POST"):     "kundli",
    ("/api/dasha", "POST"):             "horoscope",
    ("/api/panchanga", "POST"):         "horoscope",
    ("/api/ashtakavarga", "POST"):      "horoscope",
    ("/api/guna-milan", "POST"):        "kundli",
}

# POST /api/* routes that use Bearer tokens instead of session cookies
_CSRF_EXEMPT_PREFIXES = ("/api/auth/",)


def client_ip() -> str:
    """Extract the real client IP safely behind a reverse proxy (Render, Vercel, etc.)."""
    # Vercel and Render set X-Real-IP. These are harder to spoof.
    for header in ["X-Real-IP", "True-Client-IP", "CF-Connecting-IP"]:
        ip = request.headers.get(header)
        if ip:
            return ip.strip()
            
    # Fallback to X-Forwarded-For, but take the *right-most* (last) IP 
    # as the first one can be easily spoofed by the client before hitting the proxy.
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        parts = [p.strip() for p in fwd.split(",")]
        return parts[-1]
        
    return request.remote_addr or "unknown"


def check_rate_limits(ip: str, action: str) -> Optional[Tuple]:
    """
    Check both per-minute AND per-day rate limits for a given action.
    Returns a (response, status_code) tuple if blocked, or None if allowed.
    """
    per_min, per_day = _LIMITS.get(action, (30, 200))
    msg = _RATE_MESSAGES.get(action)

    # Per-minute check
    if is_rate_limited(ip, f"{action}:min", per_min, 60):
        if action == "places":
            return jsonify({"success": False, "places": []}), 429
        return jsonify({"success": False, "error": msg or "Too many requests. Please wait a minute."}), 429

    # Per-day check (86400 seconds = 24 hours)
    if is_rate_limited(ip, f"{action}:day", per_day, 86400):
        daily_msg = f"{msg or 'Daily limit reached.'} You've reached your daily limit — come back tomorrow for more cosmic insights! 🌙"
        if action == "places":
            return jsonify({"success": False, "places": []}), 429
        return jsonify({"success": False, "error": daily_msg}), 429

    return None


def ensure_csrf() -> str:
    """Ensure a CSRF token exists in the session and return it."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return str(token)


# ── Flask integration ────────────────────────────────────────────────

def register_security(app: Flask) -> Flask:
    """Register security middleware (headers, rate limiting, CSRF) on a Flask app."""

    @app.after_request
    def add_security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        if not app.config.get("DEBUG"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data: blob: https://*.supabase.co; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "connect-src 'self' https://photon.komoot.io https://timeapi.io "
            "https://api.groq.com https://api.openai.com https://*.supabase.co; "
            "base-uri 'self'; form-action 'self'"
        )
        if app.config.get("DEBUG"):
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        return resp

    @app.before_request
    def protect_requests():
        # Skip non-API routes
        if not request.path.startswith("/api/"):
            return

        ip = client_ip()

        # ── Rate limiting per endpoint ──────────────────────────
        action = _RATE_MAP.get((request.path, request.method))
        if action:
            blocked = check_rate_limits(ip, action)
            if blocked:
                logger.warning(f"⛔ Rate limited: {ip} on {action}")
                return blocked

        # ── CSRF: all session-backed POST /api/* (opt-out list for Bearer auth) ──
        needs_csrf = (
            request.method == "POST"
            and request.path.startswith("/api/")
            and not any(request.path.startswith(p) for p in _CSRF_EXEMPT_PREFIXES)
        )
        if needs_csrf:
            expected = session.get("csrf_token")
            provided = (request.headers.get("X-CSRF-Token") or "").strip()
            if not expected:
                ensure_csrf()
                expected = session.get("csrf_token")
            if not provided or provided != expected:
                return jsonify({
                    "success": False,
                    "error": "CSRF token missing/invalid. Refresh the page and try again."
                }), 403

    return app
