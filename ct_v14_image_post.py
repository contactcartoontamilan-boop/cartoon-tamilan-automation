#!/usr/bin/env python3
"""V14 automatic website-story IMAGE POST drafts. Never publishes.

Reuses the V13 website catalogue, licensed-cover fetch, Tamil typography,
platform image renderers, caption drafts and deterministic QA. This is NOT
an AI image generator or an automatic social publisher.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctos.pipeline import run
from v12_story_reader import owned_story_url

IMAGE_KINDS = ("instagram_feed", "facebook_feed", "instagram_story")
CHANNELS = ("instagram", "facebook")


def create_image_post_preview(limit=1, outdir="output/v14/image_posts",
                              pipeline_runner=None):
    """Discover owned stories and save review-only image posts under V14.

    The V13 implementation is imported, not edited or redeployed. The runner
    may be injected for offline tests; no publishing functions are called.
    """
    if not 1 <= limit <= 3:
        raise ValueError("Use 1–3 image post drafts per run")
    root = Path(outdir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    report = (pipeline_runner or run)(
        limit=limit, outdir=str(root), art_mode="cover",
        make_video=False, voice=False, audit=False, chapters=False)
    previews = []
    for item in report.get("prepared", []):
        manifest = Path(item["manifest"]).resolve()
        if not manifest.is_relative_to(root) or not manifest.is_file():
            raise ValueError("Unsafe or missing image-post manifest")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if (data.get("published") is not False
                or data.get("status") != "draft_review_required"
                or data.get("creative_qa", {}).get("passed") is not True):
            raise ValueError("Image post is not a QA-passed unpublished draft")
        story = data.get("story", {})
        if not owned_story_url(story.get("link", "")):
            raise ValueError("Only CartoonTamilan /novel/ stories are allowed")
        images = {}
        for kind in IMAGE_KINDS:
            relative = data.get("assets", {}).get(kind)
            if not relative:
                raise ValueError("Missing image format: " + kind)
            path = (manifest.parent / relative).resolve()
            if not path.is_relative_to(manifest.parent) or not path.is_file():
                raise ValueError("Unsafe or missing generated image: " + kind)
            images[kind] = str(path)
        drafts = manifest.parent / "platform_drafts.json"
        if not drafts.is_file():
            raise ValueError("Missing social caption drafts")
        channels = json.loads(drafts.read_text(encoding="utf-8"))
        if any(channels.get(channel, {}).get("publication_status") != "not_published"
               for channel in CHANNELS):
            raise ValueError("Image post draft must not be published")
        previews.append({
            "title": story.get("title", ""),
            "story_url": story["link"],
            "images": images,
            "manifest": str(manifest),
            "caption_drafts": str(drafts),
            "review_required": True,
            "published": False,
        })
    failures = report.get("failed", [])
    status = ("draft_ready_review_required" if previews and not failures
              else "partial" if previews else "failed")
    index = {
        "version": 14,
        "type": "automatic_website_image_post_preview",
        "status": status,
        "discovered": report.get("discovered", 0),
        "prepared": len(previews),
        "failed": failures,
        "artwork": "existing_story_cover_not_ai_generated",
        "stories": previews,
        "requires_human_review": True,
        "published": False,
        "live_publishing": False,
        "email_sent": False,
    }
    destination = root / "image_post_index.json"
    temp = root / "image_post_index.json.tmp"
    temp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(destination)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CartoonTamilan V14 website -> image post drafts (NO publishing)")
    parser.add_argument("--limit", type=int, default=1, help="1–3 website stories")
    parser.add_argument("--outdir", default="output/v14/image_posts")
    parser.add_argument("--status", action="store_true",
                        help="Read last saved result without accessing website")
    args = parser.parse_args(argv)
    index_file = Path(args.outdir).expanduser().resolve() / "image_post_index.json"
    if args.status:
        if not index_file.is_file():
            print(json.dumps({"status": "not_run_yet", "index_file": str(index_file)}))
            return 1
        print(index_file.read_text(encoding="utf-8"))
        return 0
    try:
        result = create_image_post_preview(limit=args.limit, outdir=args.outdir)
    except Exception as exc:
        # Do not leak provider tokens, private source text or HTTP response bodies.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "note": "Review website access, approved cover and local logs. "
                                  "No post was published."}))
        return 1
    print(json.dumps({"status": result["status"],
                      "prepared": result["prepared"],
                      "failed": len(result["failed"]),
                      "index_file": str(index_file),
                      "published": False,
                      "review_required": True}, ensure_ascii=False, indent=2))
    return 0 if result["prepared"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
