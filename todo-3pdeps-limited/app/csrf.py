"""Purpose-built CSRF protection (replaces Flask-WTF's CSRFProtect).

A random per-session token lives in the (signed) session cookie; every
state-changing request must echo it back in the ``csrf_token`` form field or
``X-CSRFToken`` header. Checks are enforced globally in ``before_request`` so
no route can forget them; a missing or wrong token is a 400, matching the
Flask-WTF behavior the tests pin.
"""
from __future__ import annotations

import hmac
import secrets

from flask import Flask, abort, request, session

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def generate_csrf() -> str:
    """Return the session's CSRF token, creating it on first use."""
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


class CSRFProtect:
    """Unbound extension; attach with ``init_app`` in the application factory."""

    def init_app(self, app: Flask) -> None:
        app.config.setdefault("CSRF_ENABLED", True)
        app.jinja_env.globals["csrf_token"] = generate_csrf

        @app.before_request
        def _check_csrf():
            if not app.config["CSRF_ENABLED"]:
                return
            if request.method in SAFE_METHODS:
                return
            expected = session.get("csrf_token")
            supplied = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                abort(400)
