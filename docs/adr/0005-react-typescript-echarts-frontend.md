# ADR-0005: React + TypeScript frontend with ECharts and client-side downsampling

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** FR-003…FR-013, NFR-004, NFR-008, NFR-012

## Context

The frontend has five views (SPEC §7.1) with URL-driven state, and its charts must:

- draw up to 5 sensors × 10,080 points ≈ **50k points** and stay responsive (NFR-004),
- break lines at gaps and shade dropouts (FR-007),
- overlay limit lines and anomaly markers (FR-008, FR-009),
- share zoom across stacked panels in the compare view (FR-005).

The frontend may be non-Python. A clear split between frontend and API is part of what the
take-home demonstrates.

## Decision

- **React 18 + TypeScript (strict)**, built with **Vite**, as a single-page app.
- **Apache ECharts** for charts (canvas rendering; `dataZoom`, `markLine`, `markArea`,
  `markPoint`, connected charts).
- **TanStack Query** for API calls and caching; **React Router** for URL state.
- **Downsampling on the client** with ECharts' built-in `sampling: 'lttb'`. The API always
  returns full-resolution points (SPEC §6.6).
- Built to static files and served by **nginx**, which also proxies `/api/*` to the backend
  (ADR-0008) — the browser sees one origin, so no CORS configuration.

## Consequences

**Positive**

- Canvas rendering handles 50k points comfortably; LTTB keeps spikes visible at full-week
  zoom and shows every point when zoomed in.
- Gaps, limits, anomalies and linked zoom are all built-in ECharts features — no custom
  drawing code.
- Typed API client models can be generated from the backend's OpenAPI document, keeping
  frontend and backend in sync.
- The frontend is independently testable (Vitest + Playwright, ADR-0007).

**Negative**

- Two toolchains (Python and Node) in the repo and in CI.
- ~400 KB gzipped payload for the largest view; fine on a local network, would need
  server-side downsampling for remote users or longer ranges (SPEC §11).
- ECharts' option-object API is verbose; chart configuration lives in small, unit-tested
  builder functions rather than inline in components.

## Alternatives considered

| Option | Why not |
|---|---|
| **Streamlit** | Fastest to build, all Python, but reruns the whole script per interaction, limited control over URL state and linked charts, and no clean API boundary to show. |
| **Plotly Dash** | Better interactivity than Streamlit and still Python, but the frontend is coupled to the Python server and harder to test as a separate client. |
| **Recharts** | Idiomatic in React but SVG-based; noticeably slow beyond ~10k points. |
| **uPlot** | Extremely fast, but fewer built-in features (annotations, linked zoom need custom code). |
| **Server-side LTTB in the API** | Smaller payloads, but extra API parameters and code for no benefit at 50k points. Revisit if ranges or sensor counts grow 10×+. |
| **Grafana** | Great for operations dashboards, but configuring it isn't building the product the assignment asks for. |
