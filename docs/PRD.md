# Product Requirements Document — Pump Skid Telemetry Explorer

| | |
|---|---|
| Status | Draft — awaiting review |
| Phase | 1 · Specify & design |
| Related | `docs/SPEC.md` (technical spec), `docs/adr/` (decisions) |

This document says **what** the product must do and **how we know it is done**.
It deliberately avoids technology choices; those live in the SPEC and ADRs.

---

## 1. Problem statement

A pumping unit on a plant floor is instrumented with five sensors that report once a minute.
The people who run, maintain, and analyse the unit have no single place to:

- look at what each sensor did over the past week,
- compare sensors against each other on the same timeline,
- tell real process events apart from bad sensor data, and
- pull the data out for their own analysis.

Raw sensor data is also messy: readings go missing, arrive late or twice, and sometimes
report physically impossible values. A tool that hides this — or silently "fixes" it — is
misleading. The product must show the data as it is, mark what is suspect, and
summarise it in ways each user group can act on.

## 2. Glossary

| Term | Meaning |
|---|---|
| **Asset** | The monitored equipment: one pump skid, `P-101`. |
| **Sensor** | One measurement point on the asset, with a fixed type and unit. |
| **Reading** | One value from one sensor at one timestamp (UTC, minute resolution). |
| **Slot** | An expected reading time: one per sensor per minute. A week has 10,080 slots per sensor. |
| **Gap** | One or more slots with no reading. Shown as a break, never interpolated. |
| **Dropout** | A gap caused by a sensor going offline for an extended period (≥ 15 minutes). |
| **Quality flag** | A label on a reading describing its trustworthiness: `ok`, `outlier`, `duplicate`, `late`. |
| **Outlier** | A *data quality* problem: a value outside the sensor's physically valid range (e.g. −999 °C). The value is wrong, not the process. |
| **Anomaly** | A *process* event: a valid value that breaches an operating limit or is statistically unusual. The value is real and worth attention. |
| **Operating limits** | Per-sensor warning and alarm thresholds (low and high). |
| **Aggregate** | Hourly min / max / avg / count of valid readings for one sensor. |

The outlier-vs-anomaly distinction is central: outliers are excluded from charts' statistics and
aggregates; anomalies are highlighted.

## 3. Users and personas

| Persona | Goal | Typical question | Primary features |
|---|---|---|---|
| **Plant operator** | Keep the unit running safely during a shift. | "Did anything go out of limits overnight?" | Sensor overview, anomaly list, single-sensor chart |
| **Process engineer** | Understand cause and effect between process variables. | "Did the vibration spike on Tuesday coincide with a pressure drop?" | Multi-sensor comparison, anomaly drill-down |
| **Data analyst** | Get clean, trustworthy data for offline analysis and reporting. | "What's the hourly average flow, and how complete is the data?" | Hourly aggregates, data quality summary, CSV export |

## 4. Scope summary

The monitored asset is a single pump skid with five sensors:

| Sensor ID | Measurement | Unit |
|---|---|---|
| `TT-101` | Inlet temperature | °C |
| `TT-102` | Outlet temperature | °C |
| `PT-101` | Discharge pressure | bar |
| `VT-101` | Vibration velocity (RMS) | mm/s |
| `FT-101` | Flow rate | m³/h |

Data covers one fixed week, **2026-11-02 00:00 UTC to 2026-11-09 00:00 UTC** (exclusive),
produced by a synthetic generator. The signals are physically related (e.g. a bearing fault
raises vibration and outlet temperature together) so that comparison is meaningful.

## 5. User stories

| ID | As a… | I want to… | So that… | FRs |
|---|---|---|---|---|
| US-01 | operator | see every sensor's latest value and status at a glance | I know immediately if something needs attention | FR-003 |
| US-02 | operator | see a list of anomalies over the week, newest first | I can review what happened while I was off shift | FR-008, FR-010 |
| US-03 | operator | open a sensor's chart over any time range | I can see what led up to an event | FR-004, FR-007 |
| US-04 | engineer | plot several sensors on one shared time axis | I can spot correlated behaviour | FR-005 |
| US-05 | engineer | click an anomaly and jump to that moment in the chart | I can investigate it in context | FR-010 |
| US-06 | engineer | see statistically unusual readings that stay inside limits | I catch developing problems before they become alarms | FR-009 |
| US-07 | analyst | see hourly min/max/avg per sensor | I can report on trends without handling raw data | FR-006 |
| US-08 | analyst | see how complete and clean each sensor's data is | I know how far I can trust it | FR-011 |
| US-09 | analyst | download raw readings or hourly aggregates as CSV | I can analyse them in my own tools | FR-012, FR-013 |
| US-10 | reviewer / developer | regenerate the exact same dataset from a seed | results and tests are reproducible | FR-001 |
| US-11 | reviewer / developer | watch data arrive as if live | I can see the system handle streaming input | FR-014 |

