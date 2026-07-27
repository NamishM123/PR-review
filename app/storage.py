"""SQLite storage for tracked repos.

Upgraded from a JSON file to a real SQL database. SQLite is a full SQL
engine that lives in a single file on disk — no separate database server
to run — and it ships with Python (the built-in `sqlite3` module), so
there's no extra dependency.

The public functions (list_repos / get_repo / record_repo_activity /
update_settings) keep the SAME shapes they had with the JSON version, so
nothing that calls this file had to change.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Where the database file lives.
#
# Serverless platforms (Vercel/Lambda) ship a read-only filesystem with only
# /tmp writable, so we fall back there when we detect one. NOTE: /tmp is
# EPHEMERAL — it is wiped between cold starts, so data does not persist across
# deploys or idle periods. For durable storage on serverless, point
# SENTINEL_DB_FILE at a mounted volume, or move to a hosted database
# (see DEPLOY.md).
def _default_db_path() -> str:
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/sentinel.db"
    return "data/sentinel.db"


DB_FILE = Path(os.environ.get("SENTINEL_DB_FILE", _default_db_path()))


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
    # One row per review the bot has posted. `repo` links back to repos.full_name
    # (a foreign key), so a repo has many reviews — a one-to-many relationship.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            repo           TEXT    NOT NULL,
            pr_number      INTEGER NOT NULL,
            created_at     TEXT    NOT NULL,   -- ISO timestamp
            summary        TEXT    NOT NULL DEFAULT '',
            finding_count  INTEGER NOT NULL DEFAULT 0,
            severities     TEXT    NOT NULL DEFAULT '{}'  -- JSON: {"bug": 2, ...}
        )
        """
    )
    # Index the columns we filter/sort by, so history lookups stay fast as rows grow.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_repo ON reviews(repo, created_at DESC)"
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

    Called by the dashboard's save button (POST /settings).
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


# --------------------------------------------------------------- review history


def record_review(repo: str, pr_number: int, summary: str, comments: list) -> None:
    """Save one completed review so the dashboard can show history and stats.

    `comments` is the list of InlineComment objects from the Review; we store a
    count plus a per-severity tally (as JSON) rather than every comment body —
    enough for stats without bloating the table.
    """
    severities: dict[str, int] = {}
    for c in comments:
        sev = getattr(c, "severity", "unknown")
        severities[sev] = severities.get(sev, 0) + 1

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO reviews (repo, pr_number, created_at, summary,
                                 finding_count, severities)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                repo,
                pr_number,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                summary[:500],
                len(comments),
                json.dumps(severities),
            ),
        )
        conn.commit()


def _review_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "repo": row["repo"],
        "pr_number": row["pr_number"],
        "created_at": row["created_at"],
        "summary": row["summary"],
        "finding_count": row["finding_count"],
        "severities": json.loads(row["severities"] or "{}"),
    }


def recent_reviews(repo: str | None = None, limit: int = 10) -> list[dict]:
    """Most recent reviews, newest first — all repos, or just one."""
    with _connect() as conn:
        if repo:
            rows = conn.execute(
                "SELECT * FROM reviews WHERE repo = ? ORDER BY created_at DESC LIMIT ?",
                (repo, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_review_row(r) for r in rows]


def stats() -> dict:
    """Aggregate numbers for the dashboard header.

    COUNT/SUM are SQL aggregate functions: they compute over many rows and
    return a single value — much faster than pulling every row into Python.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS reviews, COALESCE(SUM(finding_count), 0) AS findings"
            " FROM reviews"
        ).fetchone()
        sev_rows = conn.execute("SELECT severities FROM reviews").fetchall()

    by_severity: dict[str, int] = {}
    for r in sev_rows:
        for sev, n in json.loads(r["severities"] or "{}").items():
            by_severity[sev] = by_severity.get(sev, 0) + n

    return {
        "total_reviews": row["reviews"],
        "total_findings": row["findings"],
        "by_severity": by_severity,
    }
