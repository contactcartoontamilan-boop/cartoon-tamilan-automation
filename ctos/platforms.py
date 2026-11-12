"""Platform-specific content exports and gated real Meta / Telegram adapters.

Only Meta and Telegram have actual network publish adapters here.
YouTube, X, Pinterest, Threads and LinkedIn remain export-only until
their owner OAuth credentials, API permissions and upload APIs are integrated.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import requests

from campaign_v9 import get_approval, load_approvals, publish_pack
from ctos.review import require_approval

PLATFORM_IMAGE = {
    "instagram": "instagram_feed",
    "facebook": "facebook_feed",
    "youtube": "youtube_thumbnail",
    "pinterest": "pinterest_pin",
    "threads": "threads_feed",
    "x": "x_landscape",
    "linkedin": "linkedin_landscape",
    "telegram": "instagram_feed",
}
REAL_PUBLISH_APIS = ("facebook", "instagram", "telegram")


def export_platform_drafts(manifest):
    root = Path(manifest)
    data = json.loads(root.read_text(encoding="utf-8"))
    result = {}
    for channel, variant in PLATFORM_IMAGE.items():
        file = data.get("assets", {}).get(variant)
        if not file:
            continue
        result[channel] = {
            "image_file": file,
            "caption": data.get("copy", {}).get("captions", {}).get(channel, ""),
            "story_url": data["story"]["link"],
            "publisher": "Meta Graph API" if channel in ("facebook", "instagram") else
                         "Telegram Bot API" if channel == "telegram" else
                         "export_only_provider_auth_required",
            "publication_status": "not_published",
        }
    outfile = root.parent / "platform_drafts.json"
    outfile.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _get_reviewed_bundle(manifest_path):
    require_approval(manifest_path)
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    original_approval = get_approval(data["story"], load_approvals())
    if not original_approval or original_approval.get("v10_visual_policy_approved") is not True:
        raise PermissionError("V9 story rights/copy + V10 visual approval are also required")
    return data


def publish_meta(manifest_path, day=None, live=False):
    """Uses the existing tested V9 Meta flow, HTTPS media host, journal & opt-ins."""
    if not live or os.getenv("CT_LIVE_PUBLISH") != "YES_I_APPROVE_META":
        raise PermissionError("Live Meta publication requires explicit CLI confirmation and CT_LIVE_PUBLISH")
    data = _get_reviewed_bundle(manifest_path)
    if "facebook_feed" not in data["assets"] or "instagram_feed" not in data["assets"]:
        raise ValueError("Missing platform-specific outputs")
    # Existing V9 publisher publishes one 1080x1350 JPG for BOTH.
    # Use the new text-safe V13 feed graphic, never the old V10 typeset poster.
    file = (Path(manifest_path).parent / data["assets"]["instagram_feed"]).resolve()
    pack = {
        "poster": str(file),
        "facebook": {"caption": data["copy"]["captions"]["facebook"]},
        "instagram": {"caption": data["copy"]["captions"]["instagram"]},
        "copyright_checked": True,
        "copy_reviewed": True,
        "v10_visual_policy_approved": True,
    }
    return publish_pack(data["story"], pack, day=day or date.today())


def publish_telegram(manifest_path, live=False, session=None):
    """Optional single Telegram channel post. Nothing is sent unless fully gated."""
    if not live or os.getenv("CT_LIVE_TELEGRAM") != "YES_I_APPROVE_TELEGRAM":
        raise PermissionError("Telegram live publishing disabled")
    data = _get_reviewed_bundle(manifest_path)
    token = os.getenv("CT_TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("CT_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("Telegram bot and channel credentials missing")
    img = (Path(manifest_path).parent / data["assets"]["instagram_feed"]).resolve()
    # Telegram captions have their own limit; the full social copy stays in exports.
    caption = data["copy"]["captions"]["telegram"][:900]
    try:
        with img.open("rb") as media:
            response = (session or requests).post(
                "https://api.telegram.org/bot" + token + "/sendPhoto",
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": ("story.jpg", media, "image/jpeg")},
                timeout=45,
            )
        response.raise_for_status()
        payload = response.json()
        if payload.get("ok") is not True:
            raise RuntimeError("Telegram rejected publication")
    except requests.RequestException:
        raise RuntimeError("Telegram publication status uncertain; check channel before retry (secrets hidden)") from None
    return {"channel": "telegram", "status": "published", "id": payload.get("result", {}).get("message_id")}


def publish_platform(manifest_path, platform, *, live=False):
    if platform == "meta":
        return publish_meta(manifest_path, live=live)
    if platform == "telegram":
        return publish_telegram(manifest_path, live=live)
    raise NotImplementedError(
        "This channel is export-only. OAuth app permissions and uploader not connected: " + platform)
