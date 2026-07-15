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
| [`todo-3pdeps-limited/`](todo-3pdeps-limited/) | The same app after the removal experiment: heavy dependencies replaced with purpose-built code, behavior preserved. Sole declared runtime dependency: `flask`. Third-party prod footprint: 217,493 → 32,654 LOC (−85%). |
| [`research/`](research/notes.md) | The article premise, measurement method, per-step removal log, the "keep Flask" rationale, and the testing strategy. |

Both variants are **independent `uv` projects** (each with its own `pyproject.toml`,
lockfile, and virtualenv) so their dependency sets can diverge. They are
behavior-identical and share the same test bodies — byte-identical across variants,
with each variant's `tests/conftest.py` as the only implementation-aware adapter.
That shared suite is the contract that proves each removal preserved behavior.

## Running a variant

```bash
cd todo-3pdeps           # or todo-3pdeps-limited
uv sync
uv run python run.py     # http://127.0.0.1:5000
uv run pytest            # 65 tests
```

Each variant needs a `SECRET_KEY` (see its `.env.example`). See the variant's own
`README.md` for full details, configuration, and production notes.

## Measuring the trade-off

The premise is quantified with `cloc`. See [`research/notes.md`](research/notes.md)
for the reproducible method, the production-scoped baseline (first-party vs.
third-party shipping code), and the **removal log** recording what each of the six
replacement steps shed and cost. The experiment ran as one git commit per
dependency, so `git log` doubles as the step-by-step diff trail.