## 6. Functional requirements

Priority uses MoSCoW: **M**ust, **S**hould, **C**ould. Musts form the minimum shippable product;
Coulds are cut first if time runs short (see §10).

Acceptance criteria are written to become automated tests directly. Exact parameter
values (limits, window sizes, response shapes) are defined in the SPEC.

### Data generation and ingestion

**FR-001 — Reproducible synthetic data** · M
The system generates one week of readings for the five sensors, including gaps, dropouts,
out-of-order timestamps, duplicates and outliers, deterministically from a seed.

- *Given* seed `42` and the same generator version, *when* the dataset is generated twice, *then* both outputs are identical.
- *Given* seeds `42` and `43`, *when* each is generated, *then* the outputs differ.
- *Given* a generated dataset, *when* it is inspected, *then* every sensor has at least one gap, at least one sensor has a dropout ≥ 15 min, and the dataset contains at least one out-of-order reading, one duplicate, and one outlier.
- *Given* a generated dataset, *when* it is inspected, *then* every timestamp lies within the fixed week and is in UTC.

**FR-002 — Load data with quality flags** · M
Generated readings are loaded into the database. Nothing is silently dropped: every
reading is stored with a quality flag.

- *Given* an empty database, *when* the dataset is loaded, *then* the number of stored readings equals the number of generated readings.
- *Given* a reading whose value is outside its sensor's valid range, *when* loaded, *then* it is stored with flag `outlier`.
- *Given* two readings for the same sensor and timestamp, *when* loaded, *then* the first received is stored as `ok` and the second as `duplicate`.
- *Given* a reading that arrives after a later-timestamped reading for the same sensor, *when* loaded, *then* it is stored with flag `late` and is returned in correct time order by queries.
- *Given* a loaded dataset, *when* the same dataset is loaded again, *then* the stored readings are unchanged (idempotent load).
- *Given* a load completes, *then* the run records the generator seed, generator version, load time, and counts per flag.

**FR-014 — Live replay mode** · C
Readings can be streamed into the running system at an accelerated rate instead of being
batch-loaded.

- *Given* replay is started at 60× speed, *when* 1 minute of wall-clock time passes, *then* about 60 minutes of data (±5%) have been ingested.
- *Given* replay is running, *when* the user views a chart, *then* new readings appear without a full page reload.
- *Given* replay is used instead of batch load, *when* it finishes, *then* stored readings and flags are identical to a batch load with the same seed.

### Browsing and comparison

**FR-003 — Sensor overview** · M
A landing view lists all sensors with ID, name, type, unit, latest valid value and
timestamp, current limit status, and data completeness for the week.

- *Given* the loaded dataset, *when* the overview opens, *then* all five sensors are listed.
- *Given* a sensor whose latest valid reading breaches an alarm limit, *when* the overview opens, *then* that sensor shows an alarm status.
- *Given* a sensor whose most recent slots are a gap, *when* the overview opens, *then* it shows the last *valid* reading and its timestamp, not a blank or zero.

**FR-004 — Single-sensor time series** · M
The user selects one sensor and a time range (default: the full week) and sees a line chart of its readings.

- *Given* a sensor and a range, *when* the chart loads, *then* it shows every `ok` and `late` reading in that range in time order.
- *Given* the range contains `outlier` or `duplicate` readings, *when* the chart loads, *then* they are not drawn as part of the line (outliers may be shown as separate markers).
- *Given* a range with no readings, *when* the chart loads, *then* an empty-state message is shown instead of an error.
- *Given* the user zooms or pans, *when* the range changes, *then* the chart updates to the new range.

**FR-005 — Multi-sensor comparison** · M
The user selects two or more sensors and sees them on one shared time axis. Sensors with
different units are plotted on separate y-axes or stacked panels so values stay readable.

- *Given* two sensors with different units, *when* compared, *then* each has its own labelled y-axis or panel with the correct unit.
- *Given* the user zooms on one series, *when* the range changes, *then* all compared series show the same range.
- *Given* all five sensors selected over the full week, *when* the comparison loads, *then* it meets NFR-004.

**FR-007 — Gaps are visible** · M
Missing data is shown as a break in the line, never interpolated.

