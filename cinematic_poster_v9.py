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


def mask_cover_titles(image, fade_start=515, solid_start=730, color=(10, 8, 31)):
    """Hide printed cover text in lower artwork while retaining faces above.

    From solid_start down, the original cover pixels must be fully concealed.
    Covers with lettering above solid_start still require a clean source image.
    """
    w, h = image.size
    solid_start = min(max(solid_start, fade_start + 1), h)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(fade_start, solid_start):
        progress = (y - fade_start) / (solid_start - fade_start)
        alpha = min(255, round(255 * progress ** 0.75))
        draw.line((0, y, w, y), fill=(*color, alpha))
    draw.rectangle((0, solid_start, w, h), fill=(*color, 255))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


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
    # Existing novel covers often have the title printed in the lower half.
    # A translucent title card alone cannot hide those old glyphs. Finish
    # the key-art area with a completely opaque matte before adding text.
    canvas = mask_cover_titles(canvas)

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

    d.rounded_rectangle((62, 790, 1018, 1110), radius=34, fill=(13, 10, 38, 245),
                        outline=(*primary, 240), width=4)
    # Fit up to 3 title rows, truncating no Tamil words.
    chosen = None
    for size in range(68, 35, -2):
        font = font_at(ta, size)
        try:
            rows = lines_for(d, title, font, 866)
        except ValueError:
            continue
        if len(rows) <= 4 and len(rows) * (size + 19) <= 282:
            chosen = (font, rows, size)
            break
    if not chosen:
        raise ValueError("Story headline too long; shorten the title before publishing")
    font, rows, size = chosen
    row_height = size + 19
    top = 814 + (272 - len(rows) * row_height) // 2
    for row in rows:
        d.text((96, top), row, font=font, fill="#fff8f9", stroke_width=2,
               stroke_fill=(36, 15, 69))
        top += row_height

    d.rounded_rectangle((145, 1140, 935, 1234), radius=37, fill=(*secondary, 255))
    cta = "READ THE STORY  >>"
    d.text((220, 1163), cta, font=font_at(en, 44), fill="#ffffff", stroke_width=1)
    d.text((320, 1286), "cartoontamilan.in", font=font_at(en, 29), fill="#ece7ff")
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(dest, "JPEG", quality=92, optimize=True)
    return dest
