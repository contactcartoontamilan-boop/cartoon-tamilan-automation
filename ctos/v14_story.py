"""Source-faithful V14 story planning. Never fabricate plot from a title/URL."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image

from ctos.creative import clean_source


def normalize_script(text: str) -> str:
    """Preserve Tamil graphemes; normalize whitespace, not spelling or meaning."""
    if not isinstance(text, str):
        raise TypeError("Story script must be UTF-8 text")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def plan_story(script: str, scene_count: int = 8) -> dict:
    """Split ONLY the provided, editorially approved narration into scenes.

    This is not an AI plot writer. For story-specific shots, supply separate
    original/approved illustrations in scene_01..scene_N order.
    """
    text = normalize_script(script)
    words = text.split()
    if not 6 <= scene_count <= 12:
        raise ValueError("Use 6–12 scenes")
    if not 70 <= len(words) <= 340:
        raise ValueError(
            "Supply a reviewed 70–340 word Tamil narration for a 60–120s target; "
            "actual voice duration is validated separately."
        )
    scenes = []
    for index in range(scene_count):
        first = len(words) * index // scene_count
        last = len(words) * (index + 1) // scene_count
        line = " ".join(words[first:last])
        if not line:
            raise ValueError("Not enough narration for each scene")
        scenes.append({
            "scene": index + 1,
            "narration": line,
            "words": last - first,
            "visual": "Needs original approved illustration matching this passage",
        })
    return {
        "version": 14,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "scene_count": scene_count,
        "word_count": len(words),
        "source_faithful": True,
        "editorial_review_required": True,
        "scenes": scenes,
    }


def validate_scene_images(folder: str | Path, scene_count: int) -> list[Path]:
    """Require unique, original, text-free images; no repeated poster slideshow."""
    root = Path(folder).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Scene image directory missing: {root}")
    paths = []
    hashes = set()
    for i in range(1, scene_count + 1):
        matches = [
            p for ext in ("png", "jpg", "jpeg", "webp")
            for p in [root / f"scene_{i:02d}.{ext}"] if p.is_file()
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one scene_{i:02d}.png/jpg/jpeg/webp")
        path = matches[0].resolve()
        if not path.is_relative_to(root):
            raise ValueError("Scene artwork must stay inside the approved art folder")
        clean_source(path)
        with Image.open(path) as image:
            if image.width < 512 or image.height < 512:
                raise ValueError(f"Scene {i} artwork is too small (<512px)")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError(f"Scene {i} repeats identical artwork; supply a new shot")
        hashes.add(digest)
        paths.append(path)
    return paths


def save_plan(plan: dict, destination: str | Path) -> Path:
    out = Path(destination)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return out
