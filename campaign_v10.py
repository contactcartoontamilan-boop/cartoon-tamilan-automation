"""CartoonTamilan V10: auto story discovery → artwork → premium poster → captions.

Preview is the DEFAULT and makes no Meta API calls.
For live publishing, use existing V9 rights, Meta permission, public JPEG
hosting and duplicate-protection journal plus V10 visual policy approval.
"""
import argparse
import json
import os
import shutil
from pathlib import Path

from campaign_v9 import create_campaign, run as run_v9, write_json
from premium_poster_v10 import make_premium_poster
from art_direction_v10 import concept_prompt

ART_MODES = ("cover", "comfyui")
THEMES = ("royal", "crimson", "cosmic", "emerald")


def _theme_for(record):
    theme = (record or {}).get("premium_theme", "royal")
    if theme not in THEMES:
        raise ValueError("Unsupported premium_theme in story approval record")
    return theme


def build_premium_campaign(item, day, art_mode="cover", outdir="output/premium_v10",
                           approval=None, publish=False, cover_fetcher=None,
                           image_generator=None, poster_maker=None):
    """Build ONE reviewed, trackable Instagram/Facebook campaign draft."""
    if art_mode not in ART_MODES:
        raise ValueError("Use art_mode cover or comfyui")
    record = approval or {}
    if publish:
        if not approval or record.get("v10_visual_policy_approved") is not True:
            raise ValueError("Visual publishing requires approved V10 visual policy")
        if art_mode == "comfyui" and record.get("v10_automatic_ai_approved") is not True:
            raise ValueError("AI art autopublishing requires v10_automatic_ai_approved=true")

    genre = ((record.get("genres") or ["fantasy"])[0] or "fantasy")
    theme = _theme_for(record)
    style = os.getenv("ART_STYLE", "anime")
    prompt = concept_prompt(
        item["title"], genre=genre,
        character_notes=record.get("verified_character_notes", ""),
        world_notes=record.get("verified_world_notes", ""),
        style=style)

    def generate_art(title, destination):
        if image_generator:
            return image_generator(prompt, destination)
        from comfyui_art_v9 import generate
        return generate(prompt, destination)

    def poster(draft, artwork, destination):
        return ((poster_maker or make_premium_poster)(
            draft, artwork, destination, theme=theme))

    pack = create_campaign(
        item, day, art_provider=art_mode, outdir=outdir, approval=approval,
        cover_fetcher=cover_fetcher,
        artwork_generator=generate_art if art_mode == "comfyui" else None,
        poster_maker=poster,
    )
    original = Path(pack["poster"])
    premium = original.with_name("premium_poster.jpg")
    if premium != original:
        original.replace(premium)
    pack["poster"] = str(premium)
    pack["art_prompt"] = prompt
    pack["visual_theme"] = theme
    pack["actual_new_art_generated"] = art_mode == "comfyui"
    pack["art_generation_backend"] = "ComfyUI" if art_mode == "comfyui" else "website_cover"
    pack["story_specific_notes_verified"] = bool(record.get("verified_character_notes")
                                                   or record.get("verified_world_notes"))
    pack["v10_visual_policy_approved"] = record.get("v10_visual_policy_approved") is True
    pack["status"] = ("approved_for_automated_publishing"
                      if publish else "draft_review_required")
    write_json(premium.parent / "social_pack.json", pack)
    return pack


def run_v10(limit=2, publish=False, art_mode="cover", outdir="output/premium_v10",
            day=None, discovery_func=None, export_dir=None, campaign_builder=None):
    def make_campaign(item, campaign_day, passed_mode, passed_dir, approval=None):
        return (campaign_builder or build_premium_campaign)(
            item, campaign_day, art_mode=passed_mode, outdir=passed_dir,
            approval=approval, publish=publish)
    summary = run_v9(
        limit=limit, publish=publish, art_provider=art_mode, day=day,
        outdir=outdir, discovery_func=discovery_func, campaign_func=make_campaign)
    if export_dir:
        destination = Path(export_dir).expanduser()
        destination.mkdir(parents=True, exist_ok=True)
        exported = []
        for item in summary.get("prepared", []):
            image = Path(item["poster"])
            if image.is_file():
                unique = image.parent.parent.name + "_" + image.parent.name + ".jpg"
                target = destination / unique
                shutil.copy2(image, target)
                exported.append(str(target))
        summary["exported_jpgs"] = exported
    return summary


def main():
    parser = argparse.ArgumentParser(description="CartoonTamilan premium V10 campaign")
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--art-mode", choices=ART_MODES, default="cover")
    parser.add_argument("--publish", action="store_true", help="Opt-in after Meta/rights and visual policy gates")
    parser.add_argument("--export-dir", default="")
    args = parser.parse_args()
    if not 1 <= args.limit <= 6:
        parser.error("--limit must be 1–6")
    report = run_v10(limit=args.limit, publish=args.publish, art_mode=args.art_mode,
                     export_dir=args.export_dir or None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
