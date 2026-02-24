"""SQLite database layer for tracking seen and approved posts."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "digest.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    """Initialize database tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_posts (
            post_id TEXT PRIMARY KEY,
            subreddit TEXT,
            title TEXT,
            url TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS approved_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT UNIQUE,
            subreddit TEXT,
            title TEXT,
            url TEXT,
            content TEXT,
            grok_reason TEXT,
            approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            emailed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_approved_emailed ON approved_posts(emailed_at);
    """)
    conn.commit()


def is_seen(post_id: str) -> bool:
    """Check if we've already processed this post."""
    with get_connection() as conn:
        result = conn.execute(
            "SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return result is not None


def mark_seen(post_id: str, subreddit: str, title: str, url: str) -> None:
    """Record that we've seen a post."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO seen_posts (post_id, subreddit, title, url)
            VALUES (?, ?, ?, ?)
            """,
            (post_id, subreddit, title, url),
        )
        conn.commit()


def save_approved(
    post_id: str,
    subreddit: str,
    title: str,
    url: str,
    content: str,
    grok_reason: str,
) -> None:
    """Save an approved post."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO approved_posts
            (post_id, subreddit, title, url, content, grok_reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (post_id, subreddit, title, url, content, grok_reason),
        )
        conn.commit()


def get_unsent_approved() -> list[dict]:
    """Get approved posts that haven't been emailed yet."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, post_id, subreddit, title, url, content, grok_reason, approved_at
            FROM approved_posts
            WHERE emailed_at IS NULL
            ORDER BY approved_at ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def mark_emailed(post_ids: list[int]) -> None:
    """Mark posts as emailed."""
    if not post_ids:
        return
    with get_connection() as conn:
        placeholders = ",".join("?" * len(post_ids))
        conn.execute(
            f"UPDATE approved_posts SET emailed_at = ? WHERE id IN ({placeholders})",
            [datetime.now(), *post_ids],
        )
        conn.commit()


def get_stats() -> dict:
    """Get database statistics for CLI display."""
    with get_connection() as conn:
        seen_count = conn.execute("SELECT COUNT(*) FROM seen_posts").fetchone()[0]
        approved_count = conn.execute("SELECT COUNT(*) FROM approved_posts").fetchone()[0]
        unsent_count = conn.execute(
            "SELECT COUNT(*) FROM approved_posts WHERE emailed_at IS NULL"
        ).fetchone()[0]

        last_fetch = conn.execute(
            "SELECT MAX(fetched_at) FROM seen_posts"
        ).fetchone()[0]

        last_email = conn.execute(
            "SELECT MAX(emailed_at) FROM approved_posts WHERE emailed_at IS NOT NULL"
        ).fetchone()[0]

        return {
            "seen_posts": seen_count,
            "approved_posts": approved_count,
            "unsent_posts": unsent_count,
            "last_fetch": last_fetch,
            "last_email": last_email,
        }


def clear_seen() -> int:
    """Clear all seen posts. Returns count of deleted rows."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM seen_posts")
        conn.commit()
        return cursor.rowcount
