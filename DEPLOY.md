# Deploying PR Sentinel

## Deploy to Vercel

### 1. Push the repo to GitHub, then import it
On [vercel.com](https://vercel.com) → **Add New → Project** → import this repo.
No build settings to change: `vercel.json` routes every request to
`api/index.py`, which serves the FastAPI app.

### 2. Set environment variables
In **Project → Settings → Environment Variables**, add:

| Variable | Value |
|---|---|
| `GITHUB_APP_ID` | your GitHub App's ID |
| `GITHUB_WEBHOOK_SECRET` | the webhook secret you generated |
| `GITHUB_PRIVATE_KEY` | the **contents** of your `.pem` file (see below) |
| `GROQ_API_KEY` | your Groq key (or use `OPENAI_API_KEY` instead) |
| `SENTINEL_MODEL` | optional — defaults to `llama-3.3-70b-versatile` on Groq, `gpt-4o` on OpenAI |

**Choosing a provider:** Groq serves an OpenAI-compatible API, so the same SDK
works for both. Set **`GROQ_API_KEY`** to use Groq, or **`OPENAI_API_KEY`** to
use OpenAI — the app picks whichever is present (Groq wins if both are set).
`LLM_BASE_URL` overrides the endpoint for any other compatible provider.

Groq model names change over time; if you get a "model not found" error, check
the current list at <https://console.groq.com/docs/models> and set
`SENTINEL_MODEL` accordingly.

**About the private key:** there's no filesystem to drop a `.pem` on, so paste
the key itself into `GITHUB_PRIVATE_KEY`. If your input box flattens newlines,
paste it with literal `\n` sequences — the app converts them back:

```
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----"
```

Never commit the key. `.gitignore` blocks `*.pem` and `.vercelignore` keeps it
out of the deployment bundle.

### 3. Point the GitHub App at your deployment
In your GitHub App settings, set the **Webhook URL** to:

```
https://<your-project>.vercel.app/webhook
```

### 4. Verify
- `https://<your-project>.vercel.app/healthz` → `{"status":"ok"}`
- `https://<your-project>.vercel.app/dashboard` → the dashboard

Open a PR on a repo where the App is installed and watch the review appear.

---

## ⚠️ Two real limitations of serverless for this app

Vercel runs **serverless functions**, not a long-lived server. That conflicts
with two things this app does. Both are fine for a demo; neither is fine for
sustained production use.

### 1. Storage is ephemeral — data does not persist
Serverless filesystems are read-only except `/tmp`, and `/tmp` is **wiped on
cold starts**. The app detects Vercel and puts SQLite in `/tmp`, so it works,
but **repo settings (your vibes), review history, and stats will reset**
whenever the function goes cold.

**Fixes, in order of effort:**
- Point `SENTINEL_DB_FILE` at a mounted persistent volume (if your host offers one).
- Move to a hosted database — Vercel Postgres, Neon, Supabase, or
  [Turso](https://turso.tech) (SQLite-compatible, so `storage.py` changes least).
- Deploy somewhere with a real disk instead (see below).

### 2. Background tasks vs. function timeouts
The webhook handler answers GitHub immediately and does the review in a
background task. On a normal server the process keeps running afterwards. On
serverless, the function stays alive until the background work finishes and is
**killed at `maxDuration`** (set to 60s in `vercel.json`; the ceiling depends on
your plan). A slow LLM review on a large diff can be cut off mid-flight.

**Fixes:** raise `maxDuration`, keep diffs small (`MAX_DIFF_CHARS`), or move the
review onto a queue (e.g. QStash/Inngest) instead of an in-process background task.

---

## Alternative: a host with a real server

Because this app is a long-running service with a database, a container host is
a better architectural fit than serverless. **Railway**, **Fly.io**, and
**Render** all run the app as-is with a persistent disk:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set the same environment variables (there you *can* mount a real `.pem` file and
use `GITHUB_PRIVATE_KEY_PATH`), and SQLite persists on the attached volume with
no code changes.

---

## Before any public deployment

**The dashboard has no authentication.** Anyone who finds the URL can view your
tracked repos and change their settings. Add auth (Phase 5) before exposing a
deployment publicly, or keep the deployment private.
