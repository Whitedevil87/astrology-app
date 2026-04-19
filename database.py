import sqlite3
from typing import Any, Dict, Optional

from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        )
        """
    )
    conn.commit()
    conn.close()


def migrate_db() -> None:
    conn = get_connection()
    cursor = conn.execute("PRAGMA table_info(reports)")
    columns = {row[1] for row in cursor.fetchall()}
    for name, definition in (
        ("strengths", "TEXT"),
        ("weaknesses", "TEXT"),
        ("wellness", "TEXT"),
        ("compatibility", "TEXT"),
        ("seasonal_energy", "TEXT"),
        ("report_extras", "TEXT"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {name} {definition}")
    conn.commit()
    conn.close()


def fetch_report_row(report_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    return row


def save_report(payload: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO reports (
            full_name, birth_date, birth_time, birth_place, palm_enabled, hand_choice, palm_image_path,
            zodiac, moon_sign, ascendant, personality, career, love_life, future_outlook,
            strengths, weaknesses, wellness, compatibility, seasonal_energy,
            palm_analysis, report_html, report_extras, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["full_name"],
            payload["birth_date"],
            payload["birth_time"],
            payload["birth_place"],
            payload["palm_enabled"],
            payload["hand_choice"],
            payload["palm_image_path"],
            payload["profile"]["zodiac"],
            payload["profile"]["moon_sign"],
            payload["profile"]["ascendant"],
            payload["sections"]["personality"],
            payload["sections"]["career"],
            payload["sections"]["love"],
            payload["sections"]["future"],
            payload["sections"]["strengths"],
            payload["sections"]["weaknesses"],
            payload["sections"]["wellness"],
            payload["sections"]["compatibility"],
            payload["sections"]["seasonal_energy"],
            payload["palm_analysis"],
            payload["report_html"],
            payload["report_extras"],
            payload["created_at"],
        ),
    )
    conn.commit()
    report_id = cursor.lastrowid or 0
    conn.close()
    return report_id
