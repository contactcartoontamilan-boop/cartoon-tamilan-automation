"""Offline V14 regression tests: no cloud, FFmpeg rendering or live posting."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ctos.story_video_v14 import (
    read_storyboard, scene_frame_counts, write_estimated_srt, build_full_story,
)
from ctos.voice_v14 import _azure_ssml, synthesize_tamil


class StoryVideoV14Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.scenes = []
        for n in range(8):
            image = self.folder / f"scene_{n}.png"
            Image.new("RGB", (80, 100), (n * 20, 40, 100)).save(image)
            self.scenes.append({
                "image": image.name,
                "narration": f"இது எங்கள் அசல் தமிழ் கதையின் காட்சி {n + 1}. "
                             "இந்த இடத்தில் கதையின் முக்கியமான நிகழ்வு நடைபெறுகிறது.",
            })
        self.storyboard = self.folder / "storyboard.json"
        self._write()

    def _write(self):
        self.storyboard.write_text(
            json.dumps({"title": "Original story", "scenes": self.scenes},
                       ensure_ascii=False), encoding="utf-8",
        )

    def test_distinct_scenes_and_90_second_frame_budget(self):
        _, scenes = read_storyboard(self.storyboard)
        frames = scene_frame_counts(scenes, 90.0)
        self.assertEqual(len(frames), 8)
        self.assertEqual(sum(frames), 90 * 24)
        self.assertTrue(all(frame >= 48 for frame in frames))
        srt = write_estimated_srt(scenes, frames, self.folder / "subtitles.srt")
        text = srt.read_text(encoding="utf-8")
        self.assertIn("00:01:30,000", text)
        self.assertIn("தமிழ்", text)

    def test_duplicate_image_is_rejected(self):
        self.scenes[1]["image"] = self.scenes[0]["image"]
        self._write()
        with self.assertRaisesRegex(ValueError, "reuses identical artwork"):
            read_storyboard(self.storyboard)

    def test_duration_mismatch_is_rejected(self):
        for scene in self.scenes:
            scene["duration_seconds"] = 5
        self._write()
        _, scenes = read_storyboard(self.storyboard)
        with self.assertRaisesRegex(ValueError, "differ"):
            scene_frame_counts(scenes, 90.0)

    def test_short_audio_is_rejected(self):
        _, scenes = read_storyboard(self.storyboard)
        with self.assertRaisesRegex(ValueError, "60–120"):
            scene_frame_counts(scenes, 12.0)

    def test_rights_gate_precedes_external_tools(self):
        with self.assertRaises(PermissionError):
            build_full_story(self.storyboard, self.folder / "out",
                             tts="azure", rights_confirmed=False)

    def test_azure_ssml_escapes_text_and_validates_voice(self):
        xml = _azure_ssml("தமிழ் & <அசல்>", "ta-IN-PallaviNeural", "-5%")
        self.assertIn(b"&amp;", xml)
        self.assertIn(b"&lt;", xml)
        with self.assertRaises(ValueError):
            _azure_ssml("Hello", 'bad"voice', "-5%")

    def test_azure_needs_private_credentials(self):
        with patch.dict(os.environ, {
            "CT_AZURE_SPEECH_KEY": "",
            "CT_AZURE_SPEECH_REGION": "",
        }):
            with self.assertRaisesRegex(RuntimeError, "needs"):
                synthesize_tamil(
                    "இது ஒரு புதிய தமிழ் அசல் கதை. "
                    "இது சோதனைக்கான நீளமான உரை.",
                    self.folder / "voice.wav", rights_confirmed=True,
                )
        self.assertFalse((self.folder / "voice.wav").exists())


if __name__ == "__main__":
    unittest.main()
