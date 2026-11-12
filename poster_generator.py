"""Create original, text-first promotional posters from CartoonTamilan draft JSON.

No copyrighted anime art is downloaded or generated. Optional artwork must be
owned/licensed. Requires Pillow and a Unicode Tamil font for Tamil text.
"""
import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT_CANDIDATES = [
    "/system/fonts/NotoSansTamil-Regular.ttf",
    "/system/fonts/NotoSansTamil-VF.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansTamil-Regular.ttf",
    "/data/data/com.termux/files/usr/share/fonts/TTF/NotoSansTamil-Regular.ttf",
]


def find_font(path=None):
    if path:
        if not Path(path).is_file():
            raise FileNotFoundError("Font not found: " + path)
        return path
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError(
        "Tamil Unicode font not found. Download a licensed Noto Sans Tamil TTF "
        "and pass --font /path/to/font.ttf. Do not use a Latin-only font."
    )


def fit_lines(draw, text, font, max_width):
    words = text.split()
    lines, line = [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def make_poster(draft_path, destination, font_path, artwork=None):
    data = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    item = data["item"]
    title = item["title"].strip()
    link = item.get("link", "")
    if not title:
        raise ValueError("Draft title is empty")

    width, height = 1080, 1350
    img = Image.new("RGB", (width, height), "#10142a")
    draw = ImageDraw.Draw(img)
    for y in range(height):
        draw.line((0, y, width, y), fill=(16 + y // 160, 20 + y // 100, 42 + y // 100))

    if artwork:
        art = Image.open(artwork).convert("RGB")
        target = (920, 610)
        ratio = max(target[0] / art.width, target[1] / art.height)
        art = art.resize((int(art.width * ratio), int(art.height * ratio)), Image.Resampling.LANCZOS)
        x = (art.width - target[0]) // 2
        y = (art.height - target[1]) // 2
        img.paste(art.crop((x, y, x + target[0], y + target[1])), (80, 170))
    else:
        draw.rounded_rectangle((80, 170, 1000, 780), radius=36, fill="#263056")
        draw.ellipse((610, 250, 940, 580), fill="#485ca0")
        draw.polygon([(150, 690), (470, 310), (810, 690)], fill="#3b4c83")

    fontfile = find_font(font_path)
    brand = ImageFont.truetype(fontfile, 46)
    heading = ImageFont.truetype(fontfile, 52)
    small = ImageFont.truetype(fontfile, 31)
    draw.text((80, 65), "CartoonTamilan", font=brand, fill="#f7f5ff")
    draw.text((80, 810), "ORIGINAL STORY  |  புதிய கதை", font=small, fill="#f7cf7c")

    lines = fit_lines(draw, title, heading, 920)
    if len(lines) > 4:
        raise ValueError("Title too long for poster; shorten title or customize layout")
    y = 875
    for line in lines:
        draw.text((80, y), line, font=heading, fill="#ffffff")
        y += 76
    draw.rounded_rectangle((80, 1205, 1000, 1290), radius=20, fill="#efbb61")
    draw.text((110, 1220), "READ THE STORY  •  cartoontamilan.in", font=small, fill="#12172b")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination, format="PNG")
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", required=True, help="Path to output/*.json")
    parser.add_argument("--out", default="output/poster.png")
    parser.add_argument("--font", help="Path to Unicode Tamil TTF font")
    parser.add_argument("--artwork", help="Optional original/licensed image")
    args = parser.parse_args()
    print("Poster saved:", make_poster(args.draft, args.out, args.font, args.artwork))


if __name__ == "__main__":
    main()
