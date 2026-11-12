"""V14 multi-scene, 60–120 second story-video PREVIEW assembler.

Input is a reviewed storyboard containing 6–16 distinct, licensed scene images
and corresponding truthful narration. Creates gentle Ken Burns motion (NOT
generative character animation), a voice track and estimated scene-level SRT.
No social publishing, scraping, or external image-generation happens here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from ctos.voice_v14 import synthesize_tamil

FPS = 24
MIN_SECONDS = 60
MAX_SECONDS = 120


def _timestamp(seconds):
    milliseconds = round(seconds * 1000)
    h, remainder = divmod(milliseconds, 3_600_000)
    m, remainder = divmod(remainder, 60_000)
    s, ms = divmod(remainder, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def read_storyboard(filename):
    """Resolve artwork paths relative to the JSON, rejecting duplicate scenes."""
    path = Path(filename).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 6 <= len(scenes) <= 16:
        raise ValueError("A full story requires 6 to 16 distinct scenes")
    prepared = []
    image_hashes = set()
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} is not an object")
        narration = scene.get("narration", "")
        if not isinstance(narration, str) or len(narration.strip()) < 20:
            raise ValueError(f"Scene {index} needs a reviewed narration of 20+ characters")
        name = scene.get("image")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Scene {index} has no image path")
        image_path = Path(name)
        if not image_path.is_absolute():
            image_path = path.parent / image_path
        image_path = image_path.resolve(strict=True)
        with Image.open(image_path) as opened:
            opened.verify()
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if digest in image_hashes:
            raise ValueError(
                f"Scene {index} reuses identical artwork; supply changing story images"
            )
        image_hashes.add(digest)
        duration = scene.get("duration_seconds")
        if duration is not None:
            if isinstance(duration, bool) or not isinstance(duration, (float, int)):
                raise ValueError(f"Scene {index} has invalid duration")
            if not math.isfinite(duration) or not 2 <= duration <= 40:
                raise ValueError(f"Scene {index} duration must be 2–40 seconds")
        prepared.append({
            "image": image_path,
            "narration": narration.strip(),
            "duration_seconds": duration,
        })
    if any(s["duration_seconds"] is not None for s in prepared) and not all(
        s["duration_seconds"] is not None for s in prepared
    ):
        raise ValueError("Either specify every scene duration or none")
    return data, prepared


def probe_audio_seconds(filename, executable=None):
    ffprobe = executable or shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe missing; install ffmpeg on Oracle")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(filename)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Cannot inspect narration audio with ffprobe")
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        raise RuntimeError("Narration audio duration is not readable") from None
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("Narration audio duration is invalid")
    return duration


def scene_frame_counts(scenes, audio_seconds):
    """Assign exact integer video frames, respecting explicit reviewed timings."""
    total_frames = round(audio_seconds * FPS)
    if not MIN_SECONDS * FPS <= total_frames <= MAX_SECONDS * FPS:
        raise ValueError("Narration must be 60–120 seconds; revise script or speech rate")
    manual = all(s["duration_seconds"] is not None for s in scenes)
    if manual:
        desired = [s["duration_seconds"] for s in scenes]
        if abs(sum(desired) - audio_seconds) > 0.35:
            raise ValueError(
                "Storyboard timings and actual voice duration differ by >0.35 seconds"
            )
    else:
        # Fallback is only approximate. For precise subtitles use forced alignment.
        desired = [max(1, len(s["narration"])) for s in scenes]
    weights = [d / sum(desired) for d in desired]
    frames = [round(total_frames * w) for w in weights]
    frames[-1] += total_frames - sum(frames)
    if any(n < 2 * FPS for n in frames):
        raise ValueError("One scene is under two seconds; revise narration/timings")
    return frames


def _caption_chunks(text, max_chars=64):
    chunks, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if line and len(candidate) > max_chars:
            chunks.append(line)
            line = word
        else:
            line = candidate
    if line:
        chunks.append(line)
    return chunks


def write_estimated_srt(scenes, frames, output):
    """Create scene-timed subtitles; timing is approximate, not word-aligned."""
    captions = []
    cue = 0
    start_frame = 0
    for scene, count in zip(scenes, frames):
        chunks = _caption_chunks(scene["narration"])
        weights = [max(1, len(part)) for part in chunks]
        total = sum(weights)
        boundaries = [start_frame]
        cumulative = 0
        for weight in weights[:-1]:
            cumulative += weight
            boundaries.append(start_frame + round(count * cumulative / total))
        boundaries.append(start_frame + count)
        for part, first, last in zip(chunks, boundaries, boundaries[1:]):
            if last <= first:
                continue
            cue += 1
            captions.append(
                f"{cue}\n{_timestamp(first / FPS)} --> "
                f"{_timestamp(last / FPS)}\n{part}\n"
            )
        start_frame += count
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(captions) + "\n", encoding="utf-8")
    return path


def _run_ffmpeg(args, *, timeout=600):
    result = subprocess.run(
        args, capture_output=True, text=True, check=False, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError("FFmpeg failed: " + result.stderr[-650:])


def _concat_path(path):
    # concat demuxer accepts single-quoted absolute paths.
    return str(path.resolve()).replace("\\", "\\\\").replace("'", "'\\''")


def build_full_story(storyboard, outdir, *, audio=None, tts=None,
                     rights_confirmed=False, speech_rate="-5%"):
    if not rights_confirmed:
        raise PermissionError("Confirm ownership/licensing of story, images and audio")
    if bool(audio) == bool(tts):
        raise ValueError("Provide exactly one of audio=PATH or tts='azure'/'espeak'")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("Install ffmpeg and ffprobe on Oracle before rendering")

    data, scenes = read_storyboard(storyboard)
    folder = Path(outdir)
    folder.mkdir(parents=True, exist_ok=True)
    narration = folder / "narration.wav"
    if audio:
        supplied = Path(audio).resolve(strict=True)
        if supplied.suffix.lower() not in (".wav", ".mp3", ".m4a"):
            raise ValueError("Narration must be WAV, MP3 or M4A")
        narration = folder / ("narration" + supplied.suffix.lower())
        if supplied != narration.resolve():
            shutil.copy2(supplied, narration)
    else:
        script = "\n".join(scene["narration"] for scene in scenes)
        narration = synthesize_tamil(
            script, narration, provider=tts, rights_confirmed=True,
            rate=speech_rate,
        )

    audio_seconds = probe_audio_seconds(narration)
    frames = scene_frame_counts(scenes, audio_seconds)
    subtitles = write_estimated_srt(scenes, frames, folder / "subtitles.srt")
    output = folder / "full_story_9x16.mp4"

    with tempfile.TemporaryDirectory(prefix="ct-v14-", dir=folder) as tmp:
        scratch = Path(tmp)
        clips = []
        for index, (scene, count) in enumerate(zip(scenes, frames), start=1):
            clip = scratch / f"scene_{index:02}.mp4"
            # Fit without cutting faces; each distinct scene gets subtle motion.
            # This is NOT AI character animation or a 3D-rendered scene.
            filters = (
                "scale=720:1280:force_original_aspect_ratio=decrease,"
                "pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x101229,"
                "zoompan=z='min(zoom+0.00045,1.06)':d=1:s=720x1280:fps=24,"
                "format=yuv420p"
            )
            _run_ffmpeg([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-framerate", str(FPS),
                "-i", str(scene["image"]), "-vf", filters,
                "-frames:v", str(count), "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                "-r", str(FPS), "-pix_fmt", "yuv420p", str(clip),
            ])
            clips.append(clip)
        concat_file = scratch / "clips.txt"
        concat_file.write_text(
            "".join(f"file '{_concat_path(clip)}'\n" for clip in clips),
            encoding="utf-8",
        )
        joined = scratch / "joined.mp4"
        _run_ffmpeg([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", str(joined),
        ])
        _run_ffmpeg([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(joined), "-i", str(narration),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-af", "apad", "-t", str(sum(frames) / FPS),
            "-movflags", "+faststart", str(output),
        ])
    if not output.is_file() or output.stat().st_size < 1000:
        raise RuntimeError("Full story video missing after FFmpeg render")

    manifest = {
        "version": 14,
        "status": "draft_ready_review_required",
        "published": False,
        "rights_confirmed_by_operator": True,
        "story_title": data.get("title", ""),
        "story_url": data.get("story_url", ""),
        "video": str(output),
        "audio": str(narration),
        "subtitles": str(subtitles),
        "audio_seconds": round(audio_seconds, 3),
        "video_seconds": round(sum(frames) / FPS, 3),
        "scene_count": len(scenes),
        "video_type": "multi_scene_animated_stills_not_generative_video",
        "subtitle_alignment": "estimated_not_forced_aligned",
        "visual_qa_required": True,
        "audio_qa_required": True,
        "external_posting_enabled": False,
    }
    (folder / "story_video_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a reviewed 60–120s multi-scene Tamil story preview"
    )
    parser.add_argument("--storyboard", required=True, help="Reviewed scenes JSON")
    parser.add_argument("--outdir", default="output/v14/story_video")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--audio", help="Approved WAV/MP3/M4A narration")
    source.add_argument("--tts", choices=("azure", "espeak"),
                        help="Generate narration from approved scene text")
    parser.add_argument("--speech-rate", default="-5%")
    parser.add_argument("--rights-confirmed", action="store_true", required=True)
    args = parser.parse_args(argv)
    result = build_full_story(
        args.storyboard, args.outdir, audio=args.audio, tts=args.tts,
        rights_confirmed=args.rights_confirmed, speech_rate=args.speech_rate
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
