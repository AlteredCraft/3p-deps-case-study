"""Security-contract tests.

These pin behavior currently provided by Flask-WTF (CSRF), Werkzeug (password
hashing), and our own config layer, so that a dependency swap must preserve it.
CSRF is disabled in the default `client`; these use the dedicated `csrf_client`
with protection turned ON.
"""
from __future__ import annotations

import pytest

from tests.conftest import csrf_token, db_query, register


# ---- CSRF (Flask-WTF contract) ----------------------------------------------

def test_csrf_token_rendered_on_forms(csrf_client):
    page = csrf_client.get("/register").data
    assert csrf_token(page) is not None


def test_post_without_csrf_is_rejected(csrf_client):
    resp = csrf_client.post(
        "/register",
        data={"username": "nocsrf", "email": "nocsrf@example.com",
              "password": "password123", "confirm": "password123"},
    )
    assert resp.status_code == 400  # CSRF token missing


def test_post_with_csrf_succeeds(csrf_client):
    token = csrf_token(csrf_client.get("/register").data)
    resp = csrf_client.post(
        "/register",
        data={"csrf_token": token,
              "username": "withcsrf", "email": "withcsrf@example.com",
              "password": "password123", "confirm": "password123"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"My tasks" in resp.data


# ---- password storage (Werkzeug — a dependency we intend to KEEP) -----------

def test_password_is_not_stored_in_plaintext(client, db_path):
    register(client, username="secure", email="secure@example.com", password="sup3rsecret!")
    row = db_query(db_path, "SELECT password_hash FROM users WHERE username = ?", ("secure",))[0]
    assert "sup3rsecret!" not in row["password_hash"]
    assert ":" in row["password_hash"]        # algorithm:params:salt:hash
    assert len(row["password_hash"]) > 20


# ---- config fail-fast (our own contract; no insecure fallback) --------------

def test_missing_required_config_fails_fast(monkeypatch):
    from app.config import _require

    monkeypatch.delenv("DEFINITELY_MISSING_VAR", raising=False)
    with pytest.raises(RuntimeError) as exc:
        _require("DEFINITELY_MISSING_VAR")
    assert "DEFINITELY_MISSING_VAR" in str(exc.value)
