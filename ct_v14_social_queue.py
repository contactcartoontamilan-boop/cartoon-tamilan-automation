#!/usr/bin/env python3
"""V14 multi-platform image inventory + review-only posting queue.

A planned time is NOT a background scheduler or a publication authorization.
This module never makes API requests, publishes, emails, or uploads content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from ctos.creative import SIZES
from ctos.platforms import PLATFORM_IMAGE
from v12_story_reader import owned_story_url

IMAGE_POST_PLATFORMS = ("instagram", "facebook", "pinterest", "threads", "x",
                        "linkedin", "telegram")
VIDEO_PLATFORMS = (
    ("instagram_reels", "instagram_story"),
    ("facebook_reels", "instagram_story"),
    ("youtube_shorts", "youtube_short"),
)
EXISTING_REVIEW_GATED_ADAPTERS = ("instagram", "facebook", "telegram")


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object: " + str(path))
    return data


def _safe_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("Missing relative media path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Unsafe file path outside preview folder")
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_image(root: Path, relative: str, variant: str, expected_hash=None) -> dict:
    if variant not in SIZES:
        raise ValueError("Unsupported image variant: " + variant)
    file = _safe_file(root, relative)
    with Image.open(file) as opened:
        if opened.format != "JPEG" or opened.size != SIZES[variant]:
            raise ValueError("Wrong image format/dimensions: " + relative)
        opened.verify()
    digest = _sha256(file)
    if expected_hash is not None and expected_hash != digest:
        raise ValueError("Image changed since preview was created: " + relative)
    return {"file": relative, "variant": variant,
            "dimensions": list(SIZES[variant]), "sha256": digest}


def _planned_time(start_at: str | None) -> datetime | None:
    if not start_at:
        return None
    try:
        when = datetime.fromisoformat(start_at)
    except ValueError as exc:
        raise ValueError("Use an ISO timestamp such as 2026-11-15T09:00:00+05:30") from exc
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("Planned time must include a timezone offset")
    return when


def prepare_social_queue(outdir: str | Path = "output/v14/image_posts",
                         *, start_at: str | None = None,
                         interval_minutes: int = 30) -> dict:
    """Check all image formats and save an idempotent, review-only post queue."""
    if not 1 <= interval_minutes <= 1440:
        raise ValueError("Interval must be 1 to 1440 minutes")
    root = Path(outdir).resolve()
    source = _read_json(root / "image_post_preview.json")
    if source.get("published") is not False or source.get("live_publishing") is not False:
        raise PermissionError("Only unpublished V14 preview indexes are accepted")
    if source.get("requires_human_review") is not True:
        raise PermissionError("Source preview must require human review")
    start = _planned_time(start_at)

    images = []
    inventory = {}
    for relative_manifest in source.get("story_manifests", []):
        manifest = _safe_file(root, relative_manifest)
        record = _read_json(manifest)
        story = record.get("story", {})
        url = story.get("link", "")
        if not owned_story_url(url) or record.get("published") is not False:
            raise PermissionError("Invalid/unreviewed owned-story preview manifest")
        by_variant = {}
        for variant, rel in record.get("assets", {}).items():
            file = (manifest.parent / rel).resolve()
            if not file.is_relative_to(root):
                raise ValueError("Unsafe manifest image path")
            item = _verify_image(root, str(file.relative_to(root)), variant)
            images.append({"story_url": url, **item})
            by_variant[variant] = item
        inventory[url] = by_variant

    queue = []
    exports = []
    seen_platform_stories = {}
    for post in source.get("posts", []):
        platform = post.get("platform")
        if platform not in PLATFORM_IMAGE:
            raise ValueError("Unknown platform: " + str(platform))
        url = post.get("story_url", "")
        if not owned_story_url(url) or url not in inventory:
            raise ValueError("Post has no verified owned story manifest")
        variant = PLATFORM_IMAGE[platform]
        verified = _verify_image(root, post.get("image_file", ""), variant,
                                 expected_hash=post.get("image_sha256"))
        if verified["sha256"] != inventory[url][variant]["sha256"]:
            raise ValueError("Post image and story manifest differ")
        caption = post.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError("Missing platform caption")
        if post.get("published") is not False or post.get("status") != "draft_review_required":
            raise PermissionError("Cannot queue a non-draft or published post")
        identity = hashlib.sha256(
            (platform + "\n" + url + "\n" + verified["sha256"] +
             "\n" + caption).encode("utf-8")).hexdigest()[:24]
        key = (platform, url)
        if key in seen_platform_stories:
            if seen_platform_stories[key] != identity:
                raise ValueError("Conflicting drafts for the same story and platform")
            continue  # Idempotent duplicate discovery must not enqueue twice.
        seen_platform_stories[key] = identity
        item = {
            "id": identity,
            "platform": platform,
            "story_url": url,
            "story_title": post.get("story_title", ""),
            "image_file": verified["file"],
            "image_sha256": verified["sha256"],
            "caption": caption,
            "status": "pending_human_review",
            "requires_account_authorization": True,
            "published": False,
            "publisher": ("existing_review_gated_adapter" if platform in
                          EXISTING_REVIEW_GATED_ADAPTERS else
                          "not_integrated_export_only"),
            "planned_time_for_review": None,
        }
        if platform == "youtube":
            item["status"] = "thumbnail_only_video_upload_required"
            exports.append(item)
        elif platform in IMAGE_POST_PLATFORMS:
            queue.append(item)
        else:
            raise ValueError("Unexpected platform mapping")

    # Never treat a planned time as a real scheduled publication.
    for number, item in enumerate(queue):
        if start is not None:
            item["planned_time_for_review"] = (
                start + timedelta(minutes=interval_minutes * number)).isoformat()

    videos = []
    for url, variants in inventory.items():
        for platform, cover_variant in VIDEO_PLATFORMS:
            cover = variants.get(cover_variant)
            videos.append({
                "platform": platform, "story_url": url,
                "cover_image_file": cover["file"] if cover else None,
                "status": "mp4_video_required",
                "published": False,
            })

    result = {
        "version": 14,
        "workflow": "review_only_multi_platform_image_queue",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "generated_image_formats": len(images),
        "image_post_queue_count": len(queue),
        "thumbnail_only_count": len(exports),
        "video_workflows_waiting_for_mp4": len(videos),
        "image_inventory": images,
        "image_post_queue": queue,
        "thumbnail_exports": exports,
        "reel_short_requirements": videos,
        "published": False,
        "live_publishing": False,
        "background_scheduler_running": False,
        "requires_human_review": True,
        "notes": [
            "These are existing website-cover designs, not newly generated AI illustrations.",
            "planned_time_for_review is only a suggested review slot, not an auto-post.",
            "Reels and Shorts require an MP4; a JPEG cover is not a publishable video.",
            "YouTube thumbnails require a real video upload, account authorization and review.",
            "Official API credentials, permissions, rate limits and rights approval are required before live posting.",
        ],
    }
    destination = root / "social_queue.json"
    temp = root / ".social_queue.json.tmp"
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(destination)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare 7-platform image queue, YouTube thumbnail and Reel/Short cover inventory")
    parser.add_argument("command", choices=("prepare", "create-and-prepare", "status"))
    parser.add_argument("--limit", type=int, default=1,
                        help="Used only by create-and-prepare")
    parser.add_argument("--outdir", default="output/v14/image_posts")
    parser.add_argument("--start-at", default=None,
                        help="Optional timezone-aware review plan; NOT live scheduling")
    parser.add_argument("--interval-minutes", type=int, default=30)
    args = parser.parse_args(argv)
    if args.command == "create-and-prepare":
        from ct_v14_image_post import prepare_image_posts
        first = prepare_image_posts(args.limit, args.outdir)
        if not first["posts"]:
            print(json.dumps({"status": "no_images_created", "published": False}))
            return 1
    if args.command == "status":
        path = Path(args.outdir) / "social_queue.json"
        if not path.is_file():
            print(json.dumps({"status": "not_prepared", "published": False}))
            return 1
        result = _read_json(path)
    else:
        result = prepare_social_queue(args.outdir, start_at=args.start_at,
                                      interval_minutes=args.interval_minutes)
    print(json.dumps({
        "generated_image_formats": result["generated_image_formats"],
        "image_post_queue_count": result["image_post_queue_count"],
        "thumbnail_only_count": result["thumbnail_only_count"],
        "video_workflows_waiting_for_mp4": result["video_workflows_waiting_for_mp4"],
        "queue_file": str(Path(args.outdir) / "social_queue.json"),
        "published": False, "background_scheduler_running": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
