"""Optional CPU-friendly original Tamil/English narration and subtitle files.

Uses locally installed espeak-ng; its speech is mechanical and not comparable
to premium commercial dubbing. Only synthesize scripts you are authorized to use.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path


VOICES = {"ta": "ta", "en": "en-us"}


def synthesize(script, destination, lang="ta", rights_confirmed=False, executable=None):
    if not rights_confirmed:
        raise PermissionError("Narration script must be original or licensed")
    if lang not in VOICES:
        raise ValueError("Supported languages: ta and en")
    if not 5 <= len(script.strip()) <= 2500:
        raise ValueError("Narration must contain 5–2500 characters")
    binary = executable or shutil.which("espeak-ng")
    if not binary:
        raise RuntimeError("espeak-ng missing; install espeak-ng on Oracle to make WAV narration")
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "narration.txt"
        script_path.write_text(script, encoding="utf-8")
        command = [binary, "-v", VOICES[lang], "-s", "145",
                   "-f", str(script_path), "-w", str(output)]
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=120, check=False)
    if result.returncode != 0:
        raise RuntimeError("Voice synthesis failed; verify supported espeak-ng language")
    if not output.is_file() or output.stat().st_size < 100:
        raise RuntimeError("TTS returned no audio")
    return output


def _timestamp(seconds):
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def srt_from_script(script, output, duration=12):
    """Create external UTF-8 Tamil-friendly captions, not burned into MP4."""
    rows = [s.strip() for s in script.splitlines() if s.strip()]
    if not rows or len(rows) > 16 or not 4 <= duration <= 180:
        raise ValueError("Supply 1–16 reviewed caption lines and 4–180s duration")
    each = duration / len(rows)
    content = []
    for i, row in enumerate(rows):
        content.append(f"{i+1}\n{_timestamp(i*each)} --> {_timestamp((i+1)*each)}\n{row}\n")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return path
