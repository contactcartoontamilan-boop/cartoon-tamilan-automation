#!/data/data/com.termux/files/usr/bin/bash
# Run on Android Termux only. Pull creative previews; never store SSH keys on GitHub.
set -Eeuo pipefail
if [[ -n "${SSH_CONNECTION:-}" ]] || [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Run this on your Android Termux, NOT within an Oracle SSH session." >&2
  exit 2
fi
KEY="$HOME/.ssh/oracle_key"
if [[ ! -f "$KEY" ]]; then
  echo "SSH key missing at $KEY" >&2
  exit 2
fi
chmod 600 "$KEY"
command -v rsync >/dev/null || {
  echo "Install rsync first: pkg install rsync -y" >&2
  exit 2
}
[[ -d "$HOME/storage/pictures" ]] || {
  echo "Run termux-setup-storage on the phone first." >&2
  exit 2
}
DEST="$HOME/storage/pictures/CartoonTamilanV13"
mkdir -p "$DEST"
# Keep date/story folders. Don't overwrite private review decisions or
# delete gallery pictures; no credentials downloaded.
rsync -av --ignore-existing \
  -e "ssh -i $KEY -o IdentitiesOnly=yes" \
  --include="*/" --include="*.jpg" --include="*.png" \
  --include="*.mp4" --include="*.wav" --include="*.srt" \
  --exclude="*" \
  ubuntu@80.225.239.193:/home/ubuntu/cartoon-tamilan-automation/output/v13/ \
  "$DEST/"
echo "Phone Gallery folder: $DEST"
