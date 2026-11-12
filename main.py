import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import requests
import yaml
from dotenv import load_dotenv

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
OUTPUT_DIR = BASE / "output"
STATE_FILE = DATA_DIR / "state.json"

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_config():
    with open(BASE / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"published_or_seen": []}


def save_state(state):
    DATA_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def clean_html(value):
    from bs4 import BeautifulSoup
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def item_id(item):
    raw = (item.get("link", "") + "|" + item.get("title", "")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def collect_items(config):
    collected = []
    for source in config.get("sources", []):
        url = source["url"]
        logging.info("Reading feed: %s", source["name"])
        try:
            feed = feedparser.parse(url)
            if getattr(feed, "bozo", False) and not feed.entries:
                logging.warning("Feed could not be parsed: %s", url)
                continue

            for entry in feed.entries[:config.get("max_items_per_source", 10)]:
                title = clean_html(entry.get("title", "")).strip()
                link = entry.get("link", "").strip()
                summary = clean_html(entry.get("summary", entry.get("description", "")))
                if not title or not link:
                    continue
                # RSS image discovery is best-effort. Instagram needs a public HTTPS media URL.
                image_url = ""
                media_items = entry.get("media_content", [])
                if media_items:
                    image_url = media_items[0].get("url", "")
                if not image_url:
                    enclosures = entry.get("enclosures", [])
                    if enclosures:
                        image_url = enclosures[0].get("href", "")
                collected.append({
                    "id": item_id({"link": link, "title": title}),
                    "title": title,
                    "link": link,
                    "summary": summary[:1200],
                    "source": source["name"],
                    "kind": source.get("kind", "news"),
                    "published": entry.get("published", entry.get("updated", "")),
                    "image_url": image_url,
                })
        except Exception:
            logging.exception("Failed to read source: %s", url)
    return collected


def make_caption(item):
    title = item["title"]
    link = item["link"]
    if item["kind"] == "story":
        return (
            "📖 புதிய Original Story Update! | New Original Story Update!\n\n"
            f"✨ {title}\n\n"
            "🇮🇳 தமிழ் வாசகர்களுக்காக: எங்கள் original anime stories-ஐ படித்து உங்கள் கருத்தைப் பகிருங்கள்!\n"
            "🌍 For global readers: Discover original anime-inspired stories and follow the next chapter.\n\n"
            f"👉 Read here: {link}\n\n"
            "#CartoonTamilan #OriginalStories #AnimeNovels #TamilStories #WebNovels"
        )
    return (
        "🌍 Anime & Animation Update!\n\n"
        f"📰 {title}\n\n"
        "🇮🇳 தமிழ்: இந்த செய்தியின் முழு விவரங்களையும் source-ல் சரிபார்த்து படிக்கவும்.\n"
        "🌍 English: Check the source for the full announcement and details.\n\n"
        f"🔗 Read more: {link}\n\n"
        "#CartoonTamilan #AnimeNews #AnimationNews #AnimeUpdates"
    )


def save_draft(item, caption):
    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = f'{item["id"][:16]}.json'
    path = OUTPUT_DIR / filename
    path.write_text(
        json.dumps({"item": item, "caption": caption}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return path


def publish_facebook(caption):
    page_id = os.getenv("META_PAGE_ID", "").strip()
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        logging.info("Facebook credentials missing; keeping this as a draft.")
        return False

    endpoint = f"https://graph.facebook.com/v23.0/{page_id}/feed"
    response = requests.post(
        endpoint,
        data={"message": caption, "access_token": token},
        timeout=30
    )
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:500]}

    if not response.ok or "error" in data:
        logging.error("Facebook publish failed: %s", data)
        return False

    logging.info("Facebook post created: %s", data.get("id", "ID not returned"))
    return True


def main():
    config = load_config()
    state = load_state()
    seen = set(state.get("published_or_seen", []))
    items = collect_items(config)

    new_items = [item for item in items if item["id"] not in seen]
    logging.info("Collected %d items; %d are new.", len(items), len(new_items))

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    publish_fb = os.getenv("PUBLISH_FACEBOOK", "false").lower() == "true"

    # Limit each run so one feed burst cannot flood social accounts.
    for item in new_items[:5]:
        caption = make_caption(item)
        draft_path = save_draft(item, caption)
        logging.info("Draft saved: %s", draft_path)

        # Shared publisher handles Facebook and Instagram flags independently.
        # Instagram is skipped unless the feed supplied a public image URL.
        try:
            from social.publisher import publish_item
            media = {"type": "image", "url": item["image_url"]} if item.get("image_url") else None
            results = publish_item(item, caption, media=media)
            logging.info("Social publishing result: %s", results)
        except Exception:
            logging.exception("Social publishing failed; draft remains saved.")
            # Do not mark failed posts as seen, so a later run can retry.
            continue

        seen.add(item["id"])

    state["published_or_seen"] = list(seen)[-2000:]
    state["last_run_utc"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    logging.info("Run complete. New items processed: %d", min(len(new_items), 5))


if __name__ == "__main__":
    main()
