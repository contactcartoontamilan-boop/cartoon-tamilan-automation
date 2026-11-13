"""Offline V14 layout regressions for review-only social image drafts.

No website fetch, platform upload, or publishing occurs in these tests.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from ctos.creative import CTA_BY_KIND, SIZES, _contained_art, _layout


class VisualLayoutTests(unittest.TestCase):
    @staticmethod
    def fake_layout(kind: str):
        width, height = SIZES[kind]
        fake_font = SimpleNamespace(size=64)
        # Exercise geometry without depending on system Tamil font installation.
        with patch("ctos.creative._measured_font", return_value=fake_font), \
             patch("ctos.creative._bbox", return_value=(0, 0, 120, 25)), \
             patch("ctos.creative._fit_title",
                   return_value=(fake_font, ["தமிழ் கதை"], 86, 120)):
            return _layout(
                None, "தமிழ் கதை", "unused-tamil-font", "unused-latin-font",
                width, height, round(width * .052), "CartoonTamilan.in",
                CTA_BY_KIND[kind])

    def test_instagram_story_uses_safe_bottom_and_compact_title_cta_gap(self):
        result = self.fake_layout("instagram_story")
        self.assertTrue(result["vertical_story"])
        self.assertGreaterEqual(result["footer_bottom_margin"], 130)
        self.assertEqual(
            1920 - result["footer_top"] - 25,
            result["footer_bottom_margin"])
        self.assertLess(result["panel_y"], 1100)
        self.assertGreaterEqual(result["cta_top"] - result["title_bottom"], 48)
        self.assertLessEqual(result["cta_top"] - result["title_bottom"], 100)
        self.assertLess(result["cta_top"] + 25, result["footer_top"])

    def test_youtube_short_has_same_mobile_safe_area(self):
        result = self.fake_layout("youtube_short")
        self.assertTrue(result["vertical_story"])
        self.assertGreaterEqual(result["footer_bottom_margin"], 130)
        self.assertLess(result["title_bottom"], result["cta_top"])

    def test_feed_preserves_small_footer_margin_and_platform_cta(self):
        result = self.fake_layout("instagram_feed")
        self.assertFalse(result["vertical_story"])
        self.assertLess(result["footer_bottom_margin"], 50)
        self.assertIn("LINK IN BIO", result["cta"])
        self.assertIn("LINK IN POST", CTA_BY_KIND["facebook_feed"])

    def test_contain_preserves_wide_cover_edges_after_background_tint(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "original_cover.png"
            art = Image.new("RGB", (800, 400), "green")
            for x in range(100):
                for y in range(400):
                    art.putpixel((x, y), (255, 0, 0))
            for x in range(700, 800):
                for y in range(400):
                    art.putpixel((x, y), (0, 0, 255))
            art.save(source)
            rendered, bbox = _contained_art(
                source, (1080, 1920), 145, 998, "#101229")
            self.assertEqual(bbox[0], 0)
            self.assertEqual(bbox[2], 1080)
            center_y = (bbox[1] + bbox[3]) // 2
            self.assertEqual(rendered.getpixel((30, center_y))[:3],
                             (255, 0, 0))
            self.assertEqual(rendered.getpixel((1050, center_y))[:3],
                             (0, 0, 255))
            self.assertLess(bbox[1] - 145, 180)


if __name__ == "__main__":
    unittest.main()
