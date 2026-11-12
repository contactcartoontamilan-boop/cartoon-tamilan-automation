"""Extract images from own story pages; search conservative fallback candidates.

Do not automatically use third-party images for public posts. Openverse metadata
can be inaccurate; license and identity need independent review.
"""
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
from image_sources import search_public_domain


def same_site(url, site_url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    base = (urlparse(site_url).hostname or "").lower()
    return parsed.scheme == "https" and (host == base or host == "www." + base or ("www." + host) == base)


def extract_post_image(html, page_url, site_url):
    soup = BeautifulSoup(html, "html.parser")
    for attrs in ({"property": "og:image"}, {"name": "twitter:image"}):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            url = urljoin(page_url, meta["content"])
            if same_site(url, site_url):
                return url
    for image in soup.select("article img, .entry-content img, .post-thumbnail img"):
        src = image.get("data-src") or image.get("src")
        if src:
            url = urljoin(page_url, src)
            if same_site(url, site_url):
                return url
    return None


def find_own_image(item, site_url, session=None):
    link = item.get("link", "")
    if not same_site(link, site_url):
        return None
    direct = item.get("image_url", "")
    if direct and same_site(direct, site_url):
        return {"url": direct, "origin": "own_site", "license": "owner_must_confirm", "requires_manual_rights_review": True}
    http = session or requests
    response = http.get(link, timeout=20, headers={"User-Agent": "CartoonTamilanAutomation/0.2"})
    response.raise_for_status()
    url = extract_post_image(response.text, link, site_url)
    return {"url": url, "origin": "own_site", "license": "owner_must_confirm", "requires_manual_rights_review": True} if url else None


def choose_asset(item, site_url, enable_openverse=False, session=None):
    try:
        own = find_own_image(item, site_url, session=session)
        if own:
            return own
    except requests.RequestException:
        pass
    if enable_openverse:
        # Use generic background concepts; don't treat unrelated stock art as
        # actual characters or events from a user's story.
        kind = item.get("kind", "story")
        query = "fantasy landscape illustration" if kind == "story" else "animation cinema background"
        try:
            candidates = search_public_domain(query, session=session)
            if candidates:
                return candidates[0]
        except (requests.RequestException, ValueError):
            pass
    return None
