import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, features
from poster_generator import make_poster, find_font, latin_font


class PosterTest(unittest.TestCase):
    def test_requires_artwork(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.json"
            draft.write_text(json.dumps({"item": {"title": "தமிழ் கதை"}}, ensure_ascii=False), encoding="utf-8")
            if not features.check("raqm"):
                self.skipTest("RAQM unavailable")
            try:
                font = find_font()
                latin_font()
            except RuntimeError:
                self.skipTest("Fonts unavailable")
            with self.assertRaisesRegex(ValueError, "artwork required"):
                make_poster(draft, Path(d) / "out.png", font)

    def test_poster_dimensions(self):
        if not features.check("raqm"):
            self.skipTest("RAQM unavailable")
        try:
            font = find_font()
            latin_font()
        except RuntimeError:
            self.skipTest("Fonts unavailable")
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.json"
            artwork = Path(d) / "art.png"
            output = Path(d) / "poster.png"
            draft.write_text(json.dumps({"item": {"title": "தமிழ் கதை"}}, ensure_ascii=False), encoding="utf-8")
            Image.new("RGB", (600, 800), "#203c78").save(artwork)
            make_poster(draft, output, font_path=font, artwork=artwork)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.format, "PNG")


if __name__ == "__main__":
    unittest.main()
