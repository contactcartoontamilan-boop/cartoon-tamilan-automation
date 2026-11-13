"""Offline multi-platform image-post queue tests. No platform API calls."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ctos.creative import SIZES
from ctos.platforms import PLATFORM_IMAGE
from ct_v14_social_queue import prepare_social_queue, main


URL = "https://cartoontamilan.in/novel/amrutha-ulaga-perangadi/"


class SocialQueueTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / "2026-11-13" / "story1"
        media = self.folder / "media"
        media.mkdir(parents=True)
        assets = {}
        for variant, size in SIZES.items():
            path = media / (variant + ".jpg")
            Image.new("RGB", size, "#304b84").save(path, "JPEG")
            assets[variant] = "media/" + variant + ".jpg"
        (self.folder / "manifest.json").write_text(
            json.dumps({"story": {"title": "அம்ருதா உலக பேரங்காடி",
                                   "link": URL},
                        "assets": assets, "published": False,
                        "status": "draft_review_required"}, ensure_ascii=False),
            encoding="utf-8")
        posts = []
        for platform, variant in PLATFORM_IMAGE.items():
            path = media / (variant + ".jpg")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            posts.append({
                "platform": platform, "story_title": "அம்ருதா உலக பேரங்காடி",
                "story_url": URL,
                "image_file": str(path.relative_to(self.root)),
                "image_sha256": digest,
                "caption": "புதிய கதை! " + URL,
                "status": "draft_review_required",
                "published": False,
            })
        self.index = {
            "published": False, "live_publishing": False,
            "requires_human_review": True,
            "story_manifests": [str((self.folder / "manifest.json").relative_to(self.root))],
            "posts": posts,
        }
        self.write_index()

    def write_index(self):
        (self.root / "image_post_preview.json").write_text(
            json.dumps(self.index, ensure_ascii=False), encoding="utf-8")

    def test_all_image_formats_and_platform_queue(self):
        with patch("ctos.platforms.publish_platform") as publisher:
            result = prepare_social_queue(self.root)
            publisher.assert_not_called()
        self.assertEqual(result["generated_image_formats"], 10)
        self.assertEqual(result["image_post_queue_count"], 7)
        self.assertEqual(result["thumbnail_only_count"], 1)
        self.assertEqual(result["video_workflows_waiting_for_mp4"], 3)
        self.assertFalse(result["published"])
        self.assertFalse(result["background_scheduler_running"])
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(
            {item["platform"] for item in result["image_post_queue"]},
            {"instagram", "facebook", "pinterest", "threads", "x", "linkedin", "telegram"})
        self.assertEqual(result["thumbnail_exports"][0]["platform"], "youtube")
        self.assertTrue(all(item["status"] == "mp4_video_required"
                            for item in result["reel_short_requirements"]))
        self.assertTrue((self.root / "social_queue.json").is_file())

    def test_review_time_is_not_live_scheduling(self):
        result = prepare_social_queue(
            self.root, start_at="2026-11-15T09:00:00+05:30",
            interval_minutes=30)
        self.assertEqual(result["image_post_queue"][0]["planned_time_for_review"],
                         "2026-11-15T09:00:00+05:30")
        self.assertEqual(result["image_post_queue"][1]["planned_time_for_review"],
                         "2026-11-15T09:30:00+05:30")
        self.assertFalse(result["background_scheduler_running"])

    def test_idempotent_repeated_draft_ids(self):
        first = prepare_social_queue(self.root)
        second = prepare_social_queue(self.root)
        self.assertEqual([x["id"] for x in first["image_post_queue"]],
                         [x["id"] for x in second["image_post_queue"]])

    def test_tampered_image_is_rejected(self):
        post = self.index["posts"][0]
        path = self.root / post["image_file"]
        Image.new("RGB", SIZES["instagram_feed"], "red").save(path, "JPEG")
        with self.assertRaisesRegex(ValueError, "Image changed"):
            prepare_social_queue(self.root)
        self.assertFalse((self.root / "social_queue.json").exists())

    def test_external_story_rejected(self):
        self.index["posts"][0]["story_url"] = "https://example.com/novel/test/"
        self.write_index()
        with self.assertRaisesRegex(ValueError, "owned story"):
            prepare_social_queue(self.root)

    def test_unsafe_path_rejected(self):
        self.index["posts"][0]["image_file"] = "../../../../outside.jpg"
        self.write_index()
        with self.assertRaisesRegex(ValueError, "Unsafe file path"):
            prepare_social_queue(self.root)

    def test_unapproved_index_rejected(self):
        self.index["requires_human_review"] = False
        self.write_index()
        with self.assertRaises(PermissionError):
            prepare_social_queue(self.root)

    def test_timezone_required(self):
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            prepare_social_queue(self.root, start_at="2026-11-15T09:00:00")

    def test_cli_status(self):
        with patch("builtins.print") as printer:
            self.assertEqual(main(["status", "--outdir", str(self.root)]), 1)
            self.assertEqual(main(["prepare", "--outdir", str(self.root)]), 0)
            self.assertEqual(main(["status", "--outdir", str(self.root)]), 0)
            self.assertEqual(printer.call_count, 3)


if __name__ == "__main__":
    unittest.main()
