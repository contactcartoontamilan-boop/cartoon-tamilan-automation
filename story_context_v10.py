"""Read publicly available synopsis from a CartoonTamilan ORIGINAL novel page.

Synopsis extraction is best-effort; never interpret this as verified character
lore or as a chapter-by-chapter understanding. No JS bypass or web scraping of
third-party sources; requests stay on the owner's own website.
"""
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SELECTORS = (
    ".novel-synopsis", ".book-synopsis", ".series-synopsis",
    ".novel-description", ".book-description", ".series-description",
    ".story-description", "#synopsis", ".novel-details .description",
)
HOSTS = {"cartoontamilan.in", "www.cartoontamilan.in"}


def tidy(raw):
    return re.sub(r"\s+", " ", str(raw or "")).strip()


def extract_synopsis(html):
    soup = BeautifulSoup(html, "html.parser")
    for selector in SELECTORS:
        for element in soup.select(selector)[:2]:
            text = tidy(element.get_text(" ", strip=True))
            if 35 <= len(text) <= 6000:
                return text[:900]
    for property_name in ("og:description", "description"):
        tag = soup.select_one(
            f'meta[property="{property_name}"]' if property_name.startswith("og:")
            else f'meta[name="{property_name}"]'
        )
        if tag:
            text = tidy(tag.get("content"))
            if 60 <= len(text) <= 1500 and "cartoontamilan" not in text.lower()[:80]:
                return text[:700]
    return ""


def read_synopsis(story_url, session=None):
    p = urlparse(story_url)
    if p.scheme != "https" or p.hostname not in HOSTS or not p.path.startswith("/novel/"):
        raise ValueError("Only original CartoonTamilan novel HTTPS URLs are permitted")
    http = session or requests
    result = http.get(story_url, timeout=22, allow_redirects=False,
                      headers={"User-Agent": "CartoonTamilanAutomation/1.0 (novel-synopsis)"})
    result.raise_for_status()
    if result.status_code != 200:
        raise RuntimeError("Novel page not directly reachable: HTTP " + str(result.status_code))
    if "html" not in result.headers.get("content-type", "text/html").lower():
        raise RuntimeError("Novel URL response is not HTML")
    return extract_synopsis(result.text)
