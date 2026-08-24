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
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                started_at  TEXT NOT NULL DEFAULT (datetime('now')),
                clicked_vote INTEGER NOT NULL DEFAULT 0,
                clicked_vote_at TEXT,
                voted       INTEGER NOT NULL DEFAULT 0,
                voted_at    TEXT,
                reminder_at TEXT
            )
        """)
        conn.commit()


def upsert_user(user_id: int, username: str | None, first_name: str | None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name))
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
        conn.execute("""
            UPDATE users SET reminder_at = ? WHERE user_id = ?
        """, (remind_at, user_id))
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


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        clicked = conn.execute("SELECT COUNT(*) FROM users WHERE clicked_vote = 1").fetchone()[0]
        voted = conn.execute("SELECT COUNT(*) FROM users WHERE voted = 1").fetchone()[0]
        reminded = conn.execute("SELECT COUNT(*) FROM users WHERE reminder_at IS NOT NULL").fetchone()[0]
    return {"total": total, "clicked": clicked, "voted": voted, "reminded": reminded}


def delete_user(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()


def get_user(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
