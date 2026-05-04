"""
Daily Horoscope Email Scheduler for Celestial Arc.

Uses APScheduler to run a daily cron job that:
1. Queries all users who opted in to daily horoscope emails
2. Generates a personalized horoscope for their sign
3. Sends it via Resend

Integrates with the Flask app via `init_scheduler(app)`.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler = None


def init_scheduler(app):
    """Initialize the APScheduler background scheduler within the Flask app context."""
    from config import RESEND_API_KEY, IS_PRODUCTION

    if not RESEND_API_KEY:
        logger.info("ℹ️ RESEND_API_KEY not set — daily horoscope emails disabled")
        return

    if not IS_PRODUCTION:
        logger.info("ℹ️ Scheduler disabled in development mode")
        return

    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = BackgroundScheduler(daemon=True)

        # Run every day at 07:30 UTC (≈ 1pm IST)
        _scheduler.add_job(
            func=lambda: _send_daily_horoscopes(app),
            trigger=CronTrigger(hour=7, minute=30),
            id="daily_horoscope_email",
            name="Send daily horoscope emails",
            replace_existing=True,
            misfire_grace_time=3600,  # Allow 1 hour late execution
        )

        _scheduler.start()
        logger.info("✅ Daily horoscope email scheduler started (runs 07:30 UTC)")

    except Exception as e:
        logger.error(f"❌ Scheduler initialization failed: {e}")


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler shut down")


def _send_daily_horoscopes(app):
    """Fetch opted-in users and send each a personalized horoscope email."""
    with app.app_context():
        try:
            from database import _get_engine, _use_postgres
            from vedic_engine import get_horoscope_for_sign

            engine = _get_engine()
            if not (_use_postgres and engine is not None):
                logger.debug("Scheduler: skipping — no PostgreSQL connection")
                return

            from sqlalchemy import text

            # Fetch all users who opted in
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT up.id, up.full_name, up.birth_date, au.email
                    FROM user_profiles up
                    JOIN auth.users au ON au.id = up.id
                    WHERE up.horoscope_opt_in = TRUE
                      AND au.email IS NOT NULL
                      AND au.email_confirmed_at IS NOT NULL
                """))
                users = result.fetchall()

            if not users:
                logger.info("📧 No users opted in for daily horoscope")
                return

            sent_count = 0
            error_count = 0

            for user in users:
                try:
                    user_dict = dict(user._mapping)
                    sign = _get_user_sign(user_dict.get("birth_date"))
                    if not sign:
                        continue

                    horoscope = get_horoscope_for_sign(sign)
                    if not horoscope:
                        continue

                    name = user_dict.get("full_name") or "Stargazer"
                    email = user_dict["email"]

                    success = _send_horoscope_email(
                        to_email=email,
                        name=name,
                        sign=sign,
                        horoscope=horoscope,
                    )
                    if success:
                        sent_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    logger.error(f"❌ Failed to process horoscope for user {user}: {e}")
                    error_count += 1

            logger.info(f"📧 Daily horoscope: sent={sent_count}, errors={error_count}")

        except Exception as e:
            logger.error(f"❌ Daily horoscope job failed: {e}")


def _get_user_sign(birth_date_str: Optional[str]) -> Optional[str]:
    """Derive zodiac sign from a birth_date string (YYYY-MM-DD)."""
    if not birth_date_str:
        return None
    try:
        from services.analysis_service import zodiac_sign
        from datetime import datetime
        bd = datetime.strptime(str(birth_date_str).strip(), "%Y-%m-%d").date()
        return zodiac_sign(bd)
    except Exception:
        return None


def _send_horoscope_email(to_email: str, name: str, sign: str, horoscope: str) -> bool:
    """Send a single horoscope email via Resend."""
    try:
        import resend
        from config import RESEND_API_KEY, FROM_EMAIL

        resend.api_key = RESEND_API_KEY

        today = datetime.now(timezone.utc).strftime("%B %d, %Y")

        html_body = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;
                    background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);
                    color:#e0d6ff;border-radius:16px;overflow:hidden;">

            <!-- Header -->
            <div style="text-align:center;padding:32px 24px 16px;">
                <h1 style="font-size:28px;margin:0;color:#d4a5ff;letter-spacing:2px;">
                    ✦ CELESTIAL ARC ✦
                </h1>
                <p style="font-size:13px;color:#9b8ec4;margin-top:4px;">Your Daily Cosmic Guidance</p>
            </div>

            <!-- Body -->
            <div style="padding:0 32px 32px;">
                <p style="font-size:16px;color:#c9b8f0;">
                    Namaste {name} 🙏
                </p>

                <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(212,165,255,0.15);
                            border-radius:12px;padding:24px;margin:16px 0;">
                    <h2 style="font-size:20px;color:#ffd700;margin:0 0 8px;">
                        {sign} — {today}
                    </h2>
                    <p style="font-size:15px;line-height:1.7;color:#d6ccef;margin:0;">
                        {horoscope}
                    </p>
                </div>

                <p style="font-size:13px;color:#8b7fb0;margin-top:24px;">
                    Want a deeper reading?
                    <a href="https://celestialarc.com/app"
                       style="color:#d4a5ff;text-decoration:underline;">
                        Generate your full Vedic chart →
                    </a>
                </p>
            </div>

            <!-- Footer -->
            <div style="text-align:center;padding:16px;background:rgba(0,0,0,0.2);
                        font-size:11px;color:#6b5f8a;">
                <p style="margin:0;">
                    You're receiving this because you opted in to daily horoscopes.
                    <br>
                    <a href="https://celestialarc.com/dashboard"
                       style="color:#9b8ec4;text-decoration:underline;">
                        Manage preferences
                    </a>
                </p>
            </div>
        </div>
        """

        result = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": f"✦ {sign} Daily Horoscope — {today}",
            "html": html_body,
        })

        logger.debug(f"📧 Sent horoscope to {to_email}: {result}")
        return True

    except Exception as e:
        logger.error(f"❌ Email send failed for {to_email}: {e}")
        return False
