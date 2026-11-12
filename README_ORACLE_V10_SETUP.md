# Oracle ARM64 V10 one-command setup (safe preview)

Your OCI server is Ubuntu 24.04 aarch64 / 2 OCPU / ~12 GB RAM, which is suitable for the existing website-cover premium poster workflow. It has no GPU for practical full-size generative diffusion art. This script does **not** install ComfyUI, open server ports, or enable social publishing.

## Run from an already authenticated Oracle SSH Ubuntu shell (not local Termux shell)

First clone or update the project:

```sh
cd ~
sudo apt-get update
sudo apt-get install -y git
if test -d cartoon-tamilan-automation/.git; then
  git -C cartoon-tamilan-automation pull --ff-only
else
  git clone https://github.com/contactcartoontamilan-boop/cartoon-tamilan-automation.git
fi
cd cartoon-tamilan-automation
bash setup_oracle_v10.sh
```

Installer performs the following:
- Ubuntu apt packages: Python, venv, pip, libraqm0, Noto Tamil and DejaVu fonts.
- Creates `.venv`, installs `requirements.txt`, and creates default `.env` only if not already present.
- Verifies RAQM and Tamil fonts; compiles Python and runs offline tests.
- Generates two **preview-only** premium story cover posters from your website (no Facebook / Instagram API calls).
- If and only if the above steps succeed, installs/enables `cartoontamilan-preview-v10.timer` to generate 1 daily preview at **08:30 Asia/Kolkata**.

Inspect output:
```sh
cd ~/cartoon-tamilan-automation
find output/premium_v10 -name premium_poster.jpg -type f
systemctl list-timers cartoontamilan-preview-v10.timer
sudo journalctl -u cartoontamilan-preview-v10.service -n 60 --no-pager
```

To run the preview timer's service immediately:
```sh
sudo systemctl start cartoontamilan-preview-v10.service
```

To stop automatic daily preview:
```sh
sudo systemctl disable --now cartoontamilan-preview-v10.timer
```

The script will not run if tests or first preview fail; send the last 25 non-secret error lines to debug. Publishing is **not** enabled. To publish on Facebook and Instagram later, complete rights reviews, Meta developer access, public HTTPS image hosting, and explicit publish approvals. Do not turn live publishing on just to test the scheduler.

SSH private-key notes: Your SSH key was previously shared in chat. The server can still use it to connect, but it should be rotated eventually from a trusted client; keep the replacement PRIVATE key only on your phone.
