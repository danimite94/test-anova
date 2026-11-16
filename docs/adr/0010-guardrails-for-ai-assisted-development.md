# ADR-0010: Layered guardrails for data and AI-assisted development

- **Status:** Accepted
- **Date:** 2026-11-16
- **Requirements:** GOV-001…GOV-017 (`docs/GOVERNANCE.md`), NFR-009, NFR-010

## Context

A large share of this project's code is written by an AI coding agent (Claude Code), directed
and reviewed by a human. Agents are fast and capable, but have known failure modes that matter
for a spec-driven, test-driven project:

- **Weakening checks to make them pass** — skipping or deleting tests, adding lint/type
  suppressions, lowering coverage thresholds.
- **Drifting from the spec** — implementing behaviour the PRD/SPEC doesn't describe, or
  changing behaviour without updating them.
- **Touching sensitive files** — `.env` files, credentials, CI and release configuration, and
  the guardrail configuration itself.
- **Committing data** — generated datasets or other large/unsafe files entering history.

Separately, the data itself needs rules: input must match a contract, results must be traceable
to their source, and raw readings must not be alterable by the application.

## Decision

Adopt the rules in `docs/GOVERNANCE.md` (GOV-001…GOV-017), enforced in layers where each
catches what earlier ones can miss:

| Layer | Mechanism |
|---|---|
| Agent rules | `CLAUDE.md` |
| Agent hooks | `.claude/settings.json` + standard-library Python scripts in `.claude/hooks/`: block protected reads/writes, new suppressions and risky git commands; format/lint each edited file; run fast tests before the agent stops |
| pre-commit | ruff, mypy, ESLint/Prettier/tsc, gitleaks, large-file and data-file checks, `.env` check, suppression check, no commits to `main` |
| CI | Re-runs every pre-commit hook on all files, plus gitleaks over full history, threshold floors, action pinning, workflow permissions, requirement coverage |
| Database privileges | Backend connects as `telemetry_app` (`SELECT`; `INSERT` on `reading`/`dataset`); only `init` holds the owner role |
| Human review | Branch protection on `main`, `CODEOWNERS` on protected paths, PR template checklist |

Every rule enforced by a bypassable layer (agent rules, hooks, pre-commit) is also enforced by a
non-bypassable one (CI, database privileges, review). Hook scripts and their settings are
themselves protected paths.

This ADR also adds the two-role database setup to the containerization design of ADR-0008
(SPEC §8), without changing that ADR's other decisions.

## Consequences

**Positive**

- Mistakes surface at the earliest point: on the agent's next tool call, at commit, or in CI.
- Green checks stay meaningful: weakening them needs a visible, justified, human-approved change.
- Guardrails are demonstrable — `scripts/governance/demo.sh` shows each layer rejecting a bad change.
- Data rules (contract, lineage, immutability) are testable requirements, not conventions.

**Negative**

- Hooks are pattern-based and can be evaded by indirect commands; CI and review remain the
  backstops, and that is documented rather than hidden.
- Protected paths slow down legitimate tooling changes: the agent must propose them and a human
  must apply them.
- More moving parts in the repository: hook scripts, governance scripts and their tests.

## Alternatives considered

| Option | Why not |
|---|---|
| **Human review only** | Doesn't scale to agent output volume; easy to miss a quietly skipped test. |
| **CI only** | Authoritative but slow feedback; the agent learns about violations minutes later instead of immediately. |
| **No AI-specific rules** (treat the agent like any contributor) | Misses failure modes specific to agents, such as optimising for green checks. |
| **Agent sandbox without hooks** (deny-list in permissions only) | Permissions can block tools and paths but cannot inspect content (e.g. a new `# noqa`) or run checks after edits. |
| **Application-level immutability only** (no DB roles) | One buggy or injected query could still alter evidence; privileges make it impossible rather than unlikely. |
