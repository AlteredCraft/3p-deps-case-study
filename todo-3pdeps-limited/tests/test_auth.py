"""Registration, login, logout, session, and redirect-safety behavior.

Black-box: everything is driven over HTTP. Persisted-state checks use the
stdlib sqlite3 helper, never the ORM. These pin behavior currently provided by
Flask-Login, WTForms, and email-validator so a dependency swap must preserve it.
"""
from __future__ import annotations

import pytest

from tests.conftest import db_query, login, logout, register


# ---- registration: success + persistence ------------------------------------

def test_register_logs_you_in_and_shows_tasks(client):
    resp = register(client)
    assert resp.status_code == 200
    assert b"My tasks" in resp.data  # landed on the authenticated todo index


def test_register_persists_user_with_hashed_password(client, db_path):
    register(client, username="alice", email="alice@example.com", password="password123")
    rows = db_query(
        db_path,
        "SELECT username, email, password_hash FROM users WHERE username = ?",
        ("alice",),
    )
    assert len(rows) == 1
    assert rows[0]["email"] == "alice@example.com"
    assert rows[0]["password_hash"] != "password123"  # stored hashed
    assert ":" in rows[0]["password_hash"]             # werkzeug hash format


# ---- registration: validation (WTForms + email-validator contract) ----------

@pytest.mark.parametrize(
    "bad_email",
    [
        "plainaddress",
        "missing-at-sign.com",
        "@no-local-part.com",
        "no-domain@",
        "spaces in@example.com",
        "user@localhost",              # no dot after the @-sign
    ],
)
def test_register_rejects_malformed_email(client, bad_email):
    resp = client.post(
        "/register",
        data={"username": "newuser", "email": bad_email,
              "password": "password123", "confirm": "password123"},
        follow_redirects=True,
    )
    # Rejected -> stayed on the registration form, not the authed index.
    assert b"Create your account" in resp.data
    assert b"My tasks" not in resp.data


@pytest.mark.parametrize("good_email", ["user@example.com", "First.Last@sub.example.co"])
def test_register_accepts_valid_email(client, good_email):
    resp = client.post(
        "/register",
        data={"username": "validuser", "email": good_email,
              "password": "password123", "confirm": "password123"},
        follow_redirects=True,
    )
    assert b"My tasks" in resp.data


@pytest.mark.parametrize("bad_username", ["has space", "bad!char", "semi;colon", "slash/y"])
def test_register_rejects_invalid_username_chars(client, bad_username):
    resp = client.post(
        "/register",
        data={"username": bad_username, "email": "u@example.com",
              "password": "password123", "confirm": "password123"},
        follow_redirects=True,
    )
    assert b"Use only letters, numbers" in resp.data


def test_register_rejects_short_username(client):
    resp = client.post(
        "/register",
        data={"username": "ab", "email": "u@example.com",
              "password": "password123", "confirm": "password123"},
        follow_redirects=True,
    )
    assert b"between 3 and 80 characters" in resp.data


def test_register_rejects_short_password(client):
    resp = client.post(
        "/register",
        data={"username": "dan", "email": "dan@example.com",
              "password": "short", "confirm": "short"},
        follow_redirects=True,
    )
    assert b"between 8 and 128 characters" in resp.data


def test_register_rejects_mismatched_passwords(client):
    resp = client.post(
        "/register",
        data={"username": "carol", "email": "carol@example.com",
              "password": "password123", "confirm": "different99"},
        follow_redirects=True,
    )
    assert b"must match" in resp.data


def test_register_rejects_duplicate_username(client):
    register(client)
    logout(client)  # anonymous visitor retries with a taken username
    resp = register(client, email="other@example.com")
    assert b"already taken" in resp.data


def test_register_rejects_duplicate_email_case_insensitive(client):
    register(client)
    logout(client)
    resp = register(client, username="bob", email="ALICE@example.com")
    assert b"already exists" in resp.data


# ---- login / logout / session (Flask-Login contract) ------------------------

def test_login_by_username(client):
    register(client)
    logout(client)
    resp = login(client, "alice", "password123")
    assert b"Welcome back" in resp.data


def test_login_by_email(client):
    register(client)
    logout(client)
    resp = login(client, "alice@example.com", "password123")
    assert b"Welcome back" in resp.data


def test_login_wrong_password_is_generic(client):
    register(client)
    logout(client)
    resp = login(client, "alice", "wrongpass")
    assert b"Invalid username or password" in resp.data


def test_login_unknown_user_is_generic(client):
    resp = login(client, "ghost", "whatever12")
    assert b"Invalid username or password" in resp.data


def test_protected_route_redirects_anonymous(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_clears_session(client):
    register(client)                         # now authenticated
    assert client.get("/").status_code == 200
    logout(client)
    resp = client.get("/", follow_redirects=False)  # session must be gone
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_requires_post(client):
    register(client)
    assert client.get("/logout").status_code == 405  # method not allowed


def test_authenticated_user_redirected_away_from_login(client):
    register(client)  # already logged in
    resp = client.get("/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_authenticated_user_redirected_away_from_register(client):
    register(client)
    resp = client.get("/register", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


# ---- redirect safety (open-redirect protection) -----------------------------

def test_login_honors_safe_next(client):
    register(client)
    logout(client)
    resp = client.post(
        "/login?next=/tasks/new",
        data={"username": "alice", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/tasks/new")


@pytest.mark.parametrize(
    "evil_next",
    ["http://evil.example/", "//evil.example/", "https://evil.example/x"],
)
def test_login_rejects_unsafe_next(client, evil_next):
    register(client)
    logout(client)
    resp = client.post(
        f"/login?next={evil_next}",
        data={"username": "alice", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert "evil.example" not in location   # not redirected off-site
    assert location.endswith("/")           # fell back to the index


# ---- remember me (survives session loss; cleared on logout; tamper-proof) ----

def test_remember_me_survives_session_cookie_loss(client):
    register(client)
    logout(client)
    login(client, remember=True)
    assert client.get_cookie("remember_token") is not None
    client.delete_cookie("session")                 # simulate browser restart
    assert client.get("/", follow_redirects=False).status_code == 200


def test_login_without_remember_sets_no_remember_cookie(client):
    register(client)
    logout(client)
    login(client)
    assert client.get_cookie("remember_token") is None


def test_logout_clears_remember_cookie(client):
    register(client)
    logout(client)
    login(client, remember=True)
    logout(client)
    client.delete_cookie("session")
    resp = client.get("/", follow_redirects=False)  # remember cookie must be gone
    assert resp.status_code == 302


def test_tampered_remember_cookie_is_rejected(client):
    register(client)
    logout(client)
    login(client, remember=True)
    good = client.get_cookie("remember_token").value
    bad = good[:-4] + ("beef" if not good.endswith("beef") else "dead")
    client.delete_cookie("session")
    client.delete_cookie("remember_token")
    client.set_cookie("remember_token", bad)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302


def test_failed_login_preserves_remember_checkbox(client):
    register(client)
    logout(client)
    resp = login(client, password="wrongpass", remember=True)
    assert b"Invalid username or password" in resp.data
    assert b"checked" in resp.data                  # checkbox state re-rendered
