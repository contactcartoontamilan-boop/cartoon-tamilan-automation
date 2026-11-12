# CartoonTamilan V12 — Advanced AI Digital Marketing Automation

## What this update ACTUALLY implements

V12 adds substantial **functional Python modules**, not a promise of a fully autonomous marketing agency. All newly generated content is a **review draft**. Main supported pipeline:

`CartoonTamilan.in story catalogue → safe story discovery → approved story bible / optional chapter extraction → 14-day content calendar → V10 cinematic posters → optional approved memes & aspect variants + FFmpeg Reel/voice → bilingual social captions + attribution → SEO audit + analytics → daily/weekly operational reports`.

**Default: no Facebook/Instagram live posts, no copyrighted media redistribution, no invented audience figures.**

### Implemented modules

| File | What runs now | External requirement |
|---|---|---|
| `v12_strategy.py` | 14-day / 5-channel draft content planner, Tamil+English hooks, tracked links, rights/status gates | Story records are discovered from own site |
| `v12_media.py` | 4 aspect ratios, meme copy variant, user-authorized key art, 9:16 MP4 teaser from still image | FFmpeg to produce MP4; approved source image |
| `v12_voice.py` | Tamil/English WAV narration, .srt captions | `espeak-ng` installed; robotic voice, **not premium dubbing** |
| `v12_story_reader.py` | Extract public chapters from the original story URL; optional local Ollama editorial draft | Accessible HTML chapters; local model for optional LLM |
| `v12_news.py` | Official RSS source discovery with verification-required news queue | User-reviewed official sources; **no generic scraped copyrighted images** |
| `v12_seo.py` | Owned-site technical SEO checks, canonical/H1/OG/JSON-LD advice, valid internal link candidates | Website reachable |
| `v12_google.py` | **Real** GA4 daily pageviews, Search Console queries and mobile Google PageSpeed REST endpoints | Google property authorization/OAuth consent; PageSpeed public option |
| `v12_insights.py` | Actual impressions → link clicks → website sessions → story reads, with data sufficiency checks | User-supplied measured CSV, **not invented** |
| `v12_engagement.py` | Facebook/Instagram comment reply **drafts** for moderation | Legitimate comments export |
| `v12_alerts.py` | Optional Telegram server-failure notifications (token redacted) | Opt-in bot token and chat ID |
| `v12_ops.py` | One safe daily orchestrator: V10 posters + draft calendar + metrics + health + optional site SEO and approved media variants | Existing Oracle V10 installation |
| `v12_weekly.py` | Management summary: observed pageviews vs 10K target, real social attribution, action list | Real metrics for numeric results |
| `v12_cli.py` | Manual commands for all specialized workflows | Depends on command |
| `setup_oracle_v12.sh` | Safe daily timer upgrade + Monday 09:00 IST weekly review timer | Ubuntu SSH / sudo / existing Python venv |
| `test_v12.py`, `test_v12_google.py`, `test_v12_voice.py` | Offline regression tests | Existing project requirements |

### Still waiting for accounts, hardware or permissions

- **Original anime/3D-looking image generation:** ComfyUI V10 integration exists, but Oracle Ampere A1 has **no GPU**; it will not magically produce high-end original characters. Needs compatible real image model/inference backend. Actual 3D meshes/models are **not** generated.
- **Automated Facebook + Instagram live posts:** V9/V10 Meta Graph API code exists, but publishing is **OFF** until Page permissions, linked professional account, Media URLs, rights approvals, real credentials and successful explicit live test. Facebook/Instagram Reels and Stories are **not** operational end-to-end from V12.
- **YouTube Shorts, Threads, Pinterest:** channel-specific draft plans exist, but OAuth video uploads and other provider APIs are **not** connected. Do not claim they are posting automatically.
- **Premium Tamil narrator / advanced video scene generation:** optional CPU text-to-speech and FFmpeg still-image Reel exist. Premium voices, animated scene models, translation QA and licensed music are **not** yet available.
- **Google growth optimization:** read-only Google REST connectors are implemented, but GA4/Search Console property permissions and consent are missing. No genuine conversion data until the site tracks reads, chapters and campaigns.
- **AI moderation:** replies are drafts. No unsafe unattended reply sending.
- **10,000 pageviews/day:** a growth target, never a guarantee.

## Oracle install: ONLY after existing V10 is working

Log in to Oracle via SSH, **not local Android Termux**, then run:

```bash
cd ~/cartoon-tamilan-automation
git pull --ff-only
.venv/bin/python -m unittest test_v12.py test_v12_google.py test_v12_voice.py -v
bash setup_oracle_v12.sh
```

`setup_oracle_v12.sh` runs the full regression suite + first V12 dry run before modifying the old preview service. It leaves V11 GitHub auto-sync and the daily 08:30 IST schedule in place; it adds Monday 09:00 IST real-data weekly report. Your GitHub V11 automatic deployment **only works after you installed and verified its timer** separately. Code upload does not directly SSH into Oracle.

