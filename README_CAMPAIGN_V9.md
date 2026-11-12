# CartoonTamilan V9 — Cinematic Campaign & Automatic Publishing (opt-in)

**Goal:** create promo posts inspired by dramatic anime key-art layouts while promoting ONLY CartoonTamilan original stories. Never copy screenshots, character art, logos or badges from another anime/company.

**What V9 does TODAY (no additional credentials):**
- Finds original novels from the live site automatically.
- Uses each story's existing cover as artwork, or **optionally** calls a running local ComfyUI for *new* anime/3D-style rendered illustrations.
- Produces 1080x1350 cinematic JPEGs with neon glow, branded Tamil titles, and "Read the Story" CTA.
- Writes Tamil/English Facebook and Instagram captions, hashtags and tracking URLs as JSON.
- Prepares a one-time story-rights and caption approval sheet.
- With all gates deliberately enabled, can copy images to a public HTTPS folder and publish via Meta Graph API to your Facebook Page and linked Instagram Creator professional account.
- Prevents repeated posts **per story, day and platform**; unclear upload results are marked `uncertain` and never blindly retried.

**What V9 does NOT do automatically without setup:**
- Generate original characters when ComfyUI/model/GPU is absent (it uses original website cover instead).
- Prove that site cover art is yours or translate a complete novel. Approvals are mandatory.
- Set up Oracle/ComfyUI, provision a public domain, obtain Meta tokens, or bypass platform permissions.
- Guarantee AI quality, 10,000 daily pageviews or free/unlimited image inference.
- Post videos, Stories or Reels (V9 posts images, not video).

## 1) Termux tests and safe preview

```sh
cd ~/cartoon-tamilan-automation
git pull
pip install -r requirements.txt
python -m unittest test_campaign_v9.py test_poster.py test_story_marketing.py -v
python campaign_v9.py --limit 2
find output/campaign_v9 -name cinematic_poster.jpg -type f
```

Look at `output/campaign_v9/YYYY-MM-DD/<story-id>/cinematic_poster.jpg` and `social_pack.json`. No Meta API calls are made without `--publish`.

To put new JPEGs into Android Downloads for review:

```sh
mkdir -p ~/storage/downloads/CartoonTamilanV9
find output/campaign_v9 -name cinematic_poster.jpg -type f -exec cp -v {} ~/storage/downloads/CartoonTamilanV9/ \;
```

**Caution:** multiple posters currently share filename `cinematic_poster.jpg` and a simple copy command will overwrite them. Better use the unique ID script below:

```sh
python - <<'PY'
from pathlib import Path
import shutil
src = Path("output/campaign_v9")
dst = Path.home() / "storage/downloads/CartoonTamilanV9"
dst.mkdir(parents=True, exist_ok=True)
for path in src.glob("*/*/cinematic_poster.jpg"):
    shutil.copy2(path, dst / (path.parent.name + "_" + path.parent.parent.name + ".jpg"))
print("Saved:", len(list(dst.glob("*.jpg"))), "posters in", dst)
PY
```

## 2) Review story rights and copy ONCE

```sh
python story_approvals_v9.py
nano data/story_approvals_v9.json
```

Each discovered original novel gets an entry with `rights_confirmed: false` and `copy_reviewed: false`.
Confirm you own/license the image and that both Tamil and English intros are correct, then change **only approved stories** to `true`. Do not confirm rights for third-party anime images or unrelated source covers.
`data/story_approvals_v9.json` is gitignored; it must be backed up privately on your Oracle host.

## 3) Optional real original AI artwork via ComfyUI (requires hardware)

V9 includes `comfyui_art_v9.py` and `workflows/story_txt2img_api.json`. These call native ComfyUI `POST /prompt`, `GET /history/<id>` and `GET /view`. No mock AI is used.

Install ComfyUI **yourself** on a machine with adequate VRAM/GPU, choose an authorized model checkpoint and set in `.env`:

```
ART_PROVIDER=comfyui
ART_STYLE=anime
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_CHECKPOINT=<your-actual-installed-licensed-model.safetensors>
```

`ART_STYLE=cinematic_3d` produces **3D-looking images**, not actual 3D models.

`python campaign_v9.py --limit 1 --art-provider comfyui`

**Without GPU, the 12GB Oracle CPU-only environment may be very slow, and could fail due to model/VRAM requirements.** Prefer `ART_PROVIDER=cover` until ComfyUI is proven operational. Do not expose unauthenticated ComfyUI to the internet. The local workflow example is checkpoint-dependent and may require adaptation to the installed model's nodes.

## 4) Meta/HTTPS hosting prerequisite (before any `--publish`)

Meta needs the POSTER JPEG reachable from the public Internet by HTTPS, not a private Termux path. You must independently configure an image-hosting origin: e.g., a secured static directory served through your own HTTPS domain, with `image/jpeg` content type, and direct `HTTP 200` responses.

Set (on Oracle server, not in GitHub commits):
```
PUBLIC_MEDIA_DIR=/srv/cartoontamilan-posters
PUBLIC_MEDIA_BASE_URL=https://YOUR-CONTROLLED-MEDIA-DOMAIN.example/posters
```

**These values must refer to the same files**: when Python copies `/srv/cartoontamilan-posters/ct_...jpg`, HTTPS must serve them at `https://.../posters/ct_...jpg`. V9 checks this via HEAD before contacting Meta. It does not itself provision hosting.

Meta Facebook Login workflow: Page with create-content access and necessary Page permissions; linked Instagram Professional Creator account with `instagram_content_publish`, Page-level access, a working Page token and associated Instagram ID. See Meta docs for exact access requirements.

## 5) Live posting: deliberate opt-in only

Copy `.env.example` to `.env` if needed; never put tokens in GitHub.
Once credentials/permissions, HTTPS image hosting, actual model (if used), and approved stories are working, edit Oracle-local `.env`:

```
DRY_RUN=false
AUTO_PUBLISH_APPROVED=true
PUBLISH_FACEBOOK=true
PUBLISH_INSTAGRAM=true
META_GRAPH_VERSION=v26.0
META_PAGE_ID=your-page-id
META_PAGE_ACCESS_TOKEN=your-access-token
INSTAGRAM_USER_ID=your-instagram-professional-id
ART_PROVIDER=cover
```

Then, **only when you intentionally want a live post**:

```sh
python campaign_v9.py --publish --limit 1
```

If a Meta call errors or its result is ambiguous, inspect `data/campaign_state_v9.json`; statuses `uncertain` are intentionally NOT retried automatically. Reconcile them on Meta first to avoid duplicates. Do not delete the journal to force re-posting.

## 6) Oracle automatic daily schedule (after all live tests)

Set a **once-daily cron job** using an absolute path to your actual repository on Oracle:

```cron
10 8 * * * /home/ubuntu/cartoon-tamilan-automation/run_campaign_daily_v9.sh
```

This example time is **server-local**, not necessarily Indian Standard Time. Verify with `date` and your server timezone. Start with a daily dry run; activate publishing only after reviewing an actual one-post live test.

## 7) Future professional improvements

- Verified full chapters → story/character bible → consistent illustrated characters.
- AI Tamil copy-edit and English verified summaries, never fabricated scenes.
- 9:16 video/voiceover Reel pipeline with licensed media and original music.
- Real GA4/Search Console analytics to track website readers, not vanity Reel views.
