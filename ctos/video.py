"""Video, speech and subtitles from original approved assets.

Static-art motion Reel != generative animated video. Premium AI animation uses
a separate GPU/API backend, not available on Oracle ARM64 by default.
"""
import shutil
from pathlib import Path

from v12_media import make_reel
from v12_voice import synthesize, srt_from_script


def create_short(poster, outdir, script=None, language="ta", seconds=12,
                 voice_rights=False, use_tts=False, make_mp4=True):
    folder = Path(outdir)
    folder.mkdir(parents=True, exist_ok=True)
    result = {"video": None, "voiceover": None, "subtitles": None,
              "type": "static_original_art_teaser", "requires_review": True}
    audio = None
    if script:
        sub = srt_from_script(script, folder / "subtitles.srt", duration=seconds)
        result["subtitles"] = str(sub)
        if use_tts:
            audio = synthesize(script, folder / "narration.wav",
                               lang=language, rights_confirmed=voice_rights)
            result["voiceover"] = str(audio)
    if make_mp4:
        video = make_reel(poster, folder / "teaser.mp4", seconds=seconds,
                          voiceover=str(audio) if audio else None,
                          voice_rights_confirmed=bool(audio and voice_rights))
        result["video"] = str(video)
    return result
