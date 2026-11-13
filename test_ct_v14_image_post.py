"""Offline regression tests for V14 automatic image-post drafts.

No website, email, Meta, Telegram, Azure, or other provider calls.
"""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ct_v14_image_post import create_image_post_preview, main


STORY = {
    "kind": "story",
    "title": "ஒரு அசல் தமிழ் கதை",
    "link": "https://cartoontamilan.in/novel/test-original-story/",
}


class V14ImagePostTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.calls = []

    def fake_runner(self, **kwargs):
        self.calls.append(kwargs)
        base = Path(kwargs["outdir"]) / "2026-11-13" / "story"
        media = base / "media"
        media.mkdir(parents=True, exist_ok=True)
        assets = {}
        for kind in ("instagram_feed", "facebook_feed", "instagram_story"):
            name = kind + ".jpg"
            Image.new("RGB", (64, 64), "#234567").save(media / name)
            assets[kind] = "media/" + name
        manifest = base / "manifest.json"
        manifest.write_text(json.dumps({
            "story": STORY, "status": "draft_review_required",
            "published": False, "creative_qa": {"passed": True},
            "assets": assets,
        }, ensure_ascii=False), encoding="utf-8")
        (base / "platform_drafts.json").write_text(json.dumps({
            "instagram": {"publication_status": "not_published"},
            "facebook": {"publication_status": "not_published"},
        }), encoding="utf-8")
        return {"discovered": 1, "prepared": [{"manifest": str(manifest)}],
                "failed": []}

    def test_website_image_draft_saved_without_publishing(self):
        result = create_image_post_preview(
            outdir=self.root / "preview", pipeline_runner=self.fake_runner)
        self.assertEqual(result["status"], "draft_ready_review_required")
        self.assertEqual(result["prepared"], 1)
        self.assertFalse(result["published"])
        self.assertFalse(result["live_publishing"])
        self.assertFalse(result["email_sent"])
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(set(result["stories"][0]["images"]),
                         {"instagram_feed", "facebook_feed", "instagram_story"})
        saved = json.loads((self.root / "preview" / "image_post_index.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(saved["stories"][0]["story_url"], STORY["link"])
        self.assertEqual(self.calls[0]["art_mode"], "cover")
        self.assertFalse(self.calls[0]["make_video"])
        self.assertFalse(self.calls[0]["voice"])
        self.assertFalse(self.calls[0]["audit"])
        self.assertFalse(self.calls[0]["chapters"])

    def test_empty_catalogue_fails_closed(self):
        result = create_image_post_preview(
            outdir=self.root / "empty",
            pipeline_runner=lambda **kwargs: {
                "discovered": 0, "prepared": [], "failed": []})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["prepared"], 0)
        self.assertFalse(result["published"])

    def test_rejects_published_or_qa_failed_draft(self):
        def invalid(**kwargs):
            report = self.fake_runner(**kwargs)
            manifest = Path(report["prepared"][0]["manifest"])
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["published"] = True
            manifest.write_text(json.dumps(data), encoding="utf-8")
            return report
        with self.assertRaisesRegex(ValueError, "unpublished"):
            create_image_post_preview(
                outdir=self.root / "unsafe", pipeline_runner=invalid)

    def test_rejects_escaped_manifest(self):
        def escaped(**kwargs):
            report = self.fake_runner(**kwargs)
            report["prepared"][0]["manifest"] = str(self.root / "outside.json")
            return report
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            create_image_post_preview(
                outdir=self.root / "escape", pipeline_runner=escaped)

    def test_limit_is_bounded(self):
        for limit in (0, 4):
            with self.assertRaises(ValueError):
                create_image_post_preview(
                    limit=limit, outdir=self.root / "bounded",
                    pipeline_runner=self.fake_runner)
        self.assertEqual(self.calls, [])

    def test_status_does_not_call_website(self):
        result = create_image_post_preview(
            outdir=self.root / "status", pipeline_runner=self.fake_runner)
        self.assertEqual(result["prepared"], 1)
        self.assertEqual(main(["--status", "--outdir", str(self.root / "status")]), 0)


if __name__ == "__main__":
    unittest.main()