- *Given* a sensor with a gap from 10:00 to 10:30, *when* charted, *then* no line segment connects 09:59 to 10:31.
- *Given* a dropout ≥ 15 min, *when* charted, *then* the dropout period is visually marked (e.g. shaded).

### Aggregates and analysis

**FR-006 — Hourly aggregates** · M
For any sensor and range, the system returns min, max, average and count of valid
(`ok` + `late`) readings per UTC hour, viewable as a table and chartable.

- *Given* a sensor with 60 `ok` readings in an hour, *when* aggregated, *then* min/max/avg match a reference calculation and count = 60.
- *Given* an hour containing outliers or duplicates, *when* aggregated, *then* they are excluded from min/max/avg/count.
- *Given* an hour with no valid readings, *when* aggregated, *then* the hour is still returned with count = 0 and empty min/max/avg (not zero).
- *Given* a one-day range, *when* aggregated, *then* exactly 24 rows are returned, aligned to the start of each UTC hour.

**FR-008 — Limit anomalies** · M
Each sensor has low/high warning and alarm limits. Valid readings outside a limit are flagged as anomalies of the corresponding severity.

- *Given* a valid reading above the sensor's high-alarm limit, *when* anomalies are evaluated, *then* it is flagged `alarm_high`.
- *Given* a valid reading between high-warning and high-alarm, *then* it is flagged `warning_high`. (Low limits mirror this.)
- *Given* an `outlier` reading outside the limits, *when* anomalies are evaluated, *then* it is **not** flagged as an anomaly.
- *Given* consecutive breaching readings, *when* listed, *then* they are grouped into one anomaly event with start, end, peak value and severity.

**FR-009 — Statistical anomalies** · S
Valid readings that deviate strongly from the sensor's recent behaviour are flagged, even inside limits.

- *Given* a reading more than the configured number of standard deviations from the rolling mean of the preceding window, *when* evaluated, *then* it is flagged `statistical`.
- *Given* fewer readings in the window than the configured minimum (e.g. right after a dropout), *when* evaluated, *then* no statistical flag is raised.
- *Given* the generator injects a known spike within limits, *when* evaluated, *then* it is flagged.

**FR-010 — Anomaly list and drill-down** · M
A list of anomaly events across all sensors, filterable by sensor and severity, newest first. Selecting one opens the relevant chart centred on the event.

- *Given* the loaded dataset, *when* the list opens, *then* events are sorted by start time descending.
- *Given* a severity filter of `alarm`, *when* applied, *then* only alarm events are shown.
- *Given* the user selects an event, *when* the chart opens, *then* its range includes the event plus context before and after, and the event is highlighted.

**FR-011 — Data quality summary** · S
Per sensor: completeness % (valid readings ÷ expected slots), number of gaps, longest gap, and counts per quality flag.

- *Given* a sensor with 10,080 slots and 9,576 valid readings, *when* summarised, *then* completeness shows 95.0%.
- *Given* the generated dataset with known injected issues, *when* summarised, *then* the counts per flag match the generator's manifest.

### Export

**FR-012 — Export raw readings (CSV)** · M
The user exports readings for selected sensors and a time range as CSV.

- *Given* sensors and a range, *when* exported, *then* the CSV has a header row and one row per stored reading, with columns for sensor ID, UTC timestamp (ISO 8601), value, unit and quality flag.
- *Given* the export, *when* re-imported, *then* values round-trip without precision loss beyond the stored precision.
- *Given* an option to exclude invalid readings, *when* selected, *then* `outlier` and `duplicate` rows are omitted.

**FR-013 — Export hourly aggregates (CSV)** · M
The user exports the FR-006 aggregates for selected sensors and a range as CSV.

- *Given* sensors and a one-day range, *when* exported, *then* the CSV has 24 rows per sensor with columns sensor ID, hour start (UTC, ISO 8601), min, max, avg, count, unit.
- *Given* an hour with count = 0, *when* exported, *then* min/max/avg are empty fields, not `0`.

## 7. Non-functional requirements

Sizing basis: 5 sensors × 1,440 readings/day × 7 days = **50,400 expected readings**
(≈ 10 MB in a SQL database including indexes). Targets are measured on a typical developer
laptop running the full stack in Docker.

