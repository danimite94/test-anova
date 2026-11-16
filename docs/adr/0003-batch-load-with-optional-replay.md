# ADR-0003: Batch load at startup, optional replay through the same classifier

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** FR-001, FR-002, FR-014, NFR-002, NFR-006, NFR-007
- **Resolves:** PRD open question OQ-4

## Context

Data comes from a synthetic generator (FR-001). It must reach the database with correct
quality flags (FR-002) quickly enough that `docker compose up` gives a usable product in a
few minutes (NFR-002: < 30 s; NFR-007: < 5 min). The PRD also has a *Could* requirement to
demonstrate live, streaming ingestion (FR-014), whose end state must be identical to a batch
load (FR-014 criterion 3).

Quality flags depend on **arrival order**, not timestamp order: a reading is `late` if a
later-timestamped reading for the same sensor already arrived (SPEC §4.1). So the generator's
output must preserve arrival order, and every ingestion path must apply the same rules.

## Decision

1. **The generator writes files, not database rows**: `readings.csv` in arrival order and
   `manifest.json` describing what was injected (SPEC §3).
2. **A one-shot batch loader** reads those files, classifies each record in `seq` order, and
   writes everything in one transaction with `COPY` (SPEC §4.2). It runs as a container that
   exits when done; it is idempotent via the file's SHA-256.
3. **Replay is optional** (`telemetry-replay --speed N`): it posts the same records in arrival
   order to `POST /api/v1/ingest/readings`, which uses the **same classifier function**
   (SPEC §4.3). It is not started by default.
4. **Single writer.** Only one loader or one replay writes at a time; this is documented, not
   enforced with locking.

## Consequences

**Positive**

- One classifier, one set of unit tests, two entry points — batch and replay cannot drift apart.
- The generated files are inspectable artefacts, and the manifest is the test oracle for the
  loader (FR-002) and quality summary (FR-011).
- Fast, simple default path: generate + `COPY` of 50k rows takes seconds.
- Replay shows streaming behaviour without adding a message broker.

**Negative**

- The ingest endpoint must rebuild classifier state from the database per batch
  (existing timestamps and latest timestamp per sensor). Cheap at this size, but it is extra
  code compared with the in-memory batch path.
- No protection against two concurrent writers; acceptable for a local, single-user tool.
- If FR-014 is cut (PRD §10), the ingest endpoint and replay client are not built; the
  classifier remains shared code regardless.

## Alternatives considered

| Option | Why not |
|---|---|
| **Streaming only** (generator → message broker such as MQTT/Kafka → consumer) | Most realistic, but adds a broker service, consumer offsets and delivery semantics — large scope for a *Could* requirement. |
| **Batch only** | Simplest; kept as the default. Replay is layered on top only if time allows. |
| **Generator writes straight to the database** | No inspectable artefact, no manifest-based testing, and mixes data creation with classification. |
| **Load data on backend startup** | Couples API availability to a long-running job and complicates healthchecks; a separate one-shot job is clearer (ADR-0008). |
