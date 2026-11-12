"""Opt-in Tamil speech synthesis for reviewed, original scripts.

Azure's neural Tamil voice is optional and requires owner-supplied credentials.
The local espeak-ng fallback is intentionally labeled mechanical; it is NOT
advertised as a natural female voice. No speech is generated automatically.
"""
from __future__ import annotations

import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from v12_voice import synthesize as local_synthesize

REGION_PATTERN = re.compile(r"^[a-z0-9-]{2,40}$")
VOICE_PATTERN = re.compile(r"^[A-Za-z0-9-]{3,100}$")
RATE_PATTERN = re.compile(r"^[+-]?\d{1,2}%$")


def _azure_ssml(script: str, voice: str, rate: str) -> bytes:
    if not VOICE_PATTERN.fullmatch(voice):
        raise ValueError("Invalid Azure voice name")
    if not RATE_PATTERN.fullmatch(rate):
        raise ValueError("Speech rate must look like -5% or +5%")
    safe_text = escape(script)
    return (
        '<speak version="1.0" '
        'xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ta-IN">'
        f'<voice name="{voice}"><prosody rate="{rate}">'
        f"{safe_text}</prosody></voice></speak>"
    ).encode("utf-8")


def synthesize_tamil(script: str, destination, *, provider="azure",
                     rights_confirmed=False, voice=None, rate="-5%"):
    """Return a local WAV path, never publish it.

    provider='azure' needs CT_AZURE_SPEECH_KEY and CT_AZURE_SPEECH_REGION.
    provider='espeak' is offline but noticeably robotic.
    """
    if not rights_confirmed:
        raise PermissionError("Confirm rights to the complete narration script")
    if not isinstance(script, str) or not 20 <= len(script.strip()) <= 6000:
        raise ValueError("Narration must contain 20 to 6000 characters")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    if provider == "espeak":
        return local_synthesize(script, target, lang="ta", rights_confirmed=True)
    if provider != "azure":
        raise ValueError("Supported speech providers: azure, espeak")

    region = os.getenv("CT_AZURE_SPEECH_REGION", "").strip().lower()
    key = os.getenv("CT_AZURE_SPEECH_KEY", "").strip()
    if not key or not REGION_PATTERN.fullmatch(region):
        raise RuntimeError(
            "Azure Tamil TTS needs CT_AZURE_SPEECH_KEY and a valid "
            "CT_AZURE_SPEECH_REGION on Oracle; nothing was generated"
        )
    voice = voice or os.getenv("CT_AZURE_TTS_VOICE", "ta-IN-PallaviNeural")
    payload = _azure_ssml(script, voice, rate)
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    request = urllib.request.Request(
        url, data=payload, method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "CartoonTamilan-V14-Preview",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(24_000_000)
    except urllib.error.HTTPError as error:
        # Do not print headers, request objects, or credentials.
        raise RuntimeError(f"Azure speech HTTP {error.code}; check voice/region/quota") from None
    except urllib.error.URLError:
        raise RuntimeError("Azure speech unavailable; check network and region") from None

    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise RuntimeError("Azure speech did not return a valid WAV header")
    # Atomic output: failed requests must not leave a misleading WAV behind.
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".narration-", suffix=".wav", dir=target.parent, delete=False
        ) as temporary:
            temp_name = temporary.name
            temporary.write(data)
        os.replace(temp_name, target)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return target
