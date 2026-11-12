"""Build original story promotional artwork variants from approved artwork.

Illustration: color-enhanced version of an input illustration.
3D-style: lighting, depth/shadow framing of 2D artwork. NOT 3D generation.
No automatic publishing; no downloading unlicensed assets.
"""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from poster_generator import make_poster


def render_variants(image_path, output_dir):
    source = Path(image_path)
    if not source.is_file():
        raise FileNotFoundError("Original/licensed artwork file is required: " + str(source))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        img = img.convert("RGB")
        if min(img.size) < 400:
            raise ValueError("Artwork too small; minimum width/height is 400px")
        # Instagram portrait, never distorted.
        canvas_size = (1080, 1350)
        scale = max(canvas_size[0] / img.width, canvas_size[1] / img.height)
        large = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
        left, top = (large.width - 1080) // 2, (large.height - 1350) // 2
        cropped = large.crop((left, top, left + 1080, top + 1350))

        illustration = ImageEnhance.Color(cropped).enhance(1.12)
        illustration = ImageEnhance.Contrast(illustration).enhance(1.07)
        art_file = output / "illustration_enhanced.png"
        illustration.save(art_file)

        # Pseudo-3D treatment only: cinematic vignette and raised image inset.
        backdrop = cropped.filter(ImageFilter.GaussianBlur(24)).convert("RGBA")
        backdrop = ImageEnhance.Brightness(backdrop).enhance(.32)
        panel = cropped.resize((880, 1130), Image.Resampling.LANCZOS).convert("RGBA")
        shadow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        d = ImageDraw.Draw(shadow)
        d.rounded_rectangle((120, 122, 1010, 1262), radius=34, fill=(0, 0, 0, 190))
        shadow = shadow.filter(ImageFilter.GaussianBlur(28))
        result = Image.alpha_composite(backdrop, shadow)
        result.alpha_composite(panel, (100, 105))
        d = ImageDraw.Draw(result)
        d.rounded_rectangle((99, 104, 980, 1236), radius=20, outline="#f3d491", width=6)
        style_file = output / "cinematic_depth_style.png"
        result.convert("RGB").save(style_file)
    return art_file, style_file


def produce(draft, artwork=None, outdir="output/creative_v5", headline=None, mode="story", auto_cover=False):
    if auto_cover:
        from auto_story_cover import auto_cover as fetch_cover
        artwork = str(fetch_cover(draft, Path(outdir) / "covers"))
    if not artwork:
        raise ValueError("Supply --artwork PATH or --auto-cover. No placeholder image is used.")
    art_file, style_file = render_variants(artwork, outdir)
    poster_file = Path(outdir) / "story_poster.png"
    make_poster(draft, poster_file, artwork=str(art_file), headline=headline, mode=mode)
    manifest = {
        "source_artwork": str(artwork),
        "illustration_variant": str(art_file),
        "cinematic_depth_variant": str(style_file),
        "poster": str(poster_file),
        "rights_review_required": True,
        "actual_3d_model_generated": False,
        "generative_ai_artwork_created": False,
        "status": "review_required",
    }
    path = Path(outdir) / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--draft", required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--artwork", help="Owned/licensed local artwork path")
    group.add_argument("--auto-cover", action="store_true", help="Download story-cover candidate from the chosen draft")
    p.add_argument("--outdir", default="output/creative_v5")
    p.add_argument("--headline", help="Short, reviewed Tamil or English poster headline")
    p.add_argument("--mode", choices=("story", "meme", "news"), default="story")
    a = p.parse_args()
    artwork = a.artwork
    if a.auto_cover:
        from auto_story_cover import auto_cover
        try:
            artwork = str(auto_cover(a.draft, str(Path(a.outdir) / "covers")))
            print("Story cover downloaded for review:", artwork)
        except Exception as exc:
            p.exit(2, "Auto-cover unavailable: " + str(exc) + "\\n")
    try:
        result = produce(a.draft, artwork, a.outdir, a.headline, a.mode)
    except (OSError, ValueError, RuntimeError) as exc:
        p.exit(2, "Poster creation failed: " + str(exc) + "\\n")
    print(json.dumps(result, indent=2))
    print("No content published. These are artwork treatments, not AI-created illustrations or 3D models.")
