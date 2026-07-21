"""SQLite storage for tracked repos.

Upgraded from a JSON file to a real SQL database. SQLite is a full SQL
engine that lives in a single file on disk — no separate database server
to run — and it ships with Python (the built-in `sqlite3` module), so
there's no extra dependency.

The public functions (list_repos / get_repo / record_repo_activity /
update_settings) keep the SAME shapes they had with the JSON version, so
nothing that calls this file had to change.
"""

import os
import sqlite3
from pathlib import Path

# Where the database file lives. Overridable via env var.
DB_FILE = Path(os.environ.get("SENTINEL_DB_FILE", "data/sentinel.db"))


def _connect() -> sqlite3.Connection:
    """Open a connection, making sure the folder and table exist first."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # lets us read columns by name, like a dict
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS repos (
            full_name       TEXT PRIMARY KEY,
            installation_id INTEGER NOT NULL,
            review_enabled  INTEGER NOT NULL DEFAULT 1,  -- SQLite has no bool: 1/0
            vibe            TEXT    NOT NULL DEFAULT '',
            review_count    INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a database row into the same dict shape the JSON version returned."""
    return {
        "full_name": row["full_name"],
        "installation_id": row["installation_id"],
        "settings": {
            "review_enabled": bool(row["review_enabled"]),
            "vibe": row["vibe"] or "",
        },
        "review_count": row["review_count"],
    }


def list_repos() -> list[dict]:
    """All tracked repos, sorted by name (for the dashboard)."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM repos ORDER BY full_name").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_repo(full_name: str) -> dict | None:
    """One repo's stored record, or None if we've never seen it."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM repos WHERE full_name = ?", (full_name,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def record_repo_activity(full_name: str, installation_id: int) -> None:
    """Upsert a repo when a webhook arrives: insert if new, bump count if seen.

    The `ON CONFLICT ... DO UPDATE` is SQL's way of saying 'if this repo is
    already in the table, update it instead of erroring'. Existing settings
    (review_enabled, vibe) are left untouched — only the count and install id move.
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO repos (full_name, installation_id, review_count)
            VALUES (?, ?, 1)
            ON CONFLICT(full_name) DO UPDATE SET
                installation_id = excluded.installation_id,
                review_count    = review_count + 1
            """,
            (full_name, installation_id),
        )
        conn.commit()


def update_settings(
    full_name: str,
    *,
    review_enabled: bool | None = None,
    vibe: str | None = None,
) -> None:
    """Change a repo's settings. Only the arguments you pass are updated.

    (Not used yet — this is what Phase 2's dashboard 'save' button will call.)
    """
    fields, values = [], []
    if review_enabled is not None:
        fields.append("review_enabled = ?")
        values.append(1 if review_enabled else 0)
    if vibe is not None:
        fields.append("vibe = ?")
        values.append(vibe)
    if not fields:
        return
    values.append(full_name)
    with _connect() as conn:
        conn.execute(f"UPDATE repos SET {', '.join(fields)} WHERE full_name = ?", values)
        conn.commit()
