"""Build trackable, non-publishing story campaigns from existing RSS drafts.

No AI calls, no account access, no invented facts. URL tracking uses UTM tags.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CHANNELS = ("facebook", "instagram", "youtube", "pinterest", "threads")
FORMATS = ("story_hook", "character_spotlight", "chapter_update", "reader_poll")


def tracked_link(url, channel, campaign):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"cartoontamilan.in", "www.cartoontamilan.in"}:
        raise ValueError("Only CartoonTamilan HTTPS story links are permitted")
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({"utm_source": channel, "utm_medium": "organic_social", "utm_campaign": campaign})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def make_campaign(draft, channel, campaign_id=None):
    if channel not in CHANNELS:
        raise ValueError("Unsupported platform")
    item = draft["item"]
    if item.get("kind") != "story":
        raise ValueError("Story marketing campaigns require kind=story")
    title, url = item.get("title", "").strip(), item.get("link", "")
    if not title:
        raise ValueError("Missing story title")
    identifier = (campaign_id or ("story_" + item.get("id", "unknown")[:12])).lower()
    if not identifier.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Invalid campaign ID")
    link = tracked_link(url, channel, identifier)
    # Text is deliberately conservative: no fabricated plot, roles, dates, chapters.
    tamil = f"📚 {title}\n\nஇந்தக் கதையைப் படித்துவிட்டு உங்க கருத்தைச் சொல்லுங்க!\n👉 {link}"
    english = f"📚 {title}\n\nDiscover this story and tell us what you think.\n👉 {link}"
    return {
        "story_id": item.get("id", ""),
        "story_title": title,
        "channel": channel,
        "campaign_id": identifier,
        "target_url": link,
        "tamil_draft": tamil,
        "english_draft": english,
        "content_ideas": [
            {"format": "story_hook", "direction": "Only use a verified detail from the actual chapter"},
            {"format": "character_spotlight", "direction": "Requires verified character notes; never invent names"},
            {"format": "chapter_update", "direction": "Link directly to the confirmed chapter URL"},
            {"format": "reader_poll", "direction": "Ask a spoiler-free question about the actual story"},
        ],
        "status": "draft_review_required",
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }


def generate(drafts_dir="output", destination="output/growth_campaigns", limit=5):
    src, target = Path(drafts_dir), Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    made = []
    for path in sorted(src.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if len(made) >= limit:
            break
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
            if draft.get("item", {}).get("kind") != "story":
                continue
            group = [make_campaign(draft, channel) for channel in CHANNELS]
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
        outfile = target / (path.stem + ".json")
        outfile.write_text(json.dumps(group, ensure_ascii=False, indent=2), encoding="utf-8")
        made.append(outfile)
    return made


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--drafts", default="output")
    p.add_argument("--out", default="output/growth_campaigns")
    p.add_argument("--limit", type=int, default=5)
    a = p.parse_args()
    for created in generate(a.drafts, a.out, max(0, min(a.limit, 30))):
        print("Draft campaigns saved:", created)
    print("No posts published. Review drafts and track links using site analytics.")
