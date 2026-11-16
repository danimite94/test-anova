# ADR-0002: Long-format schema, immutable readings, derived data at query time

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** FR-002, FR-006, FR-008, FR-009, FR-011, NFR-001, NFR-003, NFR-006
- **Resolves:** PRD open question OQ-2

## Context

Three modelling questions:

1. **Shape of readings.** Sensors report independently. A reading can be missing for one
   sensor and present for another, arrive late, or arrive twice. Different sensors have
   different units and limits. NFR-001 asks that more sensors not require architectural change.
2. **What happens to bad data.** The PRD requires that nothing is silently dropped or fixed
   (FR-002): duplicates and outliers must remain visible, with a flag.
3. **Where derived data lives.** Aggregates, anomaly events, gaps and completeness could be
   computed once at load time and stored, or computed from readings on every request.

Sizing: ≤ 10,080 valid readings per sensor per week. Per-request derivations scan at most
that many rows per sensor via the `(sensor_id, ts)` index.

## Decision

1. **Long format.** One row per reading: `(dataset_id, seq, sensor_id, ts, value, quality)`.
   Sensors and their limits are rows in a `sensor` table (SPEC §5.1).
2. **Readings are immutable and every delivery is stored.** Quality is expressed with exactly
   one flag per reading (`ok`, `late`, `outlier`, `duplicate`), assigned at ingest because it
   depends on arrival order (SPEC §4.1). There is no unique constraint on `(sensor_id, ts)`.
3. **Everything else is derived at query time in SQL**: hourly aggregates, limit and
   statistical anomalies, anomaly events, gaps and completeness (SPEC §5.3). Nothing derived
   is stored.

## Consequences

**Positive**

- Adding a sensor is an `INSERT` into `sensor`, not a schema change.
- Out-of-order and duplicate deliveries fit naturally; the stored data is a faithful audit
  of what arrived, which Phase 2 governance (lineage) builds on.
- Derived results can never be stale: changing a limit in `sensor` changes the anomalies
  on the next request. There is no sync or backfill job to write or test.
- Reproducibility (NFR-006) follows directly: same readings → same derived results.

**Negative**

- Each request recomputes its results. Measured cost at this scale is milliseconds, but the
  performance tests (NFR-003) must watch the anomaly-event query, which is the heaviest.
- Every query must remember to filter `quality IN ('ok', 'late')`. Mitigated by keeping that
  predicate in one place in the query module and testing each endpoint with invalid data present.
- Comparing sensors at the same instant needs a pivot in the query or the client; the API
  returns one series per sensor instead (SPEC §6.6).

## Alternatives considered

| Option | Why not |
|---|---|
| **Wide format** (one column per sensor, one row per minute) | Breaks when sensors report at different times, can't hold duplicates, and every new sensor is a schema migration. |
| **Deduplicate on insert** (unique `sensor_id, ts`) | Simpler queries, but loses the evidence the PRD requires users to see (FR-011 counts duplicates). |
| **Clean data on load** (drop outliers, reorder) | Violates FR-002 — the product must show data as it arrived. |
| **Store anomaly flags/events at load** | Faster reads, but stale whenever limits change and needs recomputation logic for replay. Revisit if detection becomes expensive (e.g. ML). |
| **Materialized hourly aggregates** | Aggregating ≤ 10k rows per sensor is already fast; a materialized view adds refresh logic. Revisit if NFR-003 is missed. |
