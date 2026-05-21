"""
Database layer for Celestial Arc.

Uses PostgreSQL (Supabase) in production via SQLAlchemy,
with automatic SQLite fallback for local development.

All public-facing IDs use UUID (public_id), never the integer primary key.
"""

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Engine initialisation ────────────────────────────────────────────
_engine = None
_use_postgres = False


def _get_engine():
    """Lazily create the SQLAlchemy engine."""
    global _engine, _use_postgres
    if _engine is not None:
        return _engine

    from config import DATABASE_URL, SQLITE_FALLBACK_PATH, INSTANCE_DIR

    if DATABASE_URL:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.pool import NullPool

            # Fix for Render: use pg8000 instead of psycopg2 to avoid Python 3.14 C-extension errors
            db_url = DATABASE_URL
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+pg8000://", 1)
            elif db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1)

            _engine = create_engine(db_url, poolclass=NullPool)
            _use_postgres = True
            logger.info("✅ PostgreSQL (Supabase) database connected")
            return _engine
        except Exception as e:
            logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
            logger.warning("⚠️ Falling back to SQLite")

    # SQLite fallback
    try:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
    except OSError:
        pass  # Vercel read-only filesystem
    _use_postgres = False
    logger.info(f"📁 Using SQLite database: {SQLITE_FALLBACK_PATH}")
    return None  # Signals to use sqlite3 directly


def _sqlite_connection():
    """Get a direct SQLite connection (fallback mode only)."""
    from config import SQLITE_FALLBACK_PATH
    conn = sqlite3.connect(SQLITE_FALLBACK_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema ───────────────────────────────────────────────────────────

_POSTGRES_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    public_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    full_name TEXT NOT NULL,
    birth_date TEXT NOT NULL,
    birth_time TEXT NOT NULL,
    birth_place TEXT NOT NULL,
    palm_enabled INTEGER NOT NULL DEFAULT 0,
    hand_choice TEXT,
    palm_image_path TEXT,
    zodiac TEXT NOT NULL,
    moon_sign TEXT NOT NULL,
    ascendant TEXT NOT NULL,
    personality TEXT NOT NULL,
    career TEXT NOT NULL,
    love_life TEXT NOT NULL,
    future_outlook TEXT NOT NULL,
    strengths TEXT,
    weaknesses TEXT,
    wellness TEXT,
    compatibility TEXT,
    seasonal_energy TEXT,
    palm_analysis TEXT,
    report_html TEXT NOT NULL,
    report_extras TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_POSTGRES_CHAT_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    report_public_id UUID REFERENCES reports(public_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_POSTGRES_USER_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    birth_date TEXT,
    birth_place TEXT,
    birth_lat REAL,
    birth_lon REAL,
    birth_tz TEXT,
    horoscope_opt_in BOOLEAN DEFAULT FALSE,
    preferred_horoscope_time TEXT DEFAULT '08:00',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

_SQLITE_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    user_id TEXT,
    full_name TEXT NOT NULL,
    birth_date TEXT NOT NULL,
    birth_time TEXT NOT NULL,
    birth_place TEXT NOT NULL,
    palm_enabled INTEGER NOT NULL DEFAULT 0,
    hand_choice TEXT,
    palm_image_path TEXT,
    zodiac TEXT NOT NULL,
    moon_sign TEXT NOT NULL,
    ascendant TEXT NOT NULL,
    personality TEXT NOT NULL,
    career TEXT NOT NULL,
    love_life TEXT NOT NULL,
    future_outlook TEXT NOT NULL,
    strengths TEXT,
    weaknesses TEXT,
    wellness TEXT,
    compatibility TEXT,
    seasonal_energy TEXT,
    palm_analysis TEXT,
    report_html TEXT NOT NULL,
    report_extras TEXT,
    created_at TEXT NOT NULL
);
"""

_SQLITE_CHAT_TABLE = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    report_public_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


# ── Initialisation ───────────────────────────────────────────────────

def init_db() -> None:
    """Create tables if they don't exist."""
    engine = _get_engine()

    if _use_postgres and engine is not None:
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text(_POSTGRES_REPORTS_TABLE))
                conn.execute(text(_POSTGRES_CHAT_TABLE))
                # user_profiles may fail if auth.users doesn't exist yet — that's OK
                try:
                    conn.execute(text(_POSTGRES_USER_PROFILES_TABLE))
                except Exception:
                    logger.info("ℹ️ user_profiles table creation skipped (auth.users may not exist yet)")
                conn.commit()
            logger.info("✅ PostgreSQL tables initialised")
        except Exception as e:
            logger.error(f"❌ PostgreSQL init error: {e}")
    else:
        conn = _sqlite_connection()
        conn.execute(_SQLITE_REPORTS_TABLE)
        conn.execute(_SQLITE_CHAT_TABLE)
        conn.commit()
        conn.close()
        logger.info("✅ SQLite tables initialised")


