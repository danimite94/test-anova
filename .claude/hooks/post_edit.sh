#!/usr/bin/env bash
# PostToolUse (Edit|Write|MultiEdit): format and lint the changed file at once (GOV-015).
# Remaining problems go back to the agent (exit 2) so it fixes them now, not in CI.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
file=$(python3 -c 'import json,sys; e=json.load(sys.stdin); i=e.get("tool_input") or {}; print(i.get("file_path") or "")')
[ -n "$file" ] && [ -f "$file" ] || exit 0
case "$file" in /*) ;; *) file="$root/$file" ;; esac

case "$file" in
  "$root"/backend/*.py|"$root"/scripts/*.py|"$root"/.claude/hooks/*.py)
    cfg="$root/backend/pyproject.toml"
    out=$(uv --directory "$root/backend" run --quiet ruff check --fix --config "$cfg" "$file" 2>&1)
    status=$?
    uv --directory "$root/backend" run --quiet ruff format --config "$cfg" "$file" >/dev/null 2>&1
    if [ $status -ne 0 ]; then
      echo "ruff found problems in $file (GOV-015):" >&2
      echo "$out" | tail -40 >&2
      exit 2
    fi
    ;;
  "$root"/frontend/*.ts|"$root"/frontend/*.tsx)
    cd "$root/frontend" || exit 0
    npx --no-install prettier --write "$file" >/dev/null 2>&1
    if ! out=$(npx --no-install eslint --fix --max-warnings 0 "$file" 2>&1); then
      echo "eslint found problems in $file (GOV-015):" >&2
      echo "$out" | tail -40 >&2
      exit 2
    fi
    ;;
  "$root"/frontend/*.css|"$root"/frontend/*.json|"$root"/frontend/*.html)
    cd "$root/frontend" && npx --no-install prettier --write "$file" >/dev/null 2>&1
    ;;
esac
exit 0
