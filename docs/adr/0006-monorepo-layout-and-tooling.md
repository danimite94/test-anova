# ADR-0006: Monorepo layout and tooling

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** NFR-006, NFR-007, NFR-009, NFR-010

## Context

The repository holds a Python backend (generator, loader, API), a TypeScript frontend,
infrastructure files, and the specs. A reviewer must find their way around quickly; CI must
run each part's checks independently; builds must be reproducible (NFR-006); and code must
pass lint, format and strict type checks (NFR-010).

## Decision

### Layout

```
.
├── backend/
│   ├── pyproject.toml        # one package: telemetry
│   ├── uv.lock
│   ├── src/telemetry/
│   │   ├── domain/           # sensor catalogue, flags, classifier, limits — pure
│   │   ├── generator/
│   │   ├── ingest/
│   │   ├── db/               # pool, migrations runner, queries
│   │   │   └── migrations/   # 0001_init.sql, 0002_…
│   │   └── api/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── perf/
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── src/
│   └── tests/                # Vitest unit tests; e2e/ for Playwright
├── docs/                     # PRD, SPEC, adr/, (Phase 2) GOVERNANCE
├── compose.yaml
├── Makefile
└── .github/workflows/
```

The module boundaries are those in SPEC §1. `domain` must not import from `db` or `api`.

### Python tooling

| Concern | Tool |
|---|---|
| Version | Python 3.12 (pinned in `.python-version` and the Docker image) |
| Dependencies & lockfile | **uv** (`uv.lock` committed) |
| Lint + format | **ruff** (rule sets incl. `E,F,I,B,UP,S,PT,SIM`) |
| Type checking | **mypy --strict** on `src/` |
| Tests | **pytest**, `pytest-cov`, `testcontainers` (ADR-0007) |
| Migrations | Numbered plain-SQL files applied in order by a small runner that records them in a `schema_migrations` table |
| CLI entry points | `telemetry-migrate`, `telemetry-generate`, `telemetry-load`, `telemetry-replay` |

### Frontend tooling

| Concern | Tool |
|---|---|
| Runtime | Node 20 LTS (pinned in `.nvmrc` and the Docker image) |
| Dependencies & lockfile | **npm** (`package-lock.json` committed) |
| Lint / format / types | **ESLint**, **Prettier**, **tsc --strict** |
| Tests | **Vitest** + Testing Library; **Playwright** for e2e |

### Entry point for humans

A `Makefile` wraps common commands: `make up`, `make down`, `make reset`, `make lint`,
`make test`, `make test-one T=<path::name>`, `make e2e`.

## Consequences

**Positive**

- One clone, one `make` vocabulary for both halves of the stack.
- Lockfiles for both ecosystems make builds reproducible locally, in CI and in images.
- uv and ruff are fast enough to run on every save and every commit hook (Phase 2).
- Plain-SQL migrations match the hand-written-SQL approach (ADR-0004) and are trivially reviewable.

**Negative**

- Two package managers and two lint stacks to maintain.
- The in-house migration runner is code we own (~50 lines); it gets its own tests.
- Import boundaries between modules are a convention until Phase 2 adds a check for them.

## Alternatives considered

| Option | Why not |
|---|---|
| **Poetry** | Mature, but slower, and uv now covers locking, virtualenvs and Python installs in one tool. |
| **pip + requirements.txt** | No lockfile for transitive dependencies without extra tooling. |
| **Black + isort + flake8** | Three tools where ruff does all three, faster. |
| **pyright** instead of mypy | Equally good; mypy chosen for its wider familiarity among reviewers. Either satisfies NFR-010. |
| **Alembic** for migrations | Designed around SQLAlchemy; with no ORM, it would only wrap raw SQL strings. |
| **Separate repos** for frontend and backend | More ceremony and cross-repo versioning for a single deliverable. |
| **pnpm** | Faster installs, but npm is preinstalled everywhere, including CI images. |
