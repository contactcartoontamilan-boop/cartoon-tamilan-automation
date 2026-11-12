#!/usr/bin/env bash
# CartoonTamilan V10 daily runner. Preview by default.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p logs
PYTHON="${PYTHON_BIN:-python3}"
# Read only named settings via python-dotenv; do NOT 'source .env' as shell code.
mapfile -t settings < <("$PYTHON" - <<'PY'
import os
from dotenv import load_dotenv
load_dotenv()
print(os.getenv("DAILY_STORY_LIMIT", "1"))
print(os.getenv("ART_MODE", "cover"))
print(os.getenv("CAMPAIGN_V10_PUBLISH", "false").lower())
PY
)
ARGS=(--limit "${settings[0]}" --art-mode "${settings[1]}")
if [[ "${settings[2]}" == "true" ]]; then
  ARGS+=(--publish)
fi
echo "=== $(date -Is) V10 daily run ===" >> logs/v10-daily.log
"$PYTHON" campaign_v10.py "${ARGS[@]}" >> logs/v10-daily.log 2>&1
