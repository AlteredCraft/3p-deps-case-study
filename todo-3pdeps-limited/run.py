"""Development entry point.

Loads environment variables from a local .env file (if present) and starts the
Flask development server.
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


load_dotenv()

from app import create_app  # noqa: E402  (import after env is loaded)

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
