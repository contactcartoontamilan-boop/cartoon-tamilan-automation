# V11 — GitHub is the Source of Truth; Oracle Automatically Updates

**Deployment architecture**: GitHub main -> **every ~5 minutes** Oracle's `cartoontamilan-autosync-v11.timer` fetches updates -> stages the candidate in a temporary Git worktree -> runs Python syntax checks and ALL `test_*.py` regression tests -> only if they pass, applies a **fast-forward merge** on the existing Oracle repo. The main 08:30 IST preview timer remains separately active.

### What "remove old scripts" means

- Files **tracked in Git** that are explicitly **removed from GitHub main** are deleted from Oracle by the fast-forward merge. This happens automatically after successful tests.
- Removed obsolete entry points: `.github/workflows/daily.yml` (old separate GitHub Actions daily automation that could duplicate work) and `run_campaign_daily_v9.sh` (superseded legacy scheduler).
- Some older-looking source files, such as `campaign_v9.py`, `social_content_v5.py`, and `poster_generator.py`, are **still directly imported** by V10. Do not delete them until replacements are tested and all imports have migrated.
- It NEVER runs `git clean -fd` or deletes untracked files. Locally created legacy Python scripts are **not** auto-deleted. The automation will not touch `.env`, private tokens, `output/`, approvals, local poster media, or `data/campaign_state_v9.json`.

### One-time Oracle install (logged in to Ubuntu using Termux SSH)

```sh
cd ~/cartoon-tamilan-automation
git pull --ff-only
bash setup_oracle_autosync_v11.sh
```

This writes two systemd units:

- `cartoontamilan-autosync-v11.service`: fetch + stage + tests + safe fast-forward update, *as ubuntu (NOT root)*.
- `cartoontamilan-autosync-v11.timer`: starts about 2 minutes after boot, then checks **every 5 minutes** after each run (not instant).

It also installs a systemd drop-in so `cartoontamilan-preview-v10.service` and the updater share a lock: preview won't run while code is being replaced.

### Verify

```sh
systemctl list-timers --all cartoontamilan-autosync-v11.timer
sudo systemctl start cartoontamilan-autosync-v11.service
tail -n 40 ~/.local/state/cartoontamilan/autosync.log
cd ~/cartoon-tamilan-automation
git log -1 --oneline
```

Expected log when no new changes: `Already up to date: <sha>`. After a new GitHub commit: `DEPLOYED: <new sha>` (after passing tests). Compare `git rev-parse HEAD` with GitHub main if needed.

### Safe blocking conditions

If tracked Oracle files have been manually modified, auto-sync **stops**, does not overwrite them.

If history was force-pushed or rebased (non-fast-forward), auto-sync **stops**. Avoid rewriting `main`.

If `requirements.txt` changes, auto-sync **stops** to require explicit dependency review/venv setup before proceeding. Do not make a destructive `git reset --hard` to get around this.

If tests fail, the new GitHub code is **not deployed**; the old working version remains on Oracle. Check `autosync.log`. There is no silent reset/retry that deletes data.

### Troubleshooting and controls

```sh
tail -n 80 ~/.local/state/cartoontamilan/autosync.log
git status --short
sudo systemctl status cartoontamilan-autosync-v11.service --no-pager
sudo systemctl status cartoontamilan-preview-v10.timer --no-pager
```

Pause automatic code updates (keep preview schedule untouched):

```sh
sudo systemctl disable --now cartoontamilan-autosync-v11.timer
```

Resume:

```sh
sudo systemctl enable --now cartoontamilan-autosync-v11.timer
```

**Security note:** auto-sync means anyone who can push to GitHub `main` can cause code to run on Oracle. Protect your GitHub account with MFA and restrict write access/branch changes. Do not store SSH private keys, Meta tokens or `.env` on the public repository.

**Facebook/Instagram publishing remains OFF**. The timer only updates repository code. It does not grant Meta permissions or turn dry-run into live publishing.
