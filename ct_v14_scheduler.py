#!/usr/bin/env python3
"""Oracle cron worker for automatically scheduled V14 Instagram/Facebook drafts.

When CT_V14_AUTO_SCHEDULE_QUEUE=true, discovers unpublished stories in the
queue and adds Instagram + Facebook jobs on daily Asia/Kolkata slots. The
publisher runs automated content and media checks before publishing.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, time as wall_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ct_v14_social_publish import CONFIRMATION, load_drafts, run
from v12_story_reader import owned_story_url

SCHEDULE = Path("data/v14_scheduled_posts.json")
STATE = Path("data/v14_scheduler.sqlite3")
ALLOWED = {"instagram", "facebook"}
IST = ZoneInfo("Asia/Kolkata")


def read_jobs(path: Path = SCHEDULE) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("published") is not False:
        raise ValueError("Schedule must be an unpublished JSON object")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("Schedule jobs must be a list")
    seen = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("Each scheduled job must be an object")
        job_id = job.get("id")
        platform = job.get("platform")
        story_url = job.get("story_url")
        scheduled_at = job.get("scheduled_at")
        if not isinstance(job_id, str) or not job_id.strip() or job_id in seen:
            raise ValueError("Each job needs a unique non-empty id")
        seen.add(job_id)
        if platform not in ALLOWED:
            raise ValueError("Only Instagram and Facebook are supported")
        if not owned_story_url(story_url):
            raise ValueError("Scheduled story must be an owned CartoonTamilan URL")
        if job.get("published") is not False:
            raise ValueError("Schedule entries must begin unpublished")
        try:
            dt = datetime.fromisoformat(scheduled_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("scheduled_at must be an ISO timestamp with timezone") from exc
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone offset")
    return jobs


def _next_daily_slot(after: datetime) -> datetime:
    local = after.astimezone(IST)
    candidate = datetime.combine(local.date(), wall_time(hour=9), tzinfo=IST)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


def sync_queue(outdir: str, schedule_path: Path = SCHEDULE) -> dict:
    """Append eligible unpublished IG+FB queue stories to daily schedule."""
    if os.getenv("CT_V14_AUTO_SCHEDULE_QUEUE", "").lower() != "true":
        return {"enabled": False, "added": 0}
    queue_path = Path(outdir) / "social_queue.json"
    if not queue_path.is_file():
        return {"enabled": True, "added": 0, "status": "queue_not_ready"}

    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    if (not isinstance(queue, dict) or queue.get("published") is not False
            or queue.get("live_publishing") is not False
            or not isinstance(queue.get("image_post_queue"), list)):
        raise ValueError("Only an unpublished V14 queue is accepted")

    if schedule_path.exists():
        jobs = read_jobs(schedule_path)
        payload = json.loads(schedule_path.read_text(encoding="utf-8"))
    else:
        jobs = []
        payload = {"version": 14, "published": False, "jobs": []}
    existing = {job["id"] for job in jobs}

    grouped = {}
    for draft in queue["image_post_queue"]:
        platform, url = draft.get("platform"), draft.get("story_url")
        if platform in ALLOWED and owned_story_url(url):
            grouped.setdefault(url, set()).add(platform)

    last_slot = max(
        (datetime.fromisoformat(j["scheduled_at"]).astimezone(IST) for j in jobs),
        default=None,
    )
    slot = _next_daily_slot(last_slot or datetime.now(IST))
    added = 0
    for story_url in grouped:
        if not ALLOWED.issubset(grouped[story_url]):
            continue
        try:
            items = {
                platform: load_drafts(outdir, platform=platform, story_url=story_url)[0]
                for platform in ("instagram", "facebook")
            }
        except (PermissionError, ValueError, FileNotFoundError):
            # Invalid queue items are skipped; there is no manual approval gate.
            continue

        new_jobs = []
        for platform in ("instagram", "facebook"):
            draft = items[platform]
            job_id = "v14-" + platform + "-" + draft["id"]
            if job_id not in existing:
                new_jobs.append({
                    "id": job_id,
                    "platform": platform,
                    "story_url": story_url,
                    "scheduled_at": slot.isoformat(),
                    "published": False,
                    "source_draft_id": draft["id"],
                })
        if new_jobs:
            jobs.extend(new_jobs)
            existing.update(job["id"] for job in new_jobs)
            added += len(new_jobs)
            slot += timedelta(days=1)

    payload["jobs"] = jobs
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    temp = schedule_path.with_suffix(schedule_path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(schedule_path)
    return {"enabled": True, "added": added, "scheduled_jobs": len(jobs)}


def init_state(path: Path = STATE) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute("""CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY, status TEXT NOT NULL,
        updated_at TEXT NOT NULL, detail TEXT
    )""")
    db.commit()
    return db


def process_due(outdir: str, schedule_path: Path = SCHEDULE,
                state_path: Path = STATE) -> dict:
    sync = sync_queue(outdir, schedule_path)
    if not schedule_path.exists():
        return {"checked_at": datetime.now(timezone.utc).isoformat(),
                "auto_schedule": sync, "results": [],
                "live_enabled_only_by_explicit_env_gates": True}
    jobs = read_jobs(schedule_path)
    now = datetime.now(timezone.utc)
    db = init_state(state_path)
    results = []
    try:
        for job in jobs:
            due = datetime.fromisoformat(job["scheduled_at"]).astimezone(timezone.utc)
            if due > now:
                continue
            row = db.execute("SELECT status FROM jobs WHERE job_id=?", (job["id"],)).fetchone()
            if row:
                results.append({"id": job["id"], "status": row[0]})
                continue
            try:
                result = run(outdir, platform=job["platform"],
                             story_url=job["story_url"], live=True,
                             confirm=CONFIRMATION)
                statuses = [item.get("status") for item in result.get("results", [])]
                status = ("published" if result.get("status") == "completed"
                          and statuses and all(s == "published" for s in statuses)
                          else "needs_reconciliation")
                detail = json.dumps(result, ensure_ascii=False)
            except Exception as exc:
                # Failed preflights can be retried after configuration is fixed.
                if type(exc).__name__ in {"PermissionError", "ValueError", "FileNotFoundError"}:
                    results.append({"id": job["id"], "status": "blocked",
                                    "error_type": type(exc).__name__, "message": str(exc)})
                    continue
                # An unknown error may have reached Meta; never auto-retry it.
                status = "needs_reconciliation"
                detail = type(exc).__name__
            db.execute("INSERT INTO jobs VALUES (?,?,?,?)",
                       (job["id"], status, datetime.now(timezone.utc).isoformat(), detail))
            db.commit()
            results.append({"id": job["id"], "status": status})
    finally:
        db.close()
    return {"checked_at": now.isoformat(), "auto_schedule": sync, "results": results,
            "live_enabled_only_by_explicit_env_gates": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Process automatically scheduled V14 FB/IG jobs")
    parser.add_argument("--outdir", default="output/v14/image_posts")
    parser.add_argument("--schedule", type=Path, default=SCHEDULE)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--poll-seconds", type=int, default=60,
                        help="Use 0 for a single check; otherwise keep polling")
    args = parser.parse_args()
    if args.poll_seconds < 0:
        parser.error("--poll-seconds must be >= 0")
    while True:
        result = process_due(args.outdir, args.schedule, args.state)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.poll_seconds == 0:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
