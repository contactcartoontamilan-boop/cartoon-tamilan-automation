"""Create private V10 publishing & original-art direction settings per story.

Default safe: every new field disabled, no Meta publishing and no false
character details. Existing story approvals/copy are preserved.
"""
import argparse
from pathlib import Path

from auto_story_marketing import discover
from campaign_v9 import APPROVALS, write_json
from story_approvals_v9 import sync_approvals

DEFAULTS = {
    "premium_theme": "royal",
    "verified_character_notes": "",
    "verified_world_notes": "",
    "v10_visual_policy_approved": False,
    "v10_automatic_ai_approved": False,
}


def initialize(stories=None, path=APPROVALS):
    found = discover(limit=30) if stories is None else stories
    records = sync_approvals(stories=found, path=path)
    for entry in records.values():
        for key, value in DEFAULTS.items():
            entry.setdefault(key, value)
    write_json(path, records)
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(APPROVALS))
    args = parser.parse_args()
    path = Path(args.out)
    result = initialize(path=path)
    print("Prepared", len(result), "original story records:", path)
    print("V10 is PREVIEW ONLY until you approve story rights, synopses and visual policy.")
    print("Available premium_theme values: royal, crimson, cosmic, emerald")
