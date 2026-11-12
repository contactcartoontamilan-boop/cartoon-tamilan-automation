"""Public-domain image discovery with conservative filtering.

Openverse is an index, not a rights authority. Results always require review
of source/licensing before real-world publication.
"""
import requests

OPENVERSE_ENDPOINT = "https://api.openverse.org/v1/images/"
ALLOWED_LICENSES = {"cc0", "pdm"}


def search_public_domain(query, limit=8, session=None):
    if not query or not query.strip():
        return []
    http = session or requests
    response = http.get(
        OPENVERSE_ENDPOINT,
        params={"q": query.strip(), "license": "cc0,pdm", "page_size": min(max(int(limit), 1), 20), "mature": "false"},
        headers={"User-Agent": "CartoonTamilanAutomation/0.2 (public-domain-image-research)"},
        timeout=20,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("results", []):
        license_name = (item.get("license") or "").lower().strip()
        url = item.get("url") or ""
        source_page = item.get("foreign_landing_url") or ""
        if license_name not in ALLOWED_LICENSES or not url.startswith("https://") or not source_page.startswith("http"):
            continue
        results.append({
            "url": url,
            "license": license_name,
            "license_url": item.get("license_url") or "",
            "creator": item.get("creator") or "Unknown",
            "source_page": source_page,
            "title": item.get("title") or "",
            "attribution": item.get("attribution") or "",
            "origin": "openverse",
            "requires_manual_rights_review": True,
        })
    return results
