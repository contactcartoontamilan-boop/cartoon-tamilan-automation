"""V12 weekly management brief assembled from REAL local measurement files.

No fabricated Google Analytics / Search Console values. Converts progress into
a concise actionable report for human review.
"""
from datetime import date, datetime, timezone
from pathlib import Path
import json

from growth_analytics import summarize_csv
from v12_insights import summarize_campaigns
from campaign_v9 import read_json, write_json


def prepare_weekly(out="output/v12/weekly_marketing_review.json",
                   pageviews_csv="data/analytics_daily.csv",
                   social_csv="data/campaign_metrics_v12.csv",
                   health_path="output/v12/latest_health.json"):
    if Path(pageviews_csv).is_file():
        pageviews = summarize_csv(pageviews_csv)
    else:
        pageviews = {"status": "no_data", "message": "GA4 real pageview export not yet connected"}
    social = summarize_campaigns(social_csv)
    health = read_json(health_path, {"status": "no_automation_health_report"})
    tasks = []
    if pageviews.get("status") == "no_data":
        tasks.append("Connect GA4/read-only analytics or export verified pageviews CSV.")
    else:
        if pageviews.get("remaining_to_target", 0) > 0:
            tasks.append("Grow organic story discovery; compare real reader sessions and chapter completion.")
    if social.get("status") == "no_data":
        tasks.append("Import social impressions, tracked sessions and actual story reads before optimizing.")
    if health.get("issues_count", 0):
        tasks.append("Investigate Oracle daily automation errors before enabling live publishing.")
    if not tasks:
        tasks.append("Review top original stories and plan next approved creative experiments.")
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "week_of": date.today().isoformat(),
        "report_type": "review_not_guaranteed_growth",
        "goal_daily_pageviews": 10000,
        "real_pageview_report": pageviews,
        "social_to_site_report": social,
        "server_health": health,
        "next_actions": tasks,
        "automatic_social_publishing": False,
    }
    write_json(out, result)
    return result


if __name__ == "__main__":
    result = prepare_weekly()
    print(json.dumps({"pageviews": result["real_pageview_report"].get("status"),
                      "social": result["social_to_site_report"].get("status"),
                      "next_actions": result["next_actions"]},
                     ensure_ascii=False, indent=2))
