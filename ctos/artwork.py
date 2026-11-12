"""Own-story artwork provider adapter; never pretends textless cover is AI art."""
from pathlib import Path

from campaign_v9 import read_json
from story_bible_v10 import BIBLES, validate_bible, scene_prompt
from ctos.creative import clean_source


def get_art(story_url, raw_cover=None, backend="cover", style="anime", output=None):
    """Return verified source file and provenance metadata; no false 3D model claims.

    For ComfyUI, an installed real model/workflow + reachable local endpoint is
    required; the returned 3D *style* is a still illustration, not a 3D mesh.
    """
    if style not in ("anime", "cinematic_3d"):
        raise ValueError("Style must be anime or cinematic_3d")
    bibles = read_json(BIBLES, {})
    bible = bibles.get(story_url, {})
    verified = validate_bible(bible)
    if backend == "cover":
        if raw_cover is None:
            raise ValueError("Raw source artwork from existing story is required")
        return {
            "path": str(clean_source(raw_cover)), "backend": "existing_story_cover",
            "generated": False, "verified_character_canon": verified,
            "source_may_have_baked_text": True,
        }
    if backend != "comfyui":
        raise ValueError("Unconfigured image generator backend. Supported: cover, comfyui")
    if not verified:
        raise PermissionError("Approve the story character bible before automatic character art")
    if not output:
        raise ValueError("Output file is required for generated art")
    prompt = scene_prompt(bible.get("title", ""), bible, style=style)
    from comfyui_art_v9 import generate
    result = generate(prompt, output)
    source = clean_source(result)
    return {
        "path": str(source), "backend": "local_comfyui",
        "generated": True, "style": style, "verified_character_canon": True,
        "source_may_have_baked_text": False,
        "prompt": prompt,
    }
