#!/usr/bin/env python3
"""V14 image-post preparation with realistic ComfyUI and cover fallback.

This builds drafts only. In auto mode, try the configured local ComfyUI using
realistic cinematic prompts; if it is unavailable or cannot prepare a story,
fall back to the existing story cover so hourly queue preparation can continue.
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
                        *, runner=None, art_mode: str = "auto",
                        art_style: str = "realistic_cinematic") -> dict:
    """Prepare unpublished drafts; auto mode prefers realistic AI art safely."""
    if not 1 <= limit <= 6:
        raise ValueError("Choose between 1 and 6 stories")
    if art_mode not in ("auto", "cover", "comfyui"):
        raise ValueError("Choose art_mode auto, cover, or comfyui")
    if art_style not in ("anime", "cinematic_3d", "realistic_cinematic"):
        raise ValueError("Choose anime, cinematic_3d, or realistic_cinematic")
    root = Path(outdir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    effective_mode = art_mode
    fallback_reason = None
    if art_mode == "auto":
        try:
            from comfyui_art_v9 import check_connection
            check_connection()
            effective_mode = "comfyui"
        except (RuntimeError, ValueError, OSError) as exc:
            effective_mode = "cover"
            fallback_reason = type(exc).__name__

    def invoke(mode):
        run_args = {
            "limit": limit, "outdir": str(root), "art_mode": mode,
            "make_video": False, "voice": False, "audit": False, "chapters": False,
        }
        # Keep compatibility with injected preview runners; only production
        # pipeline receives the selected art style.
        if runner is None:
            run_args["art_style"] = art_style
        return (runner or run)(**run_args)

    report = invoke(effective_mode)
    if art_mode == "auto" and effective_mode == "comfyui" and not report.get("prepared"):
        # A live endpoint may still lack the approved story bible/workflow.
        fallback_reason = "ComfyUICouldNotPrepareStory"
        effective_mode = "cover"
        report = invoke(effective_mode)

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
        "art_mode_requested": art_mode,
        "art_mode": effective_mode,
        "art_style": art_style,
        "art_fallback_reason": fallback_reason,
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
            ("Generated with configured ComfyUI; review the original artwork."
             if effective_mode == "comfyui"
             else "Used the existing story cover because realistic ComfyUI was unavailable."),
            "Captions use source or approved story descriptions; verify plot details and Tamil before publishing.",
            "This step only prepares drafts; the separate hourly publisher handles authorized posts.",
        ],
    }
    _write_json(root / "image_post_preview.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare social image drafts; prefer realistic ComfyUI art with safe cover fallback")
    parser.add_argument("command", nargs="?", choices=("create", "status"), default="create")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--outdir", default="output/v14/image_posts")
    parser.add_argument("--art-mode", choices=("auto", "cover", "comfyui"), default="auto",
                        help="auto tries realistic ComfyUI then falls back to the story cover")
    parser.add_argument("--style", choices=("anime", "cinematic_3d", "realistic_cinematic"),
                        default="realistic_cinematic",
                        help="Generated-art style; auto defaults to realistic cinematic")
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
        "art_mode_requested": result.get("art_mode_requested", result.get("art_mode", "cover")),
        "art_mode": result.get("art_mode", "cover"),
        "art_style": result.get("art_style", "realistic_cinematic"),
        "art_fallback_reason": result.get("art_fallback_reason"),
        "preview_file": str(Path(args.outdir) / "image_post_preview.json"),
        "failures": result.get("failures", []),
        "published": False,
    }, ensure_ascii=False, indent=2))
    return 0 if result.get("post_drafts_created", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
