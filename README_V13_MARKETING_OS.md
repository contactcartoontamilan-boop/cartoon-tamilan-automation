# CartoonTamilan V13 — Unified Marketing OS (preview-first)

**V13 GitHub source code, not a claim of 100% autonomous production readiness.**

The old process built V10 posters with typography already baked in and the V12
variant maker put *more* text on the poster. V13 solves this *architectural*
mistake: use the **original clean image source** from the story, then perform
**one fresh layout pass for each platform**. It rejects known V10/V12 decorated
poster filenames as artwork inputs. It cannot remove captions/watermarks that
are already inside a website story cover; original textless artwork is best.

## What V13 implements now

- `ct_master.py`: ONE command → website story discovery, deterministic rotation,
  artwork source, ten social platform image formats, full Unicode/Tamil layout
  using RAQM, editorial quality rules, bilingual drafts, hashtags, email
  newsletter drafts, social exports, and optional Reel + basic Tamil voice-over.
- `ctos/creative.py`: renders new layouts at:
  Instagram feed / Facebook feed / Threads 1080x1350; Instagram Story/YouTube
  Short 1080x1920; YouTube thumbnail 1280x720; Pinterest 1000x1500;
  Facebook landscape 1200x630; X 1600x900; LinkedIn 1200x627. Exact image
  dimensions and text panel/CTA geometry are checked; contrast subject matter
  and visual canon still need human review.
- `ctos/artwork.py`: uses current CartoonTamilan story cover in preview mode
  or optional **genuinely configured local ComfyUI** with approved story
  character bible. `cinematic_3d` means **3D-look artwork**, *not* a mesh
  or real 3D object. Oracle A1 (2 CPU/12GB RAM) does not have a GPU.
- `ctos/video.py`: optional FFmpeg still-art Reel MP4 and optional local
  espeak-ng Tamil narration and SRT. This is not fully AI-animated cinema.
- `ctos/content.py`: Facebook, Instagram, YouTube, Pinterest, Threads, X,
  LinkedIn and Telegram original-story bilingual copy and hashtags.
- `ctos/emailer.py`: original HTML/text newsletter drafts + optional single
  SMTP send that checks reviewed campaign, a verified opt-in subscriber CSV,
  private SMTP credentials and unsubscribe URL/address.
- `ctos/platforms.py`: drafts for 8 channels. **Only Meta FB/IG and Telegram
  have gated live APIs** here. YouTube, Threads, X, Pinterest and LinkedIn
  uploads still require OAuth apps/permissions, provider adapters and live tests.
- `ctos/review.py`: explicit rights+copy+visual approval fingerprints the
  exact files and rejects publication if a JPG or manifest changes.
- `ctos/qa.py`: tested technical image geometry/dimensions; no made-up AI
  optical/plot accuracy confidence.
- Existing V12 modules stay available: owned-site chapter extraction,
  14-day content calendar, real social analytics CSV reports, SEO audit,
  GA4/Search Console/PageSpeed with authorization, official-source anime news,
  safe comment-reply drafts, weekly analytics.

## Run on Oracle (NOT Android local Termux)

Initial V10/V12 `.venv` must already exist. Test without touching systemd:

```bash
cd ~/cartoon-tamilan-automation
git pull --ff-only
.venv/bin/python -m unittest test_ct_v13.py -v
.venv/bin/python ct_master.py campaign --limit 1
.venv/bin/python ct_master.py status
find output/v13 -name manifest.json
```

For optional MP4 and basic WAV voice:

```bash
sudo apt install -y ffmpeg espeak-ng
.venv/bin/python ct_master.py campaign --limit 1 --video --voice
```

To enable **daily SAFE draft generation at 08:30 IST** and **V11 GitHub autosync
approximately every five minutes**, after first testing:

```bash
bash setup_oracle_v13.sh
systemctl list-timers --all cartoontamilan-preview-v10.timer cartoontamilan-autosync-v11.timer
sudo journalctl -u cartoontamilan-preview-v10.service -n 60 --no-pager
```

