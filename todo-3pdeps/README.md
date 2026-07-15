# Todo — Flask + SQLite + Login

A full-featured multi-user todo web app built with Flask, SQLite, and
Flask-Login. Each user has a private, isolated list of tasks with priorities,
categories, due dates, notes, search, filtering, and sorting.

## Features

- **Accounts & auth** — register, log in (by username *or* email), "remember me",
  log out. Passwords are hashed with Werkzeug (never stored in plain text).
- **Per-user isolation** — every task is scoped to its owner; one user can never
  see or modify another user's tasks.
- **Tasks** — create, edit, delete, and toggle complete/incomplete.
- **Organize** — priority (high / medium / low), free-text categories, due dates
  (with overdue highlighting), and notes.
- **Find** — search by title/notes, filter by status / priority / category, and
  sort by newest, due date, priority, or title.
- **Bulk** — one-click "clear completed".
- **Secure by default** — CSRF protection on every form (Flask-WTF), hardened
  session cookies, open-redirect-safe `next` handling.
- **Polished UI** — responsive, with automatic light/dark mode.

## Tech stack

| Concern         | Choice                        |
| --------------- | ----------------------------- |
| Web framework   | Flask 3 (application factory) |
| Database        | SQLite via Flask-SQLAlchemy 3 (SQLAlchemy 2.0 models) |
| Auth/sessions   | Flask-Login                   |
| Forms/CSRF      | Flask-WTF / WTForms           |
| Dependency mgmt | uv                            |

## Getting started

Requirements: [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install dependencies (creates a .venv automatically)
uv sync

# 2. A .env with a generated SECRET_KEY is already present. If it's missing,
#    create one:
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" > .env

# 3. Run the app
uv run python run.py
```

Then open http://127.0.0.1:5000 and register an account.

The SQLite database is created automatically at `instance/todo.sqlite` on first
run.

## Configuration

Configuration is read from the environment (see `.env.example`):

| Variable       | Required | Default                          | Purpose                       |
| -------------- | -------- | -------------------------------- | ----------------------------- |
| `SECRET_KEY`   | **yes**  | — (fails fast if missing)        | Signs sessions / CSRF tokens. |
| `DATABASE_URL` | no       | `sqlite:///instance/todo.sqlite` | SQLAlchemy database URL.       |
| `FLASK_ENV`    | no       | —                                | Set to `production` to require secure (HTTPS-only) cookies. |

`SECRET_KEY` has no insecure fallback — a missing value stops startup with a
clear message rather than silently using a guessable default.

## Running the tests

```bash
uv run pytest
```

Covers auth (registration validation, login, hashing), full task CRUD,
per-user authorization isolation, filtering/search, and sorting.

## Project layout

```
app/
  __init__.py     # application factory, CLI, error handlers
  config.py       # environment-driven config (fails fast on missing secrets)
  extensions.py   # db, login_manager, csrf (unbound; init_app in factory)
  models.py       # User and Task models + user loader
  forms.py        # WTForms with validation
  auth.py         # register / login / logout blueprint
  todos.py        # task CRUD + filtering blueprint
  templates/      # Jinja2 templates
  static/css/     # stylesheet
run.py            # dev entry point
tests/            # pytest suite
```

## Production notes

This ships with Flask's development server for convenience. For production,
serve the app factory with a WSGI server, e.g.:

```bash
uv add gunicorn
uv run gunicorn "app:create_app()"
```

and set `FLASK_ENV=production` plus a strong `SECRET_KEY` in the environment.
