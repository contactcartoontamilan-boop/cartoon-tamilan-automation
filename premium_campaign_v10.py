"""CartoonTamilan V10: automatic premium story creative + guarded social publishing.

Default is preview only. --publish requires V9 approvals, Meta access,
public HTTPS image hosting, and explicit publication flags.
"""
import argparse
import hashlib
import json
import os
import shutil
from datetime import date
from pathlib import Path

from auto_story_marketing import discover
from auto_story_cover import auto_cover
from campaign_v9 import (read_json, write_json, load_approvals,
                         get_approval, select_stories,
                         check_publish_ready, publish_pack)
from premium_poster_v10 import make_premium_poster, THEMES
from social_content_v5 import make_social_pack
from story_bible_v10 import BIBLES, scene_prompt, validate_bible

OUT = Path("output/premium_v10")


def _story_dir(item, day, base=OUT):
    identifier = hashlib.sha256(item["link"].encode("utf-8")).hexdigest()[:16]
    return Path(base) / day.isoformat() / identifier


def create_premium_campaign(item, day, provider="cover", theme="royal",
                            style="anime", approved=None, bibles=None,
                            outdir=OUT, cover_fetcher=None,
                            art_generator=None, poster_maker=None):
    """Create poster and bilingual social pack. Never calls Meta."""
    if provider not in ("cover", "comfyui"):
        raise ValueError("art provider must be cover or comfyui")
    if theme not in THEMES:
        raise ValueError("Invalid poster theme")
    folder = _story_dir(item, day, outdir)
    folder.mkdir(parents=True, exist_ok=True)
    draft = folder / "draft.json"
    original = {"item": {**item, "kind": "story",
                         "id": folder.name}, "status": "draft_review_required"}
    write_json(draft, original)

    bible = (bibles or {}).get(item["link"], {})
    if provider == "comfyui":
        prompt = scene_prompt(item["title"], bible, style=style)
        (folder / "art_prompt.txt").write_text(prompt, encoding="utf-8")
        if art_generator is None:
            if not os.getenv("COMFYUI_CHECKPOINT", "").strip():
                raise RuntimeError(
                    "AI art requires a running ComfyUI and installed licensed "
                    "checkpoint. Configure COMFYUI_CHECKPOINT; do not use a placeholder.")
            from comfyui_art_v9 import generate
            art_generator = lambda description, path: generate(description, path)
        artwork = Path(art_generator(prompt, folder / "original_ai_art.png"))
    else:
        artwork = Path((cover_fetcher or auto_cover)(draft, folder / "covers"))

    destination = folder / "premium_poster.jpg"
    (poster_maker or make_premium_poster)(
        draft, artwork, destination, theme=theme)
    if not destination.is_file():
        raise RuntimeError("Poster renderer did not create a JPEG")

    record = approved or {}
    pack = make_social_pack(
        original["item"], genres=record.get("genres", ()),
        verified_intro_ta=record.get("intro_ta", ""),
        verified_intro_en=record.get("intro_en", ""))
    pack.update({
        "poster": str(destination),
        "draft_path": str(draft),
        "artwork": str(artwork),
        "art_provider": provider,
        "theme": theme,
        "artwork_generated_by_ai": provider == "comfyui",
        "verified_story_bible": validate_bible(bible),
        "copyright_checked": bool(record.get("rights_confirmed")),
        "copy_reviewed": bool(record.get("copy_reviewed")),
        "ai_art_approved": bool(record.get("ai_art_approved")),
        "story_specificity_warning": (
            "Character and scene details are fictional promo interpretation, "
            "NOT verified novel canon." if provider == "comfyui"
            and not validate_bible(bible) else ""),
        "status": "review_required"
    })
    write_json(folder / "social_pack.json", pack)
    return pack


def make_campaign_batch(limit=2, provider="cover", theme="auto",
                        style="anime", publish=False, day=None,
                        outdir=OUT, export_dir=None, discovery=None,
                        cover_fetcher=None, art_generator=None,
                        poster_maker=None, publisher=None):
    """Discover, create, optionally publish APPROVED posters one story at a time."""
    day = day or date.today()
    if publish:
        check_publish_ready()
    stories = (discovery or discover)(limit=30)
    selected = select_stories(stories, day, limit)
    approvals = load_approvals()
    bibles = read_json(BIBLES, {})
    themes = tuple(THEMES)
    report = {
        "date": day.isoformat(), "discovered": len(stories),
        "selected": len(selected), "prepared": [],
        "published": [], "failed": [],
        "dry_run": not publish,
        "ai_generation_requested": provider == "comfyui",
    }
    for index, item in enumerate(selected):
        try:
            approval = get_approval(item, approvals)
            if publish and not approval:
                raise ValueError("Story rights and Tamil/English captions not approved")
            if publish and provider == "comfyui":
                if not approval.get("ai_art_approved"):
                    raise ValueError("AI artwork not individually approved")
                if not validate_bible(bibles.get(item["link"], {})):
                    raise ValueError("Verified chapter-based story bible required for live AI art")
            theme_name = themes[index % len(themes)] if theme == "auto" else theme
            pack = create_premium_campaign(
                item, day, provider=provider, theme=theme_name,
                style=style, approved=approval, bibles=bibles,
                outdir=outdir, cover_fetcher=cover_fetcher,
                art_generator=art_generator, poster_maker=poster_maker)
            report["prepared"].append({
                "title": item["title"], "story_url": item["link"],
                "poster": pack["poster"], "social_pack":
                str(Path(pack["poster"]).parent / "social_pack.json"),
                "theme": theme_name})
            if publish:
                result = (publisher or publish_pack)(item, pack, day=day)
                report["published"].append({
                    "title": item["title"], "result": result})
        except Exception as exc:
            # Avoid leaking tokens, private prompts or URLs in reports.
            report["failed"].append({
                "title": item.get("title", ""), "error_type": type(exc).__name__,
                "message": str(exc)[:180] if isinstance(
                    exc, (ValueError, FileNotFoundError, RuntimeError, TimeoutError))
                else "Review server logs locally"})
    report_path = Path(outdir) / day.isoformat() / "report.json"
    write_json(report_path, report)
    if export_dir:
        export = Path(export_dir).expanduser()
        export.mkdir(parents=True, exist_ok=True)
        saved = []
        for row in report["prepared"]:
            poster = Path(row["poster"])
            name = f"CT_{day.isoformat()}_{poster.parent.name}.jpg"
            destination = export / name
            shutil.copy2(poster, destination)
            saved.append(str(destination))
        report["exported_jpgs"] = saved
        write_json(report_path, report)
    return report


def main():
    p = argparse.ArgumentParser(description="Generate premium original story posts.")
    p.add_argument("--limit", type=int, default=2, help="1–6 stories")
    p.add_argument("--art-provider", choices=["cover", "comfyui"], default="cover")
    p.add_argument("--theme", choices=["auto", *THEMES], default="auto")
    p.add_argument("--style", choices=["anime", "cinematic_3d"], default="anime")
    p.add_argument("--export-dir", help="Android Downloads folder for generated JPEGs")
    p.add_argument("--publish", action="store_true",
                   help="Real Meta API posting; only when ALL safety gates pass")
    args = p.parse_args()
    if not 1 <= args.limit <= 6:
        p.error("--limit must be between 1 and 6")
    result = make_campaign_batch(
        limit=args.limit, provider=args.art_provider, theme=args.theme,
        style=args.style, publish=args.publish, export_dir=args.export_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
