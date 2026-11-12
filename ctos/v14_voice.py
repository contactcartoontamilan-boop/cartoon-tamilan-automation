"""Opt-in natural Tamil female neural voice; never silently use robotic eSpeak.

Azure Speech is an optional PAID external service. Requires owner credentials,
approved script and human listening review. No voice cloning is performed.
"""
from __future__ import annotations

import os
import re
import tempfile
import wave
from pathlib import Path
from xml.sax.saxutils import escape

import requests

VOICE = "ta-IN-PallaviNeural"
RATE = "-8%"
PITCH = "-2st"


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            raise ValueError("Expected 16-bit mono PCM WAV")
        if audio.getframerate() != 24000:
            raise ValueError("Expected 24000 Hz WAV from neural voice provider")
        if not audio.getnframes():
            raise ValueError("WAV is empty")
        return audio.getnframes() / audio.getframerate()


def azure_tamil_female(text: str, destination: str | Path, *,
                       rights_confirmed: bool = False,
                       region: str | None = None,
                       subscription_key: str | None = None) -> Path:
    """Synthesize ONE reviewed Tamil scene using an explicit female neural voice."""
    if not rights_confirmed:
        raise PermissionError("Confirm narration/script rights before sending to TTS")
    if not 5 <= len(text.strip()) <= 3000:
        raise ValueError("Supply a 5–3000 character reviewed narration segment")
    region = region or os.environ.get("AZURE_SPEECH_REGION", "")
    subscription_key = subscription_key or os.environ.get("AZURE_SPEECH_KEY", "")
    if not re.fullmatch(r"[a-z0-9-]{2,40}", region):
        raise RuntimeError("Set valid AZURE_SPEECH_REGION")
    if not subscription_key:
        raise RuntimeError("Set private AZURE_SPEECH_KEY; no local female neural model configured")
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xml:lang="ta-IN">'
        f'<voice name="{VOICE}"><prosody rate="{RATE}" pitch="{PITCH}">'
        f"{escape(text.strip())}</prosody></voice></speak>"
    )
    endpoint = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    response = requests.post(
        endpoint, data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "CartoonTamilan-V14-Preview",
        },
        timeout=(10, 90),
    )
    if response.status_code != 200:
        # Never print API keys, request headers or the private script.
        raise RuntimeError(f"Neural TTS HTTP {response.status_code}; check region, quota and voice")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".wav",
                                         delete=False) as temp:
            temp_name = Path(temp.name)
            temp.write(response.content)
        wav_duration(temp_name)
        temp_name.replace(target)
    finally:
        if temp_name and temp_name.exists():
            temp_name.unlink()
    return target


def concatenate_wav(files: list[Path], destination: str | Path,
                    pause_ms: int = 250) -> tuple[Path, list[float]]:
    """Merge equal-format PCM clips, returning exact per-scene SRT durations."""
    if not files or not 0 <= pause_ms <= 1500:
        raise ValueError("Need WAV clips and a valid pause duration")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    durations = []
    with wave.open(str(target), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        for index, file in enumerate(files):
            with wave.open(str(file), "rb") as clip:
                if (clip.getnchannels(), clip.getsampwidth(),
                        clip.getframerate(), clip.getcomptype()) != (1, 2, 24000, "NONE"):
                    raise ValueError("WAV format mismatch: expected 24kHz 16-bit mono PCM")
                frames = clip.readframes(clip.getnframes())
                duration = clip.getnframes() / 24000
                out.writeframes(frames)
            if index < len(files) - 1:
                silence_frames = round(24000 * pause_ms / 1000)
                out.writeframes(b"\x00\x00" * silence_frames)
                duration += silence_frames / 24000
            durations.append(duration)
    return target, durations
