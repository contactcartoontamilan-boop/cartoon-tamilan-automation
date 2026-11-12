"""CartoonTamilan V8: quality-gated editorial posters and Tamil memes.

Uses only user-owned/licensed artwork; never substitutes geometric placeholders.
Requires Pillow with RAQM for correctly shaped Tamil and a Tamil-capable font.
Publishing is deliberately not part of this script.
"""
import argparse
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features

ROOT = Path(__file__).resolve().parent
TAMIL_FONTS = [
    "/system/fonts/NotoSansTamil-VF.ttf",
    "/system/fonts/NotoSansTamil-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansTamil-Regular.ttf",
]
LATIN_FONTS = [
    "/system/fonts/Roboto-Regular.ttf",
    "/system/fonts/RobotoStatic-Regular.ttf",
    "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def find_font(path=None):
    candidates = ([path] if path else []) + TAMIL_FONTS
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Tamil font missing. Supply --font /path/to/NotoSansTamil.ttf")


def latin_font(path=None):
    for candidate in ([path] if path else []) + LATIN_FONTS:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Latin font missing. Supply --latin-font /path/to/Roboto.ttf")


def font_at(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def require_tamil_shaping():
    if not features.check("raqm"):
        raise RuntimeError("Tamil shaping unavailable: Pillow RAQM is required.")


def lines_for(draw, text, font, max_width):
    result, line = [], ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            if line:
                result.append(line)
            if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                raise ValueError("One word exceeds available width; shorten headline.")
            line = word
    if line:
        result.append(line)
    return result


def make_poster(draft_path, destination, font_path=None, artwork=None,
                headline=None, mode="story", latin_font_path=None):
    require_tamil_shaping()
    tamil_path = find_font(font_path)
    english_path = latin_font(latin_font_path)
    data = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    item = data["item"]
    title = (headline or item.get("title") or "").strip()
    if not title:
        raise ValueError("Headline is empty.")
    if len(title) > 135:
        raise ValueError("Headline too long; provide a concise, reviewed --headline.")
    if not artwork:
        raise ValueError("Original/licensed artwork required: --artwork PATH. No placeholder posters.")
    if mode not in ("story", "meme", "news"):
        raise ValueError("mode must be story, meme, or news")
    art_path = Path(artwork)
    if not art_path.is_file():
        raise FileNotFoundError("Artwork missing: " + str(art_path))

    # V8 editorial composition: top-weighted cover, masked lower-cover labels,
    # clear brand header, spacious responsive headline, compact CTA.
    w, h = 1080, 1350
    bg = "#0d1429"
    img = Image.new("RGB", (w, h), bg)
    cover_top, cover_height = 104, 840
    with Image.open(art_path) as opened:
        art = opened.convert("RGB")
        scale = max(w / art.width, cover_height / art.height)
        resized = art.resize((round(art.width * scale), round(art.height * scale)),
                            Image.Resampling.LANCZOS)
        crop_x = (resized.width - w) // 2
        # Favor the top of portrait covers, keeping faces visible.
        crop_y = round((resized.height - cover_height) * 0.18)
        crop = resized.crop((crop_x, crop_y, crop_x + w, crop_y + cover_height))
        img.paste(crop, (0, cover_top))

    # Covers sometimes include printed source titles or badges along their lower
    # area. Hide that area under a smooth dark gradient rather than layering more
    # copy on top. Embedded text in the upper half still needs manual review.
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fade_draw = ImageDraw.Draw(overlay)
    fade_start, fade_end = 570, 944
    for y in range(fade_start, fade_end + 1):
        fraction = (y - fade_start) / (fade_end - fade_start)
        alpha = round(255 * min(1.0, fraction ** 0.85))
        fade_draw.line((0, y, w, y), fill=(13, 20, 41, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 104), fill=bg)
    draw.text((54, 25), "CartoonTamilan",
              font=font_at(english_path, 43), fill="#ffffff")
    draw.text((785, 42), "ORIGINALS",
              font=font_at(english_path, 23), fill="#eac16f")

    label = {"story": "ORIGINAL STORY", "meme": "TAMIL ANIME MEME",
             "news": "ANIME NEWS"}[mode]
    draw.rounded_rectangle((54, 892, 477, 948), radius=19, fill="#e9bc67")
    draw.text((81, 905), label,
              font=font_at(english_path, 26), fill="#141a2d")

    # Fit story headlines into a fixed safe zone. Center short titles instead
    # of leaving a huge empty gulf between the title and CTA button.
    available_top, available_bottom = 966, 1220
    chosen = None
    for size in range(60, 31, -2):
        font = font_at(tamil_path, size)
        rows = lines_for(draw, title, font, 966)
        step = size + 16
        if 1 <= len(rows) <= 4 and len(rows) * step <= available_bottom - available_top:
            chosen = (font, rows, size, step)
            break
    if chosen is None:
        raise ValueError("Headline too long for a professional poster. Supply a shorter --headline.")
    font, rows, size, step = chosen
    line_height = len(rows) * step
    y = available_top + ((available_bottom - available_top - line_height) // 2)
    for row in rows:
        draw.text((57, y), row, font=font, fill="#ffffff")
        y += step

    draw.rounded_rectangle((54, 1240, 1026, 1323), radius=23, fill="#e9bc67")
    draw.text((85, 1262), "READ THE STORY  |  cartoontamilan.in",
              font=font_at(english_path, 30), fill="#141a2d")

    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target, format="PNG")
    return target


def main():
    p = argparse.ArgumentParser(description="Create reviewed, artwork-backed Tamil posters")
    p.add_argument("--draft", required=True)
    p.add_argument("--out", default="output/story_poster_v2.png")
    p.add_argument("--font", help="Tamil font .ttf")
    p.add_argument("--latin-font", help="English font .ttf")
    p.add_argument("--artwork", required=True, help="Original/licensed image path")
    p.add_argument("--headline", help="Short, manually reviewed headline")
    p.add_argument("--mode", choices=["story", "meme", "news"], default="story")
    a = p.parse_args()
    print("Poster saved:", make_poster(a.draft, a.out, a.font, a.artwork, a.headline, a.mode, a.latin_font))


if __name__ == "__main__":
    main()
