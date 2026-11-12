"""Cinematic anime promo poster, using an approved image or generated original art.

Neon key-art treatment; all Tamil/English copy is rendered with local fonts,
not embedded by the image model. 1080x1350 Instagram portrait JPEG.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from poster_generator import find_font, latin_font, font_at, require_tamil_shaping, lines_for


PALETTES = {
    "purple": ((158, 53, 255), (255, 68, 109)),
    "blue": ((34, 176, 255), (202, 70, 250)),
    "gold": ((255, 174, 65), (246, 62, 113)),
}


def cinematic_poster(draft_path, artwork, destination, palette="purple"):
    require_tamil_shaping()
    if palette not in PALETTES:
        raise ValueError("Invalid palette")
    item = json.loads(Path(draft_path).read_text(encoding="utf-8"))["item"]
    title = (item.get("title") or "").strip()
    if not title:
        raise ValueError("Missing story title")
    art = Path(artwork)
    if not art.is_file():
        raise FileNotFoundError("Artwork file missing")
    w, h = 1080, 1350
    with Image.open(art) as im:
        im = im.convert("RGB")
        factor = max(w / im.width, 980 / im.height)
        image = im.resize((round(im.width * factor), round(im.height * factor)), Image.Resampling.LANCZOS)
        x = (image.width - w) // 2
        y = round((image.height - 980) * .15)
        image = image.crop((x, y, x + w, y + 980))
    canvas = Image.new("RGB", (w, h), (12, 9, 33))
    canvas.paste(image, (0, 60))
    canvas = ImageEnhance.Color(canvas).enhance(1.14)
    # Fade lower key art to a clean space for story typography.
    layer = Image.new("RGBA", (w, h))
    pen = ImageDraw.Draw(layer)
    for y in range(590, 1210):
        a = int(253 * ((y - 590) / 620) ** .8)
        pen.line((0, y, w, y), fill=(10, 8, 31, a))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), layer)

    primary, secondary = PALETTES[palette]
    glow = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-280, 310, 280, 1100), fill=(*primary, 55))
    gd.ellipse((780, 180, 1330, 900), fill=(*secondary, 65))
    canvas = Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(80)))
    d = ImageDraw.Draw(canvas)
    # Neon borders without encroaching on characters.
    d.line([(18, 150), (18, 1160)], fill=(*primary, 190), width=7)
    d.line([(1062, 230), (1062, 1160)], fill=(*secondary, 190), width=7)
    en = latin_font()
    ta = find_font()
    d.rounded_rectangle((32, 28, 1048, 112), radius=20, fill=(10, 11, 35, 220))
    d.text((58, 42), "CartoonTamilan.in", font=font_at(en, 46), fill="#ffffff", stroke_width=1)
    d.rounded_rectangle((760, 127, 1029, 187), radius=25, fill=(*primary, 235))
    d.text((785, 145), "ORIGINAL STORY", font=font_at(en, 25), fill="#ffffff")

    d.rounded_rectangle((62, 890, 1018, 1162), radius=34, fill=(13, 10, 38, 195),
                        outline=(*primary, 240), width=4)
    # Fit up to 3 title rows, truncating no Tamil words.
    chosen = None
    for size in range(68, 35, -2):
        font = font_at(ta, size)
        try:
            rows = lines_for(d, title, font, 866)
        except ValueError:
            continue
        if len(rows) <= 3 and len(rows) * (size + 19) <= 230:
            chosen = (font, rows, size)
            break
    if not chosen:
        raise ValueError("Story headline too long; shorten the title before publishing")
    font, rows, size = chosen
    row_height = size + 19
    top = 916 + (220 - len(rows) * row_height) // 2
    for row in rows:
        d.text((96, top), row, font=font, fill="#fff8f9", stroke_width=2,
               stroke_fill=(36, 15, 69))
        top += row_height

    d.rounded_rectangle((145, 1183, 935, 1273), radius=37, fill=(*secondary, 255))
    cta = "READ THE STORY  >>"
    d.text((220, 1201), cta, font=font_at(en, 44), fill="#ffffff", stroke_width=1)
    d.text((320, 1300), "cartoontamilan.in", font=font_at(en, 29), fill="#ece7ff")
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(dest, "JPEG", quality=92, optimize=True)
    return dest