Once this is installed, GitHub main can update Oracle automatically if V11
validator tests pass and requirements haven't changed; GitHub code does
**not** update Oracle without that installed timer. Do **not** remove old
source files still imported by V13/V12.

For optional original chapter analysis and SEO:
```bash
.venv/bin/python ct_master.py campaign --limit 1 --chapters --seo
```

## Android Gallery

Exit SSH to return to phone Termux:

```bash
pkg install rsync -y
cd ~/cartoon-tamilan-automation
git pull --ff-only
bash phone_gallery_sync_v13.sh
```

Pictures appear in `Pictures/CartoonTamilanV13/YYYY-MM-DD/story-id/media/`.
The rsync script is a **phone-side pull**; Oracle cannot directly transfer
files into a disconnected phone. It preserves multiple story filenames and
does not delete older Gallery images.

## Required permissions for LIVE publishing (NOT enabled by installer)

1. Review a specific story's source, character canon, Tamil/English copy,
   all exported graphics, source media licenses, URL and appropriate social use.
2. Ensure the original story already has approved rights, copy and V10 visual
   policy in your **Oracle private** `data/story_approvals_v9.json`.
3. Approve one inspected manifest (three independent confirmations):

```bash
.venv/bin/python ct_master.py approve \
  --manifest output/v13/YYYY-MM-DD/STORY_ID/manifest.json \
  --rights-confirmed --copy-reviewed --visual-reviewed
```

4. For Meta FB Page/linked professional IG, enable existing V9 Meta settings,
   public HTTPS media hosting, `DRY_RUN=false`,
   `AUTO_PUBLISH_APPROVED=true`, `PUBLISH_FACEBOOK=true` or
   `PUBLISH_INSTAGRAM=true`. Set private `.env`
   `CT_LIVE_PUBLISH=YES_I_APPROVE_META` before manually running:

```bash
.venv/bin/python ct_master.py publish \
  --manifest output/v13/YYYY-MM-DD/STORY_ID/manifest.json \
  --platform meta --live
```

**Never enable this in a timer without platform and copyright testing.**
Existing Meta integration retains its journal and marks ambiguous failures
uncertain rather than blindly retrying.

**Telegram** single bot-channel post is independently gated by
`CT_LIVE_TELEGRAM=YES_I_APPROVE_TELEGRAM`, a bot token and chat ID.
No credential is stored in GitHub.

**Email sending:** keep subscriber consent data privately at
`data/subscribers_v13.csv` with `email,opted_in,unsubscribed` columns.
You must configure real SMTP, sender mailing address and verified unsubscribe
endpoint. Live sends require `CT_EMAIL_LIVE=YES_SEND_OPTED_IN`; V13 preview
only saves `newsletter.html` and `newsletter.txt`. Do not send unsolicited
marketing mail or use harvested addresses.

## Unfinished, do not misrepresent

- Dedicated real AI video animation / pro Tamil voices / character-consistent
  original 3D rendering require local GPU or paid/free-external-inference API
  models AND character references. You cannot promise unlimited free GPU.
- YouTube, Threads, X, Pinterest and LinkedIn **auto-posting APIs are NOT wired**:
  V13 produces their files/captions and clearly labels them `export_only`.
- Google property OAuth, email consent and Meta token/private HTTPS media hosting
  need owner configuration. Search traffic cannot be manufactured. Daily 10K
  pageviews is a measurement goal, not a guarantee.
- Automated detection of **baked text inside a raw cover**, proof of copyright,
  real scene continuity and semantic Tamil accuracy require further review.

## Rollback V13 scheduled run without losing user data

```bash
sudo rm /etc/systemd/system/cartoontamilan-preview-v10.service.d/40-v13-marketing-os.conf
sudo systemctl daemon-reload
```

V12/V10 preview override still works. Do not delete or expose `.env`,
private SSH keys, reviews, or generated `output/`.
