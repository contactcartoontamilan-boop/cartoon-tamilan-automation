"""Find a matching story cover and save it for REVIEW, never for automatic publishing.

Priority: a validated URL in a story draft -> story page metadata -> relevant
featured/article image. Fetches only same-site page URLs and same-site images.
External CDN images must be handled separately with a trusted allowlist.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from asset_pipeline import download_image
from asset_selector import same_site

SITE = "https://cartoontamilan.in"
HEADERS = {"User-Agent": "CartoonTamilanAutomation/0.6 (+story-cover-check)"}
IMAGE_SELECTORS = (
    ".novel-cover img", ".story-cover img", ".book-cover img",
    ".series-cover img", ".novel-card img", ".anime-card img",
    ".post-thumbnail img", ".featured-image img", ".entry-content img",
    "article img"
)


def image_candidate(url, page_url, site_url=SITE):
    if not url or not isinstance(url, str):
        return None
    value = url.strip()
    if value.startswith("data:") or value.startswith("blob:"):
        return None
    resolved = urljoin(page_url, value)
    return resolved if same_site(resolved, site_url) else None


def cover_from_html(html, page_url, site_url=SITE):
    soup = BeautifulSoup(html, "html.parser")
    for key, val in [("property", "og:image:secure_url"), ("property", "og:image"), ("name", "twitter:image"), ("name", "og:image")]:
        meta = soup.find("meta", attrs={key: val})
        if meta:
            result = image_candidate(meta.get("content"), page_url, site_url)
            if result:
                return result
    for selector in IMAGE_SELECTORS:
        for tag in soup.select(selector):
            for value in (tag.get("data-src"), tag.get("data-lazy-src"), tag.get("data-original"), tag.get("src")):
                candidate = image_candidate(value, page_url, site_url)
                if candidate:
                    return candidate
            srcset = tag.get("srcset", "")
            if srcset:
                candidate = image_candidate(srcset.split(",")[-1].strip().split()[0], page_url, site_url)
                if candidate:
                    return candidate
    return None


def resolve_draft(path):
    if str(path) != "latest":
        return str(path)
    files = sorted(Path("output").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for file in files:
        try:
            obj = json.loads(file.read_text(encoding="utf-8"))
            if obj.get("item", {}).get("kind") == "story":
                return str(file)
        except (ValueError, OSError, TypeError):
            continue
    raise FileNotFoundError("No original story draft in output/. Run python main.py or pass --draft PATH.")


def load_draft(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    item = data.get("item", {})
    if item.get("kind") != "story":
        raise ValueError("Selected JSON is not an original story draft")
    link = (item.get("link") or "").strip()
    if not same_site(link, SITE):
        raise ValueError("Story URL is not HTTPS on CartoonTamilan.in")
    return data


def auto_cover(draft_path, outdir="output/covers", session=None):
    draft_path = resolve_draft(draft_path)
    data = load_draft(draft_path)
    item = data["item"]
    url = item["link"]
    candidate = image_candidate(item.get("image_url"), url)
    if not candidate:
        selected = data.get("selected_media") or {}
        if selected.get("origin") == "own_site":
            candidate = image_candidate(selected.get("url"), url)
    if not candidate:
        http = session or requests
        response = http.get(url, headers=HEADERS, timeout=25, allow_redirects=False)
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            raise RuntimeError("Story page redirected; no cover downloaded")
        if not response.headers.get("Content-Type", "text/html").lower().startswith("text/html"):
            raise ValueError("Story URL did not return HTML")
        candidate = cover_from_html(response.text, url)
    if not candidate:
        raise RuntimeError("No same-site cover found. Page may use JavaScript or an external image CDN.")

    stem = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    directory = Path(outdir)
    destination = directory / (stem + ".png")
    # download_image rejects private IP targets, redirects and invalid images.
    download_image(candidate, destination, session=session)
    record = {
        "story_url": url,
        "title": item.get("title", ""),
        "image_url": candidate,
        "local_path": str(destination),
        "rights_status": "requires_manual_review",
        "status": "downloaded_not_approved",
        "note": "Being present on your site does not prove the image is licensed."
    }
    (directory / (stem + ".rights.json")).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination


def diagnose(draft_path):
    data = load_draft(resolve_draft(draft_path))
    url = data["item"]["link"]
    response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=False)
    print("Status:", response.status_code, "Page:", url)
    print("Content-Type:", response.headers.get("Content-Type", "unknown"))
    if response.status_code != 200:
        print("Website response not 200. Verify link in browser.")
        return
    soup = BeautifulSoup(response.text, "html.parser")
    print("HTML title:", soup.title.get_text(" ", strip=True)[:140] if soup.title else "(none)")
    print("Matching same-site cover:", cover_from_html(response.text, url) or "(none)")
    for tag in soup.select("meta[property='og:image'], meta[name='twitter:image']")[:5]:
        print("Image metadata:", (tag.get("content") or "")[:180])
    for tag in soup.select("img")[:5]:
        print("IMG:", (tag.get("data-src") or tag.get("src") or "")[:180])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--draft", default="latest")
    p.add_argument("--outdir", default="output/covers")
    p.add_argument("--poster", action="store_true")
    p.add_argument("--diagnose", action="store_true", help="Print page image metadata; no download")
    p.add_argument("--headline", default="புதிய தமிழ் கதை")
    args = p.parse_args()
    if args.diagnose:
        try:
            diagnose(args.draft)
        except (ValueError, RuntimeError, requests.RequestException, OSError) as exc:
            p.exit(2, "Diagnosis failed: " + str(exc) + "\n")
        return
    try:
        cover = auto_cover(args.draft, args.outdir)
    except (ValueError, RuntimeError, requests.RequestException, OSError) as exc:
        p.exit(2, "Cover not available: " + str(exc) + "\n")
    print("Cover candidate saved:", cover)
    print("Rights review required. No automatic posting.")
    if args.poster:
        from poster_generator import make_poster
        poster = Path(args.outdir) / "story_poster.png"
        make_poster(resolve_draft(args.draft), poster, artwork=str(cover), headline=args.headline)
        print("Poster saved:", poster)


if __name__ == "__main__":
    main()
