"""Optional media stage for the hourly original-story queue.

It creates title-inspired draft media only; generated assets require review.
The existing scheduler's live publisher only publishes image posts, not Reels.
"""
from __future__ import annotations

import math
import wave
import hashlib
import json
import os
import re
import tempfile
import shutil
import subprocess
from pathlib import Path

import requests

from ct_multimedia import generate_image, generate_video, generate_voice
from ctos.creative import render_pack
from ctos.platforms import PLATFORM_IMAGE
from ctos.qa import validate_assets
from v12_story_reader import owned_story_url


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(path)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _enabled() -> bool:
    hourly = os.getenv("CT_V14_HOURLY_MEDIA_ENABLED", "false").lower() == "true"
    api_mode = os.getenv("ENABLE_AI_MEDIA_API", "false").lower() == "true"
    local_video = os.getenv("CT_V14_LOCAL_VIDEO_ENABLED", "false").lower() == "true"
    return hourly and (api_mode or local_video)


def _mux_voice(video: Path, voice: Path, output: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg unavailable; keep separate video and voice assets")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-i", str(voice),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart", str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=180, check=False)
    if result.returncode or not output.is_file() or output.stat().st_size < 1024:
        output.unlink(missing_ok=True)
        raise RuntimeError("Could not combine short video and voice track")
    return output




def _scene_picture(index, passage, cover, scene_dir, destination, used,
                   dimensions=(720, 1280)):
    """Use numbered episode artwork, then original local interlude illustrations."""
    from PIL import Image, ImageOps

    candidates = [scene_dir / f"scene_{index + 1:02d}.{ext}"
                  for ext in ("png", "jpg", "jpeg", "webp")]
    if index == 0:
        candidates.append(cover)
    for path in candidates:
        if not path.is_file():
            continue
        with Image.open(path) as source:
            picture = ImageOps.contain(source.convert("RGB"), dimensions)
        digest = hashlib.sha256(picture.tobytes()).digest()
        if digest not in used:
            used.add(digest)
            canvas = Image.new("RGB", dimensions, "#101827")
            canvas.paste(picture, ((720-picture.width)//2, (1280-picture.height)//2))
            canvas.save(destination)
            return
    # Keep the episode's visual identity when numbered scene illustrations are missing.
    # Alternate framing on its own artwork; never illustrate invented events.
    with Image.open(cover) as original:
        source = original.convert("RGB")
    anchors = ((0.5, 0.5), (0.25, 0.42), (0.75, 0.45), (0.5, 0.62))
    canvas = ImageOps.fit(source, dimensions, centering=anchors[index % len(anchors)])
    canvas.save(destination)



def _voice_timeline(cues, seconds, work, scene_dir):
    """Pad each spoken line to its scene boundary on the 24 fps timeline."""
    from v12_voice import synthesize

    provider = os.getenv("CT_V14_REEL_VOICE", "indic_tiny").strip().lower()
    if provider not in {"espeak", "recorded", "azure", "indic_tiny"}:
        raise ValueError("Expected CT_V14_REEL_VOICE=espeak, recorded, azure or indic_tiny")
    rate_target = "24000" if provider == "azure" else "22050"
    neural = None
    if provider == "indic_tiny":
        import sys
        configured_model_dir = os.getenv("CT_TAMIL_MODEL_DIR", "").strip()
        if configured_model_dir:
            model_dir = Path(configured_model_dir).expanduser().resolve(strict=True)
        else:
            # Free, pinned Tamil female TTS model; Hugging Face caches it for later runs.
            from huggingface_hub import HfApi, snapshot_download
            model_repo = "sulabhkatiyar/indic-tiny-tts-tamil"
            model_revision = HfApi().model_info(model_repo, revision="c3a32ec").sha
            model_dir = Path(snapshot_download(
                repo_id=model_repo, revision=model_revision,
                ignore_patterns=["*.safetensors", "samples/*", "assets/*"],
            )).resolve(strict=True)
        if str(model_dir) not in sys.path:
            sys.path.insert(0, str(model_dir))
        from indic_tiny_tts import TinyTTSOnnx
        neural = TinyTTSOnnx.from_pretrained(str(model_dir))
        rate_target = "24000"
    boundaries = [0]
    with wave.open(str(work / "narration.wav"), "wb") as track:
        for index, caption in enumerate(cues):
            spoken = caption.split("\nCartoonTamilan.in")[0].replace(" · ", ". ")
            # An episode editor can supply a recorded reading for this exact cue.
            path = scene_dir / f"voice_{index+1:02d}.wav"
            transcript = path.with_suffix(".txt")
            if path.is_file() and transcript.is_file() and transcript.read_text(encoding="utf-8").strip() == spoken:
                converted = work / f"line_{index}.wav"
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                                "-ar", rate_target, "-ac", "1", "-c:a", "pcm_s16le", str(converted)],
                               check=True, timeout=120)
                path = converted
            elif provider == "recorded":
                raise ValueError(f"Missing matching Tamil recording for scene {index + 1}")
            elif neural is not None:
                path = work / f"line_{index}.wav"
                samples = neural.synthesize(spoken, voice="female", seed=0)
                neural.save_wav(samples, str(path))
            elif provider == "azure":
                from ctos.v14_voice import azure_tamil_female
                path = azure_tamil_female(spoken, work / f"line_{index}.wav",
                                          rights_confirmed=True)
            else:
                path = synthesize(spoken, work / f"line_{index}.wav", lang="ta",
                                  rights_confirmed=True)
            if provider == "indic_tiny":
                speed = float(os.getenv("CT_TAMIL_VOICE_SPEED", "1.3"))
                if not 1.3 <= speed <= 1.5:
                    raise ValueError("CT_TAMIL_VOICE_SPEED must be between 1.3 and 1.5")
                faster = work / f"tempo_{index}.wav"
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                                "-af", f"atempo={speed}", str(faster)], check=True, timeout=120)
                path = faster
            with wave.open(str(path), "rb") as clip:
                rate = clip.getframerate()
                if clip.getnchannels() != 1 or clip.getsampwidth() != 2:
                    raise ValueError("Expected mono 16-bit narration")
                if index == 0:
                    track.setparams(clip.getparams())
                elif rate != track.getframerate():
                    raise ValueError("Narration sample rate changed")
                count = clip.getnframes()
                samples = clip.readframes(count)
            slot = max(60, math.ceil(24 * count / rate) + 10)
            end = boundaries[-1] + slot
            length = end * rate // 24 - boundaries[-1] * rate // 24
            track.writeframesraw(samples + bytes(2 * (length - count)))
            boundaries.append(end)
    return boundaries


