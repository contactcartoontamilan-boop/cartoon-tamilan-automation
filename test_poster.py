import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from poster_generator import make_poster, find_font


class PosterTest(unittest.TestCase):
    def test_poster_dimensions(self):
        try:
            font = find_font()
        except RuntimeError:
            self.skipTest("Tamil font not installed; supply one for manual test")
        with tempfile.TemporaryDirectory() as temp:
            draft = Path(temp) / "draft.json"
            output = Path(temp) / "poster.png"
            draft.write_text(json.dumps({
                "item": {"title": "தமிழ் கதை", "link": "https://cartoontamilan.in/test/"}
            }, ensure_ascii=False), encoding="utf-8")
            make_poster(draft, output, font)
            with Image.open(output) as im:
                self.assertEqual(im.size, (1080, 1350))
                self.assertEqual(im.format, "PNG")


if __name__ == "__main__":
    unittest.main()
