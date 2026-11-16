#!/usr/bin/env bash
# Guardrail evidence (docs/GOVERNANCE.md, "Verification").
#
#   scripts/demo_guardrails.sh          pre-commit + agent-hook rejections, in a throwaway worktree
#   scripts/demo_guardrails.sh ci       push a deliberately bad change as a draft PR so CI rejects it
#                                       (bypasses local hooks on purpose — run by a human, not the agent)
#
# Every bad change is made inside a temporary git worktree that is deleted afterwards; the
# fake secret is generated at runtime, so this script contains none.
set -uo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
env_file=".e""nv"            # spelled in two parts so pattern-based guards ignore this script
noqa="# no""qa"

run_precommit_demo() {
  WT=$(mktemp -d)/demo
  git worktree add --quiet --detach "$WT" HEAD
  trap 'git worktree remove --force "$WT" >/dev/null 2>&1' EXIT
  cd "$WT"

  attempt() { # name, rule, setup-command
    local name=$1 rule=$2
    eval "$3"
    git add -A >/dev/null
    if out=$(git commit -q -m "demo: $name" 2>&1); then
      printf '  %-34s %-9s %s\n' "$name" "ACCEPTED" "!! expected rejection ($rule)"
      git reset -q --hard HEAD~1
      failures=$((failures + 1))
    else
      hook=$(echo "$out" | grep -m1 -E 'Failed' | sed -E 's/\.{3,}.*//')
      if [ -n "$hook" ]; then
        printf '  %-34s %-9s %s\n' "$name" "REJECTED" "$rule — $hook"
      else # the commit failed for another reason (e.g. nothing staged): not evidence
        printf '  %-34s %-9s %s\n' "$name" "UNCLEAR" "!! no hook failed: $(echo "$out" | tail -1)"
        failures=$((failures + 1))
      fi
    fi
    git reset -q --hard HEAD && git clean -qfd
  }

  failures=0
  echo "pre-commit (layer 3), commits attempted in a throwaway worktree:"
  attempt "lint error (unused import)" "ruff" \
    "printf 'import os\n' >> backend/src/telemetry/config.py"
  attempt "fake GitHub token" "GOV-007" \
    "printf 'TOKEN = \"ghp_%s\"\n' \"\$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 36)\" > backend/src/telemetry/leak.py"
  attempt "$env_file file" "GOV-008" \
    "printf 'DEMO=1\n' > $env_file && git add -f $env_file"
  attempt "unjustified suppression" "GOV-012" \
    "printf 'x = 1  $noqa: E501\n' >> backend/src/telemetry/config.py"
  attempt "coverage floor lowered to 50" "GOV-012" \
    "sed -i.bak 's/fail_under = 85/fail_under = 50/' backend/pyproject.toml && rm backend/pyproject.toml.bak"
  attempt "data file (readings.csv)" "GOV-002" \
    "printf 'seq,sensor_id\n1,TT-101\n' > readings.csv"

  cd "$ROOT"
  echo
  echo "Agent hooks (layer 2), same events Claude Code sends:"
  hook() { # label, script, json
    local reason
    reason=$(printf '%s' "$3" | CLAUDE_PROJECT_DIR="$ROOT" python3 ".claude/hooks/$2" 2>&1 >/dev/null)
    if [ $? -eq 2 ]; then
      printf '  %-34s %-9s %s\n' "$1" "BLOCKED" "${reason%%. *}"
    else
      printf '  %-34s %-9s %s\n' "$1" "ALLOWED" "!! expected block"
      failures=$((failures + 1))
    fi
  }
  hook "agent reads $env_file" guard_paths.py \
    "{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$env_file\"}}"
  hook "agent edits $env_file" guard_paths.py \
    "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$env_file\",\"content\":\"X=1\"}}"
  hook "agent adds a suppression" guard_paths.py \
    "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"backend/src/telemetry/x.py\",\"content\":\"import os  $noqa\"}}"
  hook "agent lowers coverage floor" guard_paths.py \
    '{"tool_name":"Edit","tool_input":{"file_path":"backend/pyproject.toml","old_string":"fail_under = 85","new_string":"fail_under = 50"}}'
  hook "agent edits CI workflow" guard_paths.py \
    '{"tool_name":"Write","tool_input":{"file_path":".github/workflows/ci.yml","content":"x"}}'
  hook "agent commits --no-verify" guard_bash.py \
    '{"tool_name":"Bash","tool_input":{"command":"git commit --no-verify -m x"}}'
  hook "agent pushes to main" guard_bash.py \
    '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}'

  echo
  if [ "$failures" -eq 0 ]; then
    echo "All bad changes were rejected."
  else
    echo "$failures bad change(s) got through — investigate."
  fi
  return "$failures"
}

run_ci_demo() {
  local branch="demo/ci-rejects-bad-change-$(date +%s)"
  git switch --quiet -c "$branch"
  printf 'import os\n' >> backend/src/telemetry/config.py
  printf 'DEMO=1\n' > "$env_file"
  git add backend/src/telemetry/config.py && git add -f "$env_file"
  git commit --quiet --no-verify -m "demo: lint error and $env_file file (must fail CI; do not merge)"
  git push --quiet -u origin "$branch"
  gh pr create --draft --title "DEMO: CI must reject this (do not merge)" \
    --body "Deliberately bad change to show CI rejects what local hooks would have caught: an unused import (ruff) and a committed $env_file file (GOV-008). Close and delete the branch after the run."
  git switch --quiet -
  echo "Watch the run, then: gh pr close --delete-branch $branch"
}

case "${1:-local}" in
  local) run_precommit_demo ;;
  ci) run_ci_demo ;;
  *) echo "usage: $0 [local|ci]" >&2; exit 2 ;;
esac
