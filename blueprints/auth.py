"""Auth blueprint — /api/auth/* routes using Supabase Auth."""
import logging
from flask import Blueprint, jsonify, request
from services.auth_service import (
    signup_email, login_email, google_oauth_url,
    send_otp, verify_otp, get_current_user, logout,
    require_auth
)

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/signup", methods=["POST"])
def api_signup():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters"}), 400
    result = signup_email(email, password)
    if "error" in result:
        return jsonify({"success": False, "error": result["error"]}), 400
    return jsonify(result)


@auth_bp.route("/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400
    result = login_email(email, password)
    if "error" in result:
        return jsonify({"success": False, "error": result["error"]}), 401
    return jsonify(result)


@auth_bp.route("/logout", methods=["POST"])
def api_logout():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        logout(auth_header[7:])
    return jsonify({"success": True})


@auth_bp.route("/google", methods=["GET"])
def api_google_oauth():
    redirect_to = request.args.get("redirect_to", "")
    url = google_oauth_url(redirect_to)
    if url is None:
        return jsonify({"success": False, "error": "Google OAuth not configured"}), 503
    return jsonify({"success": True, "url": url})


@auth_bp.route("/callback", methods=["GET"])
def api_oauth_callback():
    # Supabase handles the callback and redirects to the frontend
    # This endpoint is a placeholder for custom handling if needed
    return jsonify({"success": True, "message": "OAuth callback received"})


@auth_bp.route("/otp/send", methods=["POST"])
def api_send_otp():
    from config import ENABLE_PHONE_OTP
    if not ENABLE_PHONE_OTP:
        return jsonify({"success": False, "error": "Phone OTP is not enabled"}), 503
    data = request.get_json(force=True, silent=True) or {}
    phone = (data.get("phone") or "").strip()
    if not phone:
        return jsonify({"success": False, "error": "Phone number required"}), 400
    result = send_otp(phone)
    if "error" in result:
        return jsonify({"success": False, "error": result["error"]}), 400
    return jsonify(result)


@auth_bp.route("/otp/verify", methods=["POST"])
def api_verify_otp():
    data = request.get_json(force=True, silent=True) or {}
    phone = (data.get("phone") or "").strip()
    token = (data.get("token") or "").strip()
    if not phone or not token:
        return jsonify({"success": False, "error": "Phone and token required"}), 400
    result = verify_otp(phone, token)
    if "error" in result:
        return jsonify({"success": False, "error": result["error"]}), 400
    return jsonify(result)


@auth_bp.route("/me", methods=["GET"])
@require_auth
def api_me():
    return jsonify({"success": True, "user": request.current_user})


@auth_bp.route("/me", methods=["PUT"])
@require_auth
def api_update_profile():
    data = request.get_json(force=True, silent=True) or {}
    user_id = request.current_user["id"]
    # Update user_profiles table
    try:
        from database import _get_engine, _use_postgres
        engine = _get_engine()
        if _use_postgres and engine is not None:
            from sqlalchemy import text
            fields = []
            params = {"uid": user_id}
            for key in ["full_name", "birth_date", "birth_place", "birth_lat", "birth_lon",
                        "birth_tz", "horoscope_opt_in", "preferred_horoscope_time"]:
                if key in data:
                    fields.append(f"{key} = :{key}")
                    params[key] = data[key]
            if fields:
                fields.append("updated_at = NOW()")
                with engine.connect() as conn:
                    conn.execute(text(f"UPDATE user_profiles SET {', '.join(fields)} WHERE id = :uid"), params)
                    conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        return jsonify({"success": False, "error": "Failed to update profile"}), 500
