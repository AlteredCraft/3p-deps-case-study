# todo-deps — an experiment in limiting third-party dependencies

This repository backs an [AlteredCraft](https://alteredcraft.com) article investigating
how AI changes the economics of third-party dependencies (3PDeps). When code was
expensive to write, pulling in a general-purpose library was usually the rational
trade. When AI can produce a precise, minimal implementation on demand, that trade
inverts for many dependencies — though not all (security-sensitive code stays with
the experts).

The vehicle is a full-featured Flask + SQLite + login todo app, kept in two variants
so the trade-off can be measured directly:

| Directory | What it is |
| --- | --- |
| [`todo-3pdeps/`](todo-3pdeps/) | The baseline — conventional Python web stack (Flask, SQLAlchemy, Flask-Login, Flask-WTF, WTForms, email-validator). |
| [`todo-3pdeps-limited/`](todo-3pdeps-limited/) | A copy whose heavy dependencies are progressively replaced with purpose-built code, keeping the same behavior. |
| [`research/`](research/notes.md) | The article premise, cloc dependency baselines, and the testing strategy. |

Both variants are **independent `uv` projects** (each with its own `pyproject.toml`,
lockfile, and virtualenv) so their dependency sets can diverge. They start behavior-
identical and share the exact same test suite — the contract that proves a dependency
removal preserved behavior.

## Running a variant

```bash
cd todo-3pdeps           # or todo-3pdeps-limited
uv sync
uv run run.py     # http://127.0.0.1:5000
uv run pytest            # 57 tests
```

Each variant needs a `SECRET_KEY` (see its `.env.example`). See the variant's own
`README.md` for full details, configuration, and production notes.

## Measuring the trade-off

The premise is quantified with `cloc`. See [`research/notes.md`](research/notes.md)
for method and the production-scoped baseline (first-party vs. third-party
shipping code). Re-running the same measurement against each variant is how we track
how much dependency code each replacement sheds.
