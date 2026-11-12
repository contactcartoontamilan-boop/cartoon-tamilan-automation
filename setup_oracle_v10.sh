#!/usr/bin/env bash
# CartoonTamilan Oracle A1 ARM64 bootstrap (safe V10 preview only).
# Run as the ubuntu user, on the actual Oracle Ubuntu instance.
# Does NOT open network ports, accept SSH keys, or publish Facebook/Instagram posts.
set -Eeuo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as the normal ubuntu SSH user, not root." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
echo "[1/7] Installing Ubuntu Python, Git, RAQM and Tamil fonts"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git python3 python3-pip python3-venv \
  fonts-noto-core fonts-dejavu-core libraqm0

echo "[2/7] Creating project virtual environment"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "[3/7] Configuring safe preview-only local .env"
if [[ ! -e .env ]]; then
  cp .env.example .env
  chmod 600 .env
else
  echo "Existing .env was preserved. This installer never enables live publishing."
fi

echo "[4/7] Checking Tamil text shaping and available fonts"
.venv/bin/python - <<'PY'
from PIL import features
from poster_generator import find_font, latin_font
print("Pillow RAQM:", features.check("raqm"))
print("Tamil font:", find_font())
print("Latin font:", latin_font())
if not features.check("raqm"):
    raise SystemExit("Pillow RAQM unavailable; cannot make correct Tamil posters.")
PY

echo "[5/7] Compiling code and running offline regression tests"
.venv/bin/python -m compileall -q .
.venv/bin/python -m unittest \
  test_premium_v10.py test_story_context_v10.py test_campaign_v9.py \
  test_story_marketing.py test_auto_story_cover.py -v

echo "[6/7] Running first live-site story-cover PREVIEW (no social posting)"
.venv/bin/python campaign_v10.py --limit 2 --art-mode cover

echo "[7/7] Installing once-daily PREVIEW timer (never uses --publish)"
SERVICE=/etc/systemd/system/cartoontamilan-preview-v10.service
TIMER=/etc/systemd/system/cartoontamilan-preview-v10.timer
sudo tee "$SERVICE" >/dev/null <<EOF
[Unit]
Description=CartoonTamilan V10 safe campaign preview
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$(id -un)
Group=$(id -gn)
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/python $ROOT/campaign_v10.py --limit 1 --art-mode cover
TimeoutStartSec=15min
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
sudo tee "$TIMER" >/dev/null <<'EOF'
[Unit]
Description=Daily CartoonTamilan safe preview at 08:30 India time

[Timer]
OnCalendar=*-*-* 08:30:00 Asia/Kolkata
Persistent=true
Unit=cartoontamilan-preview-v10.service

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now cartoontamilan-preview-v10.timer
echo
echo "Oracle V10 preview installation completed."
echo "Project: $ROOT"
echo "Check schedule: systemctl list-timers cartoontamilan-preview-v10.timer"
echo "Review logs: sudo journalctl -u cartoontamilan-preview-v10.service -n 60 --no-pager"
echo "IMPORTANT: NO Facebook or Instagram live posts were enabled."
