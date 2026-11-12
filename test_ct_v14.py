"""Offline V14 tests. No provider calls, publishing or email sending."""
from __future__ import annotations

import io
import os
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from ct_v14 import build
from ctos.v14_story import plan_story, validate_scene_images
from ctos.v14_video import make_story_video, write_scene_srt
from ctos.v14_voice import azure_tamil_female, concatenate_wav, wav_duration


def fake_wav(seconds=1.0):
    data = io.BytesIO()
    with wave.open(data, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(b"\x00\x00" * round(seconds * 24000))
    return data.getvalue()


class V14OfflineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.script = " ".join(["இது அசல் தமிழ் கதை"] * 36)

    def test_storyboard_never_invents_plot(self):
        plan = plan_story(self.script, scene_count=8)
        self.assertEqual(len(plan["scenes"]), 8)
        self.assertEqual(
            " ".join(s["narration"] for s in plan["scenes"]),
            self.script)
        self.assertTrue(plan["source_faithful"])
        self.assertTrue(plan["editorial_review_required"])

    def test_title_alone_cannot_generate_full_story(self):
        with self.assertRaises(ValueError):
            plan_story("ஒரு சிறிய தலைப்பு மட்டும்", scene_count=8)

    def test_requires_eight_unique_real_scene_images(self):
        for i in range(1, 9):
            Image.new("RGB", (512, 512), (i * 25, 10, 100)).save(
                self.root / f"scene_{i:02d}.png")
        paths = validate_scene_images(self.root, 8)
        self.assertEqual(len(paths), 8)
        (self.root / "scene_08.png").write_bytes(
            (self.root / "scene_01.png").read_bytes())
        with self.assertRaisesRegex(ValueError, "repeats identical"):
            validate_scene_images(self.root, 8)

    def test_srt_timestamps_are_monotonic(self):
        scenes = plan_story(self.script)["scenes"]
        file = write_scene_srt(scenes, [11.25] * 8, self.root / "story.srt")
        data = file.read_text(encoding="utf-8")
        self.assertIn("00:00:00,000 -->", data)
        self.assertIn("தமிழ்", data)
        self.assertIn("00:01:30,000", data)

    def test_tts_requires_rights(self):
        with self.assertRaises(PermissionError):
            azure_tamil_female("அசல் தமிழ் கதை", self.root / "voice.wav")

    def test_tts_requires_real_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                azure_tamil_female(
                    "அசல் தமிழ் கதை", self.root / "voice.wav",
                    rights_confirmed=True)

    def test_azure_voice_escapes_xml_and_checks_pcm(self):
        response = Mock(status_code=200, content=fake_wav(1))
        with patch("ctos.v14_voice.requests.post", return_value=response) as post:
            file = azure_tamil_female(
                'தமிழ் & கதை <அசல்>', self.root / "voice.wav",
                rights_confirmed=True, region="centralindia",
                subscription_key="test-secret")
        self.assertAlmostEqual(wav_duration(file), 1.0)
        data = post.call_args.kwargs["data"].decode("utf-8")
        self.assertIn("ta-IN-PallaviNeural", data)
        self.assertIn("&amp;", data)
        self.assertIn("&lt;", data)
        self.assertNotIn("test-secret", data)

    def test_exact_wav_scene_boundaries(self):
        clips = []
        for i in range(3):
            file = self.root / f"clip{i}.wav"
            file.write_bytes(fake_wav(1))
            clips.append(file)
        file, durations = concatenate_wav(
            clips, self.root / "merged.wav", pause_ms=250)
        self.assertEqual([round(n, 2) for n in durations], [1.25, 1.25, 1.0])
        self.assertAlmostEqual(wav_duration(file), 3.5)

    def test_no_unauthorized_video_build(self):
        with self.assertRaises(PermissionError):
            build(SimpleNamespace(rights_confirmed=False,
                                  copy_reviewed=False,
                                  visual_reviewed=False))
        with self.assertRaises(PermissionError):
            make_story_video([], [], self.root / "video.mp4")

    def test_duration_gate_before_ffmpeg(self):
        with self.assertRaisesRegex(ValueError, "60–120"):
            make_story_video([self.root / "missing.png"] * 8, [1.0] * 8,
                             self.root / "video.mp4", rights_confirmed=True)


if __name__ == "__main__":
    unittest.main()
