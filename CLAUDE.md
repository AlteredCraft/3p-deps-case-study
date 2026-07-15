# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A case study for an AlteredCraft article on using AI to remove/limit third-party dependencies. It holds **two variants of the same Flask + SQLite + login todo app** plus shared research:

- `todo-3pdeps/` — the baseline, full conventional dependency stack.
- `todo-3pdeps-limited/` — a behavior-identical copy whose heavy dependencies (SQLAlchemy first, ~62% of the prod footprint; then email-validator, Flask-WTF, WTForms, Flask-Login) are progressively replaced with small, purpose-built code. Security-sensitive libraries (`werkzeug.security` password hashing) are deliberately **kept**.
- `research/notes.md` — the premise, the cloc dependency-footprint baselines, and the testing strategy. **Read it before doing any dependency-removal work.**

The two variants are **independent `uv` projects** (each with its own `pyproject.toml`, lockfile, and `.venv`) so their dependency sets can diverge. They start identical and must pass the same test suite; the diff in their `cloc` metrics is the article's payload.

## Commands

Run everything **from inside a variant directory** (that's where each `pyproject.toml`/`.venv` lives). Python ≥3.14, managed with `uv`.

```bash
cd todo-3pdeps            # or todo-3pdeps-limited
uv sync                   # create/refresh the variant's .venv
uv run python run.py      # http://127.0.0.1:5000 (Flask dev server, debug on)
uv run pytest             # all 57 tests
uv run pytest tests/test_todos.py::test_edit_updates_task   # a single test (or -k <expr>)
uv run pytest --cov=app --cov-report=term-missing           # coverage (app/ stays at 100%)
uv run flask --app run init-db                              # create DB tables (factory also does this on startup)
```

To drive a variant without changing directory, use `uv run --directory <variant> …`.

Each variant needs `SECRET_KEY` in its environment or local `.env` (see `.env.example`); `run.py` loads `.env` via `python-dotenv`. Missing required config fails fast (`app/config._require`). The SQLite file is `instance/todo.sqlite` (gitignored).

## Architecture (applies to both variants)

Application-factory pattern. `create_app()` in `app/__init__.py` binds the unbound extensions from `app/extensions.py` (`db`, `login_manager`, `csrf`, plus the SQLAlchemy 2.0 `Base`) via `init_app`, registers the two blueprints, runs `db.create_all()`, and wires the `init-db` CLI command, error handlers, and a `today` template context processor. Extensions are unbound so tests can build many independent app instances.

- **Blueprints** (flat modules): `app/auth.py` (`register` / `login` / `logout`) and `app/todos.py` (task CRUD + list filtering/sorting).
- **Models** — `app/models.py`: `User` (subclasses `UserMixin`) and `Task`, SQLAlchemy 2.0 `Mapped`/`mapped_column`. The Flask-Login `user_loader` lives here.
- **Forms** — `app/forms.py`: Flask-WTF/WTForms with validation, including case-insensitive uniqueness checks for username/email.

Cross-cutting invariants (each spans multiple files — preserve them through any refactor):

- **Per-user authorization returns 404, not 403.** Every task route resolves the task through `todos._get_owned_task_or_404()`, which aborts 404 when the task's `user_id` isn't the `current_user`. This deliberately hides existence; there is no reachable 403 path.
- **CSRF is global** via Flask-WTF `CSRFProtect`; every state-changing form posts a `csrf_token`.
- **Open-redirect protection**: the login `next` parameter is gated by `auth._is_safe_redirect()` (same-site relative paths only).
- **Priority sorting is done in SQL**, not Python — `todos._priority_ordering()` builds a `CASE` from `models.PRIORITY_RANK`.

## Testing is a black-box refactor oracle (important)

The suite exists to prove a dependency swap **preserved behavior**, so it is deliberately decoupled from the libraries being replaced. This matters most in `todo-3pdeps-limited/`, where dependencies are actively being removed. Rules (full rationale in `research/notes.md` → "Testing strategy"):

- **Test bodies assert only through the HTTP boundary** (the Flask test client) **or the stdlib `sqlite3` module** against the `users`/`tasks` schema. **Do not import the ORM, models, or forms in a test body** — that reintroduces the coupling the suite is designed to avoid.
- **`tests/conftest.py` is the single implementation-aware adapter** (it builds the app, wires the temp DB, disposes connections, and provides HTTP + `sqlite3` helpers). When a dependency is swapped in the limited variant, update *its* `conftest.py` — not the test bodies.
- The `csrf_client` fixture runs with CSRF enabled (the default `client` disables it); use it for CSRF-contract tests.
- **The same suite must stay green after each dependency is removed.** A green run in `todo-3pdeps-limited/` is the evidence a LOC reduction came for free. Keep the two variants' test suites in sync unless a behavior genuinely changed.
