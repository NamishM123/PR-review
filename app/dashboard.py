"""Renders the dashboard HTML.

Phase 2 (Push A): each repo is now an editable form — you can set its
"vibe" (what the app is about / what to focus on) and turn review on or
off, then hit Save. The form POSTs to /settings, which writes to storage
and redirects back here.

We escape any user-supplied text with html.escape() so a stray quote or
'<' in a vibe can't break the page (or inject markup — basic XSS safety).
"""

import html


def _repo_card(repo: dict) -> str:
    """Build one editable card of HTML for a single repo."""
    full_name = html.escape(repo["full_name"])
    settings = repo.get("settings", {})
    enabled = settings.get("review_enabled", True)
    vibe = html.escape(settings.get("vibe", ""))
    count = repo.get("review_count", 0)

    # <option ... selected> marks the currently-saved choice as pre-selected.
    on_sel = "selected" if enabled else ""
    off_sel = "" if enabled else "selected"

    return f"""
    <div class="card">
      <form method="post" action="/settings">
        <input type="hidden" name="full_name" value="{full_name}">
        <div class="card-head">
          <code>{full_name}</code>
          <span class="count">{count} review(s) run</span>
        </div>
        <div class="fields">
          <label class="field-review">
            <span>Review</span>
            <select name="review_enabled">
              <option value="on" {on_sel}>🟢 on</option>
              <option value="off" {off_sel}>⚪️ off</option>
            </select>
          </label>
          <label class="field-vibe">
            <span>Vibe</span>
            <input type="text" name="vibe" value="{vibe}"
                   placeholder="e.g. Fast-moving MVP — flag bugs & security, skip style nitpicks">
          </label>
          <button type="submit">Save</button>
        </div>
      </form>
    </div>"""


def render_dashboard(repos: list[dict]) -> str:
    """Build the full dashboard HTML page from the list of tracked repos."""
    if repos:
        body = "".join(_repo_card(r) for r in repos)
    else:
        body = """
      <p class="muted">No repos yet. Once Sentinel reviews a PR on a repo it's
      installed on, it'll show up here automatically.</p>"""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PR Sentinel — Dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto;
           padding: 0 20px; color: #1a1a1a; background: #fafafa; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
    .count {{ color: #888; font-size: 0.85rem; }}
    .card {{ background: #fff; border: 1px solid #eee; border-radius: 10px;
             padding: 16px 18px; margin: 14px 0; }}
    .card-head {{ display: flex; justify-content: space-between; align-items: center;
                  margin-bottom: 12px; }}
    code {{ background: #f4f4f5; padding: 3px 8px; border-radius: 5px; font-size: 0.95rem; }}
    .fields {{ display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }}
    label {{ display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem;
             color: #666; text-transform: uppercase; letter-spacing: 0.03em; }}
    .field-vibe {{ flex: 1; min-width: 220px; }}
    select, input[type=text] {{ font-size: 0.95rem; padding: 8px 10px;
             border: 1px solid #ccc; border-radius: 6px; font-family: inherit; }}
    button {{ background: #1a1a1a; color: #fff; border: none; border-radius: 6px;
              padding: 9px 18px; font-size: 0.95rem; cursor: pointer; }}
    button:hover {{ background: #333; }}
    .muted {{ color: #999; }}
  </style>
</head>
<body>
  <h1>🛡️ PR Sentinel</h1>
  <p class="count">Tracking {len(repos)} repo(s). Set each repo's vibe so reviews match its goals.</p>
  {body}
</body>
</html>"""
