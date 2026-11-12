"""Offline tests for V10 story verification and poster prompt accuracy."""
import json
import tempfile
import unittest
from pathlib import Path

from story_bible_v10 import scene_prompt, validate_bible, sync


STORY = {"kind": "story", "title": "வியூகம்: நட்சத்திரங்களின் பாதை",
         "link": "https://cartoontamilan.in/novel/example/"}


class StoryBibleV10Tests(unittest.TestCase):
    def test_new_story_unverified_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bibles.json"
            entries = sync([STORY], target)
            self.assertFalse(entries[STORY["link"]]["verified"])
            self.assertFalse(validate_bible(entries[STORY["link"]]))
            self.assertEqual(len(entries), 1)

    def test_verified_character_visuals_in_prompt(self):
        record = {
            "verified": True,
            "synopsis": "A hero visits an enchanted city, confirmed in the chapters.",
            "world_visuals": "golden towers and floating islands",
            "characters": [{"appearance": "short brown hair, red cloak, silver shoulder armor"}],
        }
        self.assertTrue(validate_bible(record))
        prompt = scene_prompt(STORY["title"], record, style="cinematic_3d")
        self.assertIn("golden towers", prompt)
        self.assertIn("red cloak", prompt)
        self.assertIn("3D-render", prompt)
        self.assertIn("No text", prompt)

    def test_unverified_prompt_discloses_noncanon(self):
        prompt = scene_prompt(STORY["title"], {"verified": False}, style="anime")
        self.assertIn("Non-canonical", prompt)
        self.assertNotIn("Verified original character appearance:", prompt)

    def test_bad_character_notes_rejected(self):
        self.assertFalse(validate_bible({
            "verified": True, "synopsis": "some intro",
            "characters": [{"name": "hero"}]}))

    def test_existing_records_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bibles.json"
            current = {STORY["link"]: {
                "verified": True, "synopsis": "verified source",
                "characters": []}}
            target.write_text(json.dumps(current), encoding="utf-8")
            result = sync([STORY], target)
            self.assertEqual(result[STORY["link"]]["synopsis"], "verified source")
            self.assertTrue(result[STORY["link"]]["verified"])


if __name__ == "__main__":
    unittest.main()
