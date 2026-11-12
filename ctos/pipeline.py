"""CartoonTamilan Marketing OS V13: preview-first unified campaign bundles.

Actual source artwork is always a raw cover or genuinely generated AI output.
Does not retype on an existing poster. Facebook/Instagram/other publishing
is isolated in ctos.platforms and never invoked by this pipeline.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

from auto_story_cover import auto_cover
from auto_story_marketing import discover, poster_headline
from campaign_v9 import load_approvals, select_stories, write_json, read_json
from ctos.artwork import get_art
from ctos.content import make_captions
from ctos.creative import render_pack
from ctos.emailer import build_email, save_draft
from ctos.platforms import export_platform_drafts
from ctos.qa import validate_assets
from ctos.video import create_short


def _key(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _draft(story, folder):
    file = folder / "source_story.json"
    write_json(file, {"item": story, "status": "source_story"})
    return file


def _relative(path, folder):
    return str(Path(path).resolve().relative_to(folder.resolve()))


def build_one(story, base, approval=None, art_mode="cover", art_style="anime",
              make_video=False, voice=False, seconds=12,
              art_fetcher=None, renderer=None, video_builder=None):
    folder = Path(base) / _key(story["link"])
    folder.mkdir(parents=True, exist_ok=True)
    draft = _draft(story, folder)
    if art_mode == "cover":
        raw = (art_fetcher or auto_cover)(draft, folder / "original_cover")
        art = get_art(story["link"], raw_cover=raw, backend="cover",
                      style=art_style)
    else:
        art = get_art(story["link"], backend=art_mode, style=art_style,
                      output=folder / "ai_original_art.png")
    title = poster_headline(story["title"], limit=85)
    assets = (renderer or render_pack)(
        art["path"], title, folder / "media", story_url=story["link"])
    relative = {kind: _relative(row["file"], folder)
                for kind, row in assets["assets"].items()}
    audit = validate_assets(folder, relative)
    if not audit["passed"]:
        raise RuntimeError("Image dimensions/format QA failed; no bundle approved")
    copy = make_captions(story, approval=approval)
    email = build_email(
        story, intro_ta=str((approval or {}).get("intro_ta", "")),
        intro_en=str((approval or {}).get("intro_en", "")))
    save_draft(email, folder / "email")
    media = {"video": None, "voiceover": None, "subtitles": None}
    errors = []
    if voice and not make_video:
        errors.append("Voice needs --video to form a complete Reel package")
    if make_video:
        script = (str((approval or {}).get("intro_ta", "")).strip()
                  if (approval or {}).get("copy_reviewed") is True
                  else "புதிய தமிழ் அசல் கதை. கார்ட்டூன் தமிழனில் படியுங்கள்.")
        try:
            media = (video_builder or create_short)(
                folder / relative["instagram_story"], folder / "video",
                script=script, language="ta", seconds=seconds,
                voice_rights=True, use_tts=voice)
        except (OSError, RuntimeError, ValueError) as error:
            # Don't misrepresent a failed optional video as successful.
            errors.append("Video/voice unavailable: " + type(error).__name__ + ": " + str(error)[:120])
    record = {
        "version": 13, "created_utc": datetime.now(timezone.utc).isoformat(),
        "story": story, "title": title,
        "source_artwork": _relative(art["path"], folder),
        "art_provenance": {k: v for k, v in art.items() if k not in ("path", "prompt")},
        "art_prompt": art.get("prompt", ""),
        "assets": relative, "creative_qa": audit,
        "copy": copy, "email_draft": "email/newsletter.html",
        "media": {k: (_relative(v, folder) if v else None)
                  for k, v in media.items() if k in ("video", "voiceover", "subtitles")},
        "rights_confirmed_in_old_approvals": bool((approval or {}).get("rights_confirmed")),
        "visual_reviewed": False,
        "status": "draft_review_required",
        "published": False, "issues": errors,
    }
    manifest = folder / "manifest.json"
    write_json(manifest, record)
    exports = export_platform_drafts(manifest)
    return {
        "story_title": title, "story_url": story["link"],
        "manifest": str(manifest), "art_source": str(art["path"]),
        "platform_count": len(exports), "images": len(relative),
        "video_generated": bool(media.get("video")),
        "voice_generated": bool(media.get("voiceover")),
        "review_required": True, "issues": errors,
    }


def run(limit=1, day=None, outdir="output/v13", art_mode="cover",
        art_style="anime", make_video=False, voice=False, seconds=12,
        discover_func=None, artwork_fetcher=None,
        renderer=None, video_builder=None):
    if not 1 <= limit <= 6:
        raise ValueError("Use limit between 1 and 6")
    if art_mode not in ("cover", "comfyui"):
        raise ValueError("Supported artwork: own story cover or configured ComfyUI")
    day = day or date.today()
    source = (discover_func or discover)(limit=30)
    selected = select_stories(source, day, limit)
    approvals = load_approvals()
    folder = Path(outdir) / day.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    report = {
        "date": day.isoformat(), "version": 13,
        "discovered": len(source), "selected": len(selected),
        "prepared": [], "failed": [], "live_publishing": False,
        "review_required": True,
        "art_mode": art_mode,
        "important": "No AI artwork is generated in cover mode. All creatives require review."
    }
    for item in selected:
        try:
            result = build_one(
                item, folder, approval=approvals.get(item["link"], {}),
                art_mode=art_mode, art_style=art_style,
                make_video=make_video, voice=voice, seconds=seconds,
                art_fetcher=artwork_fetcher, renderer=renderer,
                video_builder=video_builder)
            report["prepared"].append(result)
        except Exception as error:
            report["failed"].append({
                "story_url": item.get("link", ""),
                "error_type": type(error).__name__,
                "reason": str(error)[:220],
            })
    report["status"] = ("draft_ready_review_required" if report["prepared"] and not report["failed"]
                        else "partial" if report["prepared"] else "failed")
    write_json(folder / "report.json", report)
    write_json(Path(outdir) / "latest.json",
               {"status": report["status"], "report": str(folder / "report.json"),
                "prepared": len(report["prepared"]),
                "failed": len(report["failed"]),
                "last_run_utc": datetime.now(timezone.utc).isoformat()})
    return report
