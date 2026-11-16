# ADR-0004: FastAPI REST backend with hand-written SQL

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** FR-003…FR-014, NFR-003, NFR-009, NFR-010, NFR-011

## Context

The backend is Python 3.12. It serves a read-heavy JSON API with ten endpoints, two streamed
CSV exports, and one ingest endpoint (SPEC §6). It must:

- validate parameters strictly (UTC offsets required, range limits; SPEC §6.1),
- return RFC 9457 problem details for errors (SPEC §6.2),
- publish an OpenAPI document that contract tests compare against (ADR-0007),
- run analytical SQL — window functions, gaps-and-islands, `generate_series` (SPEC §5.3).

The queries are the core of the product; most of the logic is in SQL, not in object graphs.

## Decision

- **FastAPI** with **Pydantic v2** models for parameters and responses. OpenAPI is generated
  from those models.
- **REST** resources under `/api/v1`, as in SPEC §6.
- **psycopg 3** with a connection pool and **hand-written, parameterised SQL** kept in one
  query module (`telemetry.db`). No ORM.
- **Synchronous** endpoint functions (FastAPI runs them in a thread pool). Async adds
  complexity with no benefit at this load.
- CSV exports use `StreamingResponse`; errors go through a single exception handler that
  emits problem details.

## Consequences

**Positive**

- Request validation, serialisation and OpenAPI come from one set of type-annotated models,
  which also keeps strict type checking (NFR-010) effective.
- The SQL in the code is the SQL in SPEC §5.3 — easy to review, `EXPLAIN`, and test against
  a real database.
- Small dependency footprint and fast startup.

**Negative**

- Hand-written SQL means no automatic query building; mapping rows to models is manual.
  Mitigated by a small number of queries (≈ 10) and integration tests for each.
- Parameterisation must be done consistently to avoid SQL injection; enforced by always passing
  values as parameters and checked by the `S608` (Bandit) rule in ruff (ADR-0006).
- Synchronous handlers cap concurrency at the thread-pool size; irrelevant for a single-user tool.

## Alternatives considered

| Option | Why not |
|---|---|
| **Flask** | Mature, but validation, OpenAPI and typed models need several extensions. |
| **Django + Django REST Framework** | Strong admin and ORM, but heavy for ten read endpoints, and the ORM fights window-function queries. |
| **SQLAlchemy ORM / SQLModel** | Adds a mapping layer that most of these queries would bypass with raw SQL anyway. |
| **GraphQL** | Flexible queries aren't needed — the views and their data shapes are known up front. Harder to cache and to stream CSV. |
| **Async (asyncpg)** | Higher throughput under load the product doesn't have; more complex tests and connection handling. |
