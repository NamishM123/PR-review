# 🛡️ PR Sentinel

An AI code-review agent, built as a GitHub App. When a pull request opens,
Sentinel fetches the diff, reviews it with an LLM, and posts findings back
to the PR.

## Architecture

```
GitHub PR event
      │  webhook (HMAC-verified)
      ▼
FastAPI server (app/main.py)
      │  background task
      ▼
GitHubClient (app/github_client.py)   ← JWT → installation token auth
      │  fetch diff
      ▼
Reviewer (app/reviewer.py)            ← LLM, structured JSON output
      │
      ▼
Comment / inline review posted to the PR
```

## Setup

### 1. Register the GitHub App
1. GitHub → Settings → Developer settings → GitHub Apps → **New GitHub App**
2. Webhook URL: your smee.io channel for local dev (see step 3)
3. Webhook secret: generate one (`openssl rand -hex 32`) and save it
4. Permissions: **Pull requests: Read & write**, **Contents: Read**
5. Subscribe to events: **Pull request**
6. After creating: note the **App ID**, generate and download the
   **private key** (.pem), then install the app on one of your repos

### 2. Environment
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values
```

### 3. Local webhook tunnel
GitHub can't reach localhost, so use smee:
```bash
npx smee -u https://smee.io/YOUR_CHANNEL -t http://localhost:8000/webhook
```

### 4. Run
```bash
uvicorn app.main:app --reload --port 8000
```

Open a PR on the repo where the app is installed. Watch the review appear.

## Milestones
- [x] M1: Webhook server with signature verification
- [x] M2: Summary comment on PR open (this skeleton)
- [ ] M3: Inline comments on exact lines (`post_review` — line mapping!)
- [ ] M4: Per-file chunking for large diffs, merge results
- [ ] M5: `.sentinel.yml` config (strictness, ignored paths)
- [ ] M6: Dedupe on `synchronize` — don't re-post old findings
- [ ] M7: Deploy (Fly.io/Railway) + Dockerfile + CI
- [ ] M8: Eval harness — 20 diffs with planted bugs, measure catch rate
