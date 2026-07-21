"""Simple JSON-file storage for tracked repos.

Phase 1 of the dashboard: no database yet — just one JSON file on disk.
Every repo Sentinel has seen gets an entry with its settings and a small
bit of activity data. This is deliberately the simplest thing that works;
we can swap it for a real database later without changing the callers.
"""

import json
import os
from pathlib import Path

# Where the JSON file lives. Overridable via env var; defaults to data/repos.json.
DATA_FILE = Path(os.environ.get("SENTINEL_DATA_FILE", "data/repos.json"))

# The default settings a repo starts with the first time we see it.
DEFAULT_SETTINGS = {
    "review_enabled": True,  # Phase 2 will let the dashboard toggle this
    "vibe": "",              # Phase 2: your per-repo "what this app is about" text
}


def _load() -> dict:
    """Read the whole JSON file into a dict. Empty dict if it doesn't exist yet."""
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)


def _save(data: dict) -> None:
    """Write the whole dict back to the JSON file (creating the folder if needed)."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def list_repos() -> list[dict]:
    """All tracked repos, as a sorted list of dicts (for the dashboard)."""
    data = _load()
    return [{"full_name": name, **info} for name, info in sorted(data.items())]


def get_repo(full_name: str) -> dict | None:
    """One repo's stored record, or None if we've never seen it."""
    return _load().get(full_name)


def record_repo_activity(full_name: str, installation_id: int) -> None:
    """Upsert a repo when a webhook arrives: create it if new, bump its count.

    'Upsert' = update if it exists, insert if it doesn't. Called from the
    webhook handler so the dashboard fills in automatically as PRs come in.
    """
    data = _load()
    entry = data.get(
        full_name,
        {
            "installation_id": installation_id,
            "settings": dict(DEFAULT_SETTINGS),
            "review_count": 0,
        },
    )
    entry["installation_id"] = installation_id
    entry["review_count"] = entry.get("review_count", 0) + 1
    data[full_name] = entry
    _save(data)
