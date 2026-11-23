#!/usr/bin/env python3
"""V14 publishing adapters for generated Instagram Reels, Facebook Reels and YouTube Shorts.

Requires explicit per-channel gates and provider credentials. Ambiguous outcomes
are journaled as uncertain and are never retried automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import shutil
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

from v12_story_reader import owned_story_url

CONFIRMATION = "PUBLISH_REVIEWED_POSTS"
JOURNAL = Path("data/ct_v14_video_publish_journal.sqlite3")
SOURCE_PLATFORMS = {
    "instagram_reel": "instagram_reels",
    "instagram_story": "instagram_stories",
    "facebook_reel": "facebook_reels",
    "youtube_short": "youtube_shorts",
    "youtube_full_episode": "youtube_full_episode",
}
ENABLE_FLAGS = {
    "instagram_reel": "CT_V14_ENABLE_INSTAGRAM_REELS",
    "instagram_story": "CT_V14_ENABLE_INSTAGRAM_STORIES",
    "facebook_reel": "CT_V14_ENABLE_FACEBOOK_REELS",
    "youtube_short": "CT_V14_ENABLE_YOUTUBE_SHORTS",
    "youtube_full_episode": "CT_V14_ENABLE_YOUTUBE_LONG_VIDEO",
}


def _json_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def _load_video(outdir: str | Path, platform: str, story_url: str) -> dict:
    if platform not in SOURCE_PLATFORMS:
        raise ValueError("Choose instagram_reel, instagram_story, facebook_reel, youtube_short or youtube_full_episode")
    if not owned_story_url(story_url):
        raise PermissionError("Only CartoonTamilan story videos can be published")
    root = Path(outdir).resolve()
    queue = _json_file(root / "social_queue.json")
    preview = _json_file(root / "image_post_preview.json")
    if (queue.get("published") is not False or queue.get("live_publishing") is not False
            or preview.get("published") is not False
            or preview.get("live_publishing") is not False):
        raise PermissionError("Only unpublished V14 video drafts can be published")
    source_platform = SOURCE_PLATFORMS[platform]
    matches = [
        item for item in queue.get("reel_short_requirements", [])
        if isinstance(item, dict) and item.get("platform") == source_platform
        and item.get("story_url") == story_url
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one queued video for this platform and story")
    draft = matches[0]
    if draft.get("published") is not False or draft.get("status") != "draft_video_ready_review":
        raise PermissionError("Video is not an unpublished ready draft")
    relative = draft.get("video_file")
    if not isinstance(relative, str) or not relative:
        raise ValueError("Video file is missing")
    video = (root / relative).resolve()
    if not video.is_relative_to(root) or not video.is_file() or video.suffix.lower() != ".mp4":
        raise ValueError("Video must be an MP4 inside the queue directory")
    if video.stat().st_size < 1024 or video.stat().st_size > 512 * 1024 * 1024:
        raise ValueError("MP4 must be between 1 KB and 512 MB")
    with video.open("rb") as stream:
        header = stream.read(12)
    if len(header) < 12 or header[4:8] != b"ftyp":
        raise ValueError("Video does not have a valid MP4 container header")
    digest_builder = hashlib.sha256()
    with video.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest_builder.update(chunk)
    digest = digest_builder.hexdigest()
    expected = draft.get("video_sha256")
    if expected and digest != expected:
        raise PermissionError("Video changed after queue creation")
    title = str(draft.get("story_title") or "").strip()
    if not title:
        raise ValueError("Story title is missing")
    image_drafts = [
        item for item in queue.get("image_post_queue", [])
        if isinstance(item, dict) and item.get("story_url") == story_url
    ]
    preferred = "instagram" if platform == "instagram_reel" else "facebook"
    matching = next((item for item in image_drafts if item.get("platform") == preferred), None)
    caption = str(matching.get("caption") if matching else "").strip()
    if platform in {"youtube_short", "youtube_full_episode"} and draft.get("caption"):
        caption = str(draft["caption"]).strip()
    elif platform == "youtube_short":
        caption = f"{title} | Cartoon Tamilan\n\nRead the original Tamil story: {story_url}\n#Shorts #TamilStories #CartoonTamilan"
    elif not caption:
        caption = f"{title}\n\nRead the original Tamil story: {story_url}\n#CartoonTamilan #TamilStories"
    draft_id = hashlib.sha256(
        (platform + "\n" + story_url + "\n" + digest + "\n" + caption).encode("utf-8")
    ).hexdigest()[:24]
    return {
        "id": draft_id, "platform": platform, "source_platform": source_platform,
        "story_url": story_url, "story_title": title, "caption": caption,
        "video_file": str(video), "video_sha256": digest,
        "is_ai_generated": True,
    }


def _require_live(item: dict, confirm: str | None) -> None:
    if confirm != CONFIRMATION:
        raise PermissionError("Explicit live-publish confirmation is required")
    if os.getenv("CT_V14_LIVE_PUBLISH") != "YES_I_APPROVE_V14":
        raise PermissionError("CT_V14_LIVE_PUBLISH live gate is disabled")
    if os.getenv("DRY_RUN", "true").strip().lower() != "false":
        raise PermissionError("DRY_RUN=false is required")
    flag = ENABLE_FLAGS[item["platform"]]
    if os.getenv(flag, "").strip().lower() != "true":
        raise PermissionError(flag + "=true is required")
    if item["platform"] in ("instagram_reel", "instagram_story", "facebook_reel"):
        required = ("META_PAGE_ACCESS_TOKEN",)
        if item["platform"] in ("instagram_reel", "instagram_story"):
            required += ("INSTAGRAM_USER_ID", "PUBLIC_MEDIA_DIR", "PUBLIC_MEDIA_BASE_URL")
        else:
            required += ("META_PAGE_ID",)
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            raise ValueError("Missing environment variables: " + ", ".join(missing))
    else:
        required = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
        missing = [name for name in required if not os.getenv(name, "").strip()]
        if missing:
            raise ValueError("Missing environment variables: " + ", ".join(missing))


def _meta_response(response: requests.Response) -> dict:
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Meta returned invalid JSON") from exc
    if not response.ok or not isinstance(data, dict) or "error" in data:
        raise RuntimeError("Meta video publishing failed: HTTP " + str(response.status_code))
    return data


def _publish_video_media_url(item: dict) -> str:
    """Copy an MP4 to the configured public host and verify its served type."""
    media_dir = os.getenv("PUBLIC_MEDIA_DIR", "").strip()
    media_base = os.getenv("PUBLIC_MEDIA_BASE_URL", "").strip().rstrip("/")
    parsed = urlsplit(media_base)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or not media_dir):
        raise ValueError("Configure PUBLIC_MEDIA_DIR and a public HTTPS media base URL")
    source = Path(item["video_file"])
    if not source.is_file():
        raise FileNotFoundError(str(source))
    digest = item["video_sha256"]
    name = "ct_" + digest[:24] + ".mp4"
    destination_dir = Path(media_dir).expanduser()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / name
    if not destination.exists():
        shutil.copy2(source, destination)
    public_url = media_base + "/" + quote(name, safe="")
    response = requests.head(public_url, timeout=(10, 30), allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError("Public MP4 URL did not return HTTP 200")
    if not response.headers.get("content-type", "").lower().split(";", 1)[0].strip() == "video/mp4":
        raise RuntimeError("Public media host must serve MP4 as video/mp4")
    return public_url


def _publish_instagram_video(item: dict, media_type: str) -> dict:
    from social.instagram import (
        create_reel_container, wait_until_container_ready, publish_container,
    )
    media_url = _publish_video_media_url(item)
    parsed = urlsplit(media_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Instagram video must be reachable at a public HTTPS URL")
    if media_type == "REELS":
        container = create_reel_container(media_url, item["caption"], share_to_feed=True)
    else:
        version = os.getenv("META_GRAPH_VERSION", "v26.0").strip()
        response = requests.post(
            f"https://graph.facebook.com/{version}/{os.environ['INSTAGRAM_USER_ID']}/media",
            data={"media_type": "STORIES", "video_url": media_url,
                  "access_token": os.environ["META_PAGE_ACCESS_TOKEN"]},
            timeout=(10, 90),
        )
        container = _meta_response(response)
    container_id = str(container.get("id", ""))
    if not container_id:
        raise RuntimeError("Instagram did not return a video container ID")
    wait_until_container_ready(container_id, timeout_seconds=600, poll_seconds=10)
    result = publish_container(container_id)
    if not result.get("id"):
        raise RuntimeError("Instagram did not confirm the published video ID")
    return result


def _publish_instagram_reel(item: dict) -> dict:
    return _publish_instagram_video(item, "REELS")


def _publish_instagram_story(item: dict) -> dict:
    return _publish_instagram_video(item, "STORIES")


def _publish_facebook_reel(item: dict) -> dict:
    page_id = os.environ["META_PAGE_ID"]
    token = os.environ["META_PAGE_ACCESS_TOKEN"]
    version = os.getenv("META_GRAPH_VERSION", "v26.0").strip()
    graph = f"https://graph.facebook.com/{version}"
    path = f"{graph}/{page_id}/video_reels"
    size = Path(item["video_file"]).stat().st_size
    started = _meta_response(requests.post(
        path, data={"upload_phase": "START", "access_token": token},
        timeout=(10, 60),
    ))
    video_id = str(started.get("video_id") or "")
    upload_url = str(started.get("upload_url") or "")
    parsed = urlsplit(upload_url)
    if not video_id.isdigit() or parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("Facebook returned an invalid Reel upload session")
    if not (parsed.hostname == "facebook.com" or parsed.hostname.endswith(".facebook.com")):
        raise RuntimeError("Facebook returned an unrecognized Reel upload host")
    with Path(item["video_file"]).open("rb") as stream:
        uploaded = requests.post(
            upload_url,
            headers={
                "Authorization": "OAuth " + token,
                "offset": "0",
                "file_size": str(size),
                "Content-Type": "application/octet-stream",
            },
            data=stream, timeout=(15, 600),
        )
    try:
        uploaded_data = uploaded.json()
    except ValueError as exc:
        raise RuntimeError("Facebook Reel upload returned invalid JSON") from exc
    if not uploaded.ok or uploaded_data.get("success") is not True:
        raise RuntimeError("Facebook Reel video upload failed: HTTP " + str(uploaded.status_code))
    finished = _meta_response(requests.post(
        path,
        data={
            "upload_phase": "FINISH", "video_id": video_id,
            "video_state": "PUBLISHED", "title": item["story_title"][:100],
            "description": item["caption"], "is_ai_generated": "true",
            "access_token": token,
        },
        timeout=(10, 120),
    ))
    if finished.get("success") is False:
        raise RuntimeError("Facebook did not confirm the published Reel")
    return {"id": str(finished.get("post_id") or video_id)}


def _youtube_access_token() -> str:
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ["YOUTUBE_CLIENT_ID"],
            "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
            "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=(10, 45),
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("YouTube OAuth returned invalid JSON") from exc
    token = data.get("access_token") if isinstance(data, dict) else None
    if not response.ok or not token:
        raise RuntimeError("YouTube OAuth refresh failed: HTTP " + str(response.status_code))
    return str(token)


def _publish_youtube_video(item: dict, *, is_short: bool) -> dict:
    token = _youtube_access_token()
    path = Path(item["video_file"])
    size = path.stat().st_size
    metadata = {
        "snippet": {
            "title": ((item["story_title"][:85] + " #Shorts") if is_short
                      else item["story_title"][:100]),
            "description": item["caption"][:5000],
            "tags": (["CartoonTamilan", "TamilStories", "Shorts"] if is_short else
                     ["CartoonTamilan", "TamilStories", "TamilAnime", "FullEpisode"]),
            "categoryId": "24",
            "defaultLanguage": "ta",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    session = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": "video/mp4",
        },
        json=metadata, timeout=(10, 60),
    )
    location = session.headers.get("Location", "")
    parsed = urlsplit(location)
    if not session.ok or parsed.scheme != "https" or parsed.hostname not in (
        "www.googleapis.com", "youtube.googleapis.com"
    ):
        raise RuntimeError("YouTube did not return a valid resumable upload URL")
    with path.open("rb") as stream:
        uploaded = requests.put(
            location,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
            },
            data=stream, timeout=(15, 900),
        )
    try:
        data = uploaded.json()
    except ValueError as exc:
        raise RuntimeError("YouTube upload returned invalid JSON") from exc
    video_id = str(data.get("id") or "") if isinstance(data, dict) else ""
    if not uploaded.ok or not video_id:
        raise RuntimeError("YouTube did not confirm the uploaded Short: HTTP " + str(uploaded.status_code))
    return {"id": video_id}


def _connect(path: str | Path) -> sqlite3.Connection:
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


def _publish(item: dict) -> dict:
    if item["platform"] == "instagram_reel":
        return _publish_instagram_reel(item)
    if item["platform"] == "instagram_story":
        return _publish_instagram_story(item)
    if item["platform"] == "facebook_reel":
        return _publish_facebook_reel(item)
    if item["platform"] == "youtube_short":
        return _publish_youtube_video(item, is_short=True)
    if item["platform"] == "youtube_full_episode":
        return _publish_youtube_video(item, is_short=False)
    raise ValueError("Unsupported video platform")


def run(outdir: str | Path = "output/v14/image_posts", *,
        platform: str, story_url: str, live: bool = False,
        confirm: str | None = None, journal: str | Path = JOURNAL,
        sender=None, delivery_cycle: int = 0) -> dict:
    item = _load_video(outdir, platform, story_url)
    if delivery_cycle > 0:
        item["caption"] = item["caption"].rstrip() + "\n\n" + "இந்தக் கதையை மீண்டும் பாருங்கள்!"
        item["id"] = hashlib.sha256(
            (item["id"] + "\nrepost-cycle:" + str(delivery_cycle)).encode("utf-8")
        ).hexdigest()[:24]
    if not live:
        return {"status": "dry_run_only", "published": False,
                "platform": platform, "story_url": story_url}
    _require_live(item, confirm)
    connection = _connect(journal)
    try:
        connection.execute("BEGIN IMMEDIATE")
        prior = connection.execute(
            "SELECT status,remote_id FROM deliveries WHERE platform=? AND draft_id=?",
            (platform, item["id"]),
        ).fetchone()
        if prior:
            connection.commit()
            return {"status": "already_attempted", "published": prior[0] == "published",
                    "platform": platform, "remote_id": prior[1]}
        from datetime import datetime, timezone
        connection.execute(
            "INSERT INTO deliveries VALUES (?,?,?,?,?,?)",
            (platform, item["id"], story_url, "inflight", None,
             datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
        try:
            result = (sender or _publish)(item)
            remote_id = str(result.get("id") or "")
            if not remote_id:
                raise RuntimeError("Platform returned no confirmed publication ID")
            connection.execute(
                "UPDATE deliveries SET status='published',remote_id=? WHERE platform=? AND draft_id=?",
                (remote_id, platform, item["id"]),
            )
            connection.commit()
            return {"status": "completed", "published": True,
                    "platform": platform, "remote_id": remote_id}
        except Exception as exc:
            connection.execute(
                "UPDATE deliveries SET status='uncertain' WHERE platform=? AND draft_id=?",
                (platform, item["id"]),
            )
            connection.commit()
            return {"status": "needs_reconciliation", "published": False,
                    "platform": platform, "error_type": type(exc).__name__,
                    "note": "Check the platform manually; no automatic retry"}
    finally:
        connection.close()


__all__ = ["run", "SOURCE_PLATFORMS"]
