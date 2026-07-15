"""Shared pytest fixtures and black-box helpers.

The test *bodies* are deliberately implementation-agnostic: they drive the app
through its HTTP interface and, when they must inspect persisted state, query the
SQLite file with the stdlib ``sqlite3`` module — never the app's data layer. That
is what lets the same suite validate the app before *and* after we swap out
third-party dependencies (SQLAlchemy — now removed — Flask-WTF, WTForms,
Flask-Login, email-validator).

Only this conftest is implementation-aware. It is the thin adapter between the
tests and whatever backend is currently wired up; when a dependency is replaced,
update the fixtures here, and the test bodies should not need to change.

The persisted-state helpers rely only on the SQLite *schema* (tables ``users``
and ``tasks``), which the dependency refactor preserves.
"""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile

# Config validation requires SECRET_KEY at import time; set one for tests.
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402


# ---- fixtures ---------------------------------------------------------------

@pytest.fixture
def db_path():
    """A temp SQLite file path; the canonical DB location for a single test."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _build_app(database_path, *, csrf):
    class _TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = csrf
        SECRET_KEY = "test-secret-key"
        DATABASE_PATH = database_path

    return create_app(_TestConfig)


@pytest.fixture
def app(db_path):
    # DB connections are request-scoped (opened on flask.g, closed on
    # app-context teardown), so there is nothing pooled to dispose of.
    return _build_app(db_path, csrf=False)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf_app(db_path):
    """App with CSRF protection ON, to exercise the CSRF contract directly."""
    return _build_app(db_path, csrf=True)


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()


# ---- black-box HTTP helpers -------------------------------------------------

def register(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/register",
        data={"username": username, "email": email, "password": password, "confirm": password},
        follow_redirects=True,
    )


def login(client, username="alice", password="password123", remember=False):
    data = {"username": username, "password": password}
    if remember:
        data["remember"] = "y"
    return client.post("/login", data=data, follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)


def create_task(client, title="Buy milk", **kwargs):
    data = {"title": title, "priority": kwargs.get("priority", "medium")}
    for key in ("notes", "category", "due_date"):
        if key in kwargs:
            data[key] = kwargs[key]
    return client.post("/tasks/new", data=data, follow_redirects=True)


@pytest.fixture
def auth(client):
    """Register + log in a default user; return helpers bound to the client."""
    register(client)

    class _Auth:
        register = staticmethod(lambda **k: register(client, **k))
        login = staticmethod(lambda **k: login(client, **k))
        logout = staticmethod(lambda: logout(client))
        create_task = staticmethod(lambda **k: create_task(client, **k))

    return _Auth()


# ---- grey-box helpers: assert persisted state via stdlib sqlite3 ------------
# Depend only on the SQLite schema, never the ORM, so they survive the refactor.

def db_query(database_path, sql, params=()):
    con = sqlite3.connect(database_path)
    try:
        con.row_factory = sqlite3.Row
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def task_id(database_path, title):
    rows = db_query(database_path, "SELECT id FROM tasks WHERE title = ?", (title,))
    assert rows, f"no task titled {title!r}"
    return rows[0]["id"]


_CSRF_RE = re.compile(rb'name="csrf_token"[^>]*value="([^"]+)"')


def csrf_token(html_bytes):
    """Extract the CSRF token from a rendered form page, or None."""
    m = _CSRF_RE.search(html_bytes)
    return m.group(1).decode() if m else None
