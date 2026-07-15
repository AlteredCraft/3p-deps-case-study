# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A case study for an AlteredCraft article on using AI to remove/limit third-party dependencies. It holds **two variants of the same Flask + SQLite + login todo app** plus shared research:

- `todo-3pdeps/` — the baseline, full conventional dependency stack.
- `todo-3pdeps-limited/` — a behavior-identical copy whose heavy dependencies (SQLAlchemy, email-validator, Flask-WTF, WTForms, Flask-Login, python-dotenv) **have been replaced** with small, purpose-built modules (`app/db.py`, `app/csrf.py`, `app/formlib.py`, `app/login.py`); its only declared runtime dependency is `flask`. Security-sensitive libraries (`werkzeug.security` password hashing, itsdangerous session signing via Flask) are deliberately **kept**.
- `research/notes.md` — the premise, the cloc baselines, the **removal log** (per-step LOC deltas), the argued rationale for keeping Flask, and the testing strategy. **Read it before doing any dependency or refactor work.**

The two variants are **independent `uv` projects** (each with its own `pyproject.toml`, lockfile, and `.venv`) so their dependency sets can diverge. They must pass the same test suite; the diff in their `cloc` metrics is the article's payload (217,493 → 32,654 third-party prod LOC, −85%). The removal was executed 2026-07-15 as one commit per dependency — `git log` is the step-by-step diff trail.

## Commands

Run everything **from inside a variant directory** (that's where each `pyproject.toml`/`.venv` lives). Python ≥3.14, managed with `uv`.

```bash
cd todo-3pdeps            # or todo-3pdeps-limited
uv sync                   # create/refresh the variant's .venv
uv run python run.py      # http://127.0.0.1:5000 (Flask dev server, debug on)
uv run pytest             # all 65 tests
uv run pytest tests/test_todos.py::test_edit_updates_task   # a single test (or -k <expr>)
uv run pytest --cov=app --cov-report=term-missing           # coverage (app/ stays at 100%)
uv run flask --app run init-db                              # create DB tables (factory also does this on startup)
```

To drive a variant without changing directory, use `uv run --directory <variant> …`.

Each variant needs `SECRET_KEY` in its environment or local `.env` (see `.env.example`); `run.py` loads `.env` (via `python-dotenv` in the baseline, a small first-party loader in the limited variant). Missing required config fails fast (`app/config._require`). The SQLite file is `instance/todo.sqlite` (gitignored). DB location override: `DATABASE_URL` (baseline) / `DATABASE_PATH` (limited).

## Architecture

Both variants use the application-factory pattern. `create_app()` in `app/__init__.py` binds the unbound extensions from `app/extensions.py` via `init_app`, registers the two blueprints, creates the DB tables, and wires the `init-db` CLI command, error handlers, and a `today` template context processor. Extensions are unbound so tests can build many independent app instances. Blueprints are flat modules in both: `app/auth.py` (`register` / `login` / `logout`) and `app/todos.py` (task CRUD + list filtering/sorting).

Where the variants differ:

- **`todo-3pdeps` (baseline)** — `extensions.py` holds Flask-SQLAlchemy `db` + `Base`, Flask-Login `login_manager`, Flask-WTF `csrf`. `models.py` is SQLAlchemy 2.0 `Mapped`/`mapped_column`; `forms.py` is Flask-WTF/WTForms.
- **`todo-3pdeps-limited`** — the same seams, filled with purpose-built modules: `app/db.py` (request-scoped `sqlite3` connection on `flask.g` + schema DDL), `app/models.py` (dataclass `User`/`Task` + all SQL query functions), `app/csrf.py` (session-token CSRF, enforced globally in `before_request`, config key `CSRF_ENABLED`), `app/formlib.py` (micro form library rendering WTForms-compatible markup) + `app/forms.py` (form definitions), `app/login.py` (`current_user`, `login_required`, signed remember-me cookie). The SQLite **schema is identical** to the baseline's — the sqlite3-based tests depend on it.

Cross-cutting invariants (each spans multiple files — preserve them through any refactor, in both variants):

- **Per-user authorization returns 404, not 403.** Every task route resolves the task through `todos._get_owned_task_or_404()`, which aborts 404 when the task's `user_id` isn't the `current_user`. This deliberately hides existence; there is no reachable 403 path.
- **CSRF is global** (Flask-WTF `CSRFProtect` in the baseline; `app/csrf.py` in the limited variant); every state-changing form posts a `csrf_token`, missing/invalid → 400.
- **Open-redirect protection**: the login `next` parameter is gated by `auth._is_safe_redirect()` (same-site relative paths only).
- **Priority sorting is done in SQL**, not Python — a `CASE` built from `models.PRIORITY_RANK` (`todos._priority_ordering()` in the baseline, `models.priority_ordering()` in the limited variant).

## Testing is a black-box refactor oracle (important)

The suite exists to prove a swap or refactor **preserved behavior**, so it is deliberately decoupled from the libraries (or first-party modules) behind the seams. It validated every removal in `todo-3pdeps-limited/`. Rules (full rationale in `research/notes.md` → "Testing strategy"):

- **Test bodies assert only through the HTTP boundary** (the Flask test client) **or the stdlib `sqlite3` module** against the `users`/`tasks` schema. **Do not import the data layer, models, or forms in a test body** — that reintroduces the coupling the suite is designed to avoid.
- **`tests/conftest.py` is the single implementation-aware adapter** (it builds the app, wires the temp DB, and provides HTTP + `sqlite3` helpers). When an implementation changes, update *its* `conftest.py` — not the test bodies.
- The `csrf_client` fixture runs with CSRF enabled (the default `client` disables it); use it for CSRF-contract tests.
- **Test bodies are byte-identical across the two variants — keep them that way.** Never modify existing assertions to accommodate a change. *Adding* pins is allowed: new tests go into **both variants in lockstep**, and a new pin that fails on one variant has found a parity bug, not a bad test. A green run in both variants is the evidence a change came for free.
- Coverage floor: `app/` stays at **100%** in the limited variant. An uncovered line in a purpose-built module is either dead code (delete it) or unpinned behavior (pin it in both variants).
