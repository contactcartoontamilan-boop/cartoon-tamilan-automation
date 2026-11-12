"""Discover original-novel URLs from CartoonTamilan and draft review-only posters.

No copied/guessed novel URLs, no social publishing, no Openverse dependency.
Only cards with story-specific evidence are accepted; news and chapters excluded.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
from auto_story_cover import auto_cover
from poster_generator import make_poster

BASE = "https://cartoontamilan.in/"
HEADERS = {"User-Agent": "CartoonTamilanAutomation/0.7 (story-catalogue-review)"}
STORY_MARKERS = ("ongoing", "completed", "original", "game-world", "academy / campus", "adventure", "family drama")
NEWS_MARKERS = ("latest update", "read more", "news", "manga", "licensing", "release date")
CHAPTER_MARKERS = ("episode ", "chapter ", "அத்தியாயம்", "எபிசோட்")
SECTIONS = ("trending", "popular anime", "latest anime", "ongoing anime", "completed anime", "original stories", "my library")


def same_domain(url):
    p = urlparse(url)
    return p.scheme == "https" and p.hostname in ("cartoontamilan.in", "www.cartoontamilan.in")


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def discover_from_html(html, base=BASE, limit=30):
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    # Only discover strong-evidence novel catalogue cards; skip latest news links.
    for link in soup.select("a[href]"):
        raw = link.get("href", "").strip()
        url = urldefrag(urljoin(base, raw))[0]
        if not same_domain(url) or url.rstrip("/") == base.rstrip("/"):
            continue
        title = clean(link.get_text(" ", strip=True))
        parent = link
        for _ in range(3):
            parent = parent.parent if getattr(parent, "parent", None) else parent
        nearby = clean(parent.get_text(" ", strip=True))[:650]
        low = nearby.lower()
        titlelow = title.lower()
        if not title or len(title) < 5 or len(title) > 180:
            continue
        if any(k in titlelow for k in CHAPTER_MARKERS) or any(k in titlelow for k in NEWS_MARKERS):
            continue
        p = urlparse(url).path.lower()
        if any(k in p for k in ("/category/", "/tag/", "/author/", "/feed", "/latest-updates", "/news/", "/episode/", "/chapter/")):
            continue
        # Strong evidence: catalogue status associated with title, or
        # a link inside a recognizable novel card.
        classes = " ".join(" ".join(tag.get("class", [])) for tag in [link, link.parent] if hasattr(tag, "get"))
        card = any(k in classes.lower() for k in ("novel", "series", "story-card", "anime-card", "book-card"))
        status = any(k in low for k in ("ongoing", "completed"))
        if not card and not status:
            continue
        if any(k in low for k in ("read more", "latest update")) and not card:
            continue
        # Prefer accessible title attribute when cards contain multiple labels.
        label = clean(link.get("title") or "")
        if label and 5 <= len(label) <= 150:
            title = label
        if "view all" in title.lower() or "explore" in title.lower():
            continue
        results[url] = {"title": title, "link": url, "kind": "story", "evidence": "novel_card" if card else "catalogue_status"}
        if len(results) >= limit:
            break
    return list(results.values())


def discover(base=BASE, limit=20, session=None):
    if not same_domain(base):
        raise ValueError("Website must be CartoonTamilan HTTPS")
    http = session or requests
    response = http.get(base, timeout=25, headers=HEADERS, allow_redirects=False)
    response.raise_for_status()
    if 300 <= response.status_code < 400:
        raise RuntimeError("Homepage redirected; cannot safely discover novels")
    return discover_from_html(response.text, base, limit)


def build(outdir="output/story_discovery", limit=10, base=BASE, session=None, cover_fetcher=None, poster_maker=None):
    directory = Path(outdir)
    directory.mkdir(parents=True, exist_ok=True)
    stories = discover(base, limit, session=session)
    report = {"discovered": len(stories), "success": [], "failed": [],
              "review_required": True, "published": False}
    for item in stories:
        identifier = hashlib.sha256(item["link"].encode("utf-8")).hexdigest()[:16]
        target = directory / identifier
        target.mkdir(exist_ok=True)
        draft = target / "draft.json"
        record = {"item": {**item, "id": identifier, "summary": ""},
                  "caption": "", "status": "review_required"}
        draft.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            cover = (cover_fetcher or auto_cover)(draft, target / "covers")
            poster = target / "poster.png"
            (poster_maker or make_poster)(draft, poster, artwork=str(cover), headline="புதிய தமிழ் கதை")
            report["success"].append({"title": item["title"], "story_url": item["link"], "poster": str(poster)})
        except (ValueError, RuntimeError, OSError, requests.RequestException) as exc:
            report["failed"].append({"title": item["title"], "story_url": item["link"],
                                     "reason": f"{type(exc).__name__}: {str(exc)[:180]}"})
    report_path = directory / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--outdir", default="output/story_discovery")
    parser.add_argument("--discover-only", action="store_true")
    args = parser.parse_args()
    if args.discover_only:
        items = discover(limit=max(1, min(args.limit, 30)))
        print(json.dumps(items, ensure_ascii=False, indent=2))
        if not items:
            print("No confidently identifiable story links found in static homepage HTML.")
    else:
        report = build(args.outdir, max(1, min(args.limit, 30)))
        print("Discovered:", report["discovered"], "Posters:", len(report["success"]), "Failed:", len(report["failed"]))
        print("Details:", str(Path(args.outdir) / "report.json"))
        print("Nothing was published. Review all covers and story matches first.")
