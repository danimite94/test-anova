# ADR-0010: Guardrails for AI-assisted development

- **Status:** Proposed — to be detailed and accepted in Phase 2 (`docs/GOVERNANCE.md`)
- **Date:** 2026-11-16
- **Requirements:** NFR-009, NFR-010; PRD §8 (Data & AI governance, TBD)

## Context

A large share of this project's code will be written by an AI coding agent (Claude Code),
directed and reviewed by a human. Agents are fast and capable, but have known failure modes
that matter for a spec-driven, test-driven project:

- **Weakening checks to make them pass** — skipping or deleting tests, adding lint/type
  suppressions, lowering coverage thresholds.
- **Drifting from the spec** — implementing behaviour the PRD/SPEC doesn't describe, or
  changing behaviour without updating them.
- **Touching sensitive files** — `.env` files, credentials, CI and release configuration.
- **Committing data** — generated datasets or other large/unsafe files entering the repository.

The project already has natural enforcement points: lint/type/test tooling (ADR-0006,
ADR-0007), CI with required checks (ADR-0009), and pull-request review.

## Proposed direction

Layered guardrails, each catching what the previous one can miss:

| Layer | Applies to | Purpose |
|---|---|---|
| **`CLAUDE.md` rules** | The agent | States the workflow (spec first, TDD, requirement IDs) and what not to do |
| **Claude Code hooks** (`.claude/settings.json`) | The agent, as it works | Block edits to protected files; format/lint each changed file; run fast tests before finishing |
| **pre-commit hooks** | Anyone committing locally | Lint, format, secret scanning, large-file check, no direct commits to `main` |
| **CI required checks** | Every change, no bypass | The authoritative repeat of all the above, plus requirement coverage |
| **Human PR review** | Every change | Judgment: does the change match the spec and the intent? |

Rules in the earlier layers are advisory or bypassable (`--no-verify`, editing settings);
CI and review are the backstops.

## To be decided in Phase 2

- The concrete rule list with `GOV-xxx` IDs and the enforcement point for each.
- Which files are protected, and how "weakening a check" is detected.
- Data governance rules: synthetic-only data, lineage, retention, secrets handling.
- How evidence is produced that each guardrail actually rejects a bad change.

## Alternatives considered (preliminary)

| Option | Why not (so far) |
|---|---|
| **Human review only** | Doesn't scale to agent output volume; easy to miss a quietly skipped test. |
| **CI only** | Authoritative but slow feedback; the agent learns about violations minutes later instead of immediately. |
| **No AI-specific rules** (treat the agent like any contributor) | Misses failure modes specific to agents, such as optimising for green checks. |
