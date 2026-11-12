"""V12 licensed-source anime/cartoon news discovery and REVIEW-only briefs.

Use ONLY official RSS feeds you explicitly configure. Avoid third-party
anime poster reuploads; syndicated titles are leads, not verified facts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import feedparser
import requests


def check_source(source):
    if not source.get("official_source_confirmed"):
        raise PermissionError("RSS source must be reviewed and confirmed official")
    url = source.get("url", "")
    host = urlsplit(url)
    if host.scheme != "https" or not host.hostname or host.username or host.password:
        raise ValueError("Official RSS feed must use HTTPS without credentials")
    if host.port and host.port != 443:
        raise ValueError("Only HTTPS port 443 supported")
    # Prevent SSRF through arbitrary IP/localhost URLs.
    import ipaddress
    try:
        ipaddress.ip_address(host.hostname)
        raise ValueError("RSS sources must use a real official hostname, not an IP")
    except ValueError as error:
        if "not an IP" in str(error):
            raise
    if host.hostname in {"localhost", "local", "metadata.google.internal"} or host.hostname.endswith(".local"):
        raise ValueError("Internal host cannot be used as RSS source")
    return url


def discover_news(sources, session=None, max_per_source=5):
    if not 1 <= max_per_source <= 10:
        raise ValueError("max_per_source 1–10")
    http = session or requests
    drafts = []
    for source in sources[:10]:
        url = check_source(source)
        response = http.get(url, timeout=15, allow_redirects=False)
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("RSS source failed: HTTP " + str(response.status_code))
        raw = response.content
        if len(raw) > 1024 * 1024:
            raise ValueError("RSS feed too large")
        feed = feedparser.parse(raw)
        for entry in feed.entries[:max_per_source]:
            link = str(entry.get("link") or "").strip()
            parsed = urlsplit(link)
            if parsed.scheme != "https" or not parsed.hostname:
                continue
            title = str(entry.get("title") or "").strip()[:180]
            if not title:
                continue
            drafts.append({
                "source": source.get("name", parsed.hostname),
                "source_feed": url, "headline": title, "source_link": link,
                "published_at_raw": str(entry.get("published") or ""),
                "editorial_status": "source_verification_required",
                "image_rights_confirmed": False,
                "must_verify_facts": True,
                "note": "Review story accuracy and usage rights before writing news or publishing",
            })
    return drafts


def save_news(drafts, filename="output/v12/news_review_queue.json"):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "review_only", "entries": drafts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
