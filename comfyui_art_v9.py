"""Optional ORIGINAL AI illustrations through your own local ComfyUI.

This is a real ComfyUI HTTP client, not a placeholder image generator.
Requires a running local ComfyUI with a licensed checkpoint installed.
Only uses loopback ComfyUI by default to avoid leaking local API access.
"""
import copy
import json
import os
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image

def base_url():
    base = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
    parts = urlsplit(base)
    if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("COMFYUI_URL must point to a local HTTP loopback service")
    return base

def check_connection(session=None, timeout=5):
    """Check actual local ComfyUI health before attempting AI generation."""
    http = session or requests
    endpoint = base_url() + "/system_stats"
    try:
        response = http.get(endpoint, timeout=timeout)
        response.raise_for_status()
        info = response.json()
    except requests.ConnectionError as exc:
        raise RuntimeError(
            "COMFYUI_OFFLINE: No ComfyUI server listening on " + base_url()
            + ". On Termux, 127.0.0.1 means your Android phone, NOT the Oracle server. "
            "Start ComfyUI on the same machine or use an authorized SSH tunnel. "
            "Until then use --art-mode cover."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            "COMFYUI_UNAVAILABLE: " + str(exc)[:220]
            + ". Check local ComfyUI startup, network and port 8188."
        ) from exc
    if not isinstance(info, dict):
        raise RuntimeError("Unexpected ComfyUI system_stats response")
    return info


def load_workflow(workflow_path, prompt, checkpoint=None, seed=None):
    workflow = copy.deepcopy(json.loads(Path(workflow_path).read_text(encoding="utf-8")))
    positive = os.getenv("COMFYUI_PROMPT_NODE", "6")
    if positive not in workflow or "text" not in workflow[positive].get("inputs", {}):
        raise ValueError("Prompt node missing. Set COMFYUI_PROMPT_NODE to a CLIPTextEncode node")
    workflow[positive]["inputs"]["text"] = prompt
    if checkpoint:
        loader = os.getenv("COMFYUI_CHECKPOINT_NODE", "4")
        if loader not in workflow or "ckpt_name" not in workflow[loader].get("inputs", {}):
            raise ValueError("Checkpoint loader node missing")
        workflow[loader]["inputs"]["ckpt_name"] = checkpoint
    if seed is not None:
        sampler = os.getenv("COMFYUI_SAMPLER_NODE", "3")
        if sampler not in workflow or "seed" not in workflow[sampler].get("inputs", {}):
            raise ValueError("Sampler node missing")
        workflow[sampler]["inputs"]["seed"] = int(seed)
    return workflow

def generate(prompt, destination, workflow_path=None, timeout=600, session=None, *, seed=None):
    workflow_path = workflow_path or os.getenv("COMFYUI_WORKFLOW", "workflows/story_txt2img_api.json")
    checkpoint = os.getenv("COMFYUI_CHECKPOINT") or None
    seed = int(seed if seed is not None else os.getenv("COMFYUI_SEED", "20261112"))
    workflow = load_workflow(workflow_path, prompt, checkpoint=checkpoint, seed=seed)
    http = session or requests
    root = base_url()
    try:
        response = http.post(root + "/prompt", json={"prompt": workflow}, timeout=40)
        response.raise_for_status()
    except requests.ConnectionError as exc:
        raise RuntimeError(
            "COMFYUI_OFFLINE: Cannot reach " + root
            + ". ComfyUI must be running on this machine or reachable through "
            "a secure SSH tunnel. On Termux, 127.0.0.1 is the Android phone. "
            "Run: python comfyui_art_v9.py --check. "
            "Use --art-mode cover until the AI server is ready."
        ) from exc
    payload = response.json()
    if not payload.get("prompt_id"):
        raise RuntimeError("ComfyUI rejected workflow: " + str(payload.get("error") or payload.get("node_errors") or "no prompt ID")[:250])
    prompt_id = payload["prompt_id"]
    deadline = time.monotonic() + timeout
    images = []
    while time.monotonic() < deadline:
        result = http.get(root + "/history/" + prompt_id, timeout=30)
        result.raise_for_status()
        history = result.json().get(prompt_id, {})
        if history:
            status = history.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError("ComfyUI generation failed: " + str(status)[:300])
            for node in history.get("outputs", {}).values():
                images += node.get("images", [])
            if images:
                break
            raise RuntimeError("ComfyUI finished but returned no images; ensure SaveImage is present")
        time.sleep(3)
    if not images:
        raise TimeoutError("ComfyUI image generation timed out")
    selected = images[0]
    response = http.get(root + "/view", params={
        "filename": selected["filename"],
        "subfolder": selected.get("subfolder", ""),
        "type": selected.get("type", "output")}, timeout=45)
    response.raise_for_status()
    if len(response.content) > 18 * 1024 * 1024:
        raise ValueError("ComfyUI image exceeds maximum size")
    with Image.open(BytesIO(response.content)) as file:
        image = file.convert("RGB")
        if min(image.size) < 256:
            raise ValueError("ComfyUI image too small")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, "PNG")
    return destination

def story_prompt(title, style="anime"):
    if style not in ("anime", "cinematic_3d"):
        raise ValueError("Unsupported artwork style")
    look = ("polished original anime key visual, intricate hand painted illustration"
            if style == "anime" else "polished original cinematic stylized 3D-render look")
    return (f"{look}, vibrant fantasy-inspired novel marketing artwork for a story titled {title!r}; "
            "dynamic luminous lighting, layered depth, expressive original character designs, "
            "intricate worldbuilding ambience, dramatic color and particles, portrait key art. "
            "Marketing interpretation only; do not imply unverified plot or character details. "
            "No lettering, no words, no logos, no watermarks, no existing franchise characters.")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--title")
    p.add_argument("--check", action="store_true", help="Check whether local ComfyUI is running")
    p.add_argument("--style", choices=["anime", "cinematic_3d"], default="anime")
    p.add_argument("--out", default="output/comfy_art.png")
    a = p.parse_args()
    if a.check:
        try:
            result = check_connection()
            print("COMFYUI ONLINE: server reachable at", base_url())
            devices = result.get("devices", []) if isinstance(result, dict) else []
            print("Devices:", len(devices))
        except (RuntimeError, ValueError) as exc:
            p.exit(2, str(exc) + "\n")
    else:
        if not a.title:
            p.error("--title is required unless --check is used")
        try:
            print("Generated:", generate(story_prompt(a.title, a.style), a.out))
        except (RuntimeError, ValueError, TimeoutError) as exc:
            p.exit(2, str(exc) + "\n")
