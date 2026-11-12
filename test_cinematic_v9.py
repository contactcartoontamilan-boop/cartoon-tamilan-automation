import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, features
from cinematic_poster_v9 import cinematic_poster, mask_cover_titles
from poster_generator import find_font, latin_font


class CinematicPosterTests(unittest.TestCase):
    def test_printed_cover_title_region_is_fully_hidden(self):
        from PIL import Image
        source = Image.new("RGB", (1080, 1350), "white")
        result = mask_cover_titles(source)
        # Faces at the top of the key art remain visible.
        self.assertEqual(result.getpixel((550, 300))[:3], (255, 255, 255))
        # Text printed lower down is completely hidden; no ghost letters.
        self.assertEqual(result.getpixel((550, 800))[:3], (10, 8, 31))
        self.assertEqual(result.getpixel((550, 1050))[:3], (10, 8, 31))

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
