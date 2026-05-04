"""
Auth service wrapping Supabase Auth for Celestial Arc.
Handles signup, login, OAuth, OTP, and JWT verification.
"""
import logging
from typing import Any, Dict, Optional
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)
_supabase_client = None
_supabase_init_attempted = False


def _get_supabase():
    global _supabase_client, _supabase_init_attempted
    if _supabase_init_attempted:
        return _supabase_client
    _supabase_init_attempted = True
    try:
        from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
        if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
            from supabase import create_client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            logger.info("Supabase Auth connected")
    except Exception as e:
        logger.warning(f"Supabase Auth unavailable: {e}")
    return _supabase_client


def signup_email(email: str, password: str) -> Dict[str, Any]:
    sb = _get_supabase()
    if sb is None:
        return {"error": "Auth service unavailable"}
    try:
        result = sb.auth.sign_up({"email": email, "password": password})
        return {"success": True, "user": _serialize_user(result.user), "session": _serialize_session(result.session)}
    except Exception as e:
        return {"error": str(e)}


def login_email(email: str, password: str) -> Dict[str, Any]:
    sb = _get_supabase()
    if sb is None:
        return {"error": "Auth service unavailable"}
    try:
        result = sb.auth.sign_in_with_password({"email": email, "password": password})
        return {"success": True, "user": _serialize_user(result.user), "session": _serialize_session(result.session)}
    except Exception as e:
        return {"error": str(e)}


def google_oauth_url(redirect_to: str = "") -> Optional[str]:
    sb = _get_supabase()
    if sb is None:
        return None
    try:
        result = sb.auth.sign_in_with_oauth({"provider": "google", "options": {"redirect_to": redirect_to}})
        return result.url
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        return None


def send_otp(phone: str) -> Dict[str, Any]:
    sb = _get_supabase()
    if sb is None:
        return {"error": "Auth service unavailable"}
    try:
        sb.auth.sign_in_with_otp({"phone": phone})
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


def verify_otp(phone: str, token: str) -> Dict[str, Any]:
    sb = _get_supabase()
    if sb is None:
        return {"error": "Auth service unavailable"}
    try:
        result = sb.auth.verify_otp({"phone": phone, "token": token, "type": "sms"})
        return {"success": True, "user": _serialize_user(result.user), "session": _serialize_session(result.session)}
    except Exception as e:
        return {"error": str(e)}


def get_current_user(access_token: str) -> Optional[Dict[str, Any]]:
    sb = _get_supabase()
    if sb is None:
        return None
    try:
        result = sb.auth.get_user(access_token)
        if result and result.user:
            return _serialize_user(result.user)
        return None
    except Exception:
        return None


def logout(access_token: str) -> bool:
    sb = _get_supabase()
    if sb is None:
        return False
    try:
        sb.auth.admin.sign_out(access_token)
        return True
    except Exception:
        return False


def _serialize_user(user) -> Optional[Dict[str, Any]]:
    if user is None:
        return None
    return {
        "id": str(user.id),
        "email": user.email,
        "phone": getattr(user, "phone", None),
        "email_confirmed_at": str(user.email_confirmed_at) if getattr(user, "email_confirmed_at", None) else None,
        "created_at": str(user.created_at) if getattr(user, "created_at", None) else None,
    }


def _serialize_session(session) -> Optional[Dict[str, Any]]:
    if session is None:
        return None
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
        "token_type": getattr(session, "token_type", "bearer"),
    }


# ── Flask middleware ─────────────────────────────────────────────────

def require_auth(f):
    """Decorator: require a valid Supabase JWT Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        token = auth_header[7:]
        user = get_current_user(token)
        if user is None:
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """Decorator: attach user if token present, but don't require it."""
    @wraps(f)
    def decorated(*args, **kwargs):
        request.current_user = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            request.current_user = get_current_user(token)
        return f(*args, **kwargs)
    return decorated
