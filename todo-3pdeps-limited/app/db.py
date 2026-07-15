"""SQLite connection handling and schema (purpose-built; replaces SQLAlchemy).

One connection per request, stored on ``flask.g`` and closed on app-context
teardown. The DDL mirrors the schema the ORM used to emit so existing
databases (and the sqlite3-based test helpers) keep working unchanged.
"""
from __future__ import annotations

import sqlite3

from flask import Flask, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      VARCHAR(80)  NOT NULL,
    email         VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER       NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title        VARCHAR(200)  NOT NULL,
    notes        VARCHAR(2000) NOT NULL,
    category     VARCHAR(60)   NOT NULL,
    priority     VARCHAR(10)   NOT NULL,
    due_date     DATE,
    completed    BOOLEAN       NOT NULL,
    completed_at DATETIME,
    created_at   DATETIME      NOT NULL,
    updated_at   DATETIME      NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id);
CREATE INDEX IF NOT EXISTS ix_tasks_category ON tasks (category);
CREATE INDEX IF NOT EXISTS ix_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS ix_tasks_completed ON tasks (completed);
"""


def get_db() -> sqlite3.Connection:
    """The request-scoped connection, opened on first use."""
    if "db" not in g:
        con = sqlite3.connect(current_app.config["DATABASE_PATH"])
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        g.db = con
    return g.db


def close_db(exc: BaseException | None = None) -> None:
    con = g.pop("db", None)
    if con is not None:
        con.close()


def create_all() -> None:
    """Create the tables and indexes if they don't exist."""
    get_db().executescript(SCHEMA)


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
