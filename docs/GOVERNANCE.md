# Data & AI Governance

| | |
|---|---|
| Status | Accepted |
| Phase | 2 · Engineering foundation |
| Related | `docs/PRD.md` §8, ADR-0010, `CLAUDE.md` |

This document lists the rules for how data is handled and how code — much of it written by an
AI coding agent — gets into the repository. Each rule has an ID (`GOV-xxx`), a reason, and the
points where it is **enforced**. Rules are tested like any other requirement (ADR-0007).

## Scope

- **In scope**: the synthetic dataset and how it is stored, secrets and supply chain, and
  AI-assisted development of this repository.
- **Not in scope**: AI features in the product. The product has none; adding one (e.g. an
  LLM that explains anomalies) requires a new ADR and its own governance rules first.

## Enforcement layers

Each layer catches what earlier ones can miss. Only CI and review cannot be bypassed locally.

| Layer | Where | Applies to | Feedback | Can be bypassed? |
|---|---|---|---|---|
| **Agent rules** | `CLAUDE.md` | The agent | — | Yes (advisory) |
| **Agent hooks** | `.claude/settings.json` + `.claude/hooks/` | The agent, per tool call | Instant | Only by editing protected files — which the hooks block |
| **pre-commit** | `.pre-commit-config.yaml` | Anyone committing | Seconds | Yes (`--no-verify`, not installing) |
| **CI** | `.github/workflows/` | Every PR and push | Minutes | No — required checks |
| **Database privileges** | PostgreSQL roles | Running code | Runtime error | No (from the app) |
| **Human review** | Pull requests, `CODEOWNERS` | Every change | Hours | No — branch protection |

## Rules

Legend for enforcement columns: **H** agent hook · **P** pre-commit · **C** CI · **D** database
privileges · **R** human review.

### Data

| ID | Rule | Why | Enforced by |
|---|---|---|---|
| **GOV-001** | Only synthetic data. All readings come from the seeded generator; no real plant data enters the repository, images or database. | No confidentiality or licensing exposure; results are reproducible. | R (only data source in code); C (GOV-002 check) |
| **GOV-002** | No data files committed. `data/` is git-ignored; files with data extensions (`.csv`, `.parquet`, `.jsonl`, `.sqlite`, `.db`, `.dump`, `.xlsx`) are rejected outside `backend/tests/fixtures/`; any added file > 500 KB is rejected. | Keeps the repo small, and data out of history where it can't be removed. | P (`check-added-large-files`, `forbid-data-files`); C (same hooks, all files) |
| **GOV-003** | Data contract validated at ingestion. Before classification, every record must have a known `sensor_id`, an ISO 8601 `ts` with offset, at whole-minute resolution, inside the dataset period, and a finite numeric `value`. A batch with any contract violation is **rejected whole** with an error naming the record (`seq`) and the rule. Contract violations are distinct from quality flags: flags describe well-formed readings with doubtful values. | Malformed input must fail loudly, never be stored or silently dropped (PRD FR-002). | Code + tests tagged `GOV-003`; C |
| **GOV-004** | Lineage. Every load records seed, generator version, file SHA-256, load mode, load time and flag counts; every reading references its dataset. `GET /dataset` exposes it, and CSV exports carry `X-Dataset-Sha256` and `X-Generator-Version` response headers. | Any number shown or exported can be traced to the exact input that produced it. | Code + tests; C |
| **GOV-005** | Raw readings are immutable to the application. The backend connects as role `telemetry_app` with `SELECT` on all tables and `INSERT` on `reading` and `dataset` only. Only the `init` job (owner role) can migrate or replace a dataset. | A bug or injected SQL in the API cannot alter or delete evidence. | D; integration test asserting `UPDATE`/`DELETE` fail for `telemetry_app` |
| **GOV-006** | Retention. Locally, data lives as long as the `pgdata` volume; `make reset` is the only deletion path; generated files exist only inside the `init` container. A real deployment must define retention before go-live (PRD OQ-3). | Predictable data lifecycle; no stray copies. | R; NFR-005 test |

### Secrets and supply chain

| ID | Rule | Why | Enforced by |
|---|---|---|---|
| **GOV-007** | No credentials in source, history, images or logs. Configuration comes from environment variables. | Leaked credentials are the most common, most costly repository incident. | P (gitleaks on staged changes); C (gitleaks on full history) |
| **GOV-008** | `.env` files are never committed and never read by the agent. Only `.env.example` is tracked, with local-only placeholder values. | Keeps real values out of git and out of model context. | H (block read/write of `.env*` except `.env.example`); P (`forbid-env-files`); `.gitignore` |
| **GOV-009** | Least-privilege CI. Workflows default to `permissions: contents: read`; only the release job gets `packages: write`; no long-lived secrets — the built-in `GITHUB_TOKEN` only. | Limits damage from a compromised dependency or action. | C (workflow lint script); R |
| **GOV-010** | Pinned supply chain. Lockfiles committed (`uv.lock`, `package-lock.json`); GitHub Actions pinned to full commit SHAs; base images pinned by digest; Dependabot proposes updates weekly. | Builds are reproducible and updates arrive as reviewable PRs, not silently. | C (pin check script); Dependabot; R |

### AI-assisted development

