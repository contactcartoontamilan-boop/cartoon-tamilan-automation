"""Sync discovered original stories into review approvals without posting.

The user must confirm rights to every cover / generated-art model and review
Tamil + English story summaries BEFORE enabling recurring posts.
"""
import argparse
import json
from pathlib import Path
from auto_story_marketing import discover
from campaign_v9 import APPROVALS, read_json, write_json


def sync_approvals(stories=None, path=APPROVALS):
    stories = stories if stories is not None else discover(limit=30)
    existing = read_json(path, {})
    for item in stories:
        url = item["link"]
        if url not in existing:
            title = item["title"]
            existing[url] = {
                "title": title,
                "rights_confirmed": False,
                "copy_reviewed": False,
                "intro_ta": f"📚 {title} — CartoonTamilan-ல் இந்தக் கதையைப் படித்து உங்கள் கருத்தைப் பகிருங்கள்.",
                "intro_en": f"📚 Discover {title} on CartoonTamilan. Read the story and share your thoughts.",
                "genres": []
            }
    write_json(path, existing)
    return existing


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(APPROVALS))
    args = p.parse_args()
    approval_file = Path(args.out)
    records = sync_approvals(path=approval_file)
    print("Approval records:", len(records))
    print("File:", approval_file)
    print("Approve only the story covers you own/license. Verify Tamil & English descriptions.")
    print("To enable a story after review, change rights_confirmed and copy_reviewed to true.")
