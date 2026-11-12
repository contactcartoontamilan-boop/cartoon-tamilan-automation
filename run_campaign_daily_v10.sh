#!/usr/bin/env bash
# V10 daily runner. Preview ONLY by default, no Meta call unless deliberately enabled.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p logs
ARGS=(--limit "${DAILY_STORY_LIMIT:-1}" --art-mode "${ART_MODE:-cover}")
if [[ "${CAMPAIGN_V10_PUBLISH:-false}" == "true" ]]; then
  ARGS+=(--publish)
fi
echo "=== $(date -Is) V10 daily run ===" >> logs/v10-daily.log
"${PYTHON_BIN:-python3}" campaign_v10.py "${ARGS[@]}" >> logs/v10-daily.log 2>&1
