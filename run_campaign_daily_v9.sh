#!/usr/bin/env bash
# CartoonTamilan V9 daily job. Safe gates live inside campaign_v9.py.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p logs
echo "=== $(date -Is) starting daily campaign ===" >> logs/campaign_v9.log
"${PYTHON_BIN:-python3}" campaign_v9.py --limit 1 --publish >> logs/campaign_v9.log 2>&1
echo "=== $(date -Is) completed ===" >> logs/campaign_v9.log
