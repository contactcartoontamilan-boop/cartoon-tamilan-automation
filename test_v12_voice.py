import tempfile
import unittest
from pathlib import Path

from v12_voice import synthesize, srt_from_script


class VoiceV12Tests(unittest.TestCase):
    def test_tamil_subtitle_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = srt_from_script("தமிழ் கதைக்கு வரவேற்பு\nஇப்போது படியுங்கள்",
                                   Path(tmp)/"subs.srt", duration=12)
            text = file.read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:06,000", text)
            self.assertIn("00:00:06,000 --> 00:00:12,000", text)
            self.assertIn("தமிழ்", text)

    def test_unapproved_narration_not_run(self):
        with self.assertRaises(PermissionError):
            synthesize("A new story begins here.", "/tmp/unused.wav")

    def test_rejects_unknown_languages(self):
        with self.assertRaises(ValueError):
            synthesize("A new story begins.", "/tmp/unused.wav",
                       lang="xx", rights_confirmed=True)


if __name__ == "__main__":
    unittest.main()
