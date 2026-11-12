#!/data/data/com.termux/files/usr/bin/bash
# Android Termux only: safely pull V14 draft images, audio, SRT and MP4.
# Never uploads content, overwrites an existing gallery file, or deletes photos.
set -Eeuo pipefail
if [[ -n "$(printenv SSH_CONNECTION || true)" ]] || [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Run this on Android Termux after EXIT from Oracle SSH." >&2
  exit 2
fi
KEY="$HOME/.ssh/oracle_key"
[[ -f "$KEY" ]] || { echo "Missing private SSH key on phone" >&2; exit 2; }
chmod 600 "$KEY"
command -v rsync >/dev/null || { echo "Install: pkg install rsync -y" >&2; exit 2; }
[[ -d "$HOME/storage/pictures" ]] || {
  echo "Run termux-setup-storage and allow storage access first." >&2
  exit 2
}
DEST="$HOME/storage/pictures/CartoonTamilanV14"
mkdir -p "$DEST"
rsync -av --ignore-existing \
  -e "ssh -i $KEY -o IdentitiesOnly=yes" \
  --include="*/" --include="*.jpg" --include="*.png" \
  --include="*.mp4" --include="*.wav" --include="*.mp3" \
  --include="*.srt" --exclude="*" \
  ubuntu@80.225.239.193:/home/ubuntu/cartoon-tamilan-automation/output/v14/ \
  "$DEST/"
echo "Draft media downloaded to $DEST"
echo "Gallery indexing may take a moment; check the Pictures folder."
