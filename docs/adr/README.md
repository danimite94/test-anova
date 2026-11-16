# Architecture Decision Records

Each ADR records one significant decision in the Nygard format: Status, Context, Decision,
Consequences, plus Alternatives considered. ADRs are not edited after acceptance; a changed
decision gets a new ADR that supersedes the old one.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-postgresql-for-time-series-storage.md) | PostgreSQL for time-series storage | Accepted |
| [0002](0002-long-format-schema-with-query-time-derivations.md) | Long-format schema, immutable readings, derived data at query time | Accepted |
| [0003](0003-batch-load-with-optional-replay.md) | Batch load at startup, optional replay through the same classifier | Accepted |
| [0004](0004-fastapi-rest-with-plain-sql.md) | FastAPI REST backend with hand-written SQL | Accepted |
| [0005](0005-react-typescript-echarts-frontend.md) | React + TypeScript frontend with ECharts and client-side downsampling | Accepted |
| [0006](0006-monorepo-layout-and-tooling.md) | Monorepo layout and tooling | Accepted |
| [0007](0007-testing-strategy-tdd-and-traceability.md) | Testing strategy — TDD, real-database tests, requirement traceability | Accepted |
| [0008](0008-docker-compose-containerization.md) | Containerization with Docker Compose | Accepted |
| [0009](0009-github-actions-ci-cd.md) | CI/CD with GitHub Actions; "deploy" means publishing versioned images | Accepted |
| [0010](0010-guardrails-for-ai-assisted-development.md) | Layered guardrails for data and AI-assisted development | Accepted |
