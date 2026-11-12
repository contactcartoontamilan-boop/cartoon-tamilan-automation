#!/usr/bin/env bash
# V12 safe Oracle integration: replace V10 preview service command with V12.
# Does not modify tokens, enable publishing or reinstall the server.
set -Eeuo pipefail
if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as ubuntu (not root)" >&2
  exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || { echo "Missing virtualenv. Run original Oracle V10 setup first."; exit 2; }

# Validate candidate before touching the working systemd service.
"$PY" -m compileall -q .
"$PY" -m unittest discover -s . -p 'test_*.py' -q

STATE="$HOME/.local/state/cartoontamilan"
mkdir -p "$STATE"
chmod 700 "$STATE"
LOCK="$STATE/deploy.lock"
touch "$LOCK"

mkdir -p "output/v12"
# It must run successfully once before the automated daily timer uses it.
"$PY" v12_ops.py --limit 1

OVERRIDE=/etc/systemd/system/cartoontamilan-preview-v10.service.d
sudo mkdir -p "$OVERRIDE"
sudo tee "$OVERRIDE/30-v12-manager.conf" >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/flock --shared --wait 600 $LOCK $PY $ROOT/v12_ops.py --limit 1 --seo
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now cartoontamilan-preview-v10.timer
echo "V12 daily preview installed at the existing 08:30 Asia/Kolkata time."
echo "Oracle auto-sync V11 remains unchanged; live publishing remains OFF."
echo "To test: sudo systemctl start cartoontamilan-preview-v10.service"
echo "To see results: cat $ROOT/output/v12/latest_health.json"