def migrate_db() -> None:
    """Run schema migrations (add missing columns)."""
    engine = _get_engine()

    migration_columns = [
        ("strengths", "TEXT"),
        ("weaknesses", "TEXT"),
        ("wellness", "TEXT"),
        ("compatibility", "TEXT"),
        ("seasonal_energy", "TEXT"),
        ("report_extras", "TEXT"),
        ("public_id", "TEXT"),
        ("user_id", "TEXT"),
    ]

    if _use_postgres and engine is not None:
        from sqlalchemy import text
        try:
            with engine.connect() as conn:
                # Get existing columns
                result = conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'reports'"
                ))
                existing = {row[0] for row in result.fetchall()}

                for name, col_type in migration_columns:
                    if name not in existing:
                        pg_type = "UUID DEFAULT gen_random_uuid() UNIQUE" if name == "public_id" else col_type
                        try:
                            conn.execute(text(f"ALTER TABLE reports ADD COLUMN {name} {pg_type}"))
                            logger.info(f"  ✅ Added column: {name}")
                        except Exception as e:
                            logger.debug(f"  ⏭️ Column {name} may already exist: {e}")
                conn.commit()
        except Exception as e:
            logger.error(f"❌ PostgreSQL migration error: {e}")
    else:
        conn = _sqlite_connection()
        cursor = conn.execute("PRAGMA table_info(reports)")
        columns = {row[1] for row in cursor.fetchall()}
        for name, definition in migration_columns:
            if name not in columns:
                conn.execute(f"ALTER TABLE reports ADD COLUMN {name} {definition}")
        # Backfill public_ids for any rows missing them
        cursor = conn.execute("SELECT id FROM reports WHERE public_id IS NULL OR public_id = ''")
        rows = cursor.fetchall()
        for row in rows:
            conn.execute("UPDATE reports SET public_id = ? WHERE id = ?", (str(uuid.uuid4()), row[0]))
        conn.commit()
        conn.close()


# ── Query helpers ────────────────────────────────────────────────────

def get_connection():
    """Get a database connection. For PostgreSQL returns SQLAlchemy connection context."""
    engine = _get_engine()
    if _use_postgres and engine is not None:
        return engine.connect()
    return _sqlite_connection()


