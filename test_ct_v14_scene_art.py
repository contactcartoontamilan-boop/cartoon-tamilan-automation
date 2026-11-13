"""Offline V14 scene-art tests: no external AI or social requests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ct_v14_scene_art import prepare_scene_art, scene_prompts
from ctos.v14_story import plan_story


URL = "https://cartoontamilan.in/novel/amrutha-ulaga-perangadi/"
BIBLE = {
    "verified": True,
    "synopsis": "Original approved fantasy novel",
    "world_visuals": "forest river",
    "characters": [{"appearance": "green hair, green eyes, red tunic"}],
}
SCRIPT = " ".join(["அம்ருதா தனது நண்பர்களுடன் காட்டிற்குள் பயணித்தாள்."] * 36)


class SceneArtTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.storyboard = plan_story(SCRIPT, 8)

    def test_default_prompts_only_never_generates(self):
        called = []
        def fake(*args, **kwargs):
            called.append(1)
        report = prepare_scene_art(
            self.storyboard, story_url=URL, title="அம்ருதா உலகப் பேரங்காடி",
            bible=BIBLE, outdir=self.root, generator=fake)
        self.assertEqual(report["image_generation"], "prompts_only")
        self.assertFalse(report["published"])
        self.assertFalse(report["video_generated"])
        self.assertEqual(called, [])
        self.assertTrue((self.root / "scene_prompts.json").is_file())

    def test_generation_requires_three_explicit_approvals(self):
        with self.assertRaises(PermissionError):
            prepare_scene_art(
                self.storyboard, story_url=URL, title="அம்ருதா உலகப் பேரங்காடி",
                bible=BIBLE, outdir=self.root, generate=True)

    def test_verified_bible_required(self):
        with self.assertRaises(PermissionError):
            scene_prompts(self.storyboard, story_url=URL,
                          title="அம்ருதா உலகப் பேரங்காடி",
                          bible={**BIBLE, "verified": False})

    def test_unique_seed_and_distinct_scene_images(self):
        calls = []
        def fake(prompt, destination, *, seed):
            calls.append((seed, prompt))
            Image.new("RGB", (640, 640), (seed % 256, 50, 100)).save(destination)
            return destination
        report = prepare_scene_art(
            self.storyboard, story_url=URL, title="அம்ருதா உலகப் பேரங்காடி",
            bible=BIBLE, outdir=self.root, generate=True,
            rights_confirmed=True, story_reviewed=True,
            model_license_confirmed=True, generator=fake, seed=12345)
        self.assertEqual([x[0] for x in calls], list(range(12346, 12354)))
        self.assertEqual(len(report["scene_images"]), 8)
        self.assertTrue((self.root / "scene_08.png").is_file())
        self.assertEqual(report["image_generation"], "generated_needs_visual_review")
        self.assertFalse(report["published"])

    def test_duplicate_scene_images_are_rejected(self):
        def duplicate(prompt, destination, *, seed):
            Image.new("RGB", (640, 640), "red").save(destination)
            return destination
        with self.assertRaisesRegex(ValueError, "repeats identical artwork"):
            prepare_scene_art(
                self.storyboard, story_url=URL, title="அம்ருதா உலகப் பேரங்காடி",
                bible=BIBLE, outdir=self.root, generate=True,
                rights_confirmed=True, story_reviewed=True,
                model_license_confirmed=True, generator=duplicate)


if __name__ == "__main__":
    unittest.main()