def _split_cues(text: str, limit: int = 150) -> list[str]:
    """Split source text into short Tamil-readable narration/subtitle units."""
    source = re.sub(r"\s+", " ", str(text or "")).strip()
    if not source:
        return []
    sentences = re.split(r"(?<=[.!?…।])\s+", source)
    cues, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit + 1)
            if cut < limit // 2:
                cut = limit
            part, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            if current:
                cues.append(current)
                current = ""
            if part:
                cues.append(part)
        if not sentence:
            continue
        candidate = (current + " " + sentence).strip()
        if len(candidate) > limit and current:
            cues.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        cues.append(current)
    return cues


def _chapter_text(url: str) -> str:
    """Retrieve only an owned public chapter; return the source text without rewriting."""
    from v12_story_reader import _get_html, extract_chapter_text
    if not owned_story_url(url):
        raise ValueError("Full episode narration requires an owned HTTPS chapter URL")
    session = requests.Session()
    session.headers.update({"User-Agent": "CartoonTamilanEpisodeRenderer/1.0"})
    text = extract_chapter_text(_get_html(url, session), limit_chars=1000000)
    if len(text) < 120:
        raise ValueError("Could not extract readable chapter text from the owned story page")
    return text


def _episode_reel(story: dict, artwork: Path, folder: Path, seconds: int,
                  scene_dir: Path, *, narration_text: str | None = None,
                  output_name: str = "teaser.mp4", is_full_episode: bool = False) -> Path:
    """Render a source-faithful vertical episode video with Tamil subtitles and voice."""
    from poster_generator import find_font, lines_for, require_tamil_shaping
    from PIL import Image, ImageDraw, ImageFont
    require_tamil_shaping()

    title = " ".join(story["title"].split())
    number = story.get("episode_number")
    label = f"எபிசோடு {number}" if number else "தமிழ்க் கதை"
    opening = title if len(title) <= 70 else label
    source_text = str(narration_text or story.get("summary") or "").strip()
    if not source_text:
        raise ValueError("No story text available for voice-over")
    body_cues = _split_cues(source_text, 150)
    if is_full_episode:
        cues = [opening, *body_cues]
    else:
        # Limit Reels to an opening excerpt; the full chapter gets its own YouTube cut.
        max_chars = max(900, min(2500, seconds * 18))
        excerpt = source_text[:max_chars]
        last_stop = max(excerpt.rfind(mark) for mark in (". ", "! ", "? ", "… ", "। "))
        if last_stop >= max_chars // 2:
            excerpt = excerpt[:last_stop + 1]
        cues = [opening, *_split_cues(excerpt, 150),
                f"{label} · முழு எபிசோடைப் படிக்கவும்\nCartoonTamilan.in"]

    folder.mkdir(parents=True, exist_ok=True)
    frame_width, frame_height = (1280, 720) if is_full_episode else (720, 1280)
    frame_size = (frame_width, frame_height)
    frames = seconds * 24
    font = Path(find_font()).resolve()

    with tempfile.TemporaryDirectory(dir=folder) as temp:
        work = Path(temp)

        voiced = os.getenv("CT_V14_LOCAL_VOICE_ENABLED", "true").lower() == "true"
        boundaries = (_voice_timeline(cues, seconds, work, scene_dir) if voiced else
                      [frames * i // len(cues) for i in range(len(cues) + 1)])
        actual_seconds = boundaries[-1] / 24
        if voiced and not is_full_episode and not 60 <= actual_seconds <= 180:
            raise ValueError(
                f"Reel voice duration {actual_seconds:.1f}s is outside the requested 60–180s range"
            )
        def stamp(ms):
            return f"00:{ms // 60000:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
        blocks = []
        for index, line in enumerate(cues):
            # SRT is interpreted by libass. Keep chapter content as plain text.
            line = re.sub(r"[<>{}\\]", "", line)
            start = stamp(round(boundaries[index] * 1000 / 24))
            end = stamp(round(boundaries[index + 1] * 1000 / 24))
            blocks.append(f"{index + 1}\n{start} --> {end}\n{line}\n")
        subtitles = work / "subtitles.srt"
        subtitles.write_text("\n".join(blocks), encoding="utf-8")
        inputs, filters, used = [], [], set()
        for index, cue in enumerate(cues):
            image = work / f"shot_{index}.png"
            _scene_picture(index, cue, artwork, scene_dir, image, used, frame_size)
            with Image.open(image) as source:
                frame = source.convert("RGB")
            draw = ImageDraw.Draw(frame)
            for size in range(44, 25, -2):
                face = ImageFont.truetype(str(font), size, layout_engine=ImageFont.Layout.RAQM)
                try:
                    lines = [line for paragraph in cue.splitlines()
                             for line in lines_for(draw, paragraph, face, frame_width - 110)]
                except ValueError:
                    continue
                step = sum(face.getmetrics()) + 5
                if len(lines) * step <= frame_height // 2:
                    break
            else:
                raise ValueError("Caption exceeds the safe reading area")
            top = frame_height - 90 - step * len(lines)
            draw.rounded_rectangle((38, top-18, frame_width-38, frame_height-70),
                                   radius=18, fill="#101827")
            for line in lines:
                draw.text((frame_width // 2, top), line, font=face,
                          anchor="ma", fill="white")
                top += step
            frame.save(image)
            inputs.extend(["-i", image.name])
            shot_frames = boundaries[index + 1] - boundaries[index]
            filters.append(
                f"[{index}:v]zoompan=z='1+0.04*on/{shot_frames}':"
                f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={shot_frames}:"
                f"s={frame_width}x{frame_height}:fps=24,setsar=1,format=yuv420p[s{index}]"
            )
        sequence = "".join(f"[s{i}]" for i in range(len(cues)))
        filters.append(sequence + f"concat=n={len(cues)}:v=1:a=0[out]")
        audio = ["-an"]
        if voiced:
            inputs.extend(["-i", "narration.wav"])
            audio = ["-map", f"{len(cues)}:a:0", "-af", "highpass=f=65,loudnorm=I=-17:TP=-1.5:LRA=8", "-ar", "48000", "-c:a", "aac", "-b:a", "128k"]
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *inputs,
                        "-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                        "-map", "[out]", *audio,
                        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", output_name], cwd=work,
                       check=True, timeout=300)
        if voiced:
            (work / "narration.wav").replace(folder / "narration.wav")
        subtitles.replace(folder / "subtitles.srt")
        (work / output_name).replace(folder / output_name)
    return folder / output_name


def prepare_hourly_media(outdir: str | Path) -> dict:
    """Generate opted-in promo image/short video/CTA voice for one owned story."""
    if not _enabled():
        return {"status": "disabled", "generated": []}

    root = Path(outdir).resolve()
    preview_path = root / "image_post_preview.json"
    if not preview_path.is_file():
        return {"status": "no_story_preview", "generated": []}
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    manifests = preview.get("story_manifests", [])
    if not manifests:
        return {"status": "no_story_manifest", "generated": []}

    manifest_path = (root / manifests[0]).resolve()
    if not manifest_path.is_relative_to(root) or not manifest_path.is_file():
        return {"status": "invalid_story_manifest", "generated": []}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    story = manifest.get("story", {})
    title = str(story.get("title", "")).strip()
    story_url = str(story.get("link", "")).strip()
    if not title or not owned_story_url(story_url):
        return {"status": "invalid_owned_story", "generated": []}

    key = hashlib.sha256(story_url.encode("utf-8")).hexdigest()[:16]
    target = root / "hourly_media" / key
    target.mkdir(parents=True, exist_ok=True)

    # Zero-API CPU mode: turn the existing reviewed story artwork into a
    # motion-comic MP4 with subtitles. This is not generative text-to-video.
    local_video = os.getenv("CT_V14_LOCAL_VIDEO_ENABLED", "false").lower() == "true"
    api_enabled = os.getenv("ENABLE_AI_MEDIA_API", "false").lower() == "true"
    if local_video:
        try:
            assets = manifest.get("assets", {})
            poster_rel = (manifest.get("source_artwork") or assets.get("instagram_story")
                          or assets.get("instagram_feed"))
            if not isinstance(poster_rel, str) or not poster_rel:
                raise ValueError("Story artwork is missing")
            poster = (manifest_path.parent / poster_rel).resolve()
            if not poster.is_relative_to(root) or not poster.is_file():
                raise ValueError("Story artwork is outside the approved output folder")
            try:
                reel_seconds = max(60, min(int(os.getenv(
                    "CT_V14_REEL_SECONDS", "90")), 180))
            except ValueError:
                reel_seconds = 90
            chapter = _chapter_text(story_url)
            reel_dir = target / "reel"
            long_dir = target / "youtube_full_episode"
            reel_path = _episode_reel(
                story, poster, reel_dir, reel_seconds, manifest_path.parent / "scenes",
                narration_text=chapter, output_name="reel_9x16.mp4",
            )
            long_seconds = max(60, min(3600, len(chapter) // 12))
            long_path = _episode_reel(
                story, poster, long_dir, long_seconds, manifest_path.parent / "scenes",
                narration_text=chapter, output_name="youtube_full_episode_16x9.mp4",
                is_full_episode=True,
            )
            video_path = reel_path
            if not video_path.is_relative_to(root) or not video_path.is_file():
                raise ValueError("Local motion video was not created safely")
            if not long_path.is_relative_to(root) or not long_path.is_file():
                raise ValueError("YouTube full-episode video was not created safely")
            video_rel = str(reel_path.relative_to(root))
            long_rel = str(long_path.relative_to(root))
            generated = ["reel_1_to_3_minutes", "full_chapter_youtube_video",
                         "source_text_tamil_subtitles"]
            voiced = os.getenv("CT_V14_LOCAL_VOICE_ENABLED", "true").lower() == "true"
            if voiced:
                generated.extend(["voice", "video_with_voice"])
            preview["generated_media"] = [{
                "story_url": story_url,
                "story_title": title,
                "video_file": video_rel,
                "video_sha256": _sha(reel_path),
                "video_with_voice_file": video_rel if voiced else None,
                "video_with_voice_sha256": _sha(reel_path) if voiced else None,
                "youtube_full_episode_file": long_rel,
                "youtube_full_episode_sha256": _sha(long_path),
                "youtube_full_episode_voice_file": (
                    str(Path(long_rel).with_name("narration.wav")) if voiced else None
                ),
                "reel_subtitles_file": str(Path(video_rel).with_name("subtitles.srt")),
                "youtube_full_episode_subtitles_file": str(
                    Path(long_rel).with_name("subtitles.srt")
                ),
                "youtube_full_episode_caption": (
                    f"{title} | Full Tamil Story Episode\n\n"
                    f"இந்த வீடியோவில் இணையதள அத்தியாயத்தின் முழு தமிழ் narration உள்ளது.\n"
                    f"Read the original Tamil episode: {story_url}\n"
                    "Original Tamil stories and anime-style fiction from CartoonTamilan.in.\n\n"
                    "#TamilStories #TamilStory #TamilAnime #CartoonTamilan"
                ),
                "reel_caption": (
                    f"{title} | Tamil Story Reel\n\n"
                    f"இந்த அத்தியாயத்தின் காட்சிகளைப் பாருங்கள். முழு கதை: {story_url}\n"
                    "Discover original Tamil stories at CartoonTamilan.in.\n\n"
                    "#TamilStories #TamilReels #TamilAnime #CartoonTamilan"
                ),
                "voice_file": str(Path(video_rel).with_name("narration.wav")) if voiced else None,
                "source_text_chars": len(chapter),
                "voice_speed": float(os.getenv("CT_TAMIL_VOICE_SPEED", "1.3")),
                "reel_duration_target_seconds": reel_seconds,
                "generated": generated,
                "status": "draft_review_required",
                "published": False,
                "requires_human_review": True,
                "story_accuracy": "narration uses extracted owned chapter text verbatim; artwork is motion-comic stills",
            }]
            preview["multimedia_generation"] = {
                "status": "generated_local_episode_videos",
                "generated": generated,
                "errors": [],
                "published": False,
                "provider": "local_ffmpeg",
            }
            _write_json(preview_path, preview)
            return {
                "status": "generated_local_episode_videos",
                "generated": generated,
                "errors": [],
                "story_url": story_url,
                "reel_file": video_rel,
                "youtube_full_episode_file": long_rel,
                "voice_speed": float(os.getenv("CT_TAMIL_VOICE_SPEED", "1.3")),
                "published": False,
            }
        except Exception as exc:
            preview["generated_media"] = []
            preview["multimedia_generation"] = {
                "status": "failed",
                "generated": [],
                "errors": [{"asset": "local_video",
                            "error_type": type(exc).__name__}],
                "published": False,
                "provider": "local_ffmpeg",
            }
            _write_json(preview_path, preview)
            return {
                "status": "failed",
                "generated": [],
                "errors": [{"asset": "local_video",
                            "error_type": type(exc).__name__}],
                "story_url": story_url,
                "published": False,
            }

    prompt = (
        "Create a polished, original, text-free cinematic anime illustration "
        "for a Tamil novel promotion. Use only the story title as a broad mood "
        "cue; do not infer or depict specific plot events, characters, places, "
        "costumes, weapons or relationships. No logos, letters or watermark. "
        f"Story title: {title}"
    )
    generated = []
    errors = []
    image_file = voice_file = video_file = combined_file = None

    try:
        image_provider = os.getenv("CT_V14_QUEUE_IMAGE_PROVIDER", "gemini").strip()
        image_file = generate_image(
            prompt, manifest_path.parent / "hourly_ai_source_art.png",
            provider=image_provider,
            aspect_ratio="4:5", rights_confirmed=True,
        )
        title_for_poster = manifest.get("title") or title[:85]
        pack = render_pack(
            image_file, title_for_poster,
            manifest_path.parent / "hourly_ai_creatives",
            story_url=story_url,
        )
        assets = {
            kind: str(Path(row["file"]).resolve().relative_to(manifest_path.parent.resolve()))
            for kind, row in pack["assets"].items()
        }
        audit = validate_assets(manifest_path.parent, assets)
        if not audit.get("passed"):
            raise RuntimeError("AI poster artwork failed image quality checks")
        manifest["source_artwork"] = str(
            image_file.resolve().relative_to(manifest_path.parent.resolve())
        )
        manifest["assets"] = assets
        manifest["art_provenance"] = {
            "backend": image_provider,
            "generated": True,
            "story_accuracy": "title-inspired generic art; plot accuracy not claimed",
            "review_required": True,
        }
        manifest["art_prompt"] = prompt
        manifest["creative_qa"] = audit
        manifest["visual_reviewed"] = False
        manifest["status"] = "draft_review_required"
        manifest["published"] = False
        _write_json(manifest_path, manifest)
        # Update already-exported platform drafts from the source manifest.
        from ctos.platforms import export_platform_drafts
        export_platform_drafts(manifest_path)
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
        for post in preview.get("posts", []):
            if post.get("story_url") != story_url:
                continue
            variant = PLATFORM_IMAGE.get(post.get("platform"))
            if variant not in pack["assets"]:
                continue
            image = Path(pack["assets"][variant]["file"]).resolve()
            post["image_file"] = str(image.relative_to(root))
            post["image_sha256"] = _sha(image)
            post["dimensions"] = list(pack["assets"][variant]["size"])
            post["artwork_provider"] = image_provider
            post["status"] = "draft_review_required"
            post["published"] = False
        preview["art_mode"] = "ai_provider"
        generated.append("image")
    except Exception as exc:
        errors.append({"asset": "image", "error_type": type(exc).__name__})

    if not image_file:
        preview["generated_media"] = []
        preview["multimedia_generation"] = {
            "status": "failed", "generated": [],
            "errors": errors, "published": False,
        }
        _write_json(preview_path, preview)
        return {
            "status": "failed", "generated": [], "errors": errors,
            "story_url": story_url, "published": False,
        }

    voice_text = (
        f"{title}. கார்ட்டூன் தமிழனில் அசல் தமிழ் கதையைப் படியுங்கள்."
    )
    try:
        voice_provider = os.getenv("CT_V14_QUEUE_VOICE_PROVIDER", "azure").strip()
        extension = "wav" if voice_provider == "azure" or voice_provider == "gemini" else "mp3"
        voice_file = generate_voice(
            voice_text, target / f"story_cta.{extension}",
            provider=voice_provider, language="ta-IN",
            style="Warm, clear Tamil promotional narration.",
            rights_confirmed=True,
        )
        generated.append("voice")
    except Exception as exc:
        errors.append({"asset": "voice", "error_type": type(exc).__name__})

    try:
        video_provider = os.getenv("CT_V14_QUEUE_VIDEO_PROVIDER", "xai").strip()
        duration = max(1, min(int(os.getenv("CT_V14_QUEUE_VIDEO_SECONDS", "8")), 15))
        video_file = generate_video(
            "Create an original, atmospheric, text-free animated promo teaser "
            "for a Tamil novel. Use only the title as a broad mood cue; do not "
            "invent named characters or plot events. No logos, captions or watermark. "
            f"Title: {title}",
            target / "story_teaser.mp4", provider=video_provider,
            duration_seconds=duration, rights_confirmed=True,
        )
        generated.append("video")
        if voice_file:
            try:
                combined_file = _mux_voice(
                    video_file, voice_file, target / "story_teaser_with_voice.mp4"
                )
                generated.append("video_with_voice")
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                errors.append({"asset": "video_voice_mux", "error_type": type(exc).__name__})
    except Exception as exc:
        errors.append({"asset": "video", "error_type": type(exc).__name__})

    if image_file:
        preview["generated_media"] = [{
            "story_url": story_url,
            "story_title": title,
            "image_file": str(image_file.resolve().relative_to(root)),
            "image_sha256": _sha(image_file),
            "voice_file": (
                str(voice_file.resolve().relative_to(root)) if voice_file else None
            ),
            "video_file": (
                str(video_file.resolve().relative_to(root)) if video_file else None
            ),
            "video_sha256": _sha(video_file) if video_file else None,
            "video_with_voice_file": (
                str(combined_file.resolve().relative_to(root))
                if combined_file else None
            ),
            "video_with_voice_sha256": _sha(combined_file) if combined_file else None,
            "generated": generated,
            "status": "draft_review_required",
            "published": False,
            "requires_human_review": True,
            "story_accuracy": "title-inspired promo; not a plot summary or full-story narration",
        }]
    else:
        preview["generated_media"] = []
    preview["multimedia_generation"] = {
        "status": "partial" if errors else "generated",
        "generated": generated,
        "errors": errors,
        "published": False,
    }
    _write_json(preview_path, preview)
    return {
        "status": preview["multimedia_generation"]["status"],
        "generated": generated,
        "errors": errors,
        "story_url": story_url,
        "published": False,
    }


__all__ = ["prepare_hourly_media"]