def save_report(payload: Dict[str, Any], user_id: Optional[str] = None) -> str:
    """
    Save a report and return its public_id (UUID string).
    """
    public_id = str(uuid.uuid4())
    created_at = payload.get("created_at", datetime.now(timezone.utc).isoformat())

    engine = _get_engine()
    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO reports (
                        public_id, user_id, full_name, birth_date, birth_time, birth_place,
                        palm_enabled, hand_choice, palm_image_path,
                        zodiac, moon_sign, ascendant,
                        personality, career, love_life, future_outlook,
                        strengths, weaknesses, wellness, compatibility, seasonal_energy,
                        palm_analysis, report_html, report_extras, created_at
                    ) VALUES (
                        :public_id, :user_id, :full_name, :birth_date, :birth_time, :birth_place,
                        :palm_enabled, :hand_choice, :palm_image_path,
                        :zodiac, :moon_sign, :ascendant,
                        :personality, :career, :love_life, :future_outlook,
                        :strengths, :weaknesses, :wellness, :compatibility, :seasonal_energy,
                        :palm_analysis, :report_html, :report_extras, :created_at
                    )
                """),
                {
                    "public_id": public_id,
                    "user_id": user_id,
                    "full_name": payload["full_name"],
                    "birth_date": payload["birth_date"],
                    "birth_time": payload["birth_time"],
                    "birth_place": payload["birth_place"],
                    "palm_enabled": payload["palm_enabled"],
                    "hand_choice": payload["hand_choice"],
                    "palm_image_path": payload["palm_image_path"],
                    "zodiac": payload["profile"]["zodiac"],
                    "moon_sign": payload["profile"]["moon_sign"],
                    "ascendant": payload["profile"]["ascendant"],
                    "personality": payload["sections"]["personality"],
                    "career": payload["sections"]["career"],
                    "love_life": payload["sections"]["love"],
                    "future_outlook": payload["sections"]["future"],
                    "strengths": payload["sections"].get("strengths"),
                    "weaknesses": payload["sections"].get("weaknesses"),
                    "wellness": payload["sections"].get("wellness"),
                    "compatibility": payload["sections"].get("compatibility"),
                    "seasonal_energy": payload["sections"].get("seasonal_energy"),
                    "palm_analysis": payload["palm_analysis"],
                    "report_html": payload["report_html"],
                    "report_extras": payload["report_extras"],
                    "created_at": created_at,
                }
            )
            conn.commit()
    else:
        conn = _sqlite_connection()
        conn.execute(
            """
            INSERT INTO reports (
                public_id, user_id, full_name, birth_date, birth_time, birth_place,
                palm_enabled, hand_choice, palm_image_path,
                zodiac, moon_sign, ascendant,
                personality, career, love_life, future_outlook,
                strengths, weaknesses, wellness, compatibility, seasonal_energy,
                palm_analysis, report_html, report_extras, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                public_id, user_id,
                payload["full_name"], payload["birth_date"], payload["birth_time"], payload["birth_place"],
                payload["palm_enabled"], payload["hand_choice"], payload["palm_image_path"],
                payload["profile"]["zodiac"], payload["profile"]["moon_sign"], payload["profile"]["ascendant"],
                payload["sections"]["personality"], payload["sections"]["career"],
                payload["sections"]["love"], payload["sections"]["future"],
                payload["sections"].get("strengths"), payload["sections"].get("weaknesses"),
                payload["sections"].get("wellness"), payload["sections"].get("compatibility"),
                payload["sections"].get("seasonal_energy"),
                payload["palm_analysis"], payload["report_html"], payload["report_extras"],
                created_at,
            ),
        )
        conn.commit()
        conn.close()

    return public_id


