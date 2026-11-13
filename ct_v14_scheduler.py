#!/usr/bin/env python3
"""Oracle cron worker for pre-approved V14 Instagram/Facebook drafts.

Reads data/v14_scheduled_posts.json and publishes only entries explicitly
approved for scheduling. All publisher rights, visual, credential, HTTPS-host,
per-platform opt-in, and duplicate-journal gates remain active.
Run once per minute from cron; no workflow or scheduler enables live posting.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from ct_v14_social_publish import CONFIRMATION, run
from v12_story_reader import owned_story_url

SCHEDULE = Path("data/v14_scheduled_posts.json")
STATE = Path("data/v14_scheduler.sqlite3")
ALLOWED = {"instagram", "facebook"}


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
        if job.get("approved_for_scheduling") is not True:
            raise ValueError("Each job needs explicit scheduling approval")
        if job.get("published") is not False:
            raise ValueError("Schedule entries must begin unpublished")
        try:
            dt = datetime.fromisoformat(scheduled_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("scheduled_at must be an ISO timestamp with timezone") from exc
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone offset")
    return jobs


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
                # A failed preflight may be retried after configuration is fixed.
                if type(exc).__name__ in {"PermissionError", "ValueError", "FileNotFoundError"}:
                    results.append({"id": job["id"], "status": "blocked",
                                    "error_type": type(exc).__name__,
                                    "message": str(exc)})
                    continue
                # Unknown errors after entering publisher may have reached Meta;
                # record and stop automatic retries to prevent duplicate posts.
                status = "needs_reconciliation"
                detail = type(exc).__name__
            db.execute("INSERT INTO jobs VALUES (?,?,?,?)",
                       (job["id"], status, datetime.now(timezone.utc).isoformat(), detail))
            db.commit()
            results.append({"id": job["id"], "status": status})
    finally:
        db.close()
    return {"checked_at": now.isoformat(), "results": results,
            "live_enabled_only_by_explicit_env_gates": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Process due, approved V14 FB/IG jobs")
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
