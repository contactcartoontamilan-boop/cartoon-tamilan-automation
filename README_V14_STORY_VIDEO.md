# CartoonTamilan V14 — full-story preview video (60–120 seconds)

This is an **additive, review-first implementation**. V13 preview timers, approval
state, Meta/Telegram publishers and email sender are NOT changed. V14 never
publishes or emails anyone.

## What is implemented

- Source-faithful Tamil storyboard from an **approved original script**.
  It cannot fabricate a full story from a headline or URL.
- 6–12 **distinct, original/authorized scene illustrations**, validated by
  filenames, resolution and duplicate SHA-256. One poster repeated eight
  times is rejected. Artwork must already be created or supplied.
- Optional **Azure Speech Tamil female neural voice**:
  ta-IN-PallaviNeural, SSML with a gentle rate/pitch. It requires an Azure
  Speech resource, credentials, an internet connection and usage billing.
  Availability, pronunciation and quality must be checked by a Tamil speaker.
  This does not clone a person's voice. V13's mechanical eSpeak remains
  available only in V13; V14 does not pretend it is a natural female voice.
- Actual WAV duration drives the 60–120 second gate, per-scene boundaries,
  and Tamil UTF-8 SRT. **Within each scene, word timing is estimated**, not
  forced aligned. The reviewer must listen and inspect.
- CPU-friendly 720x1280 MP4: scene-specific Ken Burns zoom, no unsafe
  face-cropping, audio if enabled, external SRT. This is **animated still art,
  not real character-motion anime**. GPU video generation, subtitle burn-in,
  character continuity checks, 16:9 rendering and platform publishing are
  separate future integrations.
- JSON manifest with hashes, review status and an explicit publishing OFF gate.

## Oracle Ubuntu 24.04 ARM64 setup

Run these on the **Oracle SSH shell**, not local Android Termux:

    cd ~/cartoon-tamilan-automation
    git fetch origin feature/v14-story-video-voice-qa
    git worktree add -b v14-local-test ~/cartoon-tamilan-v14-test origin/feature/v14-story-video-voice-qa
    cd ~/cartoon-tamilan-v14-test
    sudo apt-get update
    sudo apt-get install -y ffmpeg fonts-noto-core libraqm0
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python -m unittest test_ct_v14.py -v

The separate worktree avoids changing the production checkout or V13 timers.
Do not merge or deploy before GitHub CI and human review.

Create a private UTF-8 script containing a **real approved 70–340 word
narration**, not a headline or invented story:

    mkdir -p private/v14_art
    nano private/approved_narration_ta.txt

Use 8 unique original scene illustrations named exactly:

    private/v14_art/scene_01.png
    private/v14_art/scene_02.png
    ...
    private/v14_art/scene_08.png

Each scene needs a visually distinct, story-accurate image at least 512x512.
PNG, JPG, JPEG and WebP are accepted. A GPU image generator may be used
separately with the approved story bible and proper commercial-use rights.

### Step 1: Offline, no-cost storyboard preview

    .venv/bin/python ct_v14.py plan \
      --script private/approved_narration_ta.txt \
      --scenes 8 --out output/v14/storyboard.json

Review each narration passage and corresponding image before proceeding.

### Step 2: Silent video test (no external AI calls)

    .venv/bin/python ct_v14.py build \
      --script private/approved_narration_ta.txt \
      --art-dir private/v14_art --scenes 8 \
      --voice none --target-seconds 90 \
      --rights-confirmed --copy-reviewed --visual-reviewed \
      --out output/v14/test

Outputs: storyboard.json, story_9x16.mp4, subtitles.srt, manifest.json.
This has **no voiceover**. It is only a motion-and-crop preview.

### Step 3: Natural Tamil female voice + full story MP4

Set your Azure Speech resource key and region privately. Do not commit keys
to GitHub, logs or screenshots.

    read -rs AZURE_SPEECH_KEY
    export AZURE_SPEECH_KEY
    export AZURE_SPEECH_REGION=centralindia

Use the **actual region** of your Speech resource; centralindia is just an
example. A service plan/quota may charge per character. Each scene is sent
to the configured provider; confirm content privacy and processing terms.

    .venv/bin/python ct_v14.py build \
      --script private/approved_narration_ta.txt \
      --art-dir private/v14_art --scenes 8 \
      --voice azure \
      --rights-confirmed --copy-reviewed --visual-reviewed \
      --out output/v14/female_test

Outputs also include narration.wav and scene_voice/*.wav.
If the **real speech duration** is outside 60–120 seconds, V14 fails
closed: revise the approved script and run again. No silent fallback.
The SRT is external, not burned into the video. Check voice pronunciation,
pacing, subtitles and character consistency manually.

### Android phone gallery transfer

V13 phone-side gallery sync is unchanged. To pull V14 MP4 manually from
**local Termux after exiting SSH**:

    mkdir -p ~/storage/movies/CartoonTamilanV14
    scp -i ~/.ssh/oracle_key \
      ubuntu@YOUR_ORACLE_HOST:cartoon-tamilan-v14-test/output/v14/female_test/story_9x16.mp4 \
      ~/storage/movies/CartoonTamilanV14/

Replace YOUR_ORACLE_HOST with your own Oracle host. If SSH key permissions
or path differ, use the working V13 Termux SSH configuration.

## Remaining engineering, explicitly not yet implemented

- GPU/API original character-consistent scene generation and actual anime
  character animation (not just Ken Burns stills).
- Tamil speech forced alignment and automatic phoneme/pronunciation scoring.
- Burned-in Tamil captions, 16:9 long-form video and responsive safe zones.
- Platform-specific OAuth uploads, analytics, consent-based email campaigns,
  job queues, durable retries, cost budgets and advanced AI orchestration.
- Source text ownership and semantic scene accuracy cannot be proven by code.

## Safe rollback

Use the isolated test worktree; leave the production main checkout alone.
This branch does not alter existing timers or .env. Do not run git pull
--ff-only in the production checkout to try to install V14. Keep generated outputs and
private narration/artwork out of GitHub.
