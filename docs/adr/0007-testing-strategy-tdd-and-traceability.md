# ADR-0007: Testing strategy — TDD, real-database tests, requirement traceability

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** NFR-009 (and every FR's acceptance criteria)

## Context

The project follows spec-driven development: PRD acceptance criteria are written as
Given/When/Then so they become tests directly, and NFR-009 requires every requirement to have
an automated test that references its ID, with ≥ 85% backend line coverage.

Most of the product's logic is in SQL (ADR-0002, ADR-0004). Mocking the database would test
the mocks, not the queries.

## Decision

### Workflow: test-driven, one requirement at a time

For each requirement in Phase 3:

1. **Red** — turn its acceptance criteria into tests; run them and see them fail for the
   right reason.
2. **Green** — write the minimum code to make them pass.
3. **Refactor** — clean up with the tests passing.

If a criterion turns out to be wrong or untestable, the PRD/SPEC is changed first, then the test.

### Test levels

| Level | Scope | Tools | Database | Runs |
|---|---|---|---|---|
| **Unit** | `domain` and `generator`: classifier, limit evaluation, signal models, determinism, manifest invariants. Frontend: chart option builders, gap → null insertion, formatting. | pytest; Vitest | None | Every commit; < 10 s |
| **Integration** | Loader vs manifest, every SQL derivation, every API endpoint end to end through FastAPI's test client, CSV format, migrations. | pytest + `testcontainers` | Real PostgreSQL 16 in a throwaway container | Every PR |
| **Contract** | The generated OpenAPI document must equal the committed `docs/openapi.json`; responses validate against it. API changes are therefore always deliberate and reviewed. | pytest | Real | Every PR |
| **End-to-end** | Full stack via `compose.yaml`: smoke test (all services healthy, UI loads) and one journey per persona (PRD §11). | Playwright | Full stack | Every PR |
| **Performance** | NFR-001 (10-week dataset), NFR-002 (load time), NFR-003 (p95 latency). | pytest, marker `perf` | Real | Every PR, **report-only** (laptop vs CI timings differ) |

### Test data

- A **session-scoped fixture** generates and loads the seed-42 dataset once per test run;
  its manifest and scripted events (EV-1…EV-3) are the oracle.
- **Small hand-built fixtures** for edge cases (an hour with only outliers, a duplicate of an
  outlier, a reading exactly on a limit).
- No mocks of the database or of our own modules.

### Traceability

- Python tests declare requirements with a marker: `@pytest.mark.req("FR-006")`.
  Playwright tests put the ID in the title: `test("[FR-010] drill down from anomaly", …)`.
- A script (`make req-coverage`) extracts every ID from `docs/PRD.md`, collects IDs from tests,
  and reports the gaps. CI **fails** if any *Must* requirement or any NFR has no test and
  **warns** for *Should*/*Could*.

### Coverage

- Backend: ≥ 85% line coverage, enforced in CI (`--cov-fail-under=85`).
- Frontend: reported, not enforced — the e2e journeys cover the views; unit tests cover logic.

## Consequences

**Positive**

- Every acceptance criterion has an executable counterpart; the traceability report shows
  progress and gaps at a glance.
- Real-database tests catch the bugs that matter here: SQL mistakes, time zone handling,
  ordering, empty-hour behaviour.
- The manifest oracle means tests don't hard-code counts that change when the generator changes.

**Negative**

- Integration tests need Docker wherever tests run (true locally and on GitHub Actions runners).
- Container startup adds ~5–10 s per test session; mitigated by one session-scoped database
  and per-test transactions rolled back after each test.
- Performance results are noisy in CI; they are tracked, not gated.

## Alternatives considered

| Option | Why not |
|---|---|
| **Mock the database** | Fast, but the SQL is the logic under test. |
| **SQLite in tests, Postgres in production** | Different SQL dialect; the window and time functions we rely on would behave differently. |
| **Shared long-lived test database** (compose service) | Works, but tests then depend on external setup and leak state between runs; `testcontainers` makes `pytest` self-contained. |
| **Behaviour-driven framework** (pytest-bdd, Gherkin files) | Matches Given/When/Then literally, but adds a layer between criteria and code. Plain pytest with the criterion in the docstring is simpler. |
| **Gate on performance** | CI runner timings are too variable to fail builds on; revisit with dedicated runners. |
