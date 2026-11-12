#!/usr/bin/env bash
# CartoonTamilan V13 all-in-one safe daily preview installer for OCI Ubuntu ARM64.
# NOTHING here changes Meta/SMTP credentials or turns live social publishing on.
set -Eeuo pipefail
if [[ "${EUID}" == 0 ]]; then
  echo "Run as the ubuntu SSH user, not root." >&2
  exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || {
  echo "Python virtualenv is missing; install V10 on this Oracle instance first."
  exit 2
}

echo "[1/5] Install CPU video/audio and Tamil-font dependencies"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ffmpeg espeak-ng rsync fonts-noto-core libraqm0

echo "[2/5] Verify all repository tests, original Tamil font and Pillow RAQM"
"$PY" -m compileall -q .
"$PY" -m unittest discover -s . -p 'test_*.py' -q
"$PY" - <<'PY'
from PIL import features
from poster_generator import find_font
if not features.check('raqm'):
    raise SystemExit("Pillow RAQM unavailable")
print("Tamil font:", find_font())
PY

echo "[3/5] Test one COMPLETE V13 creative bundle without sending posts"
"$PY" ct_master.py campaign --limit 1 --video --voice
"$PY" ct_master.py status

echo "[4/5] Set V11 GitHub auto-sync (every ~5 min) if not installed"
# Existing V11 installer protects code rollout and uses the V10 preview lock.
if [[ -f /etc/systemd/system/cartoontamilan-autosync-v11.timer ]]; then
  echo "V11 GitHub update timer already installed; preserving it."
else
  bash "$ROOT/setup_oracle_autosync_v11.sh"
fi

echo "[5/5] Make existing daily 08:30 IST preview use V13 instead of V10/V12"
STATE="$HOME/.local/state/cartoontamilan"
mkdir -p "$STATE"
chmod 700 "$STATE"
touch "$STATE/deploy.lock"
sudo mkdir -p /etc/systemd/system/cartoontamilan-preview-v10.service.d
sudo tee /etc/systemd/system/cartoontamilan-preview-v10.service.d/40-v13-marketing-os.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/flock --shared --wait 600 $STATE/deploy.lock $PY $ROOT/ct_master.py campaign --limit 1 --video --voice
TimeoutStartSec=40min
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cartoontamilan-preview-v10.timer
echo "V13 daily draft generation enabled at existing 08:30 IST."
echo "V11 GitHub auto-sync is independent; live Facebook, Instagram and email remain OFF."
echo "Test: sudo systemctl start cartoontamilan-preview-v10.service"
echo "Log: sudo journalctl -u cartoontamilan-preview-v10.service -n 50 --no-pager"
echo "Output: $ROOT/output/v13"
