"""Provider-backed image, short-video and voice generation for the AI studio.

All remote generation is opt-in. Set ENABLE_AI_MEDIA_API=true only after setting a
provider key, model, budget and reviewing content/use rights.
"""
from __future__ import annotations

import base64
import ipaddress
import os
import time
import wave
from pathlib import Path
from urllib.parse import urlparse

import requests

from ct_ai_router import AIConfigError, AIRequestError, _reserve_request


def _enabled() -> None:
    if os.getenv("ENABLE_AI_MEDIA_API", "false").strip().lower() not in {
        "1", "true", "yes", "on"
    }:
        raise AIConfigError(
            "Remote media generation is disabled. Set ENABLE_AI_MEDIA_API=true "
            "on the server after configuring its provider key and quotas."
        )


def _key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AIConfigError(f"Set {name} in the server's private environment.")
    return value


def _model(name: str, override: str | None) -> str:
    value = (override or os.getenv(name, "")).strip()
    if not value:
        raise AIConfigError(f"Set {name} to a model enabled for your provider account.")
    return value


def _json_request(method: str, url: str, *, key: str, payload: dict | None = None,
                  timeout: int = 90, key_header: str = "Authorization") -> dict:
    auth = ({"Authorization": f"Bearer {key}"} if key_header == "Authorization"
            else {key_header: key})
    try:
        response = requests.request(
            method, url,
            headers={**auth, "Content-Type": "application/json"},
            json=payload, timeout=timeout,
        )
    except requests.RequestException as exc:
        raise AIRequestError("Could not connect to the media provider.") from exc
    if not response.ok:
        raise AIRequestError(
            f"Media provider returned HTTP {response.status_code}; check key, "
            "model access, quota and request settings."
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise AIRequestError("Media provider returned invalid JSON.") from exc
    if not isinstance(body, dict):
        raise AIRequestError("Media provider returned an unexpected response.")
    return body


def _decode_to_file(encoded: str, destination: str | Path, *,
                    max_bytes: int = 40 * 1024 * 1024) -> Path:
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise AIRequestError("Provider returned invalid base64 media.") from exc
    if not data or len(data) > max_bytes:
        raise AIRequestError("Generated media is empty or exceeds the size limit.")
    return _write_bytes(data, destination)


def _write_bytes(data: bytes, destination: str | Path) -> Path:
    if not data:
        raise AIRequestError("Provider returned empty media.")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name("." + target.name + ".tmp")
    temp.write_bytes(data)
    temp.replace(target)
    return target


def _download_provider_url(url: str, destination: str | Path, *,
                           max_bytes: int) -> Path:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise AIRequestError("Provider returned a non-HTTPS media URL.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local):
        raise AIRequestError("Provider returned a non-public media URL.")
    if not ip and not (
        host == "x.ai" or host.endswith(".x.ai")
        or host.endswith(".openai.com")
        or host.endswith(".blob.core.windows.net")
    ):
        raise AIRequestError("Provider returned an unrecognized media host.")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name("." + target.name + ".tmp")
    size = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as response:
            if not response.ok:
                raise AIRequestError(
                    f"Media download returned HTTP {response.status_code}."
                )
            with temp.open("wb") as stream:
                for chunk in response.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise AIRequestError("Generated media exceeds the size limit.")
                    stream.write(chunk)
        if not size:
            raise AIRequestError("Provider returned an empty media file.")
        temp.replace(target)
    except requests.RequestException as exc:
        raise AIRequestError("Could not download generated media.") from exc
    finally:
        temp.unlink(missing_ok=True)
    return target


def generate_image(prompt: str, destination: str | Path, *,
                   provider: str = "xai", model: str | None = None,
                   aspect_ratio: str = "4:5", image_size: str = "1K",
                   rights_confirmed: bool = False) -> Path:
    """Generate and save one image with xAI, OpenAI or Gemini."""
    _enabled()
    if not rights_confirmed:
        raise PermissionError("Confirm rights to the prompt and references before generation.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be non-empty.")
    provider = provider.strip().lower()
    if provider == "xai":
        key = _key("XAI_API_KEY")
        selected = _model("XAI_IMAGE_MODEL", model)
        _reserve_request("xai")
        data = _json_request(
            "POST", "https://api.x.ai/v1/images/generations", key=key,
            payload={"model": selected, "prompt": prompt.strip(), "n": 1},
        )
        items = data.get("data") or []
        if items and isinstance(items[0], dict):
            item = items[0]
        else:
            request_id = data.get("request_id")
            if not request_id:
                raise AIRequestError("Image provider returned no image or request ID.")
            item = {}
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                item_data = _json_request(
                    "GET", f"https://api.x.ai/v1/images/{request_id}", key=key
                )
                status = item_data.get("status")
                if status == "failed" or item_data.get("error"):
                    raise AIRequestError("Image generation failed at the provider.")
                items = item_data.get("data") or []
                if status == "done" and items:
                    item = items[0]
                    break
                time.sleep(3)
            if not item:
                raise AIRequestError("Image generation timed out while waiting.")
        if item.get("b64_json"):
            return _decode_to_file(item["b64_json"], destination)
        if item.get("url"):
            return _download_provider_url(item["url"], destination, max_bytes=40 * 1024 * 1024)
        raise AIRequestError("Provider returned no downloadable image.")

    if provider == "openai":
        key = _key("OPENAI_API_KEY")
        selected = _model("OPENAI_IMAGE_MODEL", model)
        _reserve_request("openai")
        data = _json_request(
            "POST", "https://api.openai.com/v1/images/generations", key=key,
            payload={"model": selected, "prompt": prompt.strip(), "size": "1024x1024"},
            timeout=180,
        )
        items = data.get("data") or []
        if not items:
            raise AIRequestError("OpenAI returned no generated image.")
        item = items[0]
        if item.get("b64_json"):
            return _decode_to_file(item["b64_json"], destination)
        if item.get("url"):
            return _download_provider_url(item["url"], destination, max_bytes=40 * 1024 * 1024)
        raise AIRequestError("OpenAI returned no downloadable image.")

    if provider == "gemini":
        key = _key("GEMINI_API_KEY")
        selected = _model("GEMINI_IMAGE_MODEL", model)
        _reserve_request("gemini")
        data = _json_request(
            "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{selected}:generateContent",
            key=key,
            payload={
                "contents": [{"parts": [{"text": prompt.strip()}]}],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "imageConfig": {"aspectRatio": aspect_ratio, "imageSize": image_size},
                },
            },
            timeout=180, key_header="x-goog-api-key",
        )
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data") or {}
                if inline.get("data"):
                    return _decode_to_file(inline["data"], destination)
        raise AIRequestError("Gemini returned no image data.")
    raise AIConfigError("Image provider must be xai, openai, or gemini.")


def generate_video(prompt: str, destination: str | Path, *,
                   provider: str = "xai", model: str | None = None,
                   duration_seconds: int = 6, poll_seconds: int = 5,
                   timeout_seconds: int = 900,
                   rights_confirmed: bool = False) -> Path:
    """Generate a short AI video and download it; xAI generation is asynchronous."""
    _enabled()
    if not rights_confirmed:
        raise PermissionError("Confirm rights to the prompt and references before generation.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be non-empty.")
    if provider.strip().lower() != "xai":
        raise AIConfigError(
            "Video generation currently supports xAI only; Gemini/OpenAI video "
            "adapters are not enabled in this build."
        )
    if not 1 <= int(duration_seconds) <= 15:
        raise ValueError("duration_seconds must be between 1 and 15.")
    key = _key("XAI_API_KEY")
    selected = _model("XAI_VIDEO_MODEL", model)
    _reserve_request("xai")
    started = _json_request(
        "POST", "https://api.x.ai/v1/videos/generations", key=key,
        payload={
            "model": selected, "prompt": prompt.strip(),
            "duration": int(duration_seconds),
        },
    )
    request_id = started.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise AIRequestError("Video provider returned no request ID.")
    deadline = time.monotonic() + max(30, min(int(timeout_seconds), 1800))
    while time.monotonic() < deadline:
        status_data = _json_request(
            "GET", f"https://api.x.ai/v1/videos/{request_id}", key=key, timeout=60
        )
        status = status_data.get("status")
        if status == "failed" or status_data.get("error"):
            raise AIRequestError("Video generation failed at the provider.")
        video = status_data.get("video") or {}
        url = video.get("url")
        if status == "done" and isinstance(url, str) and url:
            return _download_provider_url(
                url, destination, max_bytes=250 * 1024 * 1024
            )
        time.sleep(max(2, min(int(poll_seconds), 30)))
    raise AIRequestError("Video generation timed out while waiting.")


def _write_pcm_wav(pcm: bytes, destination: str | Path,
                   sample_rate: int = 24000) -> Path:
    if not pcm or len(pcm) > 100 * 1024 * 1024:
        raise AIRequestError("Generated speech is empty or too large.")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name("." + target.name + ".tmp")
    with wave.open(str(temp), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    temp.replace(target)
    return target


def generate_voice(text: str, destination: str | Path, *,
                   provider: str = "xai", model: str | None = None,
                   voice: str | None = None, language: str = "ta-IN",
                   style: str = "",
                   rights_confirmed: bool = False) -> Path:
    """Generate narrated audio using xAI, OpenAI, Gemini, or existing Azure Tamil TTS."""
    _enabled()
    if not rights_confirmed:
        raise PermissionError("Confirm rights to the narration text before generation.")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 60000:
        raise ValueError("text must be between 1 and 60,000 characters.")
    provider = provider.strip().lower()
    target = Path(destination)

    if provider == "azure":
        from ctos.v14_voice import azure_tamil_female
        return azure_tamil_female(
            text, target, rights_confirmed=True,
            region=os.getenv("AZURE_SPEECH_REGION"),
            subscription_key=os.getenv("AZURE_SPEECH_KEY"),
        )

    if provider == "xai":
        key = _key("XAI_API_KEY")
        _reserve_request("xai")
        try:
            response = requests.post(
                "https://api.x.ai/v1/tts",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={
                    "text": text.strip(),
                    "voice_id": voice or os.getenv("XAI_TTS_VOICE", "eve"),
                    "language": language,
                    "output_format": {"codec": "mp3", "sample_rate": 24000,
                                      "bit_rate": 128000},
                },
                timeout=(10, 900),
            )
        except requests.RequestException as exc:
            raise AIRequestError("Could not connect to xAI speech service.") from exc
        if not response.ok:
            raise AIRequestError(f"xAI speech returned HTTP {response.status_code}.")
        return _write_bytes(response.content, target)

    if provider == "openai":
        key = _key("OPENAI_API_KEY")
        selected = _model("OPENAI_TTS_MODEL", model)
        _reserve_request("openai")
        try:
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": selected,
                    "input": text.strip(),
                    "voice": voice or os.getenv("OPENAI_TTS_VOICE", "coral"),
                    "response_format": "mp3",
                    **({"instructions": style} if style else {}),
                },
                timeout=(10, 900),
            )
        except requests.RequestException as exc:
            raise AIRequestError("Could not connect to OpenAI speech service.") from exc
        if not response.ok:
            raise AIRequestError(f"OpenAI speech returned HTTP {response.status_code}.")
        return _write_bytes(response.content, target)

    if provider == "gemini":
        key = _key("GEMINI_API_KEY")
        selected = _model("GEMINI_TTS_MODEL", model)
        _reserve_request("gemini")
        instruction = f"{style.strip()} Read the following text aloud: " if style else "Read the following text aloud: "
        data = _json_request(
            "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{selected}:generateContent",
            key=key,
            payload={
                "contents": [{"parts": [{"text": instruction + text.strip()}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice or os.getenv("GEMINI_TTS_VOICE", "Kore")
                            }
                        }
                    },
                },
            },
            timeout=900, key_header="x-goog-api-key",
        )
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data") or {}
                encoded = inline.get("data")
                if encoded:
                    try:
                        audio = base64.b64decode(encoded, validate=True)
                    except ValueError as exc:
                        raise AIRequestError("Gemini returned invalid speech data.") from exc
                    mime = (inline.get("mimeType") or inline.get("mime_type") or "").lower()
                    if mime.endswith("wav"):
                        return _write_bytes(audio, target)
                    if "pcm" in mime or "l16" in mime or not mime:
                        return _write_pcm_wav(audio, target)
                    return _write_bytes(audio, target)
        raise AIRequestError("Gemini returned no audio data.")
    raise AIConfigError("Voice provider must be xai, openai, gemini, or azure.")


