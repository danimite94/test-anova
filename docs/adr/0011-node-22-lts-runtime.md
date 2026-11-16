# ADR-0011: Node 22 LTS for the frontend toolchain

- **Status:** Accepted
- **Date:** 2026-11-16
- **Supersedes:** the Node runtime line of ADR-0006 (all other ADR-0006 decisions stand)

## Context

ADR-0006 pinned the frontend toolchain to Node 20 LTS. Node 20 reached end of life in
April 2026, so it no longer receives security fixes — which conflicts with GOV-010 (pinned,
maintained supply chain). The local development machine already runs Node 22, and the current
frontend dependencies (Vite 8, Vitest 5, ESLint 10, TypeScript 6) support it.

## Decision

Use **Node 22 LTS**: `.nvmrc` = `22`, `package.json` `engines.node` = `>=22`, Docker build stage
`node:22-alpine` pinned by digest, and CI `actions/setup-node` with `node-version-file`.

## Consequences

- Supported runtime with security updates until April 2027; a further move to Node 24 LTS is a
  routine Dependabot-driven change before then.
- No code changes: Node only runs the build and test tooling; the product runs in the browser
  and nginx.

## Alternatives considered

| Option | Why not |
|---|---|
| **Stay on Node 20** | End of life; contradicts GOV-010. |
| **Node 24 LTS** | Also valid, but the dev machine runs 22 and nothing requires 24 yet. |
