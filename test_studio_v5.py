import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from social_content_v5 import make_social_pack, build_from_file
from creative_studio_v5 import render_variants


class StudioV5Tests(unittest.TestCase):
    def setUp(self):
        self.item = {"id": "ab" * 15, "kind": "story", "title": "புதிய தமிழ் கதை",
                     "summary": "ஒரு புதிய கதையின் அறிமுகம்", "link": "https://cartoontamilan.in/story-one"}

    def test_social_copy_and_tags(self):
        result = make_social_pack(self.item, ["fantasy", "romance"])
        self.assertIn("utm_source=facebook", result["facebook"]["link"])
        self.assertIn("utm_source=instagram", result["instagram"]["tracked_link_for_bio"])
        self.assertIn("#FantasyNovel", result["facebook"]["caption"])
        self.assertIn("#RomanceNovel", result["instagram"]["caption"])
        self.assertEqual(result["status"], "draft_review_required")

    def test_reject_non_story(self):
        item = dict(self.item, kind="news")
        with self.assertRaises(ValueError):
            make_social_pack(item)

    def test_no_false_translation_claim(self):
        result = make_social_pack(self.item)
        self.assertTrue(any("not a chapter translation" in note for note in result["review_notes"]))

    def test_local_file_pack(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "draft.json"
            d.write_text(json.dumps({"item": self.item}, ensure_ascii=False), encoding="utf-8")
            output = Path(t) / "pack.json"
            build_from_file(d, output, ["action"])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "draft_review_required")

    def test_visual_variants(self):
        with tempfile.TemporaryDirectory() as t:
            art = Path(t) / "my_art.png"
            Image.new("RGB", (600, 850), "#395c8b").save(art)
            paths = render_variants(art, Path(t) / "renders")
            for path in paths:
                self.assertTrue(path.exists())
                with Image.open(path) as im:
                    self.assertEqual(im.size, (1080, 1350))

    def test_missing_artwork_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(FileNotFoundError):
                render_variants(Path(t) / "missing.png", Path(t) / "renders")


if __name__ == "__main__":
    unittest.main()