def fetch_report_by_public_id(public_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch a report by its public UUID.
    If user_id is provided, only returns the report if it belongs to that user.
    """
    engine = _get_engine()
    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            if user_id:
                result = conn.execute(
                    text("SELECT * FROM reports WHERE public_id = :pid AND (user_id = :uid OR user_id IS NULL)"),
                    {"pid": public_id, "uid": user_id}
                )
            else:
                result = conn.execute(
                    text("SELECT * FROM reports WHERE public_id = :pid AND user_id IS NULL"),
                    {"pid": public_id}
                )
            row = result.fetchone()
            if row is None:
                return None
            return dict(row._mapping)
    else:
        conn = _sqlite_connection()
        if user_id:
            row = conn.execute(
                "SELECT * FROM reports WHERE public_id = ? AND (user_id = ? OR user_id IS NULL)",
                (public_id, user_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM reports WHERE public_id = ? AND user_id IS NULL",
                (public_id,)
            ).fetchone()
        conn.close()
        if row is None:
            return None
        return dict(row)


def fetch_report_row(report_id: int) -> Optional[Dict[str, Any]]:
    """
    Legacy: Fetch a report by integer ID.
    Kept for backward compatibility during migration.
    """
    engine = _get_engine()
    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM reports WHERE id = :id"), {"id": report_id})
            row = result.fetchone()
            if row is None:
                return None
            return dict(row._mapping)
    else:
        conn = _sqlite_connection()
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        conn.close()
        if row is None:
            return None
        return dict(row)


def list_user_reports(user_id: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
    """List reports for a user with pagination."""
    offset = (page - 1) * limit
    engine = _get_engine()

    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT public_id, full_name, birth_date, zodiac, moon_sign, ascendant, created_at
                    FROM reports
                    WHERE user_id = :uid
                    ORDER BY created_at DESC
                    LIMIT :lim OFFSET :off
                """),
                {"uid": user_id, "lim": limit, "off": offset}
            )
            return [dict(row._mapping) for row in result.fetchall()]
    else:
        conn = _sqlite_connection()
        rows = conn.execute(
            """
            SELECT public_id, full_name, birth_date, zodiac, moon_sign, ascendant, created_at
            FROM reports
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]


def delete_report(public_id: str, user_id: Optional[str] = None) -> bool:
    """Delete a report by public_id. Returns True if deleted."""
    engine = _get_engine()
    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            if user_id:
                result = conn.execute(
                    text("DELETE FROM reports WHERE public_id = :pid AND user_id = :uid"),
                    {"pid": public_id, "uid": user_id}
                )
            else:
                result = conn.execute(
                    text("DELETE FROM reports WHERE public_id = :pid"),
                    {"pid": public_id}
                )
            conn.commit()
            return result.rowcount > 0
    else:
        conn = _sqlite_connection()
        if user_id:
            cursor = conn.execute(
                "DELETE FROM reports WHERE public_id = ? AND user_id = ?",
                (public_id, user_id)
            )
        else:
            cursor = conn.execute("DELETE FROM reports WHERE public_id = ?", (public_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted


# ── Chat messages ────────────────────────────────────────────────────

def save_chat_message(user_id: Optional[str], report_public_id: str, role: str, content: str) -> str:
    """Save a chat message and return its UUID."""
    msg_id = str(uuid.uuid4())
    engine = _get_engine()

    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO chat_messages (id, user_id, report_public_id, role, content)
                    VALUES (:id, :uid, :rpid, :role, :content)
                """),
                {"id": msg_id, "uid": user_id, "rpid": report_public_id, "role": role, "content": content}
            )
            conn.commit()
    else:
        conn = _sqlite_connection()
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, report_public_id, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, user_id, report_public_id, role, content, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    return msg_id


def get_chat_history(report_public_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get chat history for a report."""
    engine = _get_engine()

    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT role, content, created_at
                    FROM chat_messages
                    WHERE report_public_id = :rpid
                    ORDER BY created_at ASC
                    LIMIT :lim
                """),
                {"rpid": report_public_id, "lim": limit}
            )
            return [dict(row._mapping) for row in result.fetchall()]
    else:
        conn = _sqlite_connection()
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE report_public_id = ? ORDER BY created_at ASC LIMIT ?",
            (report_public_id, limit)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

def list_user_chats(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent chat history for a user across all their reports."""
    if not user_id:
        return []
    engine = _get_engine()
    if _use_postgres and engine is not None:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT role, content, created_at, report_public_id
                    FROM chat_messages
                    WHERE user_id = :uid
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"uid": user_id, "lim": limit}
            )
            return [dict(row._mapping) for row in result.fetchall()]
    else:
        conn = _sqlite_connection()
        rows = conn.execute(
            "SELECT role, content, created_at, report_public_id FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
