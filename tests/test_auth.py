"""Tests for registration, login, and logout."""
from __future__ import annotations

from app.extensions import db
from app.models import User
from tests.conftest import login, register


def test_register_creates_user_and_logs_in(client, app):
    resp = register(client)
    assert resp.status_code == 200
    assert b"My tasks" in resp.data  # redirected to the todo index
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "alice"))
        assert user is not None
        assert user.email == "alice@example.com"
        assert user.password_hash != "password123"  # stored hashed
        assert user.check_password("password123")


def test_register_rejects_duplicate_username(client):
    register(client)
    client.post("/logout", follow_redirects=True)  # anonymous visitor retries
    resp = register(client, email="other@example.com")
    assert b"already taken" in resp.data


def test_register_rejects_duplicate_email_case_insensitive(client):
    register(client)
    client.post("/logout", follow_redirects=True)
    resp = register(client, username="bob", email="ALICE@example.com")
    assert b"already exists" in resp.data


def test_register_rejects_mismatched_passwords(client):
    resp = client.post(
        "/register",
        data={
            "username": "carol",
            "email": "carol@example.com",
            "password": "password123",
            "confirm": "different99",
        },
        follow_redirects=True,
    )
    assert b"must match" in resp.data


def test_register_rejects_short_password(client):
    resp = client.post(
        "/register",
        data={"username": "dan", "email": "dan@example.com", "password": "short", "confirm": "short"},
        follow_redirects=True,
    )
    assert b"between 8 and 128 characters" in resp.data


def test_login_with_username_and_email(client):
    register(client)
    client.get("/logout")  # ignore; logout is POST only, so still logged in

    # log out properly
    client.post("/logout", follow_redirects=True)

    resp = login(client)
    assert b"Welcome back" in resp.data

    client.post("/logout", follow_redirects=True)
    resp = client.post(
        "/login",
        data={"username": "alice@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert b"Welcome back" in resp.data


def test_login_wrong_password_is_generic(client):
    register(client)
    client.post("/logout", follow_redirects=True)
    resp = client.post(
        "/login",
        data={"username": "alice", "password": "wrongpass"},
        follow_redirects=True,
    )
    assert b"Invalid username or password" in resp.data


def test_protected_route_redirects_anonymous(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_requires_post(client):
    register(client)
    resp = client.get("/logout")
    assert resp.status_code == 405  # method not allowed
