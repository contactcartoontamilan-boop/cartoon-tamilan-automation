# CartoonTamilan V14 — P0 Story Reading, Visual QA and P1 Scene Art

**Status:** Isolated experimental feature branch; review-only, not production.
The original V13 main checkout and the existing V14 preview branch remain untouched.

## What this PR actually adds

1. `ctos/creative.py`: existing 10 image layouts now show the **whole original cover** in a contained, sharp foreground over a softly blurred background. This avoids chopping off characters at the left/right edges of wide covers. CTA text is platform-specific (Instagram bio; other social captions/post links). The Tamil headline is balanced vertically within the panel. **This does not detect faces or prove artistic quality.**
2. `ct_v14_story_ingest.py`: reads accessible chapter pages **only from the exact CartoonTamilan novel path**. Follows discovered chapter links up to a configurable 40-page cap, saves source text, provenance and an **extractive/verbatim 70–340 word Tamil teaser draft**, plus a 6–12-scene storyboard. The draft is not a verified full-plot summary. Missing pages, JavaScript-only content, copyright, chapter ordering and completeness require human review.
3. `ct_v14_scene_art.py`: creates scene-specific AI image prompts using an already **verified** local character bible and real narration. In default mode it saves prompts only. With explicit `--generate`, owner approvals and an installed local ComfyUI model, it can generate 6–12 original PNG images with distinct seeds, resolution checks and duplicate detection. No GPU/model or commercial rights are supplied by this code. Character continuity is **not automatically proven**.
4. `comfyui_art_v9.py`: optional per-call seed parameter; existing calls keep the old default behavior.
5. \`ct_v14_control_center.py\`: an offline P2/P3 readiness JSON and local HTML dashboard showing draft counts and honest API integration status. It is **not** a live analytics/dashboard service.\n6. Offline tests and a new GitHub Actions workflow. **CI is not a live website, TTS, GPU or social API test.**

## Run from an isolated checkout (Termux or Oracle)

Use a new worktree. Do **not** run these commands in `~/cartoon-tamilan-automation` production:

```bash
cd ~/cartoon-tamilan-v14-image-post-test
git fetch origin feature/v14-p0-story-ingestion-visual-qa
git worktree add -b v14-p0-local \
  ~/cartoon-tamilan-v14-p0-test \
  origin/feature/v14-p0-story-ingestion-visual-qa
cd ~/cartoon-tamilan-v14-p0-test
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest test_ct_v14_story_ingest.py test_ct_v14_scene_art.py -v
```

To automatically discover the latest owned novel and read its **accessible** chapters:\n\n\`\`\`bash\n.venv/bin/python ct_v14_story_ingest.py --discover-latest --max-pages 24 --words 180 --scenes 8\n\`\`\`\n\nOr read a specific story and make a review draft:

```bash
.venv/bin/python ct_v14_story_ingest.py \
  --story-url https://cartoontamilan.in/novel/amrutha-ulaga-perangadi/ \
  --max-pages 24 --words 180 --scenes 8
```

Find the generated files:

```bash
find output/v14/full_story -name manifest.json -type f
```

Each story folder has `source_chapters.json`, `narration_draft_ta.txt`,
`storyboard_draft.json` and `manifest.json`. **Review the real chapter text,
scene ordering, Tamil narration and rights before using the draft as a script.**
Generated `output/` and `private/` files are ignored by Git.

To make prompt drafts for your already verified character bible:

```bash
.venv/bin/python ct_v14_scene_art.py \
  --storyboard output/v14/full_story/STORY_HASH/storyboard_draft.json \
  --story-url https://cartoontamilan.in/novel/amrutha-ulaga-perangadi/ \
  --title 'அம்ருதா உலகப் பேரங்காடி' \
  --outdir output/v14/scene_art
```

Replace `STORY_HASH` with the folder name shown by `find`. The private
`data/story_bibles_v10.json` must contain a **verified** entry for the exact
story URL. `verified: true` is a human editorial assertion, not automatic proof.

To **actually generate** unique images (requires a working local ComfyUI server,
a licensed checkpoint, configured workflow and GPU, which may not exist on an
Oracle free ARM instance), repeat with these explicit flags:

```bash
  --generate --rights-confirmed --story-reviewed --model-license-confirmed
```

This is an optional suffix to the preceding scene-art command, not a standalone
shell command. Verify each `scene_01.png` through `scene_08.png`. Do not
use those approvals unless you have actually completed the reviews.

After reviewing/editing the narration and images, the **existing** V14
`ct_v14.py build` can create a silent video preview; Azure Tamil female TTS
is a separate opt-in step requiring a real key, region and listening review.
Nothing in this PR automatically uploads video, posts images or sends email.

## Recreate improved 10-format image previews

```bash
.venv/bin/python ct_v14_image_post.py create --limit 1
.venv/bin/python ct_v14_social_queue.py prepare
```

Inspect all 10 JPEGs and captions. Platform-specific CTA text **inside the
images** does not make the associated platform API operational.

## Generate a local all-channel readiness dashboard

After running the image social queue, run:

\`\`\`bash
.venv/bin/python ct_v14_control_center.py
\`\`\`

Open \`output/v14/control_center/dashboard.html\` locally or copy it to
Android Downloads. This **static offline page** reports what is missing and
never attempts to publish or contact platform APIs.

## What is still pending

- Live end-to-end website coverage and chapter-order validation; actual Tamil
  narration editorial approval; automatic verified plot summarization.
- ComfyUI GPU deployment, model-license verification, reliable character
  identity and visual similarity QA; genuine anime motion.
- Natural female TTS real-provider test, burned-in Tamil subtitles and
  platform-specific 60–120-second video export.
- Real Meta/Telegram account authorization and live posting test; Pinterest,
  Threads, X, LinkedIn and YouTube upload adapters; official API quotas.
- Durable background scheduler, reconciled delivery journal, metrics APIs,
  SEO validation, subscriber consent/unsubscribe delivery, dashboard and
  24/7 Oracle V14 rollout.
- Full security, legal and cost review before production.

**No publishing is performed by any new command in this PR.**
