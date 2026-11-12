"""V12 organic growth analytics and evidence-gated campaign recommendations.

Never counts Instagram views as website pageviews. Requires a real exported
analytics CSV; absence of data returns 'no_data', not fabricated success.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

FIELDS = {"date", "channel", "campaign", "impressions",
          "link_clicks", "website_sessions", "story_reads"}


def summarize_campaigns(csv_path, target_pageviews=10000, min_impressions=100):
    path = Path(csv_path)
    if not path.exists():
        return {"status": "no_data", "message": "Connect real website analytics or import actual campaign measurements.",
                "target_daily_pageviews": target_pageviews,
                "recommendations": ["Verify GA4 / Search Console installation before optimizing campaigns"]}
    totals = defaultdict(lambda: {"impressions": 0, "link_clicks": 0, "website_sessions": 0, "story_reads": 0})
    hours = defaultdict(lambda: {"impressions": 0, "website_sessions": 0})
    total_rows = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError("CSV requires: " + ",".join(sorted(FIELDS)))
        for row in reader:
            from datetime import date
            date.fromisoformat(row["date"].strip())
            channel = (row.get("channel") or "").strip().lower()
            campaign = (row.get("campaign") or "").strip()
            if not channel or not campaign:
                raise ValueError("Missing channel or campaign identifier")
            metrics = {}
            for field in ("impressions", "link_clicks", "website_sessions", "story_reads"):
                raw = str(row[field] or "").strip()
                if not raw.isdigit():
                    raise ValueError("Metrics must be nonnegative integers")
                metrics[field] = int(raw)
            if (metrics["website_sessions"] > metrics["link_clicks"] or
                    metrics["story_reads"] > metrics["website_sessions"]):
                # Analytics attribution can differ from outbound platform clicks.
                # Do not assume the values must form a strict funnel.
                pass
            key = (channel, campaign)
            for field, value in metrics.items():
                totals[key][field] += value
            hour = str(row.get("hour_ist", "")).strip()
            if hour:
                if not (hour.isdigit() and 0 <= int(hour) <= 23):
                    raise ValueError("hour_ist must be 0–23")
                hours[int(hour)]["impressions"] += metrics["impressions"]
                hours[int(hour)]["website_sessions"] += metrics["website_sessions"]
            total_rows += 1
    if not total_rows:
        return {"status": "no_data", "message": "Analytics file contains no observations",
                "target_daily_pageviews": target_pageviews}
    rank = []
    for (channel, campaign), values in totals.items():
        impressions, clicks, sessions, reads = (values[k] for k in
             ("impressions", "link_clicks", "website_sessions", "story_reads"))
        rank.append({
            "channel": channel, "campaign": campaign, **values,
            "ctr_pct": round(clicks * 100 / impressions, 2) if impressions else None,
            "reads_per_session_pct": round(reads * 100 / sessions, 2) if sessions else None,
            "sample_sufficient_for_comparison": impressions >= min_impressions,
        })
    rank.sort(key=lambda r: (r["story_reads"], r["website_sessions"]), reverse=True)
    qualified_hours = [
        (hour, value["website_sessions"], value["impressions"])
        for hour, value in hours.items() if value["impressions"] >= min_impressions
    ]
    qualified_hours.sort(key=lambda r: (-r[1], -r[2]))
    total_sessions = sum(r["website_sessions"] for r in rank)
    recommendations = []
    if not any(r["sample_sufficient_for_comparison"] for r in rank):
        recommendations.append("Insufficient sample: collect more actual campaign measurements before A/B optimization.")
    else:
        recommendations.append("Compare approved campaign copy variants by attributable story reads, not impressions alone.")
    if not qualified_hours:
        recommendations.append("No trustworthy best posting time yet; keep an editorial schedule.")
    return {
        "status": "observed_campaign_data",
        "source": "user-provided campaign analytics CSV",
        "observations": total_rows, "target_daily_pageviews": target_pageviews,
        "total_attributed_website_sessions": total_sessions,
        "note": "Sessions are NOT daily pageviews; 10,000 pageviews/day must be checked in actual website analytics.",
        "campaigns": rank,
        "best_observed_hour_ist": qualified_hours[0][0] if qualified_hours else None,
        "recommended_next_steps": recommendations,
    }


def write_report(csv_path, out="output/v12/campaign_metrics.json"):
    report = summarize_campaigns(csv_path)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
