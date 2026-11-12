# CartoonTamilan V14: safe 60–120 second story-video preview

This is an incremental, testable code change, not a claim that every AI
marketing integration is finished. It does not modify the V13 daily timer or
enable posting. Nothing is published or emailed by this workflow.

## What the code actually does

- Requires a reviewed JSON storyboard with 6–16 different authorized images.
  Duplicate image bytes are rejected, preventing one cover from being recycled
  as every scene.
- Supports a provided licensed narration WAV/MP3/M4A or optional Azure neural
  Tamil TTS. The Azure voice defaults to ta-IN-PallaviNeural, but available
  voices and quota must be checked in the owner's Azure region.
  The espeak fallback is mechanical and is NOT a soft female AI voice.
- Reads actual narration duration with ffprobe and requires 60–120 seconds.
- Uses FFmpeg for 720x1280, 24fps, gentle pan/zoom across distinct scenes.
  This is animated still artwork, NOT generative anime character motion.
- Produces MP4, WAV/other input audio, UTF-8 SRT and a manifest. Subtitle
  timing is estimated from scene text, NOT forced word alignment.
- Requires rights confirmation and human visual/audio review.
  The output manifest always reports draft_ready_review_required and
  published=false.

## Test on a development branch (Oracle SSH)

Do not deploy a PR branch into production auto-sync main before reviewing it.

    sudo apt-get update
    sudo apt-get install -y ffmpeg fonts-noto-core libraqm0
    .venv/bin/python -m unittest test_ct_v14.py -v
    .venv/bin/python -m unittest test_ct_v13.py -v

## Prepare an authorized storyboard

Save a JSON file under data/v14_storyboard.json on Oracle. Do not commit
copyrighted chapters or private media to GitHub.

    {
      "title": "Your approved original Tamil story title",
      "story_url": "https://cartoontamilan.in/your-story/",
      "scenes": [
        {"image": "v14_scenes/01.png", "narration": "Replace with the accurate original Tamil narration for scene one."},
        {"image": "v14_scenes/02.png", "narration": "Replace with the accurate original Tamil narration for scene two."},
        {"image": "v14_scenes/03.png", "narration": "Replace with the accurate original Tamil narration for scene three."},
        {"image": "v14_scenes/04.png", "narration": "Replace with the accurate original Tamil narration for scene four."},
        {"image": "v14_scenes/05.png", "narration": "Replace with the accurate original Tamil narration for scene five."},
        {"image": "v14_scenes/06.png", "narration": "Replace with the accurate original Tamil narration for scene six."},
        {"image": "v14_scenes/07.png", "narration": "Replace with the accurate original Tamil narration for scene seven."},
        {"image": "v14_scenes/08.png", "narration": "Replace with the accurate original Tamil narration for scene eight."}
      ]
    }

Replace all English placeholders with accurate original Tamil script and use
eight different scene images under data/v14_scenes. Narration must last
60–120 seconds. Image generation is NOT performed by this command. Scene
images may come from owned artwork or separately configured AI generation.

## Preferred: recorded soft female Tamil narration

    .venv/bin/python ct_master.py story-video \
      --storyboard data/v14_storyboard.json \
      --audio /home/ubuntu/private/approved_tamil_voice.wav \
      --rights-confirmed \
      --outdir output/v14/my_story

## Optional: Azure neural Tamil narration

On Oracle, put credentials only in private environment configuration; never
in source code, GitHub, or screenshots:

    export CT_AZURE_SPEECH_REGION="your-azure-region"
    export CT_AZURE_SPEECH_KEY="your-private-key"
    export CT_AZURE_TTS_VOICE="ta-IN-PallaviNeural"

Then:

    .venv/bin/python ct_master.py story-video \
      --storyboard data/v14_storyboard.json \
      --tts azure --rights-confirmed \
      --outdir output/v14/my_story

If Azure is unavailable, the CLI fails clearly rather than silently using
robotic audio. For a mechanical, free, offline fallback, install espeak-ng and
use --tts espeak instead.

The speech may need pronunciation edits, pacing adjustments and a reviewed
phonetic glossary. Neural speech does NOT guarantee perfect Tamil.

## Outputs

    output/v14/my_story/full_story_9x16.mp4
    output/v14/my_story/narration.wav
    output/v14/my_story/subtitles.srt
    output/v14/my_story/story_video_manifest.json

The MP4 contains scene motion and narration; subtitles are external SRT.
Review the MP4 on the phone and check every Tamil word, visual, scene
sequence, duration and subtitle. This workflow does not claim lip-sync,
anime character movement, automatic story summarization or social posting.

## Android gallery sync (phone Termux only)

After the branch has been reviewed and merged, and V14 previews exist on Oracle:

    exit
    pkg install rsync -y
    cd ~/cartoon-tamilan-automation
    git pull --ff-only
    bash phone_gallery_sync_v14.sh

The script copies output/v14 media into Pictures/CartoonTamilanV14 without
deleting or overwriting existing photos.

## Troubleshooting

- espeak-ng sounds robotic: expected. Use a licensed real narrator or neural TTS.
- Narration must be 60–120 seconds: revise the verified script or voice rate.
- Scene reuses identical artwork: supply different artwork for that scene.
- Storyboard timings differ: remove all duration_seconds keys for approximate
  automatic timing or edit all to match the actual WAV.
- FFmpeg failed: inspect the terminal error tail and verify ffmpeg/ffprobe.
  Rendering 60–120 seconds on Oracle ARM64 CPU can be slow.
- Azure speech HTTP error: verify region, voice, subscription, quota and network
  without exposing credentials.

## Remaining work

This PR does not implement generative scene video, automatic character
consistency, forced subtitle alignment, full Tamil pronunciation QA,
all-platform OAuth posting, live A/B testing, or subscriber scheduling.
Those need provider credentials, test data, additional modules and explicit
review/consent gates. The ongoing deep research can guide subsequent work.
