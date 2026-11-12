"""V12 optional READ-ONLY Google Analytics, Search Console and PageSpeed APIs.

Uses current documented Google REST endpoints. Requires OAuth access token and
permission to the user's OWN properties; token refresh is not implemented.
Never claims measurements exist unless Google returned them.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import requests
from v12_seo import owned_url


def _valid_range(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if b < a or (b - a).days > 90:
        raise ValueError("Date range must be forward and at most 90 days")


def _bearer(token):
    if not token or any(char.isspace() for char in token):
        raise ValueError("A valid read-only Google OAuth access token is required")
    return {"Authorization": "Bearer " + token}


def ga4_daily_pageviews(property_id, access_token, start, end, session=None):
    """Actual GA4 reported website/app pageview metric, grouped by date."""
    _valid_range(start, end)
    if not str(property_id).isdigit():
        raise ValueError("GA4 property ID must be numeric")
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "date"}],
        "metrics": [{"name": "screenPageViews"}],
        "limit": 100,
    }
    response = (session or requests).post(url, headers=_bearer(access_token),
                                           json=body, timeout=30)
    response.raise_for_status()
    data = response.json()
    out = []
    for row in data.get("rows", []):
        try:
            raw = row["dimensionValues"][0]["value"]
            views = int(row["metricValues"][0]["value"])
            day = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).isoformat()
            if views < 0:
                raise ValueError("Negative pageview count")
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError("Invalid GA4 daily pageviews response") from error
        out.append({"date": day, "pageviews": views, "source": "ga4",
                    "story_url": ""})
    return out


def export_ga4_csv(rows, filename="data/analytics_daily.csv"):
    if not rows:
        raise ValueError("No GA4 data returned; existing analytics CSV was left untouched")
    file = Path(filename)
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "pageviews", "source", "story_url"])
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, file)
    return file


def search_console_queries(site_property, access_token, start, end, session=None, limit=100):
    _valid_range(start, end)
    allowed = {"sc-domain:cartoontamilan.in", "https://cartoontamilan.in/",
               "https://www.cartoontamilan.in/"}
    if site_property not in allowed:
        raise ValueError("Use a verified CartoonTamilan Search Console property")
    uri = ("https://www.googleapis.com/webmasters/v3/sites/"
           + quote(site_property, safe="") + "/searchAnalytics/query")
    body = {"startDate": start, "endDate": end, "dimensions": ["query"],
            "rowLimit": max(1, min(250, int(limit)))}
    response = (session or requests).post(uri, headers=_bearer(access_token),
                                           json=body, timeout=30)
    response.raise_for_status()
    rows = []
    for row in response.json().get("rows", []):
        rows.append({
            "query": str((row.get("keys") or [""])[0])[:160],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": row.get("position"),
        })
    return rows


def pagespeed_mobile(url, session=None, api_key=None):
    if not owned_url(url):
        raise ValueError("Only run PageSpeed for CartoonTamilan")
    params = {"url": url, "strategy": "mobile",
              "category": ["performance", "accessibility", "seo"]}
    if api_key:
        params["key"] = api_key
    response = (session or requests).get(
        "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed",
        params=params, timeout=90)
    response.raise_for_status()
    data = response.json()
    cats = data.get("lighthouseResult", {}).get("categories", {})
    scores = {}
    for label in ("performance", "accessibility", "seo"):
        value = cats.get(label, {}).get("score")
        scores[label] = round(value * 100) if isinstance(value, (int, float)) else None
    return {"url": url, "source": "Google PageSpeed Insights mobile Lighthouse",
            "scores": scores, "verified_live_api": True}


def export_google_report(ga4_rows=None, gsc_rows=None, pagespeed=None,
                         filename="output/v12/google_review.json"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {"ga4_daily": ga4_rows, "gsc_queries": gsc_rows,
              "pagespeed": pagespeed,
              "note": "API-based observed data only; missing fields are not measured"}
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
