#!/usr/bin/env bash
# One-time installer: enable safe GitHub -> Oracle auto-updates.
# This configures a five-minute polling timer and protects the V10 preview
# against concurrent Git deployments. Does NOT publish social posts.
set -Eeuo pipefail

if [[ "${EUID}" == "0" ]]; then
  echo "Run as ubuntu, NOT root" >&2
  exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

[[ -x "$ROOT/.venv/bin/python" ]] || {
  echo "Project venv missing: run bash setup_oracle_v10.sh first." >&2
  exit 1
}

STATE="$HOME/.local/state/cartoontamilan"
mkdir -p "$STATE"
chmod 700 "$STATE"

SERVICE=/etc/systemd/system/cartoontamilan-autosync-v11.service
TIMER=/etc/systemd/system/cartoontamilan-autosync-v11.timer
sudo tee "$SERVICE" >/dev/null <<EOF
[Unit]
Description=CartoonTamilan GitHub main to Oracle validated auto-sync
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$(id -un)
Group=$(id -gn)
WorkingDirectory=$ROOT
ExecStart=/usr/bin/bash $ROOT/oracle_autosync_v11.sh
TimeoutStartSec=15min
NoNewPrivileges=true
PrivateTmp=true
EOF

sudo tee "$TIMER" >/dev/null <<'EOF'
[Unit]
Description=Check CartoonTamilan GitHub code every five minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=15s
Unit=cartoontamilan-autosync-v11.service

[Install]
WantedBy=timers.target
EOF

# The PREVIEW uses the same shared lock as the autosync exclusive lock.
# Other publisher scripts are NOT automatically enabled.
override=/etc/systemd/system/cartoontamilan-preview-v10.service.d
sudo mkdir -p "$override"
sudo tee "$override/20-autosync-lock.conf" >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/flock --shared --wait 600 $STATE/deploy.lock $ROOT/.venv/bin/python $ROOT/campaign_v10.py --limit 1 --art-mode cover
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cartoontamilan-autosync-v11.timer

echo "GitHub->Oracle auto-sync timer installed (approximately every 5 min)."
echo "Old V10 daily preview remains at 08:30 Asia/Kolkata; live publishing remains OFF."
echo "Check status:"
echo "  systemctl list-timers --all cartoontamilan-autosync-v11.timer"
echo "  sudo systemctl start cartoontamilan-autosync-v11.service"
echo "  tail -n 40 $STATE/autosync.log"
