# CartoonTamilan V10 — Premium Original Anime Poster + Social Campaign

V10 creates professional *poster drafts* inspired by dramatic anime key art without copying Black Clover, Flox Anime, other franchise characters, trademarks, or logo designs. The illustrated example posted in ChatGPT is **not** a model that GitHub can call automatically; a running, licensed image-generation backend must be installed separately.

### V10 workflow

1. `auto_story_marketing.py` discovers novels from CartoonTamilan.in.
2. **Default** `--art-mode cover`: download the existing story cover and transform it into a premium campaign poster.
3. **Optional** `--art-mode comfyui`: use a local ComfyUI API with a real licensed checkpoint to generate an ORIGINAL 4:5 artwork. The prompt incorporates genre and *reviewed* character/world notes plus a best-effort website synopsis (unreviewed context, never a verified fact).
4. `premium_poster_v10.py`: add gold Tamil title, branded banner, professional composition, glowing button, and correct Tamil typography via RAQM.
5. `social_copy_v10.py`: prepare Tamil + English intro, Facebook clickable story link with UTM, Instagram caption and bio-link guidance, relevant hashtags, and ALT text.
6. `campaign_v10.py`: safe-preview by default; opt-in publishing routes through V9 Facebook/Instagram API modules with approvals, HTTPS media preflight, and duplicate-post journal. Neither image generation nor publishing is guaranteed on unconfigured hardware/accounts.

## Termux — first preview (NO social posts)

```sh
cd ~/cartoon-tamilan-automation
git pull
pip install -r requirements.txt
python -m unittest test_premium_v10.py test_story_context_v10.py test_campaign_v9.py -v
python campaign_v10.py --limit 2 --art-mode cover --export-dir ~/storage/downloads/CartoonTamilanV10
```

Phone File Manager -> Downloads -> CartoonTamilanV10: preview `YYYY-MM-DD_<storyid>.jpg` image files. Each campaign also has a `social_pack.json` under `output/premium_v10/YYYY-MM-DD/<id>/`.

Check an individual caption:
```sh
find output/premium_v10 -name social_pack.json -type f
```
Select the actual path and open it with `cat` or `python -m json.tool PATH`.

### Expected preview report

- `prepared`: local JPEG posters successfully generated
- `failed`: failures with reasons
- `published: []` and `dry_run: true`: Meta was NOT called
- `exported_jpgs`: real Android Downloads paths

If Tamil fonts or RAQM are absent, the poster generator stops rather than writing square boxes. Termux normally needs a font with full Tamil shaping supported by Pillow+libraqm.

## True AI art generation: requires installed model

ComfyUI `workflows/story_txt2img_api.json` is a starter workflow that **will not run** until you replace the checkpoint placeholder with an installed, legally usable text-to-image model. Start ComfyUI on a GPU-enabled local/Oracle host and configure:
```env
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_CHECKPOINT=YOUR_ACTUALLY_INSTALLED_MODEL.safetensors
COMFYUI_WORKFLOW=workflows/story_txt2img_api.json
ART_STYLE=anime
USE_SITE_SYNOPSIS=true
```
Then on the SAME computer where ComfyUI is running:
```sh
python campaign_v10.py --limit 1 --art-mode comfyui --export-dir ~/storage/downloads/CartoonTamilanV10
```
On Oracle, omit the Android Downloads option and view output files through your approved transfer method. A Termux client cannot access Oracle's `127.0.0.1` without a secure SSH tunnel; never open unauthenticated ComfyUI to the public internet.

`ART_STYLE=cinematic_3d` gives 3D-**looking** key art, not an editable 3D model. A CPU-only 12GB server may be too slow or incompatible with the chosen checkpoint; **free/unlimited** capacity is not guaranteed.

### Professional story continuity

Run once to initialize private story editorial + visual approvals:
```sh
python story_approvals_v10.py
```
Then review `data/story_approvals_v9.json` in a local editor. For each story set verified `genres`, `intro_ta`, `intro_en`, `verified_character_notes`, `verified_world_notes` and `premium_theme` (royal/crimson/cosmic/emerald). This is the key to consistent characters rather than random invented plots.

The default `rights_confirmed`, `copy_reviewed`, `v10_visual_policy_approved`, and `v10_automatic_ai_approved` are all **false**. Do not set them to true without checking image rights, copy accuracy and source character consistency.

## Facebook + Instagram automated publishing (opt-in)

V10 uses previously implemented `social/facebook.py` and `social/instagram.py` through `campaign_v9.py`. Meta must have approved posting permissions, working Page and linked Instagram professional IDs, a secure access token and a publicly accessible HTTPS image URL. See `README_CAMPAIGN_V9.md` for these prerequisites, HTTPS media hosting setup, unknown/uncertain statuses and deduplication safety. Instagram feed caption links are not clickable; set your profile link separately.

**Keep publishing OFF while previewing**:
```env
DRY_RUN=true
PUBLISH_FACEBOOK=false
PUBLISH_INSTAGRAM=false
AUTO_PUBLISH_APPROVED=false
```
When fully configured and ONLY after verifying all rights and publication conditions, `python campaign_v10.py --publish --limit 1` deliberately attempts a real post on enabled platforms. No chat action changes these flags for you.

## Oracle once-daily operation (after dry run)

`run_campaign_daily_v10.sh` is safe-preview by default. First run manually:
```sh
bash run_campaign_daily_v10.sh
```
Example cron entry (update the real home path and verify the machine's timezone first):
```cron
15 8 * * * /usr/bin/bash /home/ubuntu/cartoon-tamilan-automation/run_campaign_daily_v10.sh
```
The script enables Meta API publishing only if server environment explicitly defines `CAMPAIGN_V10_PUBLISH=true` AND the existing required flags and story approvals are satisfied. Keep state file `data/campaign_state_v9.json` persistent across server restarts to prevent duplicates.

## Remaining limits and roadmap

- Poster quality and Tamil typographic accuracy need **human visual review**, especially when a source cover contains typography high in the image.
- Current default is 1080x1350 image post; not video/Reels/Stories generation or 3D mesh files.
- The homepage catalogue is an HTML parser and may miss stories if the site UI changes.
- Website synopsis extraction cannot prove a full novel was read; prompts use metadata conservatively and do not invent canonical characters.
- Auto-publishing social posts alone does not guarantee meaningful reader acquisition; measure actual website sessions, chapter read-through, GA4/Search Console performance, not vanity views.
