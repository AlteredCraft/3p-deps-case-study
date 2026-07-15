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
| 2 | email-validator (+ idna, dnspython) | 39,457 | +21 | 40,546 | 1,085 |
| 3 | flask-wtf | 520 | +39 | 40,026 | 1,124 |
| 4 | wtforms (+ its i18n catalogs) | 5,923 | +195 | 34,103 | 1,319 |
| 5 | flask-login | 683 | +95 | 33,420 | 1,414 |
| 6 | python-dotenv | 766 | +0 (12 in dev-only `run.py`) | 32,654 | 1,414 |

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
2. **email-validator → 21-line format check** (2026-07-15). A precise,
   format-only validator in `app/forms.py` (ASCII dot-atom local part,
   dot-separated domain labels, dot required after the `@` — matching the
   library's syntax-mode behavior; deliverability DNS checks were never used).
   Deliberate narrowing: internationalized (SMTPUTF8/IDN) addresses are no
   longer accepted — a feature this app never needed and no test pins.
   **39,457 LOC (17.8 % of the original footprint) for an email format check**
   — the clearest "more code than you need" datapoint. No conftest change.
3. **Flask-WTF → first-party CSRF + form glue** (2026-07-15). New `app/csrf.py`
   (~20 lines): random per-session token in the signed session cookie, echoed
   via hidden input/header, enforced globally in `before_request`,
   constant-time compare, 400 on mismatch — same contract the tests pin.
   `FlaskForm` replaced by a small `BaseForm` (plain `wtforms.Form` + request
   binding, `validate_on_submit()`, `csrf_token` hidden-input rendering).
   `wtforms` becomes a direct dependency (was transitive). Conftest seam:
   config key `WTF_CSRF_ENABLED` → `CSRF_ENABLED`. Note the security caveat:
   we replaced the CSRF *plumbing* but kept the cryptographic primitives
   (Flask's itsdangerous-signed session, `secrets`, `hmac.compare_digest`)
   with the experts.
4. **WTForms → `app/formlib.py`** (2026-07-15). A ~195-line micro form library
   implementing exactly the slice used: 7 field types, 6 validators,
   request/obj binding, inline `validate_<field>` hooks, and rendering that
   reproduces WTForms markup (sorted attributes, HTML5 constraint attrs
   derived from validators, textarea newline guard, WTForms' default error
   messages). Verified beyond the suite: register/login/new/index/edit pages
   render **byte-identical** to the baseline variant with CSRF on. The
   biggest first-party spend so far — the price of owning form rendering —
   still ~30:1 LOC in our favor. No conftest change.
5. **Flask-Login → `app/login.py`** (2026-07-15). ~95 lines: `current_user`
   (werkzeug `LocalProxy`, cached on `g`), `login_user`/`logout_user`,
   `login_required` (flash + redirect to the login view with `next`),
   `UserMixin`, and a remember-me cookie (user id + HMAC-SHA512 signature
   from `SECRET_KEY`, mirroring Flask-Login's own scheme). Remember-me is
   not test-pinned, so it was verified by hand: cookie set only when
   requested, login restored after session-cookie loss, tampered cookie
   rejected, cleared on logout, HttpOnly/SameSite honored. Session identity
   still rides Flask's itsdangerous-signed cookie — the crypto stayed with
   the experts. No conftest change.
6. **python-dotenv → 12-line loader in `run.py`** (2026-07-15). The library
   was only ever used by the dev entry point to read `.env`
   (KEY=VALUE lines, existing env vars win). 766 LOC shipped to prod for a
   dev convenience; the replacement adds zero shipping first-party LOC
   because `run.py` is outside the `app/` count. Verified live: with
   `SECRET_KEY` unset in the environment, `run.py` still boots from `.env`.
   No conftest change.

### Where it landed (2026-07-15)

`todo-3pdeps-limited/pyproject.toml` now declares **one** runtime dependency:
`flask`. Everything else that ships is Flask's own transitive core.

| Scope | Baseline | After step 6 | Δ |
| --- | ---: | ---: | ---: |
| Third-party (prod, filtered) | 217,493 | 32,654 | **−184,839 (−85.0 %)** |
| First-party `app/` | 964 | 1,414 | +450 |
| Python-only first-party | 428 | 878 | +450 |
| 3P-to-1P shipping ratio | ~225 : 1 | ~23 : 1 | |

- **~411 lines of dependency code shed per first-party line added.**
- New purpose-built modules: `db.py` (66 raw lines), `csrf.py` (44),
  `login.py` (143), `formlib.py` (343) — each fully readable in one sitting.
- Remaining third-party, all via `flask`: werkzeug 11,986 (**the KEEP** —
  password hashing lives in `werkzeug.security`, and Flask requires werkzeug
  regardless), jinja2 8,557, click 6,673, flask 4,068, itsdangerous 650,
  markupsafe 394, blinker 268.
- The unchanged 57-test suite stayed green after every step; only
  `conftest.py` changed (steps 1 and 3), exactly as the testing strategy
  prescribes. Beyond the suite: form pages render byte-identical to the
  baseline variant, and the un-pinned remember-me contract was verified by
  hand.
- Per the caveat, the security-sensitive primitives were **not** rewritten:
  password hashing (werkzeug), session signing (itsdangerous via Flask),
  token generation/comparison (`secrets`, `hmac`).

### Post-experiment: hardening the oracle back to 100 % (2026-07-15)

After step 6, line coverage of the limited variant's `app/` had slipped to
97 % — the new purpose-built modules had branches no test exercised. Restoring
the 100 % floor produced two findings worth keeping:

1. **Dead code in "precise" replacements is a smell you can act on.** The
   uncovered lines split cleanly into (a) code this app never calls —
   `Length` custom messages, `UserMixin.is_active`, `AnonymousUser.get_id` —
   which was simply **deleted** (you can't delete unused code out of a
   library), and (b) real behavior nobody had pinned.
2. **Writing the missing pins caught a genuine parity bug.** Eight tests were
   added *identically to both variants* (suite: 57 → 65): the full remember-me
   contract (cookie only on request, survives session loss, cleared on
   logout, tamper-rejected), checkbox state re-render, server-side max-length
   rejection, blank `due_date`, dotless email domain. The first draft also
   pinned a 64-char email local-part limit — and the **baseline failed it**:
   email-validator accepts a 65-char local part, so the step-2 replacement
   had been quietly *stricter* than the library. The replacement was relaxed
   to match. Behavior-identical means identical, not "better".
   (Bonus: the new remember-me tests surface `DeprecationWarning`s from
   flask-login's own `datetime.utcnow()` calls in the baseline — dependency
   code ages too.)

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
