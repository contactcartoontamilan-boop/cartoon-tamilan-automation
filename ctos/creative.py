"""Artwork-first platform image layouts with Tamil shaping and collision-safe auto-fit.

No old V10/V12 typeset poster is accepted as a source.
Computed text/call-to-action rectangles never overlap; long titles resize
within bounded panels. Human review remains required for baked source titles.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from poster_generator import (
    require_tamil_shaping, find_font, latin_font, font_at, lines_for,
)

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
CTA_BY_KIND = {
    "instagram_feed": "READ THE STORY | LINK IN BIO",
    "instagram_story": "READ THE STORY | LINK IN BIO",
    "facebook_feed": "READ STORY | LINK IN POST",
    "facebook_landscape": "READ STORY | LINK IN POST",
    "youtube_thumbnail": "STORY VIDEO | CARTOONTAMILAN.IN",
    "youtube_short": "STORY VIDEO | CARTOONTAMILAN.IN",
    "pinterest_pin": "READ STORY | CARTOONTAMILAN.IN",
    "x_landscape": "READ STORY | LINK IN POST",
    "threads_feed": "READ STORY | LINK IN POST",
    "linkedin_landscape": "READ STORY | LINK IN POST",
}

DECORATED = {
    "premium_poster.jpg", "cinematic_poster.jpg", "story_poster.png",
    "instagram_feed.jpg", "square.jpg", "reel_cover.jpg",
    "youtube_thumbnail.jpg",
}


def clean_source(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    if p.name.lower() in DECORATED or "variants" in p.parts:
        raise ValueError(
            "Previous text-decorated poster is not raw artwork. "
            "Use the story's original cover or licensed, text-free art."
        )
    with Image.open(p) as opened:
        opened.verify()
    return p


def _crop(source, size, focus=(0.50, 0.42)):
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    width, height = size
    ratio = max(width / image.width, height / image.height)
    large = image.resize(
        (max(width, round(image.width * ratio)),
         max(height, round(image.height * ratio))),
        Image.Resampling.LANCZOS,
    )
    cx = round(large.width * max(0.0, min(1.0, float(focus[0]))))
    cy = round(large.height * max(0.0, min(1.0, float(focus[1]))))
    x = max(0, min(large.width - width, cx - width // 2))
    y = max(0, min(large.height - height, cy - height // 2))
    return large.crop((x, y, x + width, y + height))


def _contained_art(source, size, header_height, panel_y, ink):
    """Preserve the entire licensed artwork in the visible art viewport.

    Blurred cover-fill is background ONLY; the sharp foreground is contain-fit.
    This avoids cutting off people at the edges of wide source covers.
    """
    width, height = size
    art_height = panel_y - header_height
    if art_height < 20:
        raise ValueError("No usable artwork viewport")
    with Image.open(source) as opened:
        original = opened.convert("RGB")
    background = _crop(source, (width, art_height)).filter(
        ImageFilter.GaussianBlur(radius=max(8, round(width * 0.018))))
    # Subdue blurred letterbox bands without changing the sharp, full cover.
    background = Image.blend(
        background, Image.new("RGB", background.size, ink), 0.24)
    canvas = Image.new("RGB", (width, height), ink)
    canvas.paste(background, (0, header_height))
    scale = min(width / original.width, art_height / original.height)
    target_w = max(1, min(width, round(original.width * scale)))
    target_h = max(1, min(art_height, round(original.height * scale)))
    sharp = original.resize((target_w, target_h), Image.Resampling.LANCZOS)
    x = (width - target_w) // 2
    y = header_height + (art_height - target_h) // 2
    canvas.paste(sharp, (x, y))
    return canvas.convert("RGBA"), [x, y, x + target_w, y + target_h]


def _bbox(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)


def _measured_font(draw, text, font_path, max_width, max_size, min_size=16):
    """Pick the largest font with measured rendered text fitting the full width."""
    for size in range(max_size, min_size - 1, -1):
        font = font_at(font_path, size)
        box = _bbox(draw, text, font)
        if box[2] - box[0] <= max_width:
            return font
    raise ValueError("Brand/footer/CTA cannot fit image width safely.")


def _fit_title(draw, title, font_path, width, height, max_size):
    """Return font, wrapped rows, line stride, and actual max glyph extent.

    Pillow RAQM + Noto Tamil can have vertical glyph offsets. Measuring
    actual bounds rather than estimated fontsize prevents title/CTA collisions.
    """
    for size in range(max_size, 21, -1):
        font = font_at(font_path, size)
        try:
            rows = lines_for(draw, title, font, width)
        except ValueError:
            continue
        if not rows or len(rows) > 6:
            continue
        bounds = [_bbox(draw, row, font) for row in rows]
        max_h = max(b[3] - b[1] for b in bounds)
        stride = max(round(size * 1.26), max_h + max(5, round(size * .14)))
        actual_height = (len(rows) - 1) * stride + max_h
        if actual_height <= height:
            return font, rows, stride, actual_height
    raise ValueError(
        "Long Tamil headline exceeds safe layout even at minimum font size; "
        "shorten only after editorial review."
    )


def _layout(draw, title, tamil_font, latin_font_path, width, height, safe_x,
            brand, cta):
    """Reserve footer and CTA FIRST, then fit title in the remaining panel."""
    usable_width = width - 2 * safe_x
    landscape = width > height
    vertical_story = height >= round(width * 1.65)
    footer = "ORIGINAL TAMIL STORIES  •  CARTOONTAMILAN.IN"

    brand_font = _measured_font(
        draw, brand, latin_font_path, usable_width,
        max(24, round(width * .033)),
    )
    footer_font = _measured_font(
        draw, footer, latin_font_path, usable_width,
        max(17, round(width * .020)),
    )
    cta_font = _measured_font(
        draw, cta, latin_font_path, usable_width,
        max(22, round(width * .031)),
    )

    footer_box = _bbox(draw, footer, footer_font)
    cta_box = _bbox(draw, cta, cta_font)
    footer_h = footer_box[3] - footer_box[1]
    cta_h = cta_box[3] - cta_box[1]

    # Story/Reel artwork is tall and mobile UI obscures the bottom edge.
    # Keep CTA and attribution clear of the bottom interaction controls.
    footer_bottom_margin = (max(130, round(height * .095))
                            if vertical_story else max(12, round(height * .016)))
    footer_top = height - footer_bottom_margin - footer_h
    cta_spacing = (max(54, round(height * .055))
                   if vertical_story else max(16, round(height * .024)))
    cta_top = footer_top - cta_spacing - cta_h
    title_limit = cta_top - max(16, round(height * .025))

    ratios = ((.45, .49, .53, .57, .61) if landscape else
              (.48, .51, .54, .57, .60) if vertical_story else
              (.36, .39, .42, .45, .49))
    desired = 38 if landscape else 48
    max_title_size = min(84, round(width * .074))
    best = None
    for ratio in ratios:
        panel_y = height - round(height * ratio)
        title_top = panel_y + max(28, round(height * .035))
        room = title_limit - title_top
        if room < 30:
            continue
        try:
            font, rows, stride, actual_height = _fit_title(
                draw, title, tamil_font, usable_width, room, max_title_size)
        except ValueError:
            continue
        candidate = (font.size, panel_y, title_top, font, rows,
                     stride, actual_height)
        if best is None or candidate[0] > best[0]:
            best = candidate
        if font.size >= desired:
            break
    if best is None:
        raise ValueError("No safe title/CTA layout; editorial title shortening required")
    _, panel_y, title_top, title_font, rows, stride, actual_height = best
    title_bottom = title_top + actual_height
    # Balance the empty space in tall Stories instead of leaving a huge
    # blank gulf between the Tamil title and the call to action.
    free_gap = cta_top - title_bottom
    preferred_gap = max(40, round(height * .05))
    if free_gap > preferred_gap:
        # In Stories keep the headline visually connected to the CTA;
        # in feed layouts retain the established balanced spacing.
        shift = (free_gap - preferred_gap if vertical_story
                 else (free_gap - preferred_gap) // 2)
        title_top += shift
        title_bottom += shift
    if title_bottom + max(16, round(height * .025)) > cta_top:
        raise RuntimeError("Internal title/CTA layout error")
    if cta_top + cta_h + max(16, round(height * .024)) > footer_top:
        raise RuntimeError("Internal CTA/footer layout error")
    return {
        "brand": brand, "footer": footer, "cta": cta,
        "brand_font": brand_font, "footer_font": footer_font,
        "cta_font": cta_font,
        "panel_y": panel_y, "title_top": title_top,
        "title_bottom": title_bottom,
        "title_font": title_font, "rows": rows, "stride": stride,
        "cta_top": cta_top, "footer_top": footer_top,
        "font_size": title_font.size,
        "vertical_story": vertical_story,
        "footer_bottom_margin": footer_bottom_margin,
    }


def render_one(source, title, destination, kind="instagram_feed",
               focus=(0.5, 0.42), brand="CartoonTamilan.in",
               cta=None, palette_index=0):
    if kind not in SIZES:
        raise ValueError("Unknown platform format")
    if not isinstance(title, str) or not title.strip() or len(title) > 150:
        raise ValueError("Provide a concise verified Tamil headline")
    require_tamil_shaping()
    source = clean_source(source)
    w, h = SIZES[kind]
    style = PALETTES[palette_index % len(PALETTES)]
    cta = cta or CTA_BY_KIND[kind]
    # Measure layout first; only the uncovered artwork viewport needs an image.
    canvas = Image.new("RGBA", (w, h), style["ink"])
    d = ImageDraw.Draw(canvas)
    safe_x = round(w * 0.052)
    tamil, english = find_font(), latin_font()

    # Title/CTA/footer coordinates are measured before drawing. This fixes
    # V13's live 2026-11-12 CTA and Tamil title collide error.
    layout = _layout(d, title.strip(), tamil, english, w, h, safe_x,
                     brand, cta)
    header_height = max(64, round(h * .076))
    panel_y = layout["panel_y"]
    canvas, art_bbox = _contained_art(source, (w, h), header_height, panel_y,
                                      style["ink"])
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, w, header_height), fill=style["ink"])
    d.rectangle((0, panel_y, w, h), fill=style["ink"])
    d.rectangle((safe_x, panel_y + 11, safe_x + round(w * .18), panel_y + 17),
                fill=style["accent"])

    bf = layout["brand_font"]
    brand_box = _bbox(d, brand, bf)
    brand_top = max(7, (header_height - (brand_box[3] - brand_box[1])) // 2)
    d.text((safe_x - brand_box[0], brand_top - brand_box[1]),
           brand, font=bf, fill="#FFFFFF")

    font = layout["title_font"]
    title_y = layout["title_top"]
    for row in layout["rows"]:
        bounds = _bbox(d, row, font)
        if bounds[2] - bounds[0] > w - 2 * safe_x:
            raise ValueError("Unsafe title width")
        # Anchor by true ink top to prevent RAQM ascender/shaping offsets.
        d.text((safe_x - bounds[0], title_y - bounds[1]), row, font=font,
               fill="#FFFFFF", stroke_width=1, stroke_fill="#15152A")
        title_y += layout["stride"]

    cta_font = layout["cta_font"]
    cta_box = _bbox(d, cta, cta_font)
    d.text((safe_x - cta_box[0], layout["cta_top"] - cta_box[1]),
           cta, font=cta_font, fill=style["accent"])
    footer_font = layout["footer_font"]
    footer_box = _bbox(d, layout["footer"], footer_font)
    d.text((safe_x - footer_box[0], layout["footer_top"] - footer_box[1]),
           layout["footer"], font=footer_font, fill="#D3CEE1")

    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(dest, "JPEG", quality=92, optimize=True)
    with Image.open(dest) as checked:
        if checked.size != (w, h) or checked.format != "JPEG":
            raise RuntimeError("Saved image dimensions/format incorrect")
    return {
        "file": str(dest), "size": [w, h],
        "title_lines": len(layout["rows"]),
        "title_font_size": layout["font_size"],
        "title_bbox_region": [
            safe_x, layout["title_top"], w - safe_x, layout["title_bottom"],
        ],
        "panel_y": panel_y,
        "cta_top": layout["cta_top"],
        "footer_top": layout["footer_top"],
        "art_source": str(source),
        "artwork_contained_without_face_crop": True,
        "visible_artwork_bbox": art_bbox,
        "cta": cta,
        "story_safe_area_applied": layout["vertical_story"],
        "footer_bottom_margin": layout["footer_bottom_margin"],
        "source_text_free_not_automatically_verified": True,
    }


def render_pack(artwork, title, outdir, story_url="", focus=(0.5, 0.42),
                variants=None, genre=""):
    source = clean_source(artwork)
    output = Path(outdir)
    output.mkdir(parents=True, exist_ok=True)
    seed = hashlib.sha256((story_url or title).encode("utf-8")).digest()[0]
    renders = {}
    for kind in (variants or tuple(SIZES)):
        file = output / (kind + ".jpg")
        renders[kind] = render_one(
            source, title, file, kind=kind, focus=focus,
            palette_index=seed + list(SIZES).index(kind),
        )
    result = {
        "assets": renders, "art_source": str(source),
        "art_provenance_needs_review": True, "original_model_generated": False,
        "genre_hint": genre,
    }
    (output / "render_manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result
