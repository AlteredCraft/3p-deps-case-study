# AlteredCraft Article — Research Notes

## Working title
AI and the shrinking case for third-party dependencies

## Premise

We're investigating the use of AI to **remove or limit the need for third-party
dependencies (3PDeps)**.

The core argument is about a shifting economic tradeoff:

- **When code was expensive** (slow and costly for a human to write), pulling in
  a third-party dependency was usually the rational choice. You got a working
  solution cheaply, and in exchange you accepted real costs:
  - **Unknown maintainers and support** — you're trusting code from people you
    don't know, with no guarantee of upkeep, response, or longevity.
  - **More code than you need** — a general-purpose library carries surface area,
    configuration, and features that your specific problem never touches. You
    inherit all of it (and its bugs, CVEs, and transitive deps).
  - **"Good enough" vs. precise** — the library solves the *general* problem, not
    *your* problem. You bend your design to fit its abstractions and settle for a
    close-enough fit instead of the exact solution you'd have written.

- **When code is cheap** (AI can generate a precise, minimal solution on demand),
  that tradeoff inverts. If you can produce exactly the code your problem needs —
  no more, no less — the appeal of a heavyweight general dependency weakens. You
  can own a small, purpose-built implementation you fully understand.

## Important caveat — where you still want the experts

Not every dependency should be replaced. **Security-sensitive** functionality is
the clearest example: cryptography, password hashing, TLS, authentication/session
primitives. These are domains where subtle, non-obvious mistakes are catastrophic
and where battle-tested, widely-audited libraries carry value that "precise but
freshly written" code does not. The goal is *limiting* 3PDeps where the tradeoff
no longer pays, **not** eliminating them dogmatically.

## The case study

A full-featured Flask + SQLite + login todo web app (this repo) is the vehicle.
As initially built, it leans on the conventional Python web stack:

- `flask` — web framework
- `flask-sqlalchemy` / `sqlalchemy` — ORM + DB layer
- `flask-login` — session/auth management
- `flask-wtf` / `wtforms` — forms + CSRF
- `email-validator`, `python-dotenv`, `werkzeug` (transitive), etc.

The investigation: progressively examine which of these could be replaced by a
small amount of AI-written, purpose-built code — and which (e.g. the security
primitives in `werkzeug.security`) are worth keeping. We'll track the
**lines-of-code tradeoff** at each step: how much dependency code we shed vs. how
much first-party code we take on.

### Repository layout (two variants)

The repo holds the app in two independent `uv` projects so the trade-off can be
measured directly:

- `todo-3pdeps/` — the baseline described above (full dependency stack).
- `todo-3pdeps-limited/` — a behavior-identical copy whose heavy dependencies are
  progressively replaced; the same test suite must stay green after each removal.

The baseline cloc figures below were taken on `todo-3pdeps/` (originally at the
repo root, before the split). Re-run the same measurement against each variant to
track the divergence — commands like `cloc todo-3pdeps/app` for first-party, and a
`uv export --no-dev` prod environment per variant for third-party.

## Baseline measurement (cloc)

Measured 2026-07-15 with `cloc 2.06`.

### Scope decisions

- **Python-the-platform is first-party.** The interpreter and standard library
  are a given — we're not reimplementing Python. Only pip-installed packages
  count as third-party.
- **"Ships to prod" only.** We measure the *production runtime* footprint, so the
  dev/test toolchain is excluded — `pytest` and its transitive deps
  (`pygments` ~100k LOC, `_pytest`, `pluggy`, `iniconfig`, `packaging`) never
  ship and are out of scope. (An earlier pass that counted the whole `.venv` at
  348,953 LOC is superseded; ~131k of that was dev tooling.)

  > **Update (2026-07-15, post test-hardening):** after adding `pytest-cov` to
  > the dev group, the dev/test toolchain now totals **142,788 LOC** (the +11,948
  > is almost entirely `coverage` 11,297 + `pytest_cov` 651). This is dev-only and
  > does **not** touch the prod figure: a re-measured `--no-dev` environment still
  > reports exactly **217,493 LOC**, and `uv tree --no-dev` contains no
  > pytest/coverage/pygments. The dev toolchain is now ~66% the size of the entire
  > prod dependency footprint — another reason to quote the prod-scoped number, not
  > the raw `.venv`. First-party: `app/` (ships) is 964 LOC; `tests/` (dev-only) is
  > 442 LOC — neither the growing suite nor the tooling moves the two headline
  > numbers.
- **Cruft filtered.** No `.pyc` / `__pycache__` (cloc treats these as non-source
  anyway; a fresh prod install has none), no `*.dist-info` metadata, no bundled
  package test suites.

### Method (reproducible)

Build a production-only environment from the lockfile and count *that*, rather
than hand-subtracting dev deps from the working `.venv`:

