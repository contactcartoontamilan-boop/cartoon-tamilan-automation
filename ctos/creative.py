"""Text-free master artwork -> platform-specific branded compositions.

Do not feed V10/V12 posters back as artwork: that creates duplicated headings.
Uses Pillow RAQM for Tamil and refuses headlines that cannot fit.
All actual original-model imagery comes from a separately configured backend.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance
from poster_generator import require_tamil_shaping, find_font, latin_font, font_at, lines_for

SIZES = {
    "instagram_feed": (1080, 1350),
    "instagram_story": (1080, 1920),
    "facebook_feed": (1080, 1350),
    "facebook_landscape": (1200, 630),
    "youtube_thumbnail": (1280, 720),
    "youtube_short": (1080, 1920),
    "pinterest_pin": (1000, 1500),
    "x_landscape": (1600, 900),
    "threads_feed": (1080, 1350),
    "linkedin_landscape": (1200, 627),
}
PALETTES = (
    {"ink": "#101229", "accent": "#FFCD75", "cta": "#EA3B72"},
    {"ink": "#081E27", "accent": "#8EF2D5", "cta": "#D73C6F"},
    {"ink": "#1B0E26", "accent": "#FFD9A3", "cta": "#B248DE"},
    {"ink": "#162238", "accent": "#B4DDFF", "cta": "#F14A72"},
)
# These are V10/V12 *already typeset* files; never reuse as raw artwork.
DECORATED = {"premium_poster.jpg", "cinematic_poster.jpg", "story_poster.png",
             "instagram_feed.jpg", "square.jpg", "reel_cover.jpg",
             "youtube_thumbnail.jpg"}


def clean_source(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    if p.name.lower() in DECORATED or "variants" in p.parts:
        raise ValueError("A previously typeset poster is not clean artwork; use source_artwork or licensed art.")
    with Image.open(p) as opened:
        opened.verify()
    return p


def _crop(source, size, focus=(0.50, 0.42)):
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    width, height = size
    # Give faces priority: never cover the crop with title, only an opaque footer.
    ratio = max(width / image.width, height / image.height)
    large = image.resize((max(width, round(image.width * ratio)),
                          max(height, round(image.height * ratio))),
                         Image.Resampling.LANCZOS)
    cx = round(large.width * max(0., min(1., float(focus[0]))))
    cy = round(large.height * max(0., min(1., float(focus[1]))))
    x = max(0, min(large.width - width, cx - width // 2))
    y = max(0, min(large.height - height, cy - height // 2))
    return large.crop((x, y, x+width, y+height))


def _title_fit(draw, title, path, width, height, max_size):
    for size in range(max_size, 23, -2):
        font = font_at(path, size)
        try:
            rows = lines_for(draw, title, font, width)
        except ValueError:
            continue
        line_step = round(size * 1.25)
        if rows and len(rows) <= 5 and len(rows) * line_step <= height:
            return font, rows, line_step
    raise ValueError("Tamil headline cannot fit safely. Provide a shorter verified title.")


def render_one(source, title, destination, kind="instagram_feed", focus=(0.5, 0.42),
               brand="CartoonTamilan.in", cta="READ THE STORY",
               palette_index=0):
    if kind not in SIZES:
        raise ValueError("Unknown platform format")
    if not isinstance(title, str) or not title.strip() or len(title) > 150:
        raise ValueError("Please provide a concise verified Tamil headline")
    require_tamil_shaping()
    source = clean_source(source)
    size = SIZES[kind]
    w, h = size
    style = PALETTES[palette_index % len(PALETTES)]
    art = _crop(source, size, focus).convert("RGBA")
    canvas = Image.new("RGBA", (w, h), "#090b20")
    canvas.alpha_composite(art)
    d = ImageDraw.Draw(canvas)
    safe_x = round(w * 0.052)
    header_height = max(64, round(h * 0.076))
    panel_height = round(h * (0.43 if w > h else 0.33))
    panel_y = h - panel_height
    # Fully opaque panel hides preexisting bottom-cover text. Upper-cover
    # lettering cannot be detected reliably: requires human artwork review.
    d.rectangle((0, 0, w, header_height), fill=style["ink"])
    d.rectangle((0, panel_y, w, h), fill=style["ink"])
    d.rectangle((safe_x, panel_y+10, safe_x+round(w*.18), panel_y+16),
                fill=style["accent"])
    english = latin_font()
    tamil = find_font()
    bf = font_at(english, max(26, round(w * .034)))
    d.text((safe_x, max(10, (header_height - bf.size) // 2)), brand,
           font=bf, fill="#FFFFFF")
    right = w - safe_x
    top = panel_y + max(26, round(h * .022))
    bottom_space = max(75, round(panel_height * .30))
    title_room = panel_height - (top - panel_y) - bottom_space - 12
    if title_room < 55:
        raise ValueError("Not enough room for safe typography")
    tfont, rows, step = _title_fit(
        d, title.strip(), tamil, w-2*safe_x, title_room,
        min(round(w * .072), 84))
    for row in rows:
        box = d.textbbox((0, 0), row, font=tfont)
        if box[2]-box[0] > w-2*safe_x:
            raise ValueError("Unsafe text width")
        d.text((safe_x-box[0], top), row, font=tfont,
               fill="#FFFFFF", stroke_width=1, stroke_fill="#15152A")
        top += step
    cta_font = font_at(english, max(23, round(w*.030)))
    cta_top = h - max(55, round(panel_height*.15)) - cta_font.size
    if top > cta_top - 10:
        raise ValueError("CTA and Tamil title collide; shorten headline")
    d.text((safe_x, cta_top), cta, font=cta_font, fill=style["accent"])
    footer_y = h - max(28, round(h*.022))
    footer_font = font_at(english, max(16, round(w*.019)))
    footer = "ORIGINAL TAMIL STORIES  •  CARTOONTAMILAN.IN"
    d.text((safe_x, footer_y), footer, font=footer_font, fill="#D3CEE1")
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(dest, "JPEG", quality=92, optimize=True)
    # Checks are based on actual rectangles and generated pixel dimensions,
    # not a fictional OCR/text-quality score.
    with Image.open(dest) as check:
        if check.size != size or check.format != "JPEG":
            raise RuntimeError("Incorrect saved image format/dimensions")
    return {"file": str(dest), "size": list(size), "title_lines": len(rows),
            "title_bbox_region": [safe_x, panel_y, right, top],
            "cta_top": cta_top, "art_source": str(source),
            "source_text_free_not_automatically_verified": True}


def render_pack(artwork, title, outdir, story_url="", focus=(0.5, 0.42),
                variants=None, genre=""):
    source = clean_source(artwork)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    seed = hashlib.sha256((story_url or title).encode("utf-8")).digest()[0]
    outputs = {}
    for kind in (variants or tuple(SIZES)):
        file = out / (kind + ".jpg")
        outputs[kind] = render_one(
            source, title, file, kind=kind, focus=focus,
            palette_index=seed + list(SIZES).index(kind))
    data = {"assets": outputs, "art_source": str(source),
            "art_provenance_needs_review": True,
            "original_model_generated": False, "genre_hint": genre}
    (out / "render_manifest.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data
