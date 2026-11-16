#!/usr/bin/env bash
# Stop: run the fast test suite before the agent finishes, if code changed (GOV-015).
# Exit 2 sends the failures back so the agent keeps working; a second consecutive
# block is skipped (stop_hook_active) so the agent can never loop forever.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
active=$(python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("stop_hook_active", False)).lower())' 2>/dev/null || echo false)
[ "$active" = "true" ] && exit 0

cd "$root" || exit 0
if [ -z "$(git status --porcelain -- backend frontend 2>/dev/null)" ]; then
  exit 0
fi

if ! out=$(make -s test-fast 2>&1); then
  echo "Fast tests fail (GOV-015). Fix them before finishing:" >&2
  echo "$out" | tail -60 >&2
  exit 2
fi
exit 0