```bash
uv export --no-dev --no-emit-project --no-hashes -o prod-reqs.txt
uv venv prodenv --python 3.14
uv pip install --python prodenv/bin/python -r prod-reqs.txt

# third-party code that ships to prod (cruft filtered)
cloc "$(find prodenv -type d -name site-packages)" \
  --fullpath --not-match-d='(\.dist-info|__pycache__|/tests?($|/))'

# first-party code that ships to prod (tests/ and dev-only run.py excluded)
cloc app
```

### Headline numbers (production scope)

| Scope | Files | Code (LOC) | Share |
| --- | ---: | ---: | ---: |
| **First-party** — our shipping code (`app/`) | 14 | **967** | 0.44% |
| **Third-party** — prod deps only | 657 | **217,493** | 99.56% |
| **Total shipping code** | 671 | **218,460** | 100% |

- First-party shipping code = **967 LOC** (431 Python + 260 HTML + 276 CSS).
  Python-only, per the scope note, that's **431 LOC**.
- **For every 1 line of our shipping code, ~225 lines of third-party code ship
  alongside it.** Measured Python-to-Python (212,421 vs 431), it's **~493×**.
- `tests/` (536 LOC) and `run.py` (11 LOC, dev entry — prod uses
  `gunicorn "app:create_app()"`) are excluded from the shipping first-party count.

### Third-party prod footprint by language

| Language | Code | Note |
| --- | ---: | --- |
| Python | 212,421 | 97.7% of prod deps |
| PO File (i18n) | 3,721 | gettext translation catalogs (click, wtforms…) |
| Cython | 583 | SQLAlchemy C-extension sources |
| JavaScript | 292 | werkzeug interactive debugger assets |
| C | 177 | markupsafe speedups |
| CSS | 130 | werkzeug debugger styles |
| (Text / Markdown) | ~169 | stray package docs |
| **Total** | **217,493** | |

### Per-dependency breakdown (prod, filtered)

| Package | Code (LOC) | % of prod deps | Role |
| --- | ---: | ---: | --- |
| **sqlalchemy** | 133,937 | **61.6%** | ORM + Core. The whole ballgame. |
| **idna** | 19,389 | 8.9% | Internationalized domain names — via `email-validator`. |
| **dns** (dnspython) | 19,300 | 8.9% | DNS toolkit — via `email-validator` (deliverability). |
| werkzeug | 11,986 | 5.5% | WSGI utils + **`werkzeug.security` password hashing (KEEP)**. |
| jinja2 | 8,557 | 3.9% | Templating. |
| click | 6,673 | 3.1% | CLI framework (the `flask` command). |
| wtforms | 5,923 | 2.7% | Form definitions + validation. |
| flask | 4,068 | 1.9% | The web framework itself. |
| typing_extensions | 2,549 | 1.2% | Back-ported typing — via SQLAlchemy. |
| flask_sqlalchemy | 1,004 | 0.5% | Flask ↔ SQLAlchemy glue. |
| email_validator | 768 | 0.4% | Email validation (drags in idna + dns). |
| dotenv | 766 | 0.4% | `.env` loading. |
| flask_login | 683 | 0.3% | Session/auth management. |
| itsdangerous | 650 | 0.3% | Signed cookies/tokens. |
| flask_wtf | 520 | 0.2% | CSRF + Flask/WTForms glue. |
| markupsafe | 394 | 0.2% | HTML escaping. |
| blinker | 268 | 0.1% | Signals. |

### The dominant finding: two features = ~79% of the footprint

- **SQLAlchemy alone is 61.6% of all production dependency code** — 133,937 LOC,
  or **~311× our shipping first-party Python** (138× counting all our shipping
  code) — for an app with two models and a handful of simple queries.
- **Email validation costs ~39k LOC.** `email-validator` is only 768 LOC, but it
  pulls in `idna` (19,389) + `dnspython` (19,300). That's **17.8% of the prod
  footprint to validate an email string** — "more code than you need," literal.
- **SQLAlchemy + the email stack = 172,626 LOC = 79.4%** of everything that
  ships. The other 15 packages combined are ~45k LOC.

### Early observations (to develop in the article)

1. **The ORM is the headline replacement target.** 134k LOC of general-purpose
   ORM to avoid a few hundred lines of purpose-built `sqlite3` data-access code —
   the "good enough / general" tradeoff at its most extreme. Prime AI-written
   replacement candidate.
2. **Validation via network protocols is bloat we can price exactly.** We use
   `email-validator` for a format check; it ships an entire IDNA + DNS stack.
   A precise regex/parse (skipping deliverability) removes ~39k LOC.
3. **The security primitive we keep is cheap.** Password hashing lives in
   `werkzeug.security`, a small slice of werkzeug (which Flask already needs).
   Per the caveat, this is exactly what to *retain*.
4. **Framework glue is thin; the engines are heavy.** flask + its three glue
   packages ≈ 6.3k LOC. The weight lives in SQLAlchemy and the email/DNS stack.