Check:

```bash
sudo systemctl start cartoontamilan-preview-v10.service
cat output/v12/latest_health.json
find output/v12 -name daily_report.json -type f
sudo journalctl -u cartoontamilan-preview-v10.service -n 40 --no-pager
systemctl list-timers --all cartoontamilan-autosync-v11.timer cartoontamilan-preview-v10.timer cartoontamilan-weekly-v12.timer
```

Uninstall only V12's service override (this reverts to earlier V10 preview command); don't delete private state:

```bash
sudo rm /etc/systemd/system/cartoontamilan-preview-v10.service.d/30-v12-manager.conf
sudo systemctl disable --now cartoontamilan-weekly-v12.timer
sudo systemctl daemon-reload
```

## Commands — AI marketing workflows

```bash
cd ~/cartoon-tamilan-automation
source .venv/bin/activate
python v12_ops.py --limit 2 --seo
python v12_cli.py calendar
python v12_cli.py seo
python v12_cli.py weekly
```

**Multi-format graphics** — only if you own/are authorized to use the artwork:

```bash
python v12_cli.py variants --artwork output/premium_v10/YYYY-MM-DD/STORY_ID/premium_poster.jpg --title "Approved Tamil headline" --rights-confirmed
```

**Video / narration** — optional on Oracle:

```bash
sudo apt install -y ffmpeg espeak-ng
python v12_cli.py reel --poster output/v12/variants/reel_cover.jpg --out output/v12/reel.mp4
```

To generate your own Tamil WAV narration and external .srt:

```bash
python v12_cli.py voice --script private_approved_narration.txt --lang ta --rights-confirmed
python v12_cli.py reel --poster output/v12/variants/reel_cover.jpg --voiceover output/v12/narration_ta.wav --voice-rights-confirmed
```

Video has no copyrighted backing music. The default is a **static-art** teaser with basic format conversion, not a real anime animation or character-acted scene.

**Chapter reading** (draft only):

```bash
python v12_cli.py chapters --story-url "https://cartoontamilan.in/novel/ACTUAL_STORY_SLUG/"
```

Optional local Ollama (only if you installed a real model on the SAME machine):

```bash
python v12_cli.py chapters --story-url "https://cartoontamilan.in/novel/ACTUAL_STORY_SLUG/" --local-ai
```

This only captures publicly accessible chapters; no invented plot or character bibles. You must verify the result. A CPU-only Oracle server may not handle a local LLM comfortably.

**Official anime / cartoon news** — copy `data/official_sources_v12.example.json` to `data/official_sources_v12.json`, replace placeholder URLs, and set `official_source_confirmed: true` ONLY after checking each source:

```bash
python v12_cli.py news
```

**Comments moderation (not sent):**

```bash
python v12_cli.py comments --csv data/comments_v12.csv
```

CSV columns: `platform,comment_id,comment_text`.

## Real Google metrics

Google API endpoints follow the official Google Analytics Data API `properties.runReport`, Search Analytics `query` and PageSpeed Insights `runPagespeed` contracts. Set the following only in Oracle-local `.env` and never commit to GitHub:

```dotenv
GA4_PROPERTY_ID=YOUR_GA4_PROPERTY_ID
GSC_PROPERTY=sc-domain:cartoontamilan.in
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
```

You must first configure **OAuth consent and authorize the site's actual properties** with read-only `analytics.readonly` and `webmasters.readonly` scopes. This repository does **not** provide an OAuth sign-in screen. Once credentials are valid:

```bash
python v12_cli.py google --days 7 --pagespeed
```

It writes real pageviews to `data/analytics_daily.csv` and separately saves `output/v12/google_review.json`. A failed/empty API response does not silently replace prior measured data. PageSpeed-only reports can run via `python v12_cli.py google --pagespeed` **without OAuth** when neither GA4 nor GSC property is configured.

If no authenticated Google data is available, `v12_weekly.py` reports `no_data` instead of fake traffic. The GA4 `screenPageViews` metric includes website and app views for the selected property, so verify that the GA4 property represents your intended website.

## 24/7 monitoring

Daily `output/v12/latest_health.json` and `daily_report.json`, weekly `output/v12/weekly_marketing_review.json`, systemd journal and optional Telegram failure alerts are available.

Optional private `.env`:

```dotenv
V12_ALERTS_ENABLED=true
V12_TELEGRAM_BOT_TOKEN=...
V12_TELEGRAM_CHAT_ID=...
```

Nothing is sent until enabled. Protect bot credentials and SSH private keys.

**Core philosophy:** use actual original stories, licensed original media, truthfully sourced news, measured organic traffic and protected accounts. Review content until editorial quality and platform permissions are demonstrably sound.
