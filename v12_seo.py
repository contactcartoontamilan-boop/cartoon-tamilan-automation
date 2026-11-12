"""V12 SEO audit for owned CartoonTamilan novel pages; suggestions, no site edits.

A real HTTP audit is optional. Pure inspect_html() is deterministic for tests.
Does not fabricate Search Console positions, keywords, or traffic metrics.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

HOSTS = {"cartoontamilan.in", "www.cartoontamilan.in"}


def owned_url(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname in HOSTS and (
        parts.path == "/" or parts.path.startswith("/novel/") or
        parts.path in ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml"))


def inspect_html(url, html, http_status=200):
    if not owned_url(url):
        raise ValueError("Only owned CartoonTamilan HTTPS pages may be audited")
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description = soup.select_one('meta[name="description"]')
    desc = (description.get("content", "").strip() if description else "")
    canonical_tag = soup.select_one('link[rel~="canonical"]')
    canonical = (urljoin(url, canonical_tag.get("href", "")) if canonical_tag else "")
    h1s = [el.get_text(" ", strip=True) for el in soup.find_all("h1")]
    robots = soup.select_one('meta[name="robots"]')
    robots_value = (robots.get("content", "").lower() if robots else "")
    og = soup.select_one('meta[property="og:image"]')
    image = og.get("content", "") if og else ""
    images = soup.select("img")
    missing_alt = sum(not img.get("alt", "").strip() for img in images[:30])
    jsonld = bool(soup.select('script[type="application/ld+json"]'))
    issues = []
    if http_status != 200:
        issues.append("HTTP response is not 200; verify page availability")
    if not title:
        issues.append("Missing <title> SEO title")
    elif len(title) > 65:
        issues.append("Title might truncate in search results (>65 chars)")
    if not desc:
        issues.append("Missing meta description")
    if not canonical:
        issues.append("Missing canonical link")
    elif not owned_url(canonical):
        issues.append("Canonical points outside the owned website")
    if len(h1s) != 1:
        issues.append("Expected one clear H1 heading")
    if "noindex" in robots_value:
        issues.append("Page explicitly marked noindex")
    if not image:
        issues.append("Missing og:image for share preview")
    if missing_alt:
        issues.append(f"{missing_alt} images lack alt text (among first 30)")
    if not jsonld:
        issues.append("No JSON-LD detected; assess suitable story/book structured data")
    return {
        "url": url, "status_code": http_status, "title": title,
        "description": desc, "canonical": canonical,
        "h1_count": len(h1s), "open_graph_image": image,
        "json_ld_detected": jsonld, "issues": issues,
        "issue_count": len(issues), "measurement_source": "live page HTML / supplied HTML",
    }


def audit_pages(urls, out="output/v12/seo_audit.json", session=None, limit=10):
    http = session or requests
    rows = []
    for url in list(dict.fromkeys(urls))[:max(0, min(limit, 25))]:
        if not owned_url(url):
            rows.append({"url": url, "error": "External or unsupported URL"})
            continue
        try:
            res = http.get(url, timeout=20, allow_redirects=False,
                           headers={"User-Agent": "CartoonTamilan-SEO-Audit/1.0"})
            if res.status_code in (301, 302, 303, 307, 308):
                rows.append({"url": url, "status_code": res.status_code,
                             "issues": ["Redirect: review destination manually"]})
            else:
                rows.append(inspect_html(url, res.text, http_status=res.status_code))
        except requests.RequestException as exc:
            rows.append({"url": url, "error": type(exc).__name__})
    payload = {
        "audit_type": "HTML SEO, NOT search rank / Core Web Vitals / GA4",
        "pages": rows,
        "pages_checked": len(rows),
        "pending_external": ["Search Console OAuth", "PageSpeed Insights API",
                             "GA4 read-only property access"],
    }
    dest = Path(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def related_link_suggestions(stories, per_story=3):
    """Only link to URLs already verified as belonging to the story catalogue."""
    valid = [s for s in stories if s.get("title") and owned_url(s.get("link", ""))
             and urlsplit(s["link"]).path.startswith("/novel/")]
    result = {}
    for story in valid:
        others = [s for s in valid if s["link"] != story["link"]]
        result[story["link"]] = [
            {"title": candidate["title"], "url": candidate["link"]}
            for candidate in others[:per_story]
        ]
    return result
