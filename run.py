"""Development entry point.

Loads environment variables from a local .env file (if present) and starts the
Flask development server.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (import after env is loaded)

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
