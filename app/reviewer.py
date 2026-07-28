"""The AI reviewer: diff in, structured review out."""

import json
import os

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

# Which LLM provider to use.
#
# Groq serves an OpenAI-COMPATIBLE API, so the same `openai` SDK works for both
# — only the base URL, key, and model name differ. If GROQ_API_KEY is set we use
# Groq; otherwise we fall back to OpenAI. LLM_BASE_URL overrides either, so any
# other OpenAI-compatible provider (Together, OpenRouter, a local server) works
# too without code changes.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_groq_key = os.environ.get("GROQ_API_KEY", "")
USING_GROQ = bool(_groq_key)

API_KEY = _groq_key or os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL") or (GROQ_BASE_URL if USING_GROQ else None)

# Default model depends on the provider (their model names are different).
MODEL = os.environ.get(
    "SENTINEL_MODEL",
    "llama-3.3-70b-versatile" if USING_GROQ else "gpt-4o",
)

MAX_DIFF_CHARS = 60_000  # naive chunking guard for milestone 2


class InlineComment(BaseModel):
    path: str
    line: int          # line number in the NEW version of the file
    severity: str      # "bug" | "security" | "style" | "suggestion"
    body: str


class Review(BaseModel):
    summary: str
    comments: list[InlineComment]

    def summary_markdown(self) -> str:
        lines = ["## 🛡️ PR Sentinel Review\n", self.summary, ""]
        if self.comments:
            lines.append("### Findings\n")
            for c in self.comments:
                lines.append(f"- **[{c.severity}]** `{c.path}:{c.line}` — {c.body}")
        else:
            lines.append("_No issues found._")
        return "\n".join(lines)


SYSTEM_PROMPT = """You are a senior code reviewer. You will receive a unified diff.
Review ONLY the changed code. Look for: real bugs, security issues,
error handling gaps, and significant style problems. Do not nitpick.

Respond with ONLY a JSON object, no markdown fences, in this exact shape:
{
  "summary": "2-4 sentence overall assessment",
  "comments": [
    {"path": "file.py", "line": 42, "severity": "bug", "body": "explanation"}
  ]
}
`line` must be a line number in the new version of the file that was
added or modified in this diff. If there are no issues, use an empty list."""


async def review_pull_request(diff: str, files: list[dict], vibe: str = "") -> Review:
    if len(diff) > MAX_DIFF_CHARS:
        # Milestone 4: chunk per-file and merge reviews. For now, truncate.
        diff = diff[:MAX_DIFF_CHARS] + "\n... [diff truncated]"

    # If this repo has a saved "vibe", append it to the system prompt so the
    # review focuses on what this project actually cares about.
    system_prompt = SYSTEM_PROMPT
    if vibe.strip():
        system_prompt += (
            f"\n\nProject context from the maintainer — weight your review "
            f"accordingly:\n{vibe.strip()}"
        )

    # Same SDK for both providers — only base_url/key/model differ.
    client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
    response = await client.chat.completions.create(
        model=MODEL,
        max_tokens=2000,
        response_format={"type": "json_object"},  # ask for guaranteed-valid JSON
        messages=[
            # These APIs carry the system prompt as the first message,
            # not as a separate `system=` argument like Anthropic does.
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Review this diff:\n\n{diff}"},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return Review(**json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        # Model went off-script; fail soft with a summary-only review.
        return Review(summary=raw[:1000], comments=[])