### The tradeoff question this sets up

If AI can write the precise ~few-hundred lines our app actually needs, how much of
the **217,493 LOC** of production dependency code can we responsibly shed — and
where (password hashing, cookie signing, HTML escaping) is keeping the
expert-maintained library still the right call? Subsequent experiments replace
dependencies one at a time and re-measure this table.

## Removal log (todo-3pdeps-limited)

Each step removes one dependency from `todo-3pdeps-limited/`, replacing it with
purpose-built first-party code. A step only counts when the **unchanged 57-test
suite is green** afterwards. Numbers come from re-running the baseline
measurement (prod-only env, cruft filtered, `cloc app` for first-party).

| Step | Dependency removed | 3P LOC shed | 1P LOC added | 3P total | 1P total (`app/`) |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | — (baseline clone) | — | — | 217,493 | 964 |
| 1 | sqlalchemy, flask-sqlalchemy (+ typing_extensions) | 137,490 | +100 | 80,003 | 1,064 |

Step notes:

1. **SQLAlchemy → stdlib `sqlite3`** (2026-07-15). New `app/db.py` (request-scoped
   connection on `flask.g`, schema DDL matching what the ORM emitted) and a
   rewritten `app/models.py` (dataclass models + ~15 purpose-built query
   functions; priority sorting stays in SQL via a generated `CASE`). Routes,
   templates, and forms untouched except for swapping query calls. The trade:
   **137,490 LOC of ORM for 100 lines of first-party SQL** (~1,375:1).
   `conftest.py` seam change: config key `SQLALCHEMY_DATABASE_URI` →
   `DATABASE_PATH`; the SQLAlchemy engine-dispose teardown became unnecessary
   (connections close per-request). One pre-existing coupling repaired in *both*
   variants: `test_app.py` derived the DB file from the ORM's config key —
   implementation-aware plumbing that belongs to the conftest seam; it now uses
   the `db_path` fixture (assertions unchanged).

## Testing strategy (the refactor oracle)

The test suite is a **black-box behavioral oracle**: its job is to prove a
dependency swap preserved behavior. Without that guarantee every LOC-reduction
number is meaningless — there'd be no evidence the slimmer app still works.

**Principle: test behavior, not implementation.** A refactor changes the
implementation on purpose, so a test coupled to it breaks *because* the work was
done — it can't tell "you broke it" from "you changed it." Tests therefore assert
only what a user can observe, through exactly two points:

1. **HTTP boundary (preferred).** Drive the app via the Flask test client; assert
   on status codes, redirects, flash messages, rendered HTML. Routing → forms →
   validation → session → DB → templates all run; the test sees only the request
   and the response.
2. **Persistence contract via stdlib `sqlite3`.** For state not observable over
   HTTP (a password is hashed, `completed_at` is set), query the SQLite file
   directly — never the ORM. This depends only on the schema (`users` / `tasks`),
   which the refactor preserves; `sqlite3` is Python-the-platform, so it survives
   every swap.

The ORM, forms library, and validators — the things being replaced — appear in
**zero** test bodies.

**One adapter.** `tests/conftest.py` is the only implementation-aware file: it
builds the app, wires the temp DB, disposes connections, and provides the HTTP +
`sqlite3` helpers. Replacing a dependency means updating this seam (e.g. swapping
the SQLAlchemy engine-dispose for closing raw `sqlite3` connections) while the
test bodies stay untouched — which is what enforces the *same* contract before and
after each cut.

**Each doomed dependency's behavior is pinned by a test**, giving the replacement
an explicit target:

| Dependency (to replace) | Behavior pinned |
| --- | --- |
| SQLAlchemy | CRUD, toggle, per-user isolation, search, category/priority/status filters, priority/title/due sorts |
| Flask-WTF | CSRF token rendered; POST without token → 400; with token → success |
| WTForms | required fields, length bounds, username regex, invalid date, invalid priority choice, password match |
| Flask-Login | login by username/email, logout clears session, protected-route redirect, safe `next` redirect, open-redirect blocked |
| email-validator | malformed addresses rejected, valid accepted |
| werkzeug (**keep**) | password stored hashed, never plaintext |

**No integration or E2E tier is needed.** The test client already exercises the
full in-process request path (routing → validation → session → real SQLite →
template) — everything a dependency-internal refactor touches. Browser E2E would
only add coverage of HTML/CSS/JS and the HTTP contract, none of which the refactor
changes; it's slow and flaky, the wrong tool for a tight red-green loop. (The
app's JS is trivial and progressively enhanced; cookie/redirect semantics are
covered by the test client.)

**The rule for every experiment:** the same suite must stay green after each
dependency is removed. Green = the LOC reduction came for free; red = the
"precise" replacement missed a case the library handled. Only `conftest.py` may
change between steps — never the assertions. (Line coverage is a floor, not the
contract: it shows every line ran, not that every behavior is asserted.)
