"""V12 creative variants and optional licensed-input vertical video.

Produces original layouts around the user's own/approved story artwork.
Does NOT manufacture artwork without an installed image model or use music
and clips from copyrighted anime series.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from poster_generator import find_font, font_at, latin_font, lines_for, require_tamil_shaping


SIZES = {"instagram_feed": (1080, 1350),
         "square": (1080, 1080),
         "reel_cover": (1080, 1920),
         "youtube_thumbnail": (1280, 720)}


def _cover_image(source, size):
    with Image.open(source) as original:
        img = original.convert("RGB")
    w, h = size
    ratio = max(w / img.width, h / img.height)
    large = img.resize((round(img.width * ratio), round(img.height * ratio)),
                       Image.Resampling.LANCZOS)
    left = (large.width - w) // 2
    top = int((large.height - h) * 0.2)
    return large.crop((left, top, left+w, top+h))


def _fit_text(draw, text, font_path, width, height, start=75):
    for sz in range(start, 23, -3):
        font = font_at(font_path, sz)
        try:
            lines = lines_for(draw, text, font, width)
        except ValueError:
            continue
        step = sz + 18
        if len(lines) * step <= height and len(lines) <= 5:
            return font, lines, step
    raise ValueError("Headline too long; supply a shorter approved title.")


def create_variants(image, title, output_dir, approved_art=False, meme_hook=None):
    """Generate a pack of real JPEG graphics from *authorized* artwork."""
    if not approved_art:
        raise PermissionError("Confirm you own/license this artwork first (approved_art=True)")
    source = Path(image)
    if not source.is_file():
        raise FileNotFoundError(source)
    require_tamil_shaping()
    tamil, latin = find_font(), latin_font()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for kind, size in SIZES.items():
        w, h = size
        canvas = _cover_image(source, size)
        # Dim entire art for strong contrast, reserve fully opaque lower panel.
        overlay = Image.new("RGBA", size)
        pen = ImageDraw.Draw(overlay)
        pen.rectangle((0, 0, w, h), fill=(18, 8, 43, 38))
        header_h = max(72, int(h * .08))
        panel_y = round(h * (.69 if kind == "youtube_thumbnail" else .65))
        pen.rectangle((0, panel_y, w, h), fill=(14, 8, 37, 248))
        pen.rectangle((0, 0, w, header_h), fill=(9, 8, 29, 220))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)
        d = ImageDraw.Draw(canvas)
        brand_font = font_at(latin, max(30, round(w * .034)))
        d.text((35, 17), "CartoonTamilan.in", font=brand_font, fill="#ffe7ab")
        title_text = str(meme_hook or title).strip()
        area_h = round((h - panel_y) * .68)
        font, lines, step = _fit_text(d, title_text, tamil, w - 100, area_h,
                                      start=round(w * .067))
        top = panel_y + 28
        for line in lines:
            d.text((54, top), line, font=font, fill="#ffffff",
                   stroke_width=2, stroke_fill="#261146")
            top += step
        cta = "READ THE STORY | LINK IN BIO"
        d.text((53, h - max(78, round(h * .078))), cta,
               font=font_at(latin, max(22, round(w * .033))), fill="#ffcf72")
        file = out / (kind + ".jpg")
        canvas.convert("RGB").save(file, "JPEG", quality=92, optimize=True)
        results[kind] = str(file)
    return results


def make_reel(cover, outfile, seconds=12, voiceover=None, voice_rights_confirmed=False,
              ffmpeg_path=None):
    """Make a short 9:16 motion teaser from authorized still art.

    FFmpeg is optional and must be installed separately. Voice/music is not
    synthesized; user-supplied narration needs explicit rights confirmation.
    """
    cover = Path(cover)
    if not cover.is_file():
        raise FileNotFoundError(cover)
    if not 4 <= seconds <= 30:
        raise ValueError("Reel duration must be between 4 and 30 seconds")
    ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is not installed; install ffmpeg on Oracle to make MP4 videos")
    if voiceover and not voice_rights_confirmed:
        raise PermissionError("Confirm rights to narration/audio before video render")
    if voiceover and not Path(voiceover).is_file():
        raise FileNotFoundError(voiceover)
    output = Path(outfile)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Moderate ARM64-friendly vertical output, letterboxed to avoid cropped title.
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
               "-loop", "1", "-framerate", "24", "-i", str(cover)]
    if voiceover:
        command += ["-i", str(voiceover)]
    command += [
        "-t", str(seconds),
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,"
               "pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x100720,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-r", "24", "-pix_fmt", "yuv420p",
    ]
    if voiceover:
        command += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        command += ["-an"]
    command += ["-movflags", "+faststart", str(output)]
    result = subprocess.run(command, capture_output=True, text=True,
                            timeout=300, check=False)
    if result.returncode != 0:
        raise RuntimeError("FFmpeg reel creation failed: " + result.stderr[-700:])
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError("FFmpeg produced no video")
    return output


def write_media_manifest(story_url, assets, destination, rights_confirmed=False):
    obj = {"story_url": story_url, "assets": assets,
           "rights_confirmed": bool(rights_confirmed),
           "instagram_reels_ready": False,
           "note": "Manual QA and public HTTPS video hosting still required."}
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest
