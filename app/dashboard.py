"""Renders the dashboard HTML.

Phase 1: a simple server-rendered page that lists the repos Sentinel has
seen. 'Server-rendered' means Python builds the HTML string here and sends
the finished page — no JavaScript needed yet. Later phases add settings
toggles and the audit report on top of this.
"""


def _repo_row(repo: dict) -> str:
    """Build one table row of HTML for a single repo."""
    settings = repo.get("settings", {})
    enabled = settings.get("review_enabled", True)
    status = "🟢 on" if enabled else "⚪️ off"
    vibe = settings.get("vibe") or "<span class='muted'>— not set —</span>"
    return f"""
      <tr>
        <td><code>{repo['full_name']}</code></td>
        <td>{status}</td>
        <td>{repo.get('review_count', 0)}</td>
        <td>{vibe}</td>
      </tr>"""


def render_dashboard(repos: list[dict]) -> str:
    """Build the full dashboard HTML page from the list of tracked repos."""
    if repos:
        rows = "".join(_repo_row(r) for r in repos)
        table = f"""
      <table>
        <thead>
          <tr><th>Repository</th><th>Review</th><th>Reviews run</th><th>Vibe</th></tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>"""
    else:
        table = """
      <p class="muted">No repos yet. Once Sentinel reviews a PR on a repo it's
      installed on, it'll show up here automatically.</p>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PR Sentinel — Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 820px; margin: 40px auto;
           padding: 0 20px; color: #1a1a1a; }}
    h1 {{ font-size: 1.6rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #eee; }}
    th {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em;
          color: #666; }}
    code {{ background: #f4f4f5; padding: 2px 6px; border-radius: 4px; }}
    .muted {{ color: #999; }}
    .count {{ color: #666; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>🛡️ PR Sentinel</h1>
  <p class="count">Tracking {len(repos)} repo(s).</p>
  {table}
</body>
</html>"""
