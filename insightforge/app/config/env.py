"""Load local environment variables from insightforge/.env when present."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_INSIGHTFORGE_ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    """Load `.env` from the insightforge project root (no-op if missing)."""
    load_dotenv(_INSIGHTFORGE_ROOT / ".env", override=False)
