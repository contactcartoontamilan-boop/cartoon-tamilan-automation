"""Verified story notes for character-consistent original AI artwork.

Discovers links automatically but never invents story events or characters.
Before promoting generated art as canon, verify notes against actual chapters.
"""
import argparse
from pathlib import Path
from auto_story_marketing import discover
from campaign_v9 import read_json, write_json

BIBLES = Path(__file__).resolve().parent / "data" / "story_bibles_v10.json"


def validate_bible(record):
    if not isinstance(record, dict) or record.get("verified") is not True:
        return False
    summary = record.get("synopsis", "")
    characters = record.get("characters", [])
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1200:
        return False
    if not isinstance(characters, list) or len(characters) > 8:
        return False
    return all(isinstance(c, dict) and isinstance(c.get("appearance"), str)
               and 0 < len(c["appearance"].strip()) <= 240 for c in characters)


def sync(stories=None, filename=BIBLES):
    stories = stories if stories is not None else discover(limit=30)
    records = read_json(filename, {})
    if not isinstance(records, dict):
        raise ValueError("Story-bible JSON must be an object keyed by story URL")
    for item in stories:
        if item.get("kind") != "story":
            continue
        records.setdefault(item["link"], {
            "title": item.get("title", ""),
            "verified": False,
            "synopsis": "",
            "world_visuals": "",
            "characters": [],
            "visual_style": "cinematic original anime fantasy art",
            "notes": "Complete based on novel chapters; verify before enabling canon art"
        })
    write_json(filename, records)
    return records


def scene_prompt(title, bible=None, style="anime"):
    if style not in ("anime", "cinematic_3d"):
        raise ValueError("Artwork style must be anime or cinematic_3d")
    verified = validate_bible(bible)
    if verified:
        synopsis = bible["synopsis"].strip()[:900]
        world = str(bible.get("world_visuals", "")).strip()[:350]
        appearances = "; ".join(c["appearance"].strip() for c in bible["characters"][:4])
        context = "Verified story synopsis: " + synopsis + ". World: " + world + "."
        characters = ("Verified original character appearance: " + appearances) if appearances else (
            "No character references; depict atmospheric world scenery, not invented characters.")
    else:
        context = "Non-canonical symbolic promotional artwork, not a verified chapter or character scene."
        characters = ("Three entirely original fantasy-adventure character designs in a dynamic ensemble; "
                      "center hero and two flanking companions.")
    medium = ("intricate original hand-painted anime fantasy key visual" if style == "anime"
              else "original premium cinematic 3D-render-style image (not a mesh/model)")
    return (
        f"High-end international illustrated fantasy novel social poster art, {medium}. "
        f"Story title context: {title[:180]}. {context} {characters} "
        "Majestic original fantasy world, distant floating castles and waterfalls if appropriate to supplied notes, "
        "dramatic magical lighting, expressive faces, intricate armor and fabrics, vivid gold-magenta-indigo color, "
        "epic layered depth, premium cinematic rim light, detailed background, attractive focal composition. "
        "Vertical 4:5, leave lower third calm for typography. "
        "No text, no Tamil glyphs, no lettering, no logo, no watermark, "
        "no existing copyrighted franchise characters."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(BIBLES))
    a = p.parse_args()
    result = sync(filename=a.out)
    print("Created/updated", len(result), "story bible entries in", a.out)
    print("All new entries start unverified. Review actual chapter facts before setting verified=true.")
