"""Offline tests for the V14 website-to-image-post preview wrapper.

These tests never access the live website or publish to social platforms.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ct_v14_image_post import main, prepare_image_posts


STORY = {
    "title": "அசல் தமிழ் கதை",
    "link": "https://cartoontamilan.in/novel/original-story/",
}


class ImagePostPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def runner(self, *, size=(1080, 1350), image_file="media/instagram_feed.jpg",
               published=False, story=None, caption="புதிய தமிழ் கதை!"):
        def fake_run(*, limit, outdir, art_mode, make_video, voice, audit, chapters):
            self.assertEqual(limit, 1)
            self.assertEqual(art_mode, "cover")
            self.assertFalse(make_video)
            self.assertFalse(voice)
            self.assertFalse(audit)
            self.assertFalse(chapters)
            folder = Path(outdir) / "2026-11-13" / "story-1"
            folder.mkdir(parents=True, exist_ok=True)
            image = folder / "media" / "instagram_feed.jpg"
            image.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", size, "#304b84").save(image, format="JPEG")
            record = {
                "story": story or STORY,
                "published": published,
                "status": "draft_review_required",
            }
            manifest = folder / "manifest.json"
            manifest.write_text(json.dumps(record, ensure_ascii=False),
                                encoding="utf-8")
            draft = {
                "instagram": {
                    "image_file": image_file,
                    "caption": caption,
                    "story_url": (story or STORY)["link"],
                    "publication_status": "not_published",
                }
            }
            (folder / "platform_drafts.json").write_text(
                json.dumps(draft, ensure_ascii=False), encoding="utf-8")
            return {"prepared": [{"manifest": str(manifest)}],
                    "failed": [], "discovered": 1, "status": "draft_ready_review_required"}
        return fake_run

    def test_creates_saved_image_post_and_status(self):
        output = self.root / "v14"
        with patch("ctos.platforms.publish_platform") as publish:
            result = prepare_image_posts(1, output, runner=self.runner())
            publish.assert_not_called()
        self.assertEqual(result["status"], "draft_ready_review_required")
        self.assertEqual(result["post_drafts_created"], 1)
        self.assertFalse(result["published"])
        self.assertFalse(result["live_publishing"])
        self.assertFalse(result["email_sent"])
        self.assertTrue(result["requires_human_review"])
        post = result["posts"][0]
        self.assertEqual(post["platform"], "instagram")
        self.assertEqual(post["dimensions"], [1080, 1350])
        self.assertEqual(len(post["image_sha256"]), 64)
        self.assertTrue((output / post["image_file"]).is_file())
        saved = json.loads((output / "image_post_preview.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["post_drafts_created"], 1)
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(main(["status", "--outdir", str(output)]), 0)
            self.assertIn("draft_ready_review_required", stdout.getvalue())

    def test_invalid_dimensions_rejected_before_saving_index(self):
        output = self.root / "wrong_size"
        with self.assertRaisesRegex(ValueError, "Invalid JPEG"):
            prepare_image_posts(1, output, runner=self.runner(size=(300, 300)))
        self.assertFalse((output / "image_post_preview.json").exists())

    def test_path_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsafe output path"):
            prepare_image_posts(
                1, self.root / "unsafe",
                runner=self.runner(image_file="../../../../secret.jpg"))

    def test_unapproved_source_is_not_pretended_published(self):
        with self.assertRaisesRegex(ValueError, "unpublished review draft"):
            prepare_image_posts(1, self.root / "published",
                                runner=self.runner(published=True))

    def test_non_owned_story_url_rejected(self):
        bad_story = {"title": "Other site", "link": "https://example.org/novel/test/"}
        with self.assertRaisesRegex(ValueError, "CartoonTamilan"):
            prepare_image_posts(1, self.root / "external",
                                runner=self.runner(story=bad_story))

    def test_no_discovery_saves_honest_empty_report(self):
        def empty_runner(**kwargs):
            return {"prepared": [], "failed": [{"reason": "No stories discovered"}],
                    "status": "failed"}
        output = self.root / "empty"
        result = prepare_image_posts(1, output, runner=empty_runner)
        self.assertEqual(result["post_drafts_created"], 0)
        self.assertEqual(result["status"], "no_drafts_created")
        self.assertTrue((output / "image_post_preview.json").exists())
        with patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(["status", "--outdir", str(output)]), 1)

    def test_limit_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 6"):
            prepare_image_posts(0, self.root / "invalid", runner=self.runner())


if __name__ == "__main__":
    unittest.main()
