"""Application configuration.

Values that are required for the app to run securely are read from the
environment and validated at startup. Missing required values fail fast with a
helpful message rather than silently falling back to an insecure default.
"""
from __future__ import annotations

import os
from pathlib import Path

# app/ -> project root
BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def _require(name: str) -> str:
    """Return a required environment variable or fail fast with guidance."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required configuration '{name}'. "
            f"Set it in your environment or in the project's .env file. "
            f"You can generate one by running: python -c "
            f'"import secrets; print(secrets.token_hex(32))"'
        )
    return value


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = _require("SECRET_KEY")

    # Default to a SQLite database stored in the instance folder.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'todo.sqlite'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session / cookie hardening.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Only send cookies over HTTPS when explicitly running in production.
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
