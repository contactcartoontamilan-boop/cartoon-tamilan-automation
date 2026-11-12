"""Deterministic quality checks; NOT OCR or automated visual-subject verification."""
from pathlib import Path
from PIL import Image
from ctos.creative import SIZES


def validate_assets(manifest_dir, assets):
    checks = {}
    all_ok = True
    for kind, relative in assets.items():
        if kind not in SIZES:
            checks[kind] = {"passed": False, "reason": "unknown format"}
            all_ok = False
            continue
        path = (Path(manifest_dir) / relative).resolve()
        if not path.is_relative_to(Path(manifest_dir).resolve()):
            raise ValueError("Unsafe media path")
        with Image.open(path) as opened:
            size_ok = opened.format == "JPEG" and opened.size == SIZES[kind]
        checks[kind] = {"passed": size_ok, "size": list(SIZES[kind])}
        all_ok = all_ok and size_ok
    return {
        "passed": all_ok and len(checks) > 0, "files": checks,
        "requires_human_review": [
            "Check visible artwork for any existing printed title, stock logo or watermark.",
            "Check character fidelity against approved story bible.",
            "Check on-device Tamil shaping, crop, contrast and CTA.",
            "Confirm source artwork rights for derivative/platform use.",
        ],
        "not_measured": "No computer vision/OCR semantic correctness guarantee",
    }
