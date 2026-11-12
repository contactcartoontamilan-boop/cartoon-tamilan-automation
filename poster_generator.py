"""CartoonTamilan V2: quality-gated bilingual posters and Tamil memes.

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

    w, h = 1080, 1350
    img = Image.new("RGB", (w, h), "#101529")
    with Image.open(art_path) as opened:
        art = opened.convert("RGB")
        target_w, target_h = 1080, 790
        scale = max(target_w / art.width, target_h / art.height)
        art = art.resize((round(art.width * scale), round(art.height * scale)), Image.Resampling.LANCZOS)
        left = (art.width - target_w) // 2
        top = (art.height - target_h) // 2
        img.paste(art.crop((left, top, left + target_w, top + target_h)), (0, 0))

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1080, 105), fill="#101529")
    draw.text((56, 23), "CartoonTamilan", font=font_at(english_path, 47), fill="#ffffff")
    label = {"story": "ORIGINAL STORY", "meme": "TAMIL ANIME MEME", "news": "ANIME NEWS"}[mode]
    draw.rounded_rectangle((54, 815, 1026, 886), radius=17, fill="#e8b960")
    draw.text((82, 831), label, font=font_at(english_path, 29), fill="#151a2b")

    # For mixed scripts, use a Tamil-capable font and RAQM; explicit review still required.
    chosen = None
    for size in range(54, 31, -2):
        font = font_at(tamil_path, size)
        rows = lines_for(draw, title, font, 960)
        if len(rows) <= 4:
            chosen = (font, rows, size)
            break
    if chosen is None:
        raise ValueError("Headline too long. Use --headline with a concise, reviewed Tamil hook.")
    font, rows, size = chosen
    y = 917
    for row in rows:
        draw.text((60, y), row, font=font, fill="#ffffff")
        y += size + 18

    draw.rounded_rectangle((55, 1234, 1025, 1318), radius=17, fill="#e8b960")
    draw.text((84, 1255), "READ MORE  |  cartoontamilan.in",
              font=font_at(english_path, 29), fill="#151a2b")
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
