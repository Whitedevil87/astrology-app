import logging
import secrets
import time as time_mod
from typing import Dict

from flask import jsonify, request, session

logger = logging.getLogger(__name__)

_RATE_BUCKETS: Dict[str, list[float]] = {}


def _client_ip() -> str:
    fwd = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return fwd or (request.remote_addr or "unknown")


def _rate_limit(key: str, limit: int, window_s: int) -> bool:
    now = time_mod.time()
    bucket = _RATE_BUCKETS.get(key, [])
    cutoff = now - window_s
    bucket = [t for t in bucket if t >= cutoff]
    if len(bucket) >= limit:
        _RATE_BUCKETS[key] = bucket
        return False
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket
    return True


def _ensure_csrf() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return str(token)


def register_security(app):
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
            "img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https://photon.komoot.io https://timeapi.io https://api.groq.com https://api.openai.com; "
            "base-uri 'self'; form-action 'self'"
        )
        return resp

    @app.before_request
    def protect_requests():
        ip = _client_ip()
        if request.path == "/api/analyze" and request.method == "POST":
            if not _rate_limit(f"{ip}:analyze", limit=20, window_s=60):
                return jsonify({"success": False, "error": "Too many requests. Please wait a minute and try again."}), 429
        if request.path == "/api/chat" and request.method == "POST":
            if not _rate_limit(f"{ip}:chat", limit=40, window_s=60):
                return jsonify({"success": False, "error": "Too many chat messages. Please slow down."}), 429
        if request.path == "/api/places" and request.method == "GET":
            if not _rate_limit(f"{ip}:places", limit=60, window_s=60):
                return jsonify({"success": False, "places": []}), 429

        if request.method == "POST" and request.path in {"/api/analyze", "/api/chat"}:
            expected = session.get("csrf_token")
            provided = (request.headers.get("X-CSRF-Token") or "").strip()
            if not expected:
                _ensure_csrf()
                expected = session.get("csrf_token")
            if not provided or provided != expected:
                return jsonify({"success": False, "error": "CSRF token missing/invalid. Refresh the page and try again."}), 403

    return app