| ID | Rule | Why | Enforced by |
|---|---|---|---|
| **GOV-011** | Spec first. A behaviour change updates `docs/PRD.md` / `docs/SPEC.md` (and adds an ADR if a decision changes) in the same PR, before or with the code; new tests carry requirement IDs. | The specs stay the source of truth (CLAUDE.md workflow). | R (PR template checklist); C (requirement coverage, GOV-016) |
| **GOV-012** | Checks are never weakened to pass. New suppressions — `# noqa`, `# type: ignore`, `# pragma: no cover`, `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `pytest.mark.skip`/`skipif`/`xfail`, `test.skip`/`.only` — require a same-line `justified: <reason>` and human approval. Quality thresholds (coverage ≥ 85%, `mypy --strict`, ruff rule set, `tsc --strict`) have floors that cannot be lowered. | Agents optimise for green checks; this keeps green meaningful. | H (blocks any new suppression by the agent); P + C (`check-suppressions`: no unjustified suppressions); C (`check-thresholds`: floors) |
| **GOV-013** | Protected paths change only by a human. Agent edits are blocked for: `.env*` (except `.env.example`), `.claude/`, `.github/`, `.pre-commit-config.yaml`, `scripts/governance/`, `CODEOWNERS`, tool configuration (`[tool.ruff]`, `[tool.mypy]`, `[tool.pytest…]`, `[tool.coverage…]` in `pyproject.toml`; `eslint.config.js`, `tsconfig*.json`), and accepted ADRs. The agent proposes the change; a human applies it. | The rules can't be edited by the party they constrain. | H; R (`CODEOWNERS` requires owner review) |
| **GOV-014** | All changes reach `main` through a reviewed PR. The agent never pushes to `main`, force-pushes, merges PRs, skips hooks (`--no-verify`), or uninstalls/redirects git hooks. | A human approves everything that ships. | H (Bash guard); P (`no-commit-to-branch`); branch protection |
| **GOV-015** | Agent output is checked continuously. Every file the agent writes is formatted and linted immediately; the fast test suite runs before the agent finishes a turn, and failures are fed back to it. | Problems are fixed in seconds, not discovered in CI. | H (PostToolUse, Stop) |
| **GOV-016** | Traceability. Every FR, NFR and GOV ID has at least one test referencing it. CI fails on any missing *Must* FR, NFR or GOV ID; *Should*/*Could* gaps are warnings. | Proves each requirement is covered (NFR-009). | C (`req-coverage`) |
| **GOV-017** | Attribution. Commits with agent-written content carry a `Co-Authored-By` trailer; PR descriptions state AI assistance. | Reviewers know where to look harder; history is honest. | R |

## Agent hook design

All hooks are committed in `.claude/settings.json` (project scope) and implemented as small
Python scripts in `.claude/hooks/` using only the standard library (they run before any
virtualenv exists). Each reads the hook event JSON from stdin.

| Event | Matcher | Script | Behaviour |
|---|---|---|---|
| `PreToolUse` | `Read` | `guard_paths.py` | Block reading `.env*` (except `.env.example`). |
| `PreToolUse` | `Edit\|Write\|MultiEdit\|NotebookEdit` | `guard_paths.py` | Block writes to protected paths (GOV-008, GOV-013), including accepted ADRs (detected by their `Status: Accepted` line). Block content that adds suppressions (GOV-012): compare suppression-token counts in new vs old text. |
| `PreToolUse` | `Bash` | `guard_bash.py` | Block `--no-verify`, `git push` to `main`, force pushes, `gh pr merge`, `git config core.hooksPath`, `pre-commit uninstall`, and commands that read or write `.env*` or redirect into protected paths (GOV-008, GOV-013, GOV-014). |
| `PostToolUse` | `Edit\|Write\|MultiEdit` | `post_edit.sh` | `.py`: `ruff format` + `ruff check --fix` on the file. `.ts/.tsx`: `prettier --write` + `eslint --fix`. Remaining errors are returned to the agent (exit 2) to fix now (GOV-015). |
| `Stop` | — | `stop_tests.sh` | If code changed since the last commit, run the fast suite (`make test-fast`: unit tests, < 10 s). On failure, return the output (exit 2) so the agent keeps working. If `stop_hook_active` is already true, report without blocking again, to avoid loops (GOV-015). |

A blocked action exits with code 2 and a message naming the rule, for example:
`Blocked by GOV-013: .github/ is a protected path. Propose the change to the user instead.`

**Known limits.** Bash guarding is pattern-based; a sufficiently indirect command (a script
that writes a file) can get past it. That is why every rule enforced by a hook is also
enforced in CI or by review, and why hook scripts and settings are themselves protected.

## Spec changes made with this document

- **SPEC §4** — contract validation before classification (GOV-003).
- **SPEC §6.11** — lineage headers on CSV exports (GOV-004).
- **SPEC §8** — two database roles: owner for `init`, `telemetry_app` for the backend (GOV-005).
  Recorded in ADR-0010 rather than by editing the accepted ADR-0008.
- **PRD §8** — summary of and pointer to this document.
- **ADR-0010** — Accepted.

## Verification

Each GOV rule gets tests in Phase 2 or Phase 3 (data rules need the loader). The guardrails
themselves are proven with a scripted demonstration (`scripts/governance/demo.sh`) that
attempts, on a throwaway branch: a lint error, a fake secret, a `.env` file, a new `# noqa`,
and a lowered coverage threshold — and records each layer rejecting it.
