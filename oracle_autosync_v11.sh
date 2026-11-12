#!/usr/bin/env bash
# Oracle V11 safe polling deploy: GitHub main -> checked Oracle working tree.
# Nothing outside tracked Git files is deleted; private .env and runtime data stay.
# On failed validation, no merge is performed.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE="$HOME/.local/state/cartoontamilan"
mkdir -p "$STATE"
exec 9>"$STATE/deploy.lock"
if ! flock --exclusive --wait 300 9; then
  echo "Auto-sync: another deployment or preview is still using the lock." >&2
  exit 1
fi
exec >> "$STATE/autosync.log" 2>&1
echo
echo "=== $(date -u +'%Y-%m-%dT%H:%M:%SZ') GitHub → Oracle update check ==="
cd "$ROOT"

if [[ "$(git rev-parse --show-toplevel)" != "$ROOT" ]]; then
  echo "ERROR: Unexpected repository directory. Nothing changed."
  exit 1
fi
if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "ERROR: Expected main branch; refusing to update a different branch."
  exit 1
fi

origin="$(git remote get-url origin)"
case "$origin" in
  https://github.com/contactcartoontamilan-boop/cartoon-tamilan-automation|\
  https://github.com/contactcartoontamilan-boop/cartoon-tamilan-automation.git|\
  git@github.com:contactcartoontamilan-boop/cartoon-tamilan-automation.git)
    ;;
  *)
    echo "ERROR: Origin remote unexpected: $origin"
    exit 1
    ;;
esac

# Never overwrite locally edited tracked files; this also prevents wiping
# customized configuration that somebody accidentally committed to tracking.
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "BLOCKED: local tracked modifications exist. No checkout or cleanup done."
  git status --short --untracked-files=no
  exit 1
fi

git fetch --no-tags --prune origin main
old="$(git rev-parse HEAD)"
new="$(git rev-parse refs/remotes/origin/main)"
if [[ "$old" == "$new" ]]; then
  echo "Already up to date: $old"
  exit 0
fi
if ! git merge-base --is-ancestor "$old" "$new"; then
  echo "BLOCKED: remote main is not a fast-forward. Manual review required."
  exit 1
fi

# Dependency changes need an independently tested venv before rollout.
# Never risk breaking the working Oracle Python environment automatically.
if ! git diff --quiet "$old" "$new" -- requirements.txt; then
  echo "BLOCKED: requirements.txt changed; manual dependency review/reinstall required."
  echo "Local commit kept: $old; remote commit: $new"
  exit 1
fi
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "BLOCKED: Python venv missing. Re-run Oracle bootstrap first."
  exit 1
fi

workdir="$(mktemp -d "$STATE/stage.XXXXXXXX")"
staged="$workdir/source"
cleanup() {
  if [[ -d "$staged" ]]; then
    git worktree remove --force "$staged" >/dev/null 2>&1 || true
  fi
  # Delete only this script's own temporary staging directory.
  if [[ -n "$workdir" && "$workdir" == "$STATE"/stage.* ]]; then
    rm -rf -- "$workdir"
  fi
}
trap cleanup EXIT
git worktree add --quiet --detach "$staged" "$new"

echo "Validating candidate: $old → $new"
(
  cd "$staged"
  export PYTHONDONTWRITEBYTECODE=1
  "$ROOT/.venv/bin/python" -m compileall -q .
  # Full regression tests from the staged commit; validation failure leaves
  # the current live version untouched.
  timeout 240 "$ROOT/.venv/bin/python" -m unittest discover -s . -p 'test_*.py' -q
)

# Tests passed; deploy only committed GitHub changes. Git itself removes files
# that were explicitly deleted from the upstream branch.
git merge --ff-only --no-edit "$new"
printf '%s\n' "$new" > "$STATE/last_success_sha"
echo "DEPLOYED: $new"
echo "Tracked files removed by the GitHub change (if any):"
git diff --name-only --diff-filter=D "$old" "$new" || true
echo "Private tokens, approvals, outputs and untracked files were not deleted."