__all__ = ["generate_image", "generate_video", "generate_voice"]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate image, short video or voice media")
    sub = parser.add_subparsers(dest="kind", required=True)
    for kind in ("image", "video", "voice"):
        command = sub.add_parser(kind)
        command.add_argument("--provider", default="xai")
        command.add_argument("--input", required=True, help="Prompt for image/video, script for voice")
        command.add_argument("--out", required=True, help="Output media file path")
        command.add_argument("--model")
        command.add_argument("--rights-confirmed", action="store_true")
        if kind == "video":
            command.add_argument("--duration", type=int, default=6)
        if kind == "voice":
            command.add_argument("--voice")
            command.add_argument("--language", default="ta-IN")
    args = parser.parse_args()
    if args.kind == "image":
        result = generate_image(args.input, args.out, provider=args.provider,
                                model=args.model, rights_confirmed=args.rights_confirmed)
    elif args.kind == "video":
        result = generate_video(args.input, args.out, provider=args.provider,
                                model=args.model, duration_seconds=args.duration,
                                rights_confirmed=args.rights_confirmed)
    else:
        result = generate_voice(args.input, args.out, provider=args.provider,
                                model=args.model, voice=args.voice,
                                language=args.language,
                                rights_confirmed=args.rights_confirmed)
    print(result)
