"""V14 offline all-channel readiness report + static local dashboard.

Reads local draft metadata only. No tokens, network, publishing or background
scheduler. Never labels an unverified channel as production-ready.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

PLATFORMS = ("instagram", "facebook", "pinterest", "threads", "x",
             "linkedin", "telegram", "youtube")
REAL_ADAPTERS = {"instagram", "facebook", "telegram"}


def _optional_json(path: str | Path | None) -> dict | None:
    if not path:
        return None
    file = Path(path)
    if not file.is_file():
        return None
    value = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object in " + str(file))
    return value


def readiness_report(queue: dict | None, story: dict | None = None,
                     scene_art: dict | None = None,
                     video: dict | None = None) -> dict:
    if queue is not None and (queue.get("published") is not False or
                              queue.get("live_publishing") is not False):
        raise ValueError("Only V14 unpublished review queues are accepted")
    drafts = queue.get("image_post_queue", []) if queue else []
    if not isinstance(drafts, list):
        raise ValueError("Invalid queue items")
    counts = {p: 0 for p in PLATFORMS}
    for item in drafts:
        platform = item.get("platform")
        if platform not in counts or item.get("published") is not False:
            raise ValueError("Invalid or already-published draft")
        counts[platform] += 1
    status = {}
    for platform in PLATFORMS:
        status[platform] = {
            "drafts": counts[platform],
            "adapter": ("v14_opt_in_gated_not_authorized_or_tested" if platform == "x" else
                        "existing_gated_not_authorized_or_tested"
                        if platform in REAL_ADAPTERS else "not_integrated"),
            "live_publishing_verified": False,
            "review_required": True,
        }
    status["youtube"]["thumbnail_only"] = bool(
        queue and queue.get("thumbnail_only_count", 0))
    return {
        "version": 14,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dashboard_kind": "offline_readiness_preview_not_live_analytics",
        "queue_loaded": queue is not None,
        "story_chapters_extracted": (story or {}).get("chapters_extracted", 0),
        "story_completeness": (story or {}).get("story_completeness", "not_verified"),
        "scene_images_generated": len((scene_art or {}).get("scene_images", [])),
        "video_manifest_loaded": video is not None,
        "video_file_verified": False,  # No media file is inspected by this report.
        "platforms": status,
        "image_post_drafts": sum(counts.values()),
        "video_workflows_waiting_for_mp4": (
            queue or {}).get("video_workflows_waiting_for_mp4", 0),
        "scheduler_running": False,
        "seo_live_verified": False,
        "email_delivery_verified": False,
        "analytics_live_verified": False,
        "requires_human_review": True,
        "published": False,
        "notes": [
            "This is a local draft dashboard, not a live control panel.",
            "Actual platform tokens, OAuth permissions and API calls are not tested.",
            "Video, SEO, email and analytics statuses are not inferred from image drafts.",
        ],
    }


def render_dashboard(report: dict) -> str:
    rows = []
    for platform, data in report["platforms"].items():
        name = html.escape(platform.title())
        adapter = html.escape(data["adapter"])
        rows.append(
            f"<tr><td>{name}</td><td>{int(data['drafts'])}</td>"
            f"<td>{adapter}</td><td>NOT LIVE</td></tr>")
    body = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>CartoonTamilan V14 - Offline Review Dashboard</title>
<style>body{{font:16px system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;background:#0e1629;color:#f2f4fa}}
h1{{font-size:1.7rem}}.muted{{color:#b9c5d7}}.stat{{display:inline-block;padding:1rem;background:#1d2b45;border-radius:12px;margin:.4rem}}
table{{border-collapse:collapse;width:100%;margin-top:1rem}}th,td{{padding:.8rem;text-align:left;border-bottom:1px solid #40506b}}
th{{color:#d4e2fa}}strong{{color:#ffd28a}}</style></head><body>
<h1>CartoonTamilan V14 — Review Dashboard</h1>
<p><strong>OFFLINE PREVIEW — NO AUTOMATIC PUBLISHING</strong></p>
<div class="stat">Image drafts: {int(report['image_post_drafts'])}</div>
<div class="stat">Extracted chapters: {int(report['story_chapters_extracted'])}</div>
<div class="stat">Scene art images: {int(report['scene_images_generated'])}</div>
<div class="stat">Video workflows waiting: {int(report['video_workflows_waiting_for_mp4'])}</div>
<h2>Platform readiness</h2>
<table><thead><tr><th>Platform</th><th>Drafts</th><th>Integration</th><th>Live status</th></tr></thead>
<tbody>{body}</tbody></table>
<p class="muted">Email, SEO, live analytics, scheduler and production publishing require separate integration and validation.</p>
<p class="muted">All original stories, artwork, licenses, captions and approvals require human review.</p>
</body></html>"""


def save_report(report: dict, outdir: str | Path) -> tuple[Path, Path]:
    root = Path(outdir)
    root.mkdir(parents=True, exist_ok=True)
    json_file = root / "readiness.json"
    html_file = root / "dashboard.html"
    json_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    html_file.write_text(render_dashboard(report), encoding="utf-8")
    return json_file, html_file


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build a local V14 draft status dashboard")
    parser.add_argument("--queue", default="output/v14/image_posts/social_queue.json")
    parser.add_argument("--story-manifest")
    parser.add_argument("--scene-art-manifest")
    parser.add_argument("--video-manifest")
    parser.add_argument("--outdir", default="output/v14/control_center")
    args = parser.parse_args(argv)
    report = readiness_report(
        _optional_json(args.queue), _optional_json(args.story_manifest),
        _optional_json(args.scene_art_manifest), _optional_json(args.video_manifest))
    json_file, html_file = save_report(report, args.outdir)
    print(json.dumps({"status": "offline_readiness_report_saved",
                      "json": str(json_file), "dashboard": str(html_file),
                      "image_drafts": report["image_post_drafts"],
                      "live_publishing": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
