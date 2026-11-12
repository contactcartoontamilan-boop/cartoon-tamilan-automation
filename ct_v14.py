#!/usr/bin/env python3
"""V14 source-faithful, review-first full story video CLI. NO publishing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ctos.v14_story import plan_story, save_plan, validate_scene_images
from ctos.v14_video import make_story_video, write_scene_srt
from ctos.v14_voice import azure_tamil_female, concatenate_wav


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(args) -> dict:
    if not (args.rights_confirmed and args.copy_reviewed and args.visual_reviewed):
        raise PermissionError(
            "Building requires --rights-confirmed --copy-reviewed --visual-reviewed. "
            "Live posting is always OFF."
        )
    script = Path(args.script).read_text(encoding="utf-8")
    plan = plan_story(script, args.scenes)
    art = validate_scene_images(args.art_dir, args.scenes)
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    save_plan(plan, output / "storyboard.json")
    narration = None
    if args.voice == "azure":
        clips = []
        for scene in plan["scenes"]:
            path = output / "scene_voice" / f"scene_{scene['scene']:02d}.wav"
            clips.append(azure_tamil_female(
                scene["narration"], path, rights_confirmed=True))
        narration, durations = concatenate_wav(
            clips, output / "narration.wav", pause_ms=250)
    else:
        if not 60 <= args.target_seconds <= 120:
            raise ValueError("Silent-preview target must be 60–120 seconds")
        durations = [args.target_seconds / args.scenes] * args.scenes
    srt = write_scene_srt(plan["scenes"], durations, output / "subtitles.srt")
    video = make_story_video(
        art, durations, output / "story_9x16.mp4",
        rights_confirmed=True, narration=narration)
    report = {
        "version": 14,
        "status": "draft_ready_review_required",
        "source_sha256": plan["source_sha256"],
        "scene_count": len(art),
        "images": [{"path": str(p), "sha256": _sha(p)} for p in art],
        "storyboard": "storyboard.json",
        "video": "story_9x16.mp4",
        "subtitles": "subtitles.srt",
        "narration": "narration.wav" if narration else None,
        "voice_provider": "azure_tamil_female_neural" if narration else "none",
        "voice_human_listening_review_required": bool(narration),
        "subtitles_timing": "scene-boundary exact; within-scene estimated, not forced-aligned",
        "video_qa": video,
        "creative_qa": {
            "unique_approved_images": True,
            "character_and_story_accuracy": "human_review_required",
            "audio_pronunciation": "human_review_required",
            "safe_area_and_captions": "human_review_required",
        },
        "requires_human_review": True,
        "published": False,
        "live_publishing": False,
        "email_sent": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="CartoonTamilan V14 — original 60–120s story video, never auto-publish")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Offline storyboard preview (no GPU, API or video)")
    plan.add_argument("--script", required=True, help="Original, reviewed UTF-8 Tamil narration")
    plan.add_argument("--scenes", type=int, default=8)
    plan.add_argument("--out", default="output/v14/storyboard.json")

    render = commands.add_parser("build", help="Review-gated 9:16 MP4 and subtitles")
    render.add_argument("--script", required=True)
    render.add_argument("--art-dir", required=True,
                        help="Unique original scene_01.png ... scene_08.png")
    render.add_argument("--scenes", type=int, default=8)
    render.add_argument("--out", default="output/v14/manual")
    render.add_argument("--voice", choices=("none", "azure"), default="none")
    render.add_argument("--target-seconds", type=int, default=90,
                        help="Only for silent preview; neural audio sets real duration")
    render.add_argument("--rights-confirmed", action="store_true")
    render.add_argument("--copy-reviewed", action="store_true")
    render.add_argument("--visual-reviewed", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "plan":
        storyboard = plan_story(Path(args.script).read_text(encoding="utf-8"),
                                args.scenes)
        destination = save_plan(storyboard, args.out)
        print(json.dumps({"status": "storyboard_review_required",
                          "file": str(destination), "scenes": args.scenes},
                         ensure_ascii=False, indent=2))
    else:
        print(json.dumps(build(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
