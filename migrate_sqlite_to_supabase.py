"""
One-time migration: SQLite → Supabase PostgreSQL.

Usage:
    python migrate_sqlite_to_supabase.py

Requires:
    DATABASE_URL env var pointing to Supabase PostgreSQL
    Existing astrology.db in instance/ folder
"""
import os
import sqlite3
import uuid
import sys

def migrate():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    sqlite_path = os.path.join(base_dir, "instance", "astrology.db")

    if not os.path.exists(sqlite_path):
        print(f"No SQLite database found at {sqlite_path}")
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("DATABASE_URL environment variable not set")
        sys.exit(1)

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    engine = create_engine(db_url, poolclass=NullPool)
    conn_sqlite = sqlite3.connect(sqlite_path)
    conn_sqlite.row_factory = sqlite3.Row

    rows = conn_sqlite.execute("SELECT * FROM reports").fetchall()
    print(f"Found {len(rows)} reports in SQLite")

    if not rows:
        print("Nothing to migrate")
        return

    migrated = 0
    with engine.connect() as pg:
        for row in rows:
            d = dict(row)
            public_id = d.get("public_id") or str(uuid.uuid4())
            try:
                pg.execute(text("""
                    INSERT INTO reports (
                        public_id, full_name, birth_date, birth_time, birth_place,
                        palm_enabled, hand_choice, palm_image_path,
                        zodiac, moon_sign, ascendant,
                        personality, career, love_life, future_outlook,
                        strengths, weaknesses, wellness, compatibility, seasonal_energy,
                        palm_analysis, report_html, report_extras, created_at
                    ) VALUES (
                        :public_id, :full_name, :birth_date, :birth_time, :birth_place,
                        :palm_enabled, :hand_choice, :palm_image_path,
                        :zodiac, :moon_sign, :ascendant,
                        :personality, :career, :love_life, :future_outlook,
                        :strengths, :weaknesses, :wellness, :compatibility, :seasonal_energy,
                        :palm_analysis, :report_html, :report_extras, :created_at
                    ) ON CONFLICT (public_id) DO NOTHING
                """), {
                    "public_id": public_id,
                    "full_name": d["full_name"], "birth_date": d["birth_date"],
                    "birth_time": d["birth_time"], "birth_place": d["birth_place"],
                    "palm_enabled": d.get("palm_enabled", 0),
                    "hand_choice": d.get("hand_choice"),
                    "palm_image_path": d.get("palm_image_path"),
                    "zodiac": d["zodiac"], "moon_sign": d["moon_sign"], "ascendant": d["ascendant"],
                    "personality": d["personality"], "career": d["career"],
                    "love_life": d["love_life"], "future_outlook": d["future_outlook"],
                    "strengths": d.get("strengths"), "weaknesses": d.get("weaknesses"),
                    "wellness": d.get("wellness"), "compatibility": d.get("compatibility"),
                    "seasonal_energy": d.get("seasonal_energy"),
                    "palm_analysis": d.get("palm_analysis"),
                    "report_html": d["report_html"],
                    "report_extras": d.get("report_extras"),
                    "created_at": d["created_at"],
                })
                migrated += 1
            except Exception as e:
                print(f"  Error migrating row {d.get('id')}: {e}")

        pg.commit()

    # Verify
    with engine.connect() as pg:
        result = pg.execute(text("SELECT COUNT(*) FROM reports"))
        pg_count = result.scalar()

    print(f"\nMigration complete:")
    print(f"  SQLite rows:    {len(rows)}")
    print(f"  Migrated:       {migrated}")
    print(f"  PostgreSQL rows: {pg_count}")

    if pg_count >= len(rows):
        print("  ✅ Verification passed")
    else:
        print("  ⚠️ Row count mismatch — check for errors above")

    conn_sqlite.close()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    migrate()
