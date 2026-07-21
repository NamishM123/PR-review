"""GitHub App auth + API calls.

Auth flow (the part that trips everyone up):
1. Sign a short-lived JWT with your app's private key  -> proves you are the App
2. Exchange it for an installation access token        -> lets you act on ONE repo/org
3. Use that token for normal REST calls (expires in 1h)
"""

import os
import time

import httpx
import jwt  # pip install PyJWT

APP_ID = os.environ.get("GITHUB_APP_ID", "")
PRIVATE_KEY_PATH = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "private-key.pem")

API = "https://api.github.com"


def _app_jwt() -> str:
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = f.read()
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": APP_ID}
    return jwt.encode(payload, private_key, algorithm="RS256")


class GitHubClient:
    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self._token: str | None = None
        self._token_expires_at: float = 0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 120:
            return self._token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API}/app/installations/{self.installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {_app_jwt()}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["token"]
        self._token_expires_at = time.time() + 55 * 60
        return self._token

    async def _headers(self, accept: str = "application/vnd.github+json") -> dict:
        return {
            "Authorization": f"Bearer {await self._get_token()}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Raw unified diff of the whole PR."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API}/repos/{repo}/pulls/{pr_number}",
                headers=await self._headers("application/vnd.github.diff"),
            )
            resp.raise_for_status()
            return resp.text

    async def get_pr_files(self, repo: str, pr_number: int) -> list[dict]:
        """Per-file metadata: filename, status, patch, additions/deletions."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API}/repos/{repo}/pulls/{pr_number}/files",
                headers=await self._headers(),
                params={"per_page": 100},
            )
            resp.raise_for_status()
            return resp.json()

    async def post_issue_comment(self, repo: str, pr_number: int, body: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API}/repos/{repo}/issues/{pr_number}/comments",
                headers=await self._headers(),
                json={"body": body},
            )
            resp.raise_for_status()

    async def post_review(self, repo: str, pr_number: int, commit_sha: str, review) -> None:
        """Milestone 3: one review with inline comments attached to lines.

        Note: `line` must be a line that appears in the diff, and `side` is
        "RIGHT" for added lines. Getting this mapping right is the hard part.
        """
        comments = [
            {
                "path": c.path,
                "line": c.line,
                "side": "RIGHT",
                "body": c.body,
            }
            for c in review.comments
        ]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API}/repos/{repo}/pulls/{pr_number}/reviews",
                headers=await self._headers(),
                json={
                    "commit_id": commit_sha,
                    "event": "COMMENT",
                    "body": review.summary,
                    "comments": comments,
                },
            )
            resp.raise_for_status()
