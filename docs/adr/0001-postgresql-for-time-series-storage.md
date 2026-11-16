# ADR-0001: PostgreSQL for time-series storage

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** NFR-001, NFR-002, NFR-003, NFR-005, NFR-007

## Context

The product stores one week of readings from five sensors at one reading per minute:
**≈ 50,400 readings, ≈ 8 MB including indexes** (SPEC §5.2). The headroom requirement is 10×
that (NFR-001), ≈ 80 MB. The assignment requires a SQL database with data persisted locally,
and the whole stack must start with `docker compose up` (NFR-007).

What the queries need (SPEC §5.3):

- Range scans by sensor and time
- Window functions with **time-based frames** (`RANGE BETWEEN interval '60 minutes' PRECEDING …`)
  for the rolling z-score
- `generate_series` over timestamps, to return empty hours in aggregates
- A real timestamp-with-time-zone type, since everything is UTC (NFR-008)
- Concurrent reads from the API while replay writes (FR-014)

At this volume, raw storage performance is not a differentiator. Every option below handles it.
The deciding factors are SQL capability, how the system behaves as a multi-service app,
and how representative it is of a production setup.

## Decision

Use **PostgreSQL 16** (official `postgres:16-alpine` image) as the only datastore, with data
in a named Docker volume. No time-series extension.

## Consequences

**Positive**

- Every query in SPEC §5.3 is native SQL: `timestamptz`, `RANGE` frames with interval offsets,
  `EXCLUDE CURRENT ROW`, `generate_series`, `jsonb`.
- A normal client-server database: the API, loader and replay can run concurrently.
- Integration tests run against the same engine as production (ADR-0007).
- Upgrade path stays open: TimescaleDB is a PostgreSQL extension, so the same `reading`
  table could become a hypertable without changing the schema or queries.

**Negative**

- One more container to run than an embedded database; mitigated by a healthcheck and
  `depends_on` ordering (ADR-0008).
- No built-in retention policies or continuous aggregates; not needed at this size (SPEC §11).

## Alternatives considered

| Option | Why not |
|---|---|
| **SQLite** (file in a volume) | Fewest moving parts, and it supports window functions. But it has no timestamp type (time stored as text or numbers), no `generate_series` without an extension, `RANGE` frames only over numeric offsets, and one writer at a time. Less representative of a production database tier. |
| **PostgreSQL + TimescaleDB** | Hypertables and continuous aggregates help at hundreds of millions of rows. At 50k rows they add operational surface for no measurable benefit. Easy to add later. |
| **InfluxDB** | Purpose-built for metrics, but the query language is not standard SQL in most versions, sensor metadata and limits would need a second store, and it doesn't meet the "SQL database" constraint cleanly. |
| **DuckDB / Parquet files** | Excellent for analytics and exports, but an embedded, single-writer engine — a poor fit for a long-running API with concurrent ingest. A good candidate for an offline analysis tool later. |
