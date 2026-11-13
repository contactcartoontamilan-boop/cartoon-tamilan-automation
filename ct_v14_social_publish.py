#!/usr/bin/env python3
"""V14 automated Facebook, Instagram and X image publishing.

Safe default: offline dry-run. Live posting uses automated queue, media,
caption, account, HTTPS-host and duplicate checks. It does not wait for manual
content approvals. SQLite records an attempt BEFORE network calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

from ct_v14_social_queue import _read_json, _safe_file, _verify_image
from ctos.platforms import PLATFORM_IMAGE
from v12_story_reader import owned_story_url

PLATFORMS = ("facebook", "instagram", "x")
JOURNAL = Path("data/ct_v14_publish_journal.sqlite3")
X_API = "https://api.x.com/2"
CONFIRMATION = "PUBLISH_REVIEWED_POSTS"


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _identity(item):
    return hashlib.sha256((
        item["platform"] + "\n" + item["story_url"] + "\n" +
        item["image_sha256"] + "\n" + item["caption"]
    ).encode("utf-8")).hexdigest()[:24]


def load_drafts(outdir, platform="all", story_url=None):
    """Revalidate draft, source preview, image bytes, and manifest linkage."""
    root = Path(outdir).resolve()
    queue = _read_json(root / "social_queue.json")
    preview = _read_json(root / "image_post_preview.json")
    for record in (queue, preview):
        if (record.get("published") is not False or
                record.get("live_publishing") is not False or
                record.get("requires_human_review") is not True):
            raise PermissionError("Only unpublished review-required V14 drafts allowed")
    if not isinstance(queue.get("image_post_queue"), list) or not isinstance(preview.get("posts"), list):
        raise ValueError("Invalid V14 queue or preview index")
    if platform not in (*PLATFORMS, "all"):
        raise ValueError("Choose facebook, instagram, x, or all")
    requested = PLATFORMS if platform == "all" else (platform,)
    manifests = {}
    for relative in preview.get("story_manifests", []):
        manifest = _safe_file(root, relative)
        record = _read_json(manifest)
        url = record.get("story", {}).get("link")
        if not owned_story_url(url) or record.get("published") is not False:
            raise PermissionError("Invalid owned-story manifest")
        manifests[url] = (manifest, record)
    if not manifests:
        raise ValueError("No source story manifests")

    chosen_story = story_url
    if chosen_story is None:
        for draft in queue["image_post_queue"]:
            if draft.get("platform") in requested:
                chosen_story = draft.get("story_url")
                break
    if not chosen_story or not owned_story_url(chosen_story) or chosen_story not in manifests:
        raise ValueError("Requested story is not in the verified queue")

    source_posts = preview["posts"]
    selected = []
    for channel in requested:
        matches = [d for d in queue["image_post_queue"]
                   if d.get("platform") == channel and d.get("story_url") == chosen_story]
        if len(matches) != 1:
            raise ValueError("Expected exactly one draft for " + channel)
        item = matches[0]
        if (item.get("published") is not False or
                item.get("status") != "pending_human_review" or
                item.get("requires_account_authorization") is not True):
            raise PermissionError("Post is not a review-only draft")
        caption = item.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            raise ValueError("Missing caption")
        image = _verify_image(root, item.get("image_file", ""),
                              PLATFORM_IMAGE[channel], item.get("image_sha256"))
        if item.get("id") != _identity(item):
            raise ValueError("Draft identity does not match reviewed content")
        matching_sources = [p for p in source_posts if
                            p.get("platform") == channel and
                            p.get("story_url") == chosen_story and
                            p.get("image_file") == item["image_file"] and
                            p.get("image_sha256") == image["sha256"] and
                            p.get("caption") == caption and
                            p.get("status") == "draft_review_required" and
                            p.get("published") is False]
        if len(matching_sources) != 1:
            raise PermissionError("Queue draft differs from original preview")
        manifest, record = manifests[chosen_story]
        variant = PLATFORM_IMAGE[channel]
        asset = record.get("assets", {}).get(variant)
        if not asset:
            raise ValueError("Missing source manifest asset")
        asset_path = (manifest.parent / asset).resolve()
        if asset_path != (root / item["image_file"]).resolve():
            raise PermissionError("Queue image differs from source manifest")
        selected.append({**item, "local_image": str(asset_path),
                         "manifest": str(manifest)})
    return selected



def _automated_content_check(item):
    """Apply deterministic checks and standard brand tags before publishing."""
    title = str(item.get("story_title", "")).strip()
    caption = str(item.get("caption", "")).strip()
    if not owned_story_url(item.get("story_url")):
        raise PermissionError("Only CartoonTamilan story links can be posted")
    if not title:
        raise ValueError("Story title is missing")
    if not caption:
        raise ValueError("Caption is empty")
    if title.casefold() not in caption.casefold():
        caption = title + "\n\n" + caption
    for tag in ("#CartoonTamilan", "#TamilStories", "#TamilNovels"):
        if tag.casefold() not in caption.casefold():
            caption += "\n" + tag
    if len(caption) > 2200:
        raise ValueError("Caption exceeds Instagram's 2,200-character limit")
    item["caption"] = caption



def _require_live_access(item, confirm):
    if confirm != CONFIRMATION:
        raise PermissionError("Explicit --confirm PUBLISH_REVIEWED_POSTS required")
    if os.getenv("CT_V14_LIVE_PUBLISH") != "YES_I_APPROVE_V14":
        raise PermissionError("CT_V14_LIVE_PUBLISH=YES_I_APPROVE_V14 required")
    if os.getenv("DRY_RUN", "true").lower() != "false":
        raise PermissionError("DRY_RUN=false required")
    platform = item["platform"]
    if os.getenv("CT_V14_ENABLE_" + platform.upper(), "").lower() != "true":
        raise PermissionError("Platform-specific CT_V14_ENABLE flag is disabled: " + platform)
    names = {
        "facebook": ("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN", "PUBLIC_MEDIA_DIR", "PUBLIC_MEDIA_BASE_URL"),
        "instagram": ("INSTAGRAM_USER_ID", "META_PAGE_ACCESS_TOKEN", "PUBLIC_MEDIA_DIR", "PUBLIC_MEDIA_BASE_URL"),
        "x": ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"),
    }[platform]
    missing = [name for name in names if not os.getenv(name, "").strip()]
    if missing:
        raise ValueError("Missing environment variables: " + ", ".join(missing))
    if platform in ("facebook", "instagram"):
        url = urlsplit(os.environ["PUBLIC_MEDIA_BASE_URL"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("PUBLIC_MEDIA_BASE_URL must be a public HTTPS media host")
    if platform == "x":
        image = Path(item["local_image"])
        if image.stat().st_size > 5_000_000:
            raise ValueError("X image exceeds 5 MB")
        if len(item["caption"]) > 280:
            raise ValueError("X caption exceeds conservative 280-character limit; edit and re-review")


def _x_auth():
    try:
        from requests_oauthlib import OAuth1
    except ImportError as exc:
        raise RuntimeError("For X live publishing install: pip install requests-oauthlib") from exc
    return OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_TOKEN_SECRET"])


def _x_json(response):
    # Never include response text or tokens in persistent error logs.
    if not 200 <= response.status_code < 300:
        raise RuntimeError("X API request failed: HTTP " + str(response.status_code))
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("X API returned invalid JSON") from exc
    if not isinstance(data, dict) or "errors" in data:
        raise RuntimeError("X API returned an error response")
    return data


def publish_x_image(path, caption, *, session=None, auth=None, sleeper=time.sleep):
    """Official X v2 chunked image upload + create Post. No implicit retries."""
    file = Path(path)
    if file.stat().st_size > 5_000_000 or not file.is_file():
        raise ValueError("X image must be a local JPEG under 5 MB")
    if len(caption) > 280:
        raise ValueError("X caption exceeds conservative 280-character limit")
    http = session or requests
    oauth = auth if auth is not None else _x_auth()
    init = _x_json(http.post(
        X_API + "/media/upload/initialize",
        json={"media_type": "image/jpeg", "total_bytes": file.stat().st_size,
              "media_category": "tweet_image"},
        auth=oauth, timeout=40))
    media_id = str(init.get("data", {}).get("id", ""))
    if not media_id.isdigit():
        raise RuntimeError("X did not return a media ID")
    with file.open("rb") as stream:
        for index, chunk in enumerate(iter(lambda: stream.read(4 * 1024 * 1024), b"")):
            appended = http.post(
                X_API + "/media/upload/" + media_id + "/append",
                data={"segment_index": index},
                files={"media": ("post.jpg", chunk, "image/jpeg")},
                auth=oauth, timeout=60)
            # Successful append responses may be HTTP 204 with an empty body.
            if not 200 <= appended.status_code < 300:
                raise RuntimeError("X image chunk upload failed: HTTP " +
                                   str(appended.status_code))
    final = _x_json(http.post(
        X_API + "/media/upload/" + media_id + "/finalize",
        auth=oauth, timeout=40))
    processing = final.get("data", {}).get("processing_info")
    for _ in range(12):
        if not processing:
            break
        state = processing.get("state")
        if state == "succeeded":
            break
        if state == "failed":
            raise RuntimeError("X image processing failed")
        sleeper(max(1, min(int(processing.get("check_after_secs", 2)), 10)))
        result = _x_json(http.get(
            X_API + "/media/upload",
            params={"command": "STATUS", "media_id": media_id},
            auth=oauth, timeout=40))
        processing = result.get("data", {}).get("processing_info")
    else:
        raise TimeoutError("X image processing not confirmed; reconcile before retry")
    result = _x_json(http.post(
        X_API + "/tweets",
        json={"text": caption, "media": {"media_ids": [media_id]}},
        auth=oauth, timeout=40))
    post_id = str(result.get("data", {}).get("id", ""))
    if not post_id.isdigit():
        raise RuntimeError("X did not confirm a published post ID")
    return {"id": post_id}


def _publish(item):
    platform = item["platform"]
    if platform == "x":
        return publish_x_image(item["local_image"], item["caption"])
    from campaign_v9 import publish_media_url
    media_url = publish_media_url(item["local_image"])
    if platform == "facebook":
        from social.facebook import publish_photo
        return publish_photo(media_url, item["caption"])
    if platform == "instagram":
        from social.instagram import (create_image_container,
                                      wait_until_container_ready, publish_container)
        container = create_image_container(media_url, item["caption"])
        container_id = str(container["id"])
        wait_until_container_ready(container_id, timeout_seconds=240, poll_seconds=8)
        return publish_container(container_id)
    raise ValueError("Unsupported platform")


def _connect_journal(path):
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(file, timeout=30)
    connection.execute("""CREATE TABLE IF NOT EXISTS deliveries (
        platform TEXT NOT NULL, draft_id TEXT NOT NULL, story_url TEXT NOT NULL,
        status TEXT NOT NULL, remote_id TEXT, attempted_at TEXT NOT NULL,
        PRIMARY KEY (platform, draft_id)
    )""")
    connection.commit()
    return connection


def _claim(connection, item):
    connection.execute("BEGIN IMMEDIATE")
    found = connection.execute(
        "SELECT status, remote_id FROM deliveries WHERE platform=? AND draft_id=?",
        (item["platform"], item["id"])).fetchone()
    if found:
        connection.commit()
        return {"status": "already_attempted", "previous_status": found[0],
                "remote_id": found[1]}
    connection.execute(
        "INSERT INTO deliveries (platform,draft_id,story_url,status,attempted_at) VALUES (?,?,?,?,?)",
        (item["platform"], item["id"], item["story_url"], "inflight", _utc_now()))
    connection.commit()  # Durable before any network request.
    return None


def _finish(connection, item, status, remote_id=None):
    connection.execute(
        "UPDATE deliveries SET status=?, remote_id=? WHERE platform=? AND draft_id=?",
        (status, remote_id, item["platform"], item["id"]))
    connection.commit()


def run(outdir="output/v14/image_posts", *, platform="all", story_url=None,
        live=False, confirm=None, journal=JOURNAL, sender=None):
    items = load_drafts(outdir, platform, story_url)
    if not live:
        return {"status": "dry_run_only", "network_calls": 0,
                "published": False, "scheduler_running": False,
                "items": [{"platform": i["platform"], "id": i["id"],
                           "story_url": i["story_url"],
                           "image_file": i["image_file"],
                           "approval": "not_verified_in_dry_run"} for i in items]}
    # Automated preflight EVERY platform before publishing ANY of them.
    for item in items:
        _automated_content_check(item)
        _require_live_access(item, confirm)
    connection = _connect_journal(journal)
    results = []
    try:
        for item in items:
            prior = _claim(connection, item)
            if prior is not None:
                results.append({"platform": item["platform"], **prior})
                continue
            try:
                response = (sender or _publish)(item)
                remote_id = str(response.get("id", ""))
                if not remote_id:
                    raise RuntimeError("API response lacks a confirmed post ID")
                _finish(connection, item, "published", remote_id)
                results.append({"platform": item["platform"], "status": "published",
                                "remote_id": remote_id})
            except Exception as exc:
                _finish(connection, item, "uncertain")
                results.append({"platform": item["platform"], "status": "uncertain",
                                "error_type": type(exc).__name__,
                                "action": "Check platform manually; no automatic retry"})
                break
    finally:
        connection.close()
    return {"status": ("needs_reconciliation" if any(
                r["status"] == "uncertain" or
                (r["status"] == "already_attempted" and
                 r.get("previous_status") in ("inflight", "uncertain"))
                for r in results) else "completed"),
            "results": results, "scheduler_running": False,
            "note": "Published only when provider returned a post ID; verify in each account"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="V14 automated FB/IG/X image posting; dry-run by default")
    parser.add_argument("--outdir", default="output/v14/image_posts")
    parser.add_argument("--platform", choices=(*PLATFORMS, "all"), default="all")
    parser.add_argument("--story-url")
    parser.add_argument("--live", action="store_true", help="Real API publishing; live account settings and credentials required")
    parser.add_argument("--confirm", default=None, help="Must be PUBLISH_REVIEWED_POSTS for live")
    args = parser.parse_args(argv)
    try:
        result = run(args.outdir, platform=args.platform, story_url=args.story_url,
                     live=args.live, confirm=args.confirm)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["status"] == "needs_reconciliation" else 0
    except (ValueError, PermissionError, FileNotFoundError, RuntimeError) as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__,
                          "message": str(exc), "published": False},
                         ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
