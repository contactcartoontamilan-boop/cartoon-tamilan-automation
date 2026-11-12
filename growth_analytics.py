"""Report observed CartoonTamilan pageviews from an exported CSV.

CSV fields: date,pageviews,source,story_url
Data must be genuine analytics output; this tool does not collect website traffic.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = {"date", "pageviews", "source", "story_url"}


def summarize_csv(filename, target=10000):
    daily, by_source, by_page = defaultdict(int), defaultdict(int), defaultdict(int)
    rows = 0
    with open(filename, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError("CSV must have columns: date,pageviews,source,story_url")
        for r in reader:
            day = date.fromisoformat(r["date"].strip()).isoformat()
            views = int(r["pageviews"].strip())
            if views < 0:
                raise ValueError("Pageviews cannot be negative")
            source = r["source"].strip().lower() or "unknown"
            page = r["story_url"].strip()
            if page and (urlsplit(page).hostname or "").lower() not in {"cartoontamilan.in", "www.cartoontamilan.in"}:
                raise ValueError("Non-CartoonTamilan URL in story_url")
            daily[day] += views
            by_source[source] += views
            if page:
                by_page[page] += views
            rows += 1
    if rows == 0:
        return {"status": "no_data", "message": "No analytics observations yet", "target_daily_pageviews": target}
    latest = max(daily)
    return {
        "status": "observed_data",
        "source_note": "User-provided analytics CSV; accuracy depends on its export and metric definitions",
        "target_daily_pageviews": target,
        "observed_dates": len(daily),
        "latest_date": latest,
        "latest_pageviews": daily[latest],
        "remaining_to_target": max(0, target - daily[latest]),
        "daily_pageviews": dict(sorted(daily.items())),
        "top_sources": sorted(by_source.items(), key=lambda x: -x[1])[:10],
        "top_story_pages": sorted(by_page.items(), key=lambda x: -x[1])[:10],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/analytics_daily.csv")
    p.add_argument("--out", default="output/growth_report.json")
    a = p.parse_args()
    if not Path(a.csv).exists():
        print("NO DATA: Add a real analytics export CSV to", a.csv)
        print("Required columns: date,pageviews,source,story_url")
        raise SystemExit(0)
    result = summarize_csv(a.csv)
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
