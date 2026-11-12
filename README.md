# CartoonTamilan Original Stories Marketing Automation

**Current production-safe path: Oracle Ubuntu ARM64 → premium V10 story poster previews → GitHub V11 auto-sync.**

## Start here

- [Oracle V10 initial setup](README_ORACLE_V10_SETUP.md)
- [GitHub → Oracle automated code updates every ~5 minutes (V11)](README_ORACLE_AUTOSYNC_V11.md)
- [V10 premium posters and bilingual captions](README_PREMIUM_V10.md)
- [V9 opt-in Facebook + Instagram API integration](README_CAMPAIGN_V9.md)

## Running modules (do not delete imported dependencies)

- `campaign_v10.py`: latest **preview** and opt-in publishing orchestration.
- `premium_poster_v10.py`: branded 1080x1350 original-story JPEG layout.
- `art_direction_v10.py`, `story_context_v10.py`: optional story-specific concept art prompts.
- `social_copy_v10.py`: Tamil and English captions, hashtags and story links.
- `campaign_v9.py`, `social_content_v5.py`, `poster_generator.py`, `auto_story_cover.py`, `auto_story_marketing.py`: still **required** by the V10 import graph.
- `oracle_autosync_v11.sh`: checks GitHub main, stages full tests and fast-forward deploys to Oracle.
- `setup_oracle_autosync_v11.sh`: one-time Oracle systemd timer installer.

Legacy daily GitHub Actions workflow and V9 shell scheduler were removed to prevent duplicate automatic runs. Git-tracked scripts deleted from main will be removed from Oracle on the next successful auto-sync. Private local files are never cleaned.

## Safe defaults

```dotenv
DRY_RUN=true
PUBLISH_FACEBOOK=false
PUBLISH_INSTAGRAM=false
AUTO_PUBLISH_APPROVED=false
CAMPAIGN_V10_PUBLISH=false
```

Oracle V10 daily **preview** at 08:30 Asia/Kolkata is separate from V11 code-update checks (~every 5 min). Social posts do NOT publish until rights, copy, Meta permissions, public HTTPS media hosting and platform approvals are explicitly configured.

## Oracle SSH first-time one-command auto-sync installer

```sh
cd ~/cartoon-tamilan-automation
git pull --ff-only
bash setup_oracle_autosync_v11.sh
systemctl list-timers --all cartoontamilan-autosync-v11.timer
```

Do not commit credentials or private SSH keys into GitHub. Use full setup and rollback instructions in [V11 documentation](README_ORACLE_AUTOSYNC_V11.md).

## V12 advanced marketing upgrade (latest)

- [V12 complete development/setup guide](README_V12_ADVANCED_MARKETING.md)
- `v12_ops.py` orchestrates a safe daily marketing draft, original-story calendar, premium posters, SEO, analytics and health.
- `v12_cli.py` runs optional original chapter reading, local narrator, FFmpeg Reel, verified official RSS, Google GA4/Search Console/PageSpeed, comment moderation and weekly reports.
- [V12 Oracle installer](setup_oracle_v12.sh): once installed, retains daily 08:30 IST and adds weekly Monday 09:00 IST reviews. Live Meta publishing remains disabled.
- [V11 GitHub → Oracle updater](README_ORACLE_AUTOSYNC_V11.md): updates only once its separate auto-sync timer has been installed on Oracle.

To adopt after verifying SSH login:

```sh
cd ~/cartoon-tamilan-automation
git pull --ff-only
.venv/bin/python -m unittest test_v12.py test_v12_google.py test_v12_voice.py -v
bash setup_oracle_v12.sh
```

**Required external integrations are NOT automatically connected by merely uploading code:** AI artwork model/inference, Meta Page+Instagram token and public-media origin, Google OAuth permission, premium video/TTS models, and YouTube/Threads/Pinterest publishing credentials.