| ID | Category | Requirement | How verified |
|---|---|---|---|
| NFR-001 | Data volume | Handles the 50,400-reading week, and 10× that (e.g. 50 sensors, or 10 weeks) without architectural change. | Load test with a 10× generated dataset |
| NFR-002 | Ingestion throughput | Full-week batch load completes in < 30 s (≥ 1,700 readings/s). Replay supports up to 1,000× real time. | Timed integration test |
| NFR-003 | Query latency | API p95 < 300 ms for a one-week raw series of one sensor (10,080 points) and for one week of hourly aggregates for all sensors. | Performance test in CI (report-only) |
| NFR-004 | Frontend responsiveness | Initial page load < 2 s after services are healthy. All five sensors over the full week (~50k points) render in < 2 s and zoom/pan without visible lag. | Manual check + e2e timing |
| NFR-005 | Retention | All data is kept for the life of the local data volume. Restarting the stack keeps data; an explicit reset command clears it. | Integration test across restart |
| NFR-006 | Reproducibility | Same seed + generator version → identical data, flags, anomalies and aggregates. | Deterministic tests |
| NFR-007 | Portability | A reviewer with only Docker installed can start everything with `docker compose up` and reach the UI in < 5 min, including the first build. | Smoke test in CI on a clean runner |
| NFR-008 | Time handling | All timestamps are stored, computed and exported in UTC; the UI labels times as UTC. | Unit tests |
| NFR-009 | Testability | Every FR and NFR has at least one automated test referencing its ID. Backend line coverage ≥ 85%. | CI requirement-coverage report |
| NFR-010 | Maintainability | Code passes lint, format and strict type checks with zero errors. | CI gate |
| NFR-011 | Observability | Each service exposes a health check and writes structured logs; the load run is logged with its summary counts. | Smoke test |
| NFR-012 | Browser support | Latest desktop Chrome and Firefox. | Manual check |

## 8. Data & AI governance

**TBD — specified in Phase 2** (`docs/GOVERNANCE.md`, requirement IDs `GOV-xxx`).

Constraints already in place that Phase 2 builds on:

- Only synthetic data is used; no real plant data enters the repository.
- Every load records its seed and generator version (lineage, FR-002).
- Raw readings are never modified or deleted by the product; quality is expressed by flags (FR-002).

## 9. Out of scope

| Item | Reason |
|---|---|
| Authentication, user accounts, role-based access | Single local user for the take-home; roles revisited in Phase 2 governance |
| Machine-learning anomaly detection | Rule-based and statistical detection meet the need at this scale |
| Real device connectivity (OPC UA, MQTT, Modbus) | Data source is synthetic |
| Alerts and notifications (email, SMS, push) | Viewing anomalies is in scope; acting on them is not |
| Multiple assets or sites | One pump skid; schema should not prevent more (NFR-001) |
| Parquet / Excel export | CSV covers the analyst's needs |
| Editing or annotating data | Read-only product; raw data is immutable |
| Time zone conversion in the UI | UTC everywhere (NFR-008) |
| Cloud deployment, high availability | Runs locally; CI builds and publishes images only |
| Mobile layouts | Desktop browsers only (NFR-012) |

## 10. Scope for the ~1 week budget

If time runs short, cut in this order (last = most protected):

1. **FR-014** Live replay mode (C)
2. **FR-011** Data quality summary as its own view — the counts remain in the load log (S)
3. **FR-009** Statistical anomalies (S)
4. Dropout shading in FR-007 — gaps still break the line
5. Must-haves are not cut; they form the minimum product.

## 11. Success criteria

The take-home is successful when:

1. A reviewer clones the repo, runs `docker compose up`, and reaches a working UI within 5 minutes (NFR-007).
2. All **Must** requirements pass their acceptance tests in CI, and every requirement ID maps to at least one test (NFR-009).
3. Each persona's core journey can be demonstrated end to end:
   - operator: overview → anomaly → chart (US-01, US-02, US-03)
   - engineer: compare sensors around an anomaly (US-04, US-05)
   - analyst: aggregates → quality → CSV export (US-07, US-08, US-09)
4. Every significant technical choice is traceable to an ADR, and every behaviour to a requirement.

## 12. Open questions

| # | Question | Default until answered |
|---|---|---|
| OQ-1 | What are realistic operating limits and valid ranges per sensor? | Plausible values for a mid-size centrifugal pump, defined in the SPEC and marked illustrative |
| OQ-2 | Are anomaly flags computed once at load time or at query time? | Decided in an ADR; behaviour is the same either way |
| OQ-3 | How long should data be retained in a real deployment? | Not applicable locally (NFR-005); noted for governance |
| OQ-4 | Should replay (FR-014) share the batch loader's code path? | Yes, so flags are identical (FR-014 criterion 3); confirmed in the ingestion ADR |
| OQ-5 | Does the assignment brief impose criteria not captured here? | None known; revisit if the brief is shared |
