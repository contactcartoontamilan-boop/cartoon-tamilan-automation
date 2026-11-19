# Multi-model AI and media adapters

The project has a private server-side router for model text and opt-in media
generation. Provider capability varies; each operation uses a provider key and
model that must be enabled for the account.

| Capability | Available providers |
|---|---|
| Text | OpenAI, Anthropic Claude, Google Gemini, xAI Grok, local Ollama |
| Image generation | OpenAI, Google Gemini, xAI Grok |
| Short AI video | xAI Grok Imagine Video |
| Voice generation | OpenAI, Google Gemini, xAI Grok, existing Azure Tamil female voice |
| 60–120s story video | Existing FFmpeg montage from approved images + narration; not generated animation |

## Configure Oracle

Add provider keys only to Oracle's private `.env`, never source files or GitHub.
Set model names that are enabled for your provider account.

```dotenv
AI_PROVIDER=ollama
AI_MAX_OUTPUT_TOKENS=1200
AI_DAILY_REQUEST_LIMIT=20
AI_USAGE_DB=data/ai_usage.sqlite3

OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=coral

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=

GEMINI_API_KEY=
GEMINI_MODEL=
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
GEMINI_TTS_MODEL=gemini-3.8-flash-tts
GEMINI_TTS_VOICE=Kore

XAI_API_KEY=
XAI_MODEL=
XAI_IMAGE_MODEL=grok-imagine-image-2.0
XAI_VIDEO_MODEL=grok-imagine-video-1.5
XAI_TTS_VOICE=eve

ENABLE_AI_MEDIA_API=false
```

The media API gate defaults to off. To enable the selected external media
provider, set `ENABLE_AI_MEDIA_API=true` on Oracle. The software request budget
defaults to 20 requests per provider per UTC day and is shared with text calls.
Set `AI_DAILY_REQUEST_LIMIT=0` only if you deliberately want to remove that
software-side request cap; provider quotas and charges still apply. Each media
operation requires `--rights-confirmed` in the CLI or the equivalent Python flag.
This is a content-rights confirmation, not an auto-publishing switch.

Local Ollama text inference can avoid per-token API charges, but the Oracle A1
host is CPU-only and may be too slow or low-memory for larger models. Hosting,
storage and compute can still cost money. The local image option in the existing
project uses ComfyUI and separately requires model weights and compute.

## Generate a draft asset from Oracle

Install the repository's requirements and FFmpeg where needed. Commands create
files on Oracle; they do not publish to Facebook/Instagram or other platforms.

```sh
cd ~/cartoon-tamilan-v14-social-test
.venv/bin/python ct_multimedia.py image \
  --provider xai --input "An original fantasy-anime scene, moonlit forest" \
  --out output/ai/scene.png --rights-confirmed

.venv/bin/python ct_multimedia.py video \
  --provider xai --input "A short cinematic reveal of the original hero" \
  --duration 6 --out output/ai/teaser.mp4 --rights-confirmed

.venv/bin/python ct_multimedia.py voice \
  --provider azure --input "உங்கள் உரிமையுள்ள கதைக்கான தமிழ் narration." \
  --out output/ai/narration.wav --rights-confirmed
```

Use `--provider openai` or `gemini` for image/voice options; voice supports
`xai` too. AI video is currently xAI-only and returns a short generated clip
(up to 15 seconds). The existing story renderer can assemble approved scenes
into a longer montage, but does not create continuous character animation.
Azure voice uses the project's existing Tamil female neural voice adapter.

Python callers can use `generate_image`, `generate_video`, and
`generate_voice` from `ct_multimedia.py`. These adapters are not yet invoked
automatically by the hourly social queue; connect them to an approved story
pipeline and review the generated script/art before turning on publication.

## Provider docs

- OpenAI image/audio: https://platform.openai.com/docs
- Gemini image generation: https://ai.google.dev/gemini-api/docs/image-generation
- Gemini speech generation: https://ai.google.dev/gemini-api/docs/speech-generation
- xAI image generation: https://docs.x.ai/developers/rest-api-reference/inference/images
- xAI video generation: https://docs.x.ai/developers/rest-api-reference/inference/videos
- xAI text-to-speech: https://docs.x.ai/developers/model-capabilities/audio/text-to-speech
- Azure Speech Tamil female adapter: `ctos/v14_voice.py`

Cloud media generation is not unlimited and may incur usage charges. ChatGPT
subscription access does not by itself provide OpenAI API or image/audio API
credits. For example, Gemini offers limited free tiers for some APIs/models;
check provider account quotas and prices before enabling generation.
