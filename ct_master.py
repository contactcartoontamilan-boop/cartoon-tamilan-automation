#!/usr/bin/env python3
"""CartoonTamilan Marketing OS V13.

Safe-by-default interface. Produces review bundles for owned original stories.
Live Meta or Telegram publishing is opt-in, per-bundle approved, and uses the
existing rights/Meta journal. All other social channels export drafts only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctos.pipeline import run
from ctos.review import approve, require_approval
from ctos.platforms import publish_platform
from ctos.emailer import opted_in_subscribers, send_one
from v12_weekly import prepare_weekly


def main(argv=None):
    parser = argparse.ArgumentParser(description="CartoonTamilan V13 — approved-story marketing OS")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("preview", "campaign"):
        cmd = sub.add_parser(name, help="Create complete marketing drafts (never publish)")
        cmd.add_argument("--limit", type=int, default=1)
        cmd.add_argument("--art-mode", choices=("cover", "comfyui"), default="cover")
        cmd.add_argument("--style", choices=("anime", "cinematic_3d"), default="anime")
        cmd.add_argument("--video", action="store_true", help="Optional actual MP4 using installed ffmpeg")
        cmd.add_argument("--voice", action="store_true", help="Optional basic local Tamil TTS with video")
        cmd.add_argument("--seconds", type=int, default=12)
        cmd.add_argument("--outdir", default="output/v13")

    approval = sub.add_parser("approve", help="Explicitly approve an inspected exact local image/copy bundle")
    approval.add_argument("--manifest", required=True)
    approval.add_argument("--rights-confirmed", action="store_true", required=True)
    approval.add_argument("--copy-reviewed", action="store_true", required=True)
    approval.add_argument("--visual-reviewed", action="store_true", required=True)

    send = sub.add_parser("publish", help="Live opt-in Meta/Telegram; all other platforms are export-only")
    send.add_argument("--manifest", required=True)
    send.add_argument("--platform", choices=("meta", "telegram"), required=True)
    send.add_argument("--live", action="store_true", required=True)

    email = sub.add_parser("email", help="Consent-only optional SMTP message, no bulk auto-sending")
    email.add_argument("--manifest", required=True)
    email.add_argument("--recipient", required=True)
    email.add_argument("--send", action="store_true", required=True)

    sub.add_parser("weekly", help="Real-data weekly marketing review")
    sub.add_parser("status", help="Print last V13 dry-run report summary")

    args = parser.parse_args(argv)
    if args.command in ("preview", "campaign"):
        if args.voice and not args.video:
            parser.error("--voice requires --video")
        report = run(limit=args.limit, outdir=args.outdir,
                     art_mode=args.art_mode, art_style=args.style,
                     make_video=args.video, voice=args.voice,
                     seconds=args.seconds)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if report["status"] == "failed":
            return 1
    elif args.command == "approve":
        result = approve(args.manifest, rights=args.rights_confirmed,
                         copy=args.copy_reviewed, visual=args.visual_reviewed)
        print(json.dumps({"status": result["state"],
                          "manifest_sha": result["manifest_sha"],
                          "message": "Only the inspected files are approved. No post has been sent."}))
    elif args.command == "publish":
        result = publish_platform(args.manifest, args.platform, live=args.live)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "email":
        # An approved bundle is not blanket subscriber consent.
        require_approval(args.manifest)
        folder = Path(args.manifest).resolve().parent
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        from ctos.emailer import build_email
        from campaign_v9 import load_approvals
        rights = load_approvals().get(manifest["story"]["link"], {})
        if not (rights.get("rights_confirmed") and rights.get("copy_reviewed")):
            raise PermissionError("Original story rights+copy approvals are missing")
        import os
        payload = build_email(
            manifest["story"],
            intro_ta=rights.get("intro_ta", ""),
            intro_en=rights.get("intro_en", ""),
            unsubscribe_url=os.getenv("CT_UNSUBSCRIBE_URL", ""),
            sender_address=os.getenv("CT_SENDER_POSTAL_ADDRESS", ""))
        print(json.dumps(send_one(payload, args.recipient, approved=args.send)))
    elif args.command == "weekly":
        result = prepare_weekly()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "status":
        path = Path("output/v13/latest.json")
        print(path.read_text(encoding="utf-8")
              if path.is_file() else json.dumps({"status": "not_run_yet"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
