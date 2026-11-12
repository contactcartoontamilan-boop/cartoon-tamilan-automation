"""CartoonTamilan V9 campaign runner: website → art → poster → captions → Meta.

Run preview by default. Live publishing requires explicit per-story approvals,
enabled env switches, verified public HTTPS hosting and Meta tokens.
No credentials or generated binaries are stored on GitHub.
"""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests
from PIL import Image
from dotenv import load_dotenv

from auto_story_marketing import discover
from auto_story_cover import auto_cover
from cinematic_poster_v9 import cinematic_poster
from social_content_v5 import make_social_pack

load_dotenv()
BASE = Path(__file__).resolve().parent
STATE = BASE / "data" / "campaign_state_v9.json"
APPROVALS = BASE / "data" / "story_approvals_v9.json"


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path, default):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def load_approvals():
    content = read_json(APPROVALS, {})
    if not isinstance(content, dict):
        raise ValueError("Approval file must be a JSON object keyed by story URL")
    return content


def get_approval(item, approvals):
    record = approvals.get(item["link"], {})
    if not (record.get("rights_confirmed") is True and record.get("copy_reviewed") is True):
        return None
    if not (record.get("intro_ta") and record.get("intro_en")):
        return None
    return record


def select_stories(stories, day, limit):
    """Rotate fairly by date; avoid always promoting the first story."""
    if not stories:
        return []
    unique = {s["link"]: s for s in stories if s.get("kind") == "story"}
    ordered = sorted(unique.values(), key=lambda item: item["link"])
    n = len(ordered)
    start = day.toordinal() % n
    return [ordered[(start + i) % n] for i in range(min(limit, n))]


def create_campaign(item, day, art_provider="cover", outdir="output/campaign_v9",
                    approval=None, cover_fetcher=None, artwork_generator=None,
                    poster_maker=None):
    if art_provider not in ("cover", "comfyui"):
        raise ValueError("ART_PROVIDER must be cover or comfyui")
    key = hashlib.sha256(item["link"].encode("utf-8")).hexdigest()[:16]
    folder = Path(outdir) / day.isoformat() / key
    folder.mkdir(parents=True, exist_ok=True)
    draft = folder / "draft.json"
    story = {"item": {**item, "id": key, "summary": item.get("summary", "")},
             "status": "review_required"}
    write_json(draft, story)
    if art_provider == "comfyui":
        # A text-to-image workflow does not need the website cover. A missing
        # cover must not prevent generation once a local model is configured.
        if artwork_generator is None:
            from comfyui_art_v9 import generate, story_prompt
            style = os.getenv("ART_STYLE", "anime")
            artwork_generator = lambda title, dest: generate(story_prompt(title, style), dest)
        artwork = artwork_generator(item["title"], folder / "ai_original_art.png")
    else:
        artwork = (cover_fetcher or auto_cover)(draft, folder / "covers")
    poster_path = folder / "cinematic_poster.jpg"
    (poster_maker or cinematic_poster)(draft, artwork, poster_path)
    record = approval or {}
    pack = make_social_pack(item, genres=record.get("genres", ()),
                            verified_intro_ta=record.get("intro_ta", ""),
                            verified_intro_en=record.get("intro_en", ""))
    pack["art_provider"] = art_provider
    pack["source_artwork"] = str(artwork)
    pack["poster"] = str(poster_path)
    pack["copyright_checked"] = bool(approval and approval.get("rights_confirmed"))
    pack["copy_reviewed"] = bool(approval and approval.get("copy_reviewed"))
    pack["status"] = "approved_for_automated_publishing" if approval else "draft_review_required"
    write_json(folder / "social_pack.json", pack)
    return pack


