"""Tamper-evident manual asset approval; state is local, not stored on GitHub."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from campaign_v9 import write_json, read_json

STATE = Path("data/ct_v13_approvals.json")


def sha_file(path):
    hash_value = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            hash_value.update(block)
    return hash_value.hexdigest()


def snapshot(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("story", {}).get("link"):
        raise ValueError("Invalid V13 review manifest")
    assets = data.get("assets", {})
    if "instagram_feed" not in assets:
        raise ValueError("Missing Instagram original artwork export")
    # file paths must be within this manifest's private bundle folder
    hashes = {}
    for name, relative in assets.items():
        path = (manifest_path.parent / relative).resolve()
        if not path.is_relative_to(manifest_path.parent):
            raise ValueError("Bundle contains an unsafe file path")
        hashes[name] = sha_file(path)
    return {
        "story_url": data["story"]["link"],
        "manifest_sha": sha_file(manifest_path),
        "media_sha": hashes,
    }


def approve(manifest, rights=False, copy=False, visual=False, state_path=STATE):
    if not all((rights, copy, visual)):
        raise PermissionError("Need separate explicit rights, copy and visual review confirmations")
    current = snapshot(manifest)
    state_path = Path(state_path)
    records = read_json(state_path, {})
    key = str(Path(manifest).resolve())
    records[key] = {
        **current, "rights_confirmed": True, "copy_reviewed": True,
        "visual_reviewed": True,
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "state": "approved",
    }
    write_json(state_path, records)
    os.chmod(state_path, 0o600)
    return records[key]


def require_approval(manifest, state_path=STATE):
    current = snapshot(manifest)
    records = read_json(state_path, {})
    status = records.get(str(Path(manifest).resolve()), {})
    if not (status.get("state") == "approved"
            and status.get("rights_confirmed") is True
            and status.get("copy_reviewed") is True
            and status.get("visual_reviewed") is True
            and status.get("manifest_sha") == current["manifest_sha"]
            and status.get("media_sha") == current["media_sha"]):
        raise PermissionError("Bundle unapproved or changed after review: recheck assets and reapprove")
    return status
