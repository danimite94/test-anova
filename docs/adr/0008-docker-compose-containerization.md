# ADR-0008: Containerization with Docker Compose

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** NFR-005, NFR-007, NFR-011

## Context

A reviewer with only Docker installed must be able to run `docker compose up` and reach a
working UI within 5 minutes, including the first build (NFR-007). Data must survive restarts
(NFR-005). Services must report health (NFR-011). Startup has a strict order: the database must
be ready, then the schema created and the data loaded, before the API serves requests.

## Decision

### Services (`compose.yaml`)

| Service | Image | Role | Waits for | Health check |
|---|---|---|---|---|
| `db` | `postgres:16-alpine` (pinned minor) | Database; data in named volume `pgdata` | — | `pg_isready` |
| `init` | backend image | One-shot: `telemetry-migrate` → `telemetry-generate` → `telemetry-load`, then exits 0 | `db` healthy | exit code |
| `backend` | backend image | FastAPI on port 8000 (internal only) | `init` completed successfully | `GET /api/v1/health` |
| `frontend` | frontend image | nginx serving the SPA and proxying `/api/*` to `backend`; **only service with a published port** (`8080`) | `backend` healthy | `GET /` |

`depends_on` uses `condition: service_healthy` / `service_completed_successfully`, so
startup order needs no sleep loops.

Setting `INIT_LOAD=false` makes `init` migrate only, leaving the database empty for a replay
demo (FR-014).

### Images

- **Backend**: multi-stage. Build stage uses `uv` to install from `uv.lock` into a virtualenv;
  runtime stage is `python:3.12-slim` with only the virtualenv and source, running as a
  non-root user.
- **Frontend**: multi-stage. `node:20-alpine` runs `npm ci` and `vite build`; runtime is
  `nginxinc/nginx-unprivileged:1.27-alpine` with the static files and an nginx config.
- Base images pinned to a minor version (digests in Phase 2 governance).
- `.dockerignore` files keep `node_modules`, virtualenvs, generated data and `.git` out of
  build contexts.

### Variants

| File | Used by | Differences |
|---|---|---|
| `compose.yaml` | Reviewers, CI e2e | Production-like: built images, no source mounts, only port 8080 published |
| `compose.dev.yaml` | Developers, opt in with `-f` | Source bind mounts, `uvicorn --reload`, Vite dev server, database port published |

The dev file is opt-in rather than `compose.override.yaml` so that a plain `docker compose up`
always gives the reviewer the production-like stack.

### Lifecycle

- `docker compose up` — build and start everything; data persists in `pgdata`.
- `docker compose down` — stop; data kept.
- `docker compose down -v` (`make reset`) — stop and delete data; next `up` regenerates it.
- Re-running `init` against an already-loaded volume is a no-op (idempotent load, SPEC §4.2).

## Consequences

**Positive**

- One command, deterministic order, no manual steps; the same file drives the CI smoke and
  e2e tests (ADR-0009).
- One backend image serves three roles (`init`, `backend`, replay client), so there is one
  thing to build and scan.
- Only the frontend port is exposed; the database is unreachable from the host by default.

**Negative**

- First build pulls and builds Node and Python images; expected 2–4 minutes on a typical
  connection — inside the 5-minute budget, but the main risk to NFR-007. Mitigated by small
  base images and layer ordering (lockfile before source).
- Two compose files to keep consistent.

## Changes to other documents

SPEC §5.1 said migrations are applied on backend startup. Because `init` runs before
`backend` and needs the schema to load data, migrations move to the `init` job. SPEC §5.1
is updated in the same change as this ADR.

## Alternatives considered

| Option | Why not |
|---|---|
| **Backend runs migrations and loads data on startup** | Couples API readiness to a long job and makes the health check ambiguous. |
| **Single all-in-one container** | Simpler to run, but hides the architecture and fights one-process-per-container conventions. |
| **`compose.override.yaml` for dev** | Applied automatically, so reviewers would get the dev stack by accident. |
| **Kubernetes / kind / Tilt** | Far beyond what a local, single-user take-home needs. |
| **Alpine Python base** | Smaller, but musl breaks or slows many Python wheels (numpy, psycopg binary). |
