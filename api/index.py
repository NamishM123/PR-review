"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a file under `api/` and serves the ASGI
`app` object it exports. This module just re-exports the FastAPI app from
`app/main.py` so there's exactly one copy of the real code.

Local development is unchanged: `uvicorn app.main:app --reload --port 8000`.
"""

import os
import sys

# Make the repo root importable so `from app.main import app` resolves when
# Vercel executes this file from inside api/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402

__all__ = ["app"]
