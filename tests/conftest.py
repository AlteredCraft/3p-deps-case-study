"""Shared pytest fixtures."""
from __future__ import annotations

import os
import tempfile

# Config validation requires SECRET_KEY at import time; set one for tests.
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")

    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "test-secret-key"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    app = create_app(TestConfig)
    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


# ---- helpers exposed as fixtures --------------------------------------------

def register(client, username="alice", email="alice@example.com", password="password123"):
    return client.post(
        "/register",
        data={"username": username, "email": email, "password": password, "confirm": password},
        follow_redirects=True,
    )


def login(client, username="alice", password="password123"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def create_task(client, title="Buy milk", **kwargs):
    data = {"title": title, "priority": kwargs.get("priority", "medium")}
    for key in ("notes", "category", "due_date"):
        if key in kwargs:
            data[key] = kwargs[key]
    return client.post("/tasks/new", data=data, follow_redirects=True)


@pytest.fixture
def auth(client):
    """Register + log in a default user, return helpers bound to the client."""
    register(client)

    class _Auth:
        register = staticmethod(lambda **k: register(client, **k))
        login = staticmethod(lambda **k: login(client, **k))
        create_task = staticmethod(lambda **k: create_task(client, **k))

    return _Auth()