def publish_media_url(poster_path, media_dir=None, media_base=None, session=None):
    """Copies JPEG to a PUBLIC HTTPS served folder; verifies it is reachable."""
    media_dir = media_dir or os.getenv("PUBLIC_MEDIA_DIR", "")
    media_base = (media_base or os.getenv("PUBLIC_MEDIA_BASE_URL", "")).rstrip("/")
    url = urlsplit(media_base)
    if url.scheme != "https" or not url.hostname or not media_dir:
        raise ValueError("Configure PUBLIC_MEDIA_DIR and PUBLIC_MEDIA_BASE_URL=https://your-host/media")
    src = Path(poster_path)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    with Image.open(src) as opened:
        if opened.format != "JPEG" or opened.size != (1080, 1350):
            raise ValueError("Expected 1080x1350 JPEG poster")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:18]
    name = "ct_" + digest + ".jpg"
    folder = Path(media_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / name
    if not destination.exists():
        shutil.copy2(src, destination)
    public_url = media_base + "/" + quote(name)
    http = session or requests
    response = http.head(public_url, timeout=25, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200:
        raise RuntimeError("Public media URL did not return HTTP 200")
    if not response.headers.get("content-type", "").lower().startswith("image/jpeg"):
        raise RuntimeError("Hosting must serve Content-Type: image/jpeg")
    return public_url


def check_publish_ready():
    if os.getenv("DRY_RUN", "true").lower() != "false":
        raise ValueError("DRY_RUN must be explicitly set to false to publish")
    if os.getenv("AUTO_PUBLISH_APPROVED", "false").lower() != "true":
        raise ValueError("AUTO_PUBLISH_APPROVED=true required for live posting")
    if not any(os.getenv(k, "false").lower() == "true" for k in ("PUBLISH_FACEBOOK", "PUBLISH_INSTAGRAM")):
        raise ValueError("Enable at least one publisher flag")
    if os.getenv("PUBLISH_FACEBOOK", "false").lower() == "true":
        for key in ("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN"):
            if not os.getenv(key):
                raise ValueError("Missing " + key)
    if os.getenv("PUBLISH_INSTAGRAM", "false").lower() == "true":
        for key in ("INSTAGRAM_USER_ID", "META_PAGE_ACCESS_TOKEN"):
            if not os.getenv(key):
                raise ValueError("Missing " + key)


@contextmanager
def campaign_lock():
    lock = BASE / "data" / "campaign_v9.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as file:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def publish_pack(item, pack, journal=None, media_publisher=None, fb_func=None, ig_func=None,
                 day=None):
    """Per-platform journal prevents accidental repeat publication on later runs."""
    check_publish_ready()
    if not (pack["copyright_checked"] and pack["copy_reviewed"]):
        raise ValueError("This story is not explicitly approved for publication")
    day = day or date.today()
    signature = day.isoformat() + "|" + item["link"]
    journal_path = Path(journal or STATE)
    with campaign_lock():
        state = read_json(journal_path, {"posts": {}})
        statuses = state.setdefault("posts", {}).setdefault(signature, {})
        platforms = [p for p in ("facebook", "instagram")
                     if os.getenv("PUBLISH_" + p.upper(), "false").lower() == "true"]
        pending = [p for p in platforms if p not in statuses]
        if not pending:
            return statuses
        # Both platforms use publicly accessible poster image.
        media_url = (media_publisher or publish_media_url)(pack["poster"])
        for platform in pending:
            statuses[platform] = {"status": "inflight"}
            write_json(journal_path, state)
            try:
                if platform == "facebook":
                    if fb_func is None:
                        from social.facebook import publish_photo
                        fb_func = publish_photo
                    result = fb_func(media_url, pack["facebook"]["caption"])
                else:
                    if ig_func is None:
                        from social.instagram import (create_image_container,
                                                      wait_until_container_ready,
                                                      publish_container)
                        def ig_func(url, caption):
                            container = create_image_container(url, caption)
                            wait_until_container_ready(container["id"], timeout_seconds=240, poll_seconds=8)
                            return publish_container(container["id"])
                    result = ig_func(media_url, pack["instagram"]["caption"])
                statuses[platform] = {"status": "published", "id": str(result.get("id", ""))}
                write_json(journal_path, state)
            except Exception as error:
                # A timeout can mean Meta published anyway; don't auto-retry.
                statuses[platform] = {"status": "uncertain", "error_type": type(error).__name__}
                write_json(journal_path, state)
                raise
        return statuses


def run(limit=1, publish=False, art_provider=None, day=None, outdir="output/campaign_v9",
        discovery_func=None, campaign_func=None):
    day = day or date.today()
    stories = (discovery_func or discover)(limit=30)
    approvals = load_approvals()
    selected = select_stories(stories, day, limit)
    report = {"date": day.isoformat(), "discovered": len(stories),
              "selected": len(selected), "prepared": [], "failed": [],
              "published": [], "dry_run": not publish}
    if publish:
        check_publish_ready()
    for item in selected:
        approval = get_approval(item, approvals)
        if publish and not approval:
            report["failed"].append({"title": item["title"], "reason": "Story not rights+copy approved"})
            continue
        try:
            if publish:
                signature = day.isoformat() + "|" + item["link"]
                state = read_json(STATE, {"posts": {}})
                existing = state.get("posts", {}).get(signature, {})
                enabled = [p for p in ("facebook", "instagram") if os.getenv("PUBLISH_" + p.upper(), "false").lower() == "true"]
                if all(p in existing for p in enabled):
                    report["published"].append({"title": item["title"], "result": existing})
                    continue
            pack = (campaign_func or create_campaign)(item, day, art_provider or os.getenv("ART_PROVIDER", "cover"),
                                                       outdir, approval=approval)
            report["prepared"].append({"title": item["title"], "poster": pack["poster"]})
            if publish:
                results = publish_pack(item, pack, day=day)
                report["published"].append({"title": item["title"], "result": results})
        except Exception as error:
            report["failed"].append({"title": item.get("title", ""), "reason": type(error).__name__ + ": " + str(error)[:250]})
    destination = Path(outdir) / day.isoformat() / "report.json"
    write_json(destination, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--publish", action="store_true", help="Publish only approved stories when env gates are enabled")
    parser.add_argument("--art-provider", choices=("cover", "comfyui"), default=None)
    parser.add_argument("--export-dir", help="Copy generated JPGs to Android Downloads with unique filenames")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 6:
        parser.error("--limit must be 1–6")
    summary = run(limit=args.limit, publish=args.publish, art_provider=args.art_provider)
    if args.export_dir:
        folder = Path(args.export_dir).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        saved = []
        for prepared in summary["prepared"]:
            source = Path(prepared["poster"])
            if source.is_file():
                name = source.parent.parent.name + "_" + source.parent.name + ".jpg"
                destination = folder / name
                shutil.copy2(source, destination)
                saved.append(str(destination))
        summary["exported_jpgs"] = saved
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)
