"""PR Sentinel — AI code review GitHub App.

Milestone 1: receive and verify GitHub webhooks.
Milestone 2: on PR opened, fetch the diff and post a summary comment.
"""

import hashlib
import hmac
import os

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request

from app.github_client import GitHubClient
from app.reviewer import review_pull_request

app = FastAPI(title="PR Sentinel")

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")


def verify_signature(payload: bytes, signature_header: str | None) -> None:
    """Verify the webhook actually came from GitHub (HMAC-SHA256)."""
    if not WEBHOOK_SECRET:
        raise HTTPException(500, "Server missing GITHUB_WEBHOOK_SECRET")
    if not signature_header:
        raise HTTPException(401, "Missing X-Hub-Signature-256 header")

    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(401, "Invalid webhook signature")


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict:
    payload = await request.body()
    verify_signature(payload, x_hub_signature_256)

    event = await request.json()

    # We only care about PRs being opened or updated with new commits.
    if x_github_event == "pull_request" and event.get("action") in (
        "opened",
        "synchronize",
        "reopened",
    ):
        installation_id = event["installation"]["id"]
        repo_full_name = event["repository"]["full_name"]
        pr_number = event["pull_request"]["number"]
        head_sha = event["pull_request"]["head"]["sha"]

        # Respond to GitHub fast; do the real work in the background.
        background_tasks.add_task(
            handle_pull_request, installation_id, repo_full_name, pr_number, head_sha
        )
        return {"queued": True}

    return {"ignored": x_github_event}


async def handle_pull_request(
    installation_id: int, repo_full_name: str, pr_number: int, head_sha: str
) -> None:
    """Fetch the PR diff, run the AI review, post results back to GitHub."""
    gh = GitHubClient(installation_id)

    diff = await gh.get_pr_diff(repo_full_name, pr_number)
    files = await gh.get_pr_files(repo_full_name, pr_number)

    review = await review_pull_request(diff, files)

    # Milestone 2: single summary comment.
    await gh.post_issue_comment(repo_full_name, pr_number, review.summary_markdown())

    # Milestone 3: inline comments (uncomment once summary flow works).
    # await gh.post_review(repo_full_name, pr_number, head_sha, review)
