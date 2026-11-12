"""CartoonTamilan V12 safe daily marketing orchestrator.

The existing V10 creative engine creates drafts; V12 adds editorial calendar,
SEO advice, observed growth analytics, optional approved variants, and logs.
NO social platform publishes from this command.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from auto_story_marketing import discover
from campaign_v9 import APPROVALS, read_json, write_json
from campaign_v10 import run_v10
from story_bible_v10 import BIBLES
from v12_strategy import save_calendar
from v12_insights import write_report
from v12_seo import audit_pages, related_link_suggestions
from v12_media import create_variants


def run(limit=1, day=None, outdir="output/v12", discover_fn=None, campaign_fn=None,
        audit=False, variants=False):
    if not 1 <= limit <= 6:
        raise ValueError("limit must be 1–6")
    day = day or date.today()
    root = Path(outdir) / day.isoformat()
    root.mkdir(parents=True, exist_ok=True)
    result = {"date": day.isoformat(),
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "mode": "safe_preview_only", "live_publishing": False,
              "discovered": 0, "draft_calendar": None, "poster_preview": None,
              "seo_report": None, "campaign_analytics": None,
              "optional_assets": [], "issues": [], "requires_review": True}
    try:
        stories = (discover_fn or discover)(limit=30)
        result["discovered"] = len(stories)
        if not stories:
            result["issues"].append("No original stories confidently identified from site catalogue.")
        approvals = read_json(APPROVALS, {})
        bibles = read_json(BIBLES, {})
        calendar = save_calendar(stories, approvals, bibles,
                                 out=root / "calendar.json", days=14, posts_per_day=2)
        result["draft_calendar"] = str(calendar)
        if stories:
            poster = (campaign_fn or run_v10)(
                limit=limit, publish=False, art_mode="cover",
                outdir=str(root / "posters"),
                day=day, discovery_func=lambda limit: stories,
            )
            result["poster_preview"] = poster
            if poster.get("failed"):
                result["issues"].extend(
                    str(entry.get("reason", "Poster creation failed"))[:300]
                    for entry in poster["failed"])
            if variants:
                for p in poster.get("prepared", []):
                    story = next((s for s in stories if s["title"] == p["title"]), None)
                    if not story:
                        continue
                    approved = approvals.get(story["link"], {})
                    if not (approved.get("rights_confirmed") is True
                            and approved.get("v10_visual_policy_approved") is True):
                        result["issues"].append("Media variants skipped: artwork rights not approved for "
                                                + str(p["title"])[:60])
                        continue
                    try:
                        assets = create_variants(
                            p["poster"], story["title"],
                            Path(p["poster"]).parent / "variants",
                            approved_art=True)
                        result["optional_assets"].append({"story": story["link"], "files": assets})
                    except (OSError, RuntimeError, ValueError) as error:
                        result["issues"].append("Media variants failed: " + str(error)[:200])
        # Does NOT fake traffic stats; no_data if the site analytics integration is absent.
        metrics = write_report("data/campaign_metrics_v12.csv",
                               root / "marketing_analytics.json")
        result["campaign_analytics"] = metrics.get("status")
        links_path = root / "related_story_links.json"
        write_json(links_path, related_link_suggestions(stories))
        if audit and stories:
            seo = audit_pages([story["link"] for story in stories],
                              out=root / "seo_audit.json", limit=min(limit, 6))
            result["seo_report"] = str(root / "seo_audit.json")
            if any(page.get("error") for page in seo["pages"]):
                result["issues"].append("Some SEO pages could not be audited; check seo_audit.json")
    except Exception as error:
        result["issues"].append(type(error).__name__ + ": " + str(error)[:250])
    result["status"] = ("failed" if result["poster_preview"] is None else
                        "review_required" if result["issues"] else "draft_ready_review_required")
    write_json(root / "daily_report.json", result)
    write_json(Path(outdir) / "latest_health.json", {
        "date": day.isoformat(), "status": result["status"],
        "report_path": str(root / "daily_report.json"),
        "issues_count": len(result["issues"]),
    })
    if result["status"] == "failed":
        try:
            from v12_alerts import report_alert
            result["alert_status"] = report_alert(result["status"], result["issues"])
        except (RuntimeError, ValueError):
            # Notifications must never hide the primary automation problem.
            result["alert_status"] = "delivery_failed"
        write_json(root / "daily_report.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description="Daily content strategy and safe creative preview")
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--seo", action="store_true", help="Optional site SEO audit")
    p.add_argument("--variants", action="store_true", help="Create formats only for approved artwork")
    p.add_argument("--outdir", default="output/v12")
    a = p.parse_args()
    report = run(limit=a.limit, outdir=a.outdir, audit=a.seo, variants=a.variants)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
