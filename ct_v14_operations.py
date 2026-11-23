"""Hourly refresh of configured anime-news leads and real analytics exports.

News is written to a review queue. This worker never invents sources or turns
an unverified RSS headline into an automatic public post.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SOURCES = Path("data/anime_news_sources.json")
MARKER = Path("data/v14_intelligence_refresh.json")


def refresh_intelligence() -> dict:
    now = datetime.now(IST)
    state = {}
    if MARKER.is_file():
        try:
            state = json.loads(MARKER.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}
    stamp = state.get("refreshed_at")
    if stamp:
        try:
            if now - datetime.fromisoformat(stamp) < timedelta(hours=1):
                return {"status": "already_refreshed_this_hour",
                        "news": state.get("news", {}),
                        "analytics": state.get("analytics", {})}
        except ValueError:
            pass

    news_result = {"status": "sources_not_configured", "items": 0}
    try:
        if SOURCES.is_file():
            payload = json.loads(SOURCES.read_text(encoding="utf-8"))
            sources = payload.get("sources") if isinstance(payload, dict) else None
            if not isinstance(sources, list):
                raise ValueError("anime news config must contain a sources list")
            if sources:
                from v12_news import discover_news, save_news
                drafts = discover_news(sources)
                save_news(drafts)
                news_result = {"status": "review_queue_refreshed", "items": len(drafts)}
            else:
                news_result = {"status": "no_sources_configured", "items": 0}
    except Exception as exc:
        news_result = {"status": "refresh_failed", "error_type": type(exc).__name__}

    analytics_result = {"status": "analytics_csv_missing"}
    csv_path = Path("data/analytics_daily.csv")
    if csv_path.is_file():
        try:
            from growth_analytics import summarize_csv
            report = summarize_csv(str(csv_path))
            out = Path("output/growth_report.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            temp = out.with_suffix(out.suffix + ".tmp")
            temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
            temp.replace(out)
            analytics_result = {"status": report.get("status", "refreshed"),
                                "latest_date": report.get("latest_date"),
                                "latest_pageviews": report.get("latest_pageviews")}
        except Exception as exc:
            analytics_result = {"status": "refresh_failed",
                                "error_type": type(exc).__name__}

    state = {"refreshed_at": now.isoformat(), "news": news_result,
             "analytics": analytics_result}
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    temp = MARKER.with_suffix(MARKER.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(MARKER)
    return {"status": "refreshed", "news": news_result, "analytics": analytics_result}
