"""Minimal .env loader — dev-only, the first-party stand-in for python-dotenv.

Used solely by the ``run.py`` development entry point to read a local ``.env``
file (KEY=VALUE lines; the real environment always wins). Nothing under
``app/`` imports this: production processes are expected to receive real
environment variables, exactly as they were before the swap.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path = Path(__file__).parent / ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines; existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        os.environ.setdefault(key, value.strip().strip("'\""))
