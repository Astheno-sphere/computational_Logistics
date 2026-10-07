"""Shared local storage backed by SQLite.

Keeps every "compressed" tool return value so the LLM can later request the
full content via a small handle (e.g. ``exp_a1b2c3d4``).
"""

from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path

DB_DIR = Path.home() / ".claw-tsaver"
DB_PATH = DB_DIR / "store.db"


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Create the ``expansions`` table if it does not yet exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expansions (
                id           TEXT PRIMARY KEY,
                timestamp    INTEGER NOT NULL,
                tool_name    TEXT NOT NULL,
                full_content TEXT NOT NULL
            )
            """
        )


def save_expansion(tool_name: str, full_content: str) -> str:
    """Persist ``full_content`` and return a freshly minted handle."""
    handle = "exp_" + secrets.token_hex(4)  # 8 hex chars after the prefix
    with _connect() as conn:
        conn.execute(
            "INSERT INTO expansions (id, timestamp, tool_name, full_content) "
            "VALUES (?, ?, ?, ?)",
            (handle, int(time.time()), tool_name, full_content),
        )
    return handle


def get_expansion(handle: str) -> str | None:
    """Return the stored content for ``handle``, or ``None`` if unknown."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT full_content FROM expansions WHERE id = ?", (handle,)
        ).fetchone()
    return row[0] if row else None