"""Download a selected image safely and store rights metadata.

This command only produces a local candidate and DOES NOT publish it.
"""
import argparse
import json
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse
from io import BytesIO

import requests
from PIL import Image, UnidentifiedImageError
from asset_selector import choose_asset

MAX_BYTES = 12 * 1024 * 1024


def public_https(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    # SSRF reduction: reject private/local address results; redirects disallowed.
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(result[4][0]).is_global for result in addresses)
    except (OSError, ValueError):
        return False


def download_image(url, destination, session=None):
    if not public_https(url):
        raise ValueError("Image must use public HTTPS with no private/local addresses.")
    http = session or requests
    resp = http.get(url, timeout=25, allow_redirects=False, headers={"User-Agent": "CartoonTamilanAutomation/0.2"})
    resp.raise_for_status()
    if 300 <= resp.status_code < 400:
        raise ValueError("Image redirects are not permitted.")
    if not resp.headers.get("content-type", "").lower().startswith("image/"):
        raise ValueError("URL did not return an image.")
    if len(resp.content) > MAX_BYTES:
        raise ValueError("Image exceeds size limit.")
    try:
        img = Image.open(BytesIO(resp.content))
        img.verify()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        if img.width < 320 or img.height < 320 or img.width * img.height > 30_000_000:
            raise ValueError("Image dimensions outside accepted range.")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid image data") from exc
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target, "PNG")
    return target


def prepare(draft_path, site_url, use_openverse=False, output_dir="output/assets"):
    data = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    item = data["item"]
    asset = choose_asset(item, site_url, enable_openverse=use_openverse)
    if asset is None:
        print("No suitable image found. No poster generated.")
        return None
    asset_dir = Path(output_dir)
    stem = item.get("id", "story")[:16]
    dest = asset_dir / (stem + ".png")
    download_image(asset["url"], dest)
    info = dict(asset)
    info["local_path"] = str(dest)
    info["story_link"] = item.get("link", "")
    info["status"] = "review_required"
    (asset_dir / (stem + ".rights.json")).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Candidate saved:", dest)
    print("Rights review required. Do not auto-publish.")
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", required=True)
    parser.add_argument("--site", default="https://cartoontamilan.in")
    parser.add_argument("--openverse", action="store_true", help="Enable Openverse CC0/PDM search fallback; still requires rights review")
    args = parser.parse_args()
    prepare(args.draft, args.site, args.openverse)
