import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, features
from cinematic_poster_v9 import cinematic_poster
from poster_generator import find_font, latin_font


class CinematicPosterTests(unittest.TestCase):
    def test_cinematic_dimensions_and_brand(self):
        if not features.check("raqm"):
            self.skipTest("Pillow RAQM unavailable")
        try:
            find_font()
            latin_font()
        except RuntimeError:
            self.skipTest("Termux or Linux Tamil/Latin fonts unavailable")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            draft = folder / "story.json"
            cover = folder / "art.png"
            output = folder / "finished.jpg"
            draft.write_text(json.dumps({"item": {"title": "வியூகம்: நட்சத்திரங்களின் பாதை",
                                                  "kind": "story"}}, ensure_ascii=False),
                             encoding="utf-8")
            Image.new("RGB", (1000, 1400), "#36537b").save(cover)
            result = cinematic_poster(draft, cover, output)
            self.assertTrue(result.is_file())
            with Image.open(result) as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.format, "JPEG")

    def test_requires_real_artwork(self):
        if not features.check("raqm"):
            self.skipTest("Pillow RAQM unavailable")
        try:
            find_font()
            latin_font()
        except RuntimeError:
            self.skipTest("Tamil/Latin fonts unavailable")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "draft.json"
            path.write_text(json.dumps({"item": {"title": "தமிழ் கதை"}}, ensure_ascii=False))
            with self.assertRaises(FileNotFoundError):
                cinematic_poster(path, Path(temp) / "missing.png", Path(temp) / "poster.jpg")


if __name__ == "__main__":
    unittest.main()
