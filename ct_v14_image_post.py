#!/usr/bin/env python3
"""V14 image-post preview automation. Reuses V13 artwork/layout code; NEVER publishes.

Run on the isolated V14 checkout. Discovers an owned-site novel, builds image
drafts and captions, verifies saved JPEGs, and writes a review-only queue.
No Meta/Telegram/email API calls are made by this entry point.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ctos.creative import SIZES
from ctos.pipeline import run
from ctos.platforms import PLATFORM_IMAGE
from v12_story_reader import owned_story_url


def _inside(folder: Path, file: str | Path) -> Path:
    root = folder.resolve()
    candidate = Path(file).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Unsafe output path outside the image-post preview folder")
    return candidate


def _sha256(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(path)


def prepare_image_posts(limit: int = 1, outdir: str | Path = "output/v14/image_posts",
                        *, runner=None, art_mode: str = "cover",
                        art_style: str = "anime") -> dict:
    """Save verified, unapproved post drafts; do not post or email anything.

    Uses the existing V13 safe draft renderer instead of duplicating it.
    A runner can be injected for completely offline tests.
    """
    if not 1 <= limit <= 6:
        raise ValueError("Choose between 1 and 6 stories")
    if art_mode not in ("cover", "comfyui"):
        raise ValueError("Choose art_mode cover or comfyui")
    if art_style not in ("anime", "cinematic_3d", "realistic_cinematic"):
        raise ValueError("Choose anime, cinematic_3d, or realistic_cinematic art style")
    root = Path(outdir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    run_args = {
        "limit": limit, "outdir": str(root), "art_mode": art_mode,
        "make_video": False, "voice": False, "audit": False, "chapters": False,
    }
    # Preserve compatibility with existing preview runners using the default style.
    if art_style != "anime":
        run_args["art_style"] = art_style
    report = (runner or run)(**run_args)
    posts = []
    story_manifests = []

    for item in report.get("prepared", []):
        manifest = _inside(root, item["manifest"])
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("published") is not False or data.get("status") != "draft_review_required":
            raise ValueError("Source bundle must be an unpublished review draft")
        story = data.get("story", {})
        story_url = story.get("link", "")
        if not owned_story_url(story_url):
            raise ValueError("Only original CartoonTamilan HTTPS /novel/ stories allowed")

        exports_file = _inside(root, manifest.parent / "platform_drafts.json")
        exports = json.loads(exports_file.read_text(encoding="utf-8"))
        if not exports:
            raise ValueError("Source bundle has no platform image drafts")

        for platform, draft in exports.items():
            variant = PLATFORM_IMAGE.get(platform)
            if variant not in SIZES:
                raise ValueError("Unknown image post platform: " + platform)
            if draft.get("publication_status") != "not_published":
                raise ValueError("Post was already marked as published")
            if draft.get("story_url") != story_url:
                raise ValueError("Post story URL does not match source manifest")
            relative = draft.get("image_file", "")
            image = _inside(root, manifest.parent / relative)
            if not image.is_file():
                raise FileNotFoundError(str(image))
            with Image.open(image) as opened:
                if opened.format != "JPEG" or opened.size != SIZES[variant]:
                    raise ValueError("Invalid JPEG dimensions/format for " + platform)
            caption = draft.get("caption", "")
            if not isinstance(caption, str) or not caption.strip():
                raise ValueError("Missing caption for " + platform)
            posts.append({
                "platform": platform,
                "story_title": story.get("title", ""),
                "story_url": story_url,
                "image_file": str(image.relative_to(root)),
                "image_sha256": _sha256(image),
                "dimensions": list(SIZES[variant]),
                "caption": caption,
                "status": "draft_review_required",
                "published": False,
            })
        story_manifests.append(str(manifest.relative_to(root)))

    result = {
        "version": 14,
        "workflow": "website_to_image_post_preview",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_pipeline": "v13_safe_preview_renderer",
        "art_mode": art_mode,
        "art_style": art_style,
        "status": "draft_ready_review_required" if posts else "no_drafts_created",
        "stories_prepared": len(story_manifests),
        "post_drafts_created": len(posts),
        "story_manifests": story_manifests,
        "posts": posts,
        "failures": report.get("failed", []),
        "requires_human_review": True,
        "copyright_review_required": True,
        "published": False,
        "live_publishing": False,
        "email_sent": False,
        "notes": [
            ("Uses website story covers; not AI-generated art." if art_mode == "cover"
             else "Uses configured ComfyUI with a verified story bible; review generated artwork."),
            "Check cover license, story match, Tamil typography and any baked-in text.",
            "No post is uploaded or scheduled; approvals and API permissions are separate.",
        ],
    }
    _write_json(root / "image_post_preview.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Auto-discover CartoonTamilan stories and save review-only image posts")
    parser.add_argument("command", nargs="?", choices=("create", "status"), default="create")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--outdir", default="output/v14/image_posts")
    parser.add_argument("--art-mode", choices=("cover", "comfyui"), default="cover",
                        help="Use the existing cover or a configured ComfyUI model")
    parser.add_argument("--style", choices=("anime", "cinematic_3d", "realistic_cinematic"),
                        default="anime", help="Generated-art style; requires --art-mode comfyui")
    args = parser.parse_args(argv)
    if args.command == "status":
        path = Path(args.outdir) / "image_post_preview.json"
        if not path.is_file():
            print(json.dumps({"status": "not_created", "file": str(path)}))
            return 1
        result = json.loads(path.read_text(encoding="utf-8"))
    else:
        result = prepare_image_posts(args.limit, args.outdir,
                                      art_mode=args.art_mode, art_style=args.style)
    print(json.dumps({
        "status": result["status"],
        "stories_prepared": result.get("stories_prepared", 0),
        "post_drafts_created": result.get("post_drafts_created", 0),
        "art_mode": result.get("art_mode", "cover"),
        "art_style": result.get("art_style", "anime"),
        "preview_file": str(Path(args.outdir) / "image_post_preview.json"),
        "failures": result.get("failures", []),
        "published": False,
    }, ensure_ascii=False, indent=2))
    return 0 if result.get("post_drafts_created", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
