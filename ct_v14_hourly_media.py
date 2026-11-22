"""Optional media stage for the hourly original-story queue.

It creates title-inspired draft media only; generated assets require review.
The existing scheduler's live publisher only publishes image posts, not Reels.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import shutil
import subprocess
from pathlib import Path

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



def _episode_reel(story: dict, artwork: Path, folder: Path, seconds: int) -> Path:
    """Burn complete source sentences into a gently moving vertical teaser."""
    from poster_generator import find_font
    from PIL import ImageFont

    title = " ".join(story["title"].split())
    number = story.get("episode_number")
    label = f"எபிசோடு {number}" if number else "தமிழ்க் கதை"
    opening = title if len(title) <= 70 else label
    cues = [opening]
    # Discovery may truncate the summary mid-sentence. Skip its unfinished tail.
    for match in re.finditer(r"[^.!?…]+[.!?]+", story.get("summary") or ""):
        sentence = " ".join(match.group().split())
        if (re.search(r"[\u0b80-\u0bff]", sentence) and 8 <= len(sentence) <= 110
                and not sentence.endswith("..") and sentence not in cues):
            cues.append(sentence)
        if len(cues) == 3:
            break
    cues.append(f"{label} · முழுக் கதையைப் படிக்க\nCartoonTamilan.in")

    folder.mkdir(parents=True, exist_ok=True)
    frames = seconds * 24
    font = Path(find_font()).resolve()
    family = ImageFont.truetype(str(font), 24).getname()[0]
    with tempfile.TemporaryDirectory(dir=folder) as temp:
        work = Path(temp)
        shutil.copy2(font, work / ("caption" + font.suffix))
        def stamp(ms):
            return f"00:00:{ms // 1000:02d},{ms % 1000:03d}"
        blocks = []
        for index, line in enumerate(cues):
            # SRT is interpreted by libass. Keep chapter content as plain text.
            line = re.sub(r"[<>{}\\]", "", line)
            start = stamp(seconds * 1000 * index // len(cues))
            end = stamp(seconds * 1000 * (index + 1) // len(cues))
            blocks.append(f"{index + 1}\n{start} --> {end}\n{line}\n")
        subtitles = work / "subtitles.srt"
        subtitles.write_text("\n".join(blocks), encoding="utf-8")
        filters = (
            "scale=720:1280:force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x101827,setsar=1,"
            f"zoompan=z='1+0.06*on/{frames}':x='iw/2-iw/zoom/2':"
            f"y='ih/2-ih/zoom/2':d={frames}:s=720x1280:fps=24,"
            "subtitles=subtitles.srt:fontsdir=.:force_style='"
            f"FontName={family},FontSize=10,Outline=2,BorderStyle=3,"
            "BackColour=&H50000000,Alignment=2,MarginV=38,MarginL=18,MarginR=18'"
        )
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(artwork),
                        "-vf", filters, "-frames:v", str(frames), "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", "teaser.mp4"], cwd=work,
                       check=True, timeout=300)
        subtitles.replace(folder / "subtitles.srt")
        (work / "teaser.mp4").replace(folder / "teaser.mp4")
    return folder / "teaser.mp4"


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
    if local_video and not api_enabled:
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
                duration = max(8, min(int(os.getenv(
                    "CT_V14_LOCAL_VIDEO_SECONDS", "20")), 30))
            except ValueError:
                duration = 20
            video_path = _episode_reel(story, poster, target / "story_motion_comic", duration)
            if not video_path.is_relative_to(root) or not video_path.is_file():
                raise ValueError("Local motion video was not created safely")
            video_rel = str(video_path.relative_to(root))
            generated = ["motion_video", "subtitles"]
            preview["generated_media"] = [{
                "story_url": story_url,
                "story_title": title,
                "video_file": video_rel,
                "video_sha256": _sha(video_path),
                "video_with_voice_file": None,
                "video_with_voice_sha256": None,
                "voice_file": None,
                "generated": generated,
                "status": "draft_review_required",
                "published": False,
                "requires_human_review": True,
                "story_accuracy": "motion-comic from reviewed story artwork; no new plot facts",
            }]
            preview["multimedia_generation"] = {
                "status": "generated_local_motion_video",
                "generated": generated,
                "errors": [],
                "published": False,
                "provider": "local_ffmpeg",
            }
            _write_json(preview_path, preview)
            return {
                "status": "generated_local_motion_video",
                "generated": generated,
                "errors": [],
                "story_url": story_url,
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
