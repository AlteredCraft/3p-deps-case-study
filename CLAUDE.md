# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A full-featured Flask + SQLite + login todo app **used as a case study for an AlteredCraft article** on using AI to remove/limit third-party dependencies. The premise, dependency-footprint (cloc) baselines, and testing strategy live in `research/notes.md` — read it before doing any dependency-removal work. The planned trajectory is to replace heavy dependencies (SQLAlchemy first, ~62% of the prod footprint; then email-validator, Flask-WTF, WTForms, Flask-Login) with small, purpose-built code, while **keeping** security-sensitive libraries (`werkzeug.security` for password hashing).

## Commands

Python ≥3.14, managed with `uv` (run `uv sync` to create the `.venv`).

- Run the app: `uv run python run.py` → http://127.0.0.1:5000 (Flask dev server, debug on)
- All tests: `uv run pytest`
- A single test: `uv run pytest tests/test_todos.py::test_edit_updates_task` (or filter with `-k <expr>`)
- Coverage: `uv run pytest --cov=app --cov-report=term-missing` (`app/` is expected to stay at 100%)
- Create DB tables explicitly: `uv run flask --app run init-db` (the app factory also does this on startup)

Requires `SECRET_KEY` in the environment or a local `.env` (see `.env.example`); `run.py` loads `.env` via `python-dotenv`. Missing required config fails fast (`app/config._require`) rather than falling back. The SQLite file lives at `instance/todo.sqlite` (gitignored).

## Architecture

Application-factory pattern. `create_app()` in `app/__init__.py` binds the unbound extensions from `app/extensions.py` (`db`, `login_manager`, `csrf`, and the SQLAlchemy 2.0 `Base`) via `init_app`, registers the two blueprints, runs `db.create_all()`, and wires the `init-db` CLI command, error handlers, and a `today` template context processor. Extensions are unbound so tests can build many independent app instances.

- **Blueprints** (flat modules): `app/auth.py` (`register` / `login` / `logout`) and `app/todos.py` (task CRUD + list filtering/sorting).
- **Models** — `app/models.py`: `User` (subclasses `UserMixin`) and `Task`, SQLAlchemy 2.0 `Mapped`/`mapped_column`. The Flask-Login `user_loader` lives here.
- **Forms** — `app/forms.py`: Flask-WTF/WTForms with validation, including case-insensitive uniqueness checks for username/email.

Cross-cutting invariants (each spans multiple files — preserve them through any refactor):

- **Per-user authorization returns 404, not 403.** Every task route resolves the task through `todos._get_owned_task_or_404()`, which aborts 404 when the task's `user_id` isn't the `current_user`. This deliberately hides existence; there is no reachable 403 path.
- **CSRF is global** via Flask-WTF `CSRFProtect`; every state-changing form posts a `csrf_token`.
- **Open-redirect protection**: the login `next` parameter is gated by `auth._is_safe_redirect()` (same-site relative paths only).
- **Priority sorting is done in SQL**, not Python — `todos._priority_ordering()` builds a `CASE` from `models.PRIORITY_RANK`.

## Testing is a black-box refactor oracle (important)

The suite exists to prove a dependency swap **preserved behavior**, so it is deliberately decoupled from the libraries being replaced. When writing or editing tests, follow these rules (full rationale in `research/notes.md` → "Testing strategy"):

- **Test bodies assert only through the HTTP boundary** (the Flask test client) **or the stdlib `sqlite3` module** against the `users`/`tasks` schema. **Do not import the ORM, models, or forms in a test body** — that reintroduces the coupling the suite is designed to avoid.
- **`tests/conftest.py` is the single implementation-aware adapter** (it builds the app, wires the temp DB, disposes connections, and provides HTTP + `sqlite3` helpers). When a dependency is swapped, update `conftest.py` — not the test bodies.
- The `csrf_client` fixture runs with CSRF enabled (the default `client` disables it); use it for CSRF-contract tests.
- **The same suite must stay green after each dependency is removed.** A green run is the evidence a LOC reduction came for free.
