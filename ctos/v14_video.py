"""CPU-compatible, scene-changing 60–120s video with approximate scene SRT.

Ken Burns motion is NOT AI character animation. Each scene MUST use distinct,
approved original artwork; genuine anime motion needs a separate GPU provider.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path


def timestamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hh, rem = divmod(ms, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, rem = divmod(rem, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{rem:03d}"


def write_scene_srt(scenes: list[dict], durations: list[float],
                    destination: str | Path, words_per_cue: int = 8) -> Path:
    """Time cues to scene audio boundaries; word timing is an estimate, not ASR."""
    if len(scenes) != len(durations) or not 3 <= words_per_cue <= 12:
        raise ValueError("SRT scenes/durations mismatch")
    rows = []
    elapsed = 0.0
    index = 1
    for scene, duration in zip(scenes, durations):
        if duration <= 0:
            raise ValueError("Scene duration must be positive")
        words = scene["narration"].split()
        if not words:
            raise ValueError("Empty scene")
        groups = [words[i:i + words_per_cue]
                  for i in range(0, len(words), words_per_cue)]
        offset = 0
        for group in groups:
            start = elapsed + duration * offset / len(words)
            offset += len(group)
            end = elapsed + duration * offset / len(words)
            rows.append(
                f"{index}\n{timestamp(start)} --> {timestamp(end)}\n"
                f"{' '.join(group)}\n"
            )
            index += 1
        elapsed += duration
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return target


def _run(command: list[str], cwd: Path | None = None, timeout: int = 900):
    result = subprocess.run(command, cwd=str(cwd) if cwd else None,
                            capture_output=True, text=True, timeout=timeout,
                            check=False)
    if result.returncode:
        raise RuntimeError("FFmpeg failed: " + result.stderr[-800:])


def _probe_duration(path: Path, ffprobe: str) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise RuntimeError("ffprobe failed: " + result.stderr[-300:])
    return float(result.stdout.strip())


def make_story_video(images: list[Path], durations: list[float],
                     destination: str | Path, *,
                     rights_confirmed: bool = False,
                     narration: str | Path | None = None,
                     size: tuple[int, int] = (720, 1280),
                     fps: int = 24,
                     ffmpeg_path: str | None = None,
                     ffprobe_path: str | None = None) -> dict:
    if not rights_confirmed:
        raise PermissionError("Confirm all scene image and narration rights")
    if not images or len(images) != len(durations):
        raise ValueError("Each scene needs its own approved illustration and duration")
    total = sum(durations)
    if not 60 <= total <= 120:
        raise ValueError(
            f"Actual story duration is {total:.1f}s; revise script/TTS to reach 60–120s"
        )
    if not (2 <= fps <= 30 and 160 <= size[0] <= 1920 and
            240 <= size[1] <= 1920 and size[0] % 2 == 0 and size[1] % 2 == 0):
        raise ValueError("Invalid even video dimensions or FPS")
    ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
    ffprobe = ffprobe_path or shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("Install ffmpeg and ffprobe on Oracle before rendering")
    for image in images:
        if not Path(image).is_file():
            raise FileNotFoundError(image)
    if narration and not Path(narration).is_file():
        raise FileNotFoundError(narration)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    # Contain instead of center-cropping the approved art: preserves both faces.
    # Mild zoom creates movement, but NOT genuine animated characters.
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101229,"
        f"zoompan=z='min(zoom+0.0004,1.10)':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={width}x{height}:fps={fps},format=yuv420p"
    )
    with tempfile.TemporaryDirectory(prefix="ct_v14_", dir=target.parent) as tmp:
        folder = Path(tmp)
        entries = []
        for i, (image, duration) in enumerate(zip(images, durations), start=1):
            name = f"scene_{i:02d}.mp4"
            _run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-framerate", str(fps), "-i", str(Path(image).resolve()),
                "-vf", vf, "-frames:v", str(max(1, round(duration * fps))),
                "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "25", "-pix_fmt", "yuv420p", "-r", str(fps), name,
            ], cwd=folder)
            entries.append(f"file '{name}'")
        (folder / "concat.txt").write_text("\n".join(entries) + "\n", encoding="utf-8")
        silent = folder / "silent.mp4"
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
              "-f", "concat", "-safe", "0", "-i", "concat.txt",
              "-c", "copy", str(silent)], cwd=folder)
        if narration:
            _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                  "-i", str(silent), "-i", str(Path(narration).resolve()),
                  "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                  "-c:a", "aac", "-b:a", "128k", "-shortest",
                  "-movflags", "+faststart", str(target)])
        else:
            shutil.copy2(silent, target)
    if not target.is_file() or target.stat().st_size < 1024:
        raise RuntimeError("Video output is empty")
    actual = _probe_duration(target, ffprobe)
    if not 59 <= actual <= 121 or abs(actual - total) > 1.5:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"Video duration QA failed: expected {total:.2f}s, got {actual:.2f}s")
    return {
        "video": str(target),
        "duration_seconds": round(actual, 2),
        "resolution": [width, height],
        "animation_type": "original_scene_stills_with_ken_burns_not_ai_character_motion",
        "has_audio": bool(narration),
        "subtitles_burned_in": False,
        "requires_human_review": True,
        "published": False,
    }
