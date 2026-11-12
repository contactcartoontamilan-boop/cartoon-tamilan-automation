"""Review and export batch-generated story posters to Android Downloads.

Creates a contact sheet of actual poster PNGs, plus an index mapping images
to stories. No social publishing, no internet access, no fake AI art.
"""
import argparse
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def export_posters(report_path="output/story_discovery/report.json",
                   outdir="output/story_discovery/previews", download_dir=None):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    rows = report.get("success", [])
    if not rows:
        raise ValueError("No successful story posters in report.")
    destination = Path(outdir)
    destination.mkdir(parents=True, exist_ok=True)
    if download_dir:
        Path(download_dir).expanduser().mkdir(parents=True, exist_ok=True)

    tile_w, tile_h, gap, margin = 420, 565, 20, 24
    cols = 2
    height = margin * 2 + math.ceil(len(rows) / cols) * (tile_h + gap)
    width = margin * 2 + cols * (tile_w + gap)
    contact = Image.new("RGB", (width, height), "#101827")
    draw = ImageDraw.Draw(contact)
    labels = []
    missing = []

    for count, entry in enumerate(rows, 1):
        poster = Path(entry["poster"])
        if not poster.is_file():
            missing.append(str(poster))
            continue
        short_id = poster.parent.name[:16]
        unique_name = f"{count:02d}_{short_id}.png"
        x = margin + ((count - 1) % cols) * (tile_w + gap)
        y = margin + ((count - 1) // cols) * (tile_h + gap)
        with Image.open(poster) as opened:
            image = opened.convert("RGB")
            image.thumbnail((tile_w, tile_h - 35), Image.Resampling.LANCZOS)
            xp = x + (tile_w - image.width) // 2
            contact.paste(image, (xp, y))
        draw.text((x + 10, y + tile_h - 27), f"Story {count:02d}", fill="white", font=ImageFont.load_default())
        labels.append(f"{unique_name} | {entry.get('title', '')} | {entry.get('story_url', '')}")
        if download_dir:
            shutil.copy2(poster, Path(download_dir).expanduser() / unique_name)
    if not labels:
        raise FileNotFoundError("Report lists posters, but no image files exist.")
    sheet = destination / "contact_sheet.png"
    contact.save(sheet)
    index = destination / "story_index.txt"
    index.write_text("\n".join(labels) + "\n", encoding="utf-8")
    if download_dir:
        shutil.copy2(sheet, Path(download_dir).expanduser() / "contact_sheet.png")
        shutil.copy2(index, Path(download_dir).expanduser() / "story_index.txt")
    return {"exported": len(labels), "missing": missing, "sheet": str(sheet),
            "index": str(index), "download_dir": str(download_dir) if download_dir else None}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--report", default="output/story_discovery/report.json")
    p.add_argument("--outdir", default="output/story_discovery/previews")
    p.add_argument("--download-dir", default=None,
                   help="Optional Android folder, e.g. ~/storage/downloads/CartoonTamilanPosters")
    a = p.parse_args()
    result = export_posters(a.report, a.outdir, a.download_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Review original cover rights, Tamil glyphs, crop, and title before posting.")
