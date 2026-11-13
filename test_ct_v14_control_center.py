"""Offline readiness dashboard never invents live platform status."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ct_v14_control_center import readiness_report, render_dashboard, save_report


class ControlCenterTests(unittest.TestCase):
    def test_unpublished_queue_reports_drafts_not_live(self):
        queue = {
            "published": False, "live_publishing": False,
            "image_post_queue": [
                {"platform": "instagram", "published": False},
                {"platform": "facebook", "published": False},
                {"platform": "x", "published": False},
            ],
            "video_workflows_waiting_for_mp4": 3,
        }
        report = readiness_report(queue, story={"chapters_extracted": 2},
                                  scene_art={"scene_images": ["scene_01.png"]})
        self.assertEqual(report["image_post_drafts"], 3)
        self.assertEqual(report["scene_images_generated"], 1)
        self.assertEqual(report["story_chapters_extracted"], 2)
        self.assertFalse(report["platforms"]["instagram"]["live_publishing_verified"])
        self.assertEqual(report["platforms"]["x"]["adapter"],
                         "v14_opt_in_gated_not_authorized_or_tested")
        self.assertFalse(report["video_file_verified"])
        self.assertFalse(report["published"])
        with tempfile.TemporaryDirectory() as temp:
            js, page = save_report(report, Path(temp) / "dashboard")
            self.assertTrue(js.is_file())
            self.assertTrue(page.is_file())
            self.assertIn("OFFLINE PREVIEW", page.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(js.read_text(encoding="utf-8"))["image_post_drafts"], 3)

    def test_missing_queue_does_not_invent_success(self):
        report = readiness_report(None)
        self.assertFalse(report["queue_loaded"])
        self.assertEqual(report["image_post_drafts"], 0)
        self.assertFalse(report["analytics_live_verified"])

    def test_published_queue_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unpublished"):
            readiness_report({"published": True, "live_publishing": False})

    def test_unknown_platform_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid"):
            readiness_report({"published": False, "live_publishing": False,
                              "image_post_queue": [{"platform": "unknown",
                                                    "published": False}]})


if __name__ == "__main__":
    unittest.main()
