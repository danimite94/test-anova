# CLAUDE.md

Pump Skid Telemetry Explorer: an industrial telemetry take-home (database, Python backend,
web frontend) built with spec-driven development. The specs are the source of truth;
code is written to satisfy them.

## Status

| Phase | Scope | State |
|---|---|---|
| 1 · Specify & design | PRD, SPEC, ADRs | Done |
| 2 · Engineering foundation | Governance, guardrails, test harness, Docker, CI/CD — a walking skeleton, no features | Next |
| 3 · Implementation | One requirement at a time, test-driven | Not started |

The user approves each phase, and each document, before the next one starts.

## Specs — read before acting

- **`docs/PRD.md`** — what and why. Requirement IDs `FR-xxx` / `NFR-xxx` with Given/When/Then
  acceptance criteria. Read before any feature work; every change traces to an ID.
- **`docs/SPEC.md`** — how. Read before touching the generator, classifier, schema, queries,
  API contract or frontend views. §10 maps each requirement to its test level.
- **`docs/adr/`** — why each technical choice was made. Read the relevant ADR before changing
  a dependency, tool, service, or the repo layout. Accepted ADRs are immutable: record a
  changed decision as a new ADR that supersedes the old one.
- **`docs/GOVERNANCE.md`** — rules for data and AI-assisted work (`GOV-xxx`). Created in Phase 2.

## Changing behaviour

1. Find the requirement ID the change serves.
2. If the PRD or SPEC is wrong or silent, propose the spec change and get approval first;
   update the spec (and add an ADR if a decision changes) before the code.
3. **Red**: turn the acceptance criteria into tests tagged with the ID
   (`@pytest.mark.req("FR-006")`; Playwright titles `[FR-006] …`), and watch them fail.
4. **Green**: the minimum code that passes.
5. **Refactor** with tests green.

Done means: the ID's tests pass, lint and strict type checks are clean, and the spec still
describes what the code does.

## Architecture (planned — SPEC §1, ADR-0008)

`db` (PostgreSQL 16) → `init` (one-shot: migrate → generate → load) → `backend` (FastAPI,
`/api/v1`) → `frontend` (React + ECharts behind nginx, port 8080). Backend package
`telemetry`: `domain` (pure, no I/O) · `generator` · `ingest` · `db` · `api`.

Invariants that cut across every module:

- **Readings are immutable.** Every delivery is stored with exactly one quality flag, assigned
  at ingest from arrival order by the shared classifier (SPEC §4.1).
- **Valid = `ok` + `late`.** Only valid readings feed charts, aggregates, anomalies,
  completeness and "latest value".
- **Outlier ≠ anomaly.** Outlier: bad data, flagged at ingest. Anomaly: real process event,
  derived at query time.
- **Derived data is computed in SQL at query time**, never stored (ADR-0002).
- **UTC everywhere**; API time parameters carry an explicit offset.

## Commands

No code or tooling exists yet. Phase 2 adds a `Makefile` (ADR-0006); list its install, lint,
test-all, test-one and run commands here when it lands.

## Git

- `main` is the default branch; work on feature branches (current: `setup`).
- One commit per approved document or concern.
