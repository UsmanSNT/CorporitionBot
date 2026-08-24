import sqlite3
import os
from config import config


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      INTEGER PRIMARY KEY,
                username     TEXT,
                first_name   TEXT,
                started_at   TEXT NOT NULL DEFAULT (datetime('now')),
                clicked_vote INTEGER NOT NULL DEFAULT 0,
                clicked_vote_at TEXT,
                voted        INTEGER NOT NULL DEFAULT 0,
                voted_at     TEXT,
                reminder_at  TEXT,
                referred_by  INTEGER,
                deadline_reminded INTEGER NOT NULL DEFAULT 0
            )
        """)
        # migrate existing DB: add columns if missing
        for col, definition in [
            ("referred_by", "INTEGER"),
            ("deadline_reminded", "INTEGER NOT NULL DEFAULT 0"),
            ("mahalla", "TEXT"),
            ("awaiting_proof", "INTEGER NOT NULL DEFAULT 0"),
            ("pending_approval", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            except Exception:
                pass
        conn.commit()


def upsert_user(user_id: int, username: str | None, first_name: str | None,
                referred_by: int | None = None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, referred_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name, referred_by))
        conn.commit()


def mark_clicked_vote(user_id: int):
    with get_conn() as conn:
        conn.execute("""
            UPDATE users SET clicked_vote = 1, clicked_vote_at = datetime('now')
            WHERE user_id = ? AND clicked_vote = 0
        """, (user_id,))
        conn.commit()


def mark_voted(user_id: int):
    with get_conn() as conn:
        conn.execute("""
            UPDATE users SET voted = 1, voted_at = datetime('now')
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()


def set_reminder(user_id: int, remind_at: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET reminder_at = ? WHERE user_id = ?", (remind_at, user_id))
        conn.commit()


def clear_reminder(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET reminder_at = NULL WHERE user_id = ?", (user_id,))
        conn.commit()


def get_due_reminders() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT user_id, first_name FROM users
            WHERE reminder_at IS NOT NULL
              AND reminder_at <= datetime('now')
              AND voted = 0
        """).fetchall()
        return [dict(r) for r in rows]


def set_awaiting_proof(user_id: int, value: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET awaiting_proof = ? WHERE user_id = ?", (1 if value else 0, user_id))
        conn.commit()


def set_pending_approval(user_id: int, value: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET pending_approval = ? WHERE user_id = ?", (1 if value else 0, user_id))
        conn.commit()


def get_recent_users(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT user_id, username, first_name, started_at, voted, pending_approval
            FROM users ORDER BY started_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def set_mahalla(user_id: int, mahalla: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET mahalla = ? WHERE user_id = ?", (mahalla, user_id))
        conn.commit()


def get_mahalla_stats() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT mahalla, COUNT(*) as total,
                   SUM(voted) as voted_count
            FROM users
            WHERE mahalla IS NOT NULL
            GROUP BY mahalla
            ORDER BY total DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_non_voted_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT user_id, first_name, deadline_reminded FROM users WHERE voted = 0
        """).fetchall()
        return [dict(r) for r in rows]


def mark_deadline_reminded(user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET deadline_reminded = deadline_reminded + 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()


def get_referral_count(referrer_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by = ?", (referrer_id,)
        ).fetchone()
        return row[0] if row else 0


def get_top_referrers(limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT u.user_id, u.username, u.first_name,
                   COUNT(r.user_id) AS referral_count
            FROM users u
            JOIN users r ON r.referred_by = u.user_id
            GROUP BY u.user_id
            ORDER BY referral_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        clicked = conn.execute("SELECT COUNT(*) FROM users WHERE clicked_vote = 1").fetchone()[0]
        voted = conn.execute("SELECT COUNT(*) FROM users WHERE voted = 1").fetchone()[0]
        reminded = conn.execute("SELECT COUNT(*) FROM users WHERE reminder_at IS NOT NULL").fetchone()[0]
        via_referral = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM users WHERE pending_approval = 1").fetchone()[0]
    return {"total": total, "clicked": clicked, "voted": voted,
            "reminded": reminded, "via_referral": via_referral, "pending": pending}


def get_all_user_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [r[0] for r in rows]


def delete_user(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()


def get_user(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
