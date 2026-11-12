"""V13 end-to-end/offline tests. Never contact Meta/Google/SMTP/GitHub APIs."""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from auto_story_marketing import poster_headline
from ctos.creative import clean_source, render_pack, SIZES
from ctos.content import make_captions
from ctos.emailer import build_email, opted_in_subscribers, send_one
from ctos.review import approve, require_approval
from ctos.platforms import publish_meta
from ctos.qa import validate_assets
from ctos.pipeline import build_one, run
from ctos.video import create_short

STORY = {
    "kind": "story", "title": "அகாடமி ஆஃப் நிழல் விளையாட்டு: ரகசிய விதிகளின் உலகம்",
    "link": "https://cartoontamilan.in/novel/academy-of-shadow-games-secret-rules/",
}


class V13Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clean = self.root / "original_art.png"
        Image.new("RGB", (900, 1100), (60, 80, 130)).save(self.clean)

    def test_original_art_gate(self):
        poster = self.root / "premium_poster.jpg"
        Image.new("RGB", (700, 900), "red").save(poster)
        with self.assertRaises(ValueError):
            clean_source(poster)

    def test_exact_dimensions_and_separate_title_layouts(self):
        pack = render_pack(
            self.clean, poster_headline(STORY["title"]), self.root / "media",
            story_url=STORY["link"],
            variants=("instagram_feed", "instagram_story", "youtube_thumbnail"))
        self.assertEqual(len(pack["assets"]), 3)
        files = {kind: str(Path("media") / (kind + ".jpg"))
                 for kind in pack["assets"]}
        checks = validate_assets(self.root, files)
        self.assertTrue(checks["passed"])
        for kind, row in pack["assets"].items():
            with Image.open(row["file"]) as output:
                self.assertEqual(output.size, SIZES[kind])
            self.assertLess(row["title_bbox_region"][3] + 9, row["cta_top"])

    def test_text_does_not_use_derivative_poster(self):
        poster = self.root / "instagram_feed.jpg"
        Image.new("RGB", (1080, 1350), "red").save(poster)
        with self.assertRaises(ValueError):
            render_pack(poster, STORY["title"], self.root / "bad",
                        variants=("instagram_feed",))

    def test_bilingual_platform_exports_and_safe_email(self):
        data = make_captions(STORY)
        self.assertEqual(len(data["captions"]), 8)
        self.assertIn("instagram", data["captions"])
        self.assertIn("facebook", data["captions"])
        self.assertTrue(data["requires_editorial_review"])
        email = build_email(
            STORY, intro_ta="<script>alert(1)</script>",
            intro_en="A new original story")
        self.assertIn("&lt;script&gt;", email["html"])
        self.assertFalse(email["ready_to_send"])
        with self.assertRaises(PermissionError):
            send_one(email, "reader@example.org")

    def test_consent_filter(self):
        file = self.root / "subscribers.csv"
        file.write_text(
            "email,opted_in,unsubscribed\n"
            "yes@example.org,true,false\n"
            "no@example.org,false,false\n"
            "off@example.org,true,true\n"
            "yes@example.org,true,false\n", encoding="utf-8")
        self.assertEqual(opted_in_subscribers(file), ["yes@example.org"])

    def test_bundle_requires_explicit_exact_review(self):
        def fake_art(draft, folder):
            dest = Path(folder) / "clean_original.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(self.clean.read_bytes())
            return dest
        output = build_one(
            STORY, self.root / "campaign", art_fetcher=fake_art,
            renderer=lambda art, title, folder, **kwargs: render_pack(
                art, title, folder,
                story_url=STORY["link"], variants=("instagram_feed", "instagram_story")))
        path = Path(output["manifest"])
        state = self.root / "approval.json"
        with self.assertRaises(PermissionError):
            require_approval(path, state)
        with self.assertRaises(PermissionError):
            approve(path, rights=True, copy=False, visual=True, state_path=state)
        approve(path, rights=True, copy=True, visual=True, state_path=state)
        self.assertEqual(require_approval(path, state)["state"], "approved")
        media = path.parent / "media" / "instagram_feed.jpg"
        media.write_bytes(media.read_bytes() + b"touched")
        with self.assertRaises(PermissionError):
            require_approval(path, state)

    def test_preview_pipeline_never_live_publishes(self):
        def fake_art(draft, folder):
            dest = Path(folder) / "source.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(self.clean.read_bytes())
            return dest
        # No V10 approvals or external links required for preview.
        with patch("ctos.pipeline.load_approvals", return_value={}):
            report = run(
                limit=1, day=date(2026, 11, 12),
                outdir=str(self.root / "out"),
                discover_func=lambda limit: [STORY], artwork_fetcher=fake_art,
                renderer=lambda art, title, folder, **kwargs: render_pack(
                    art, title, folder, variants=("instagram_feed",)))
        # V13 must have a visual image to publish; without the other 9 formats
        # it still creates an editable draft, never a social API call.
        self.assertEqual(report["selected"], 1)
        self.assertFalse(report["live_publishing"])
        self.assertIn(report["status"], ("draft_ready_review_required", "partial"))

    def test_meta_live_requires_explicit_confirmation(self):
        with self.assertRaises(PermissionError):
            publish_meta(self.root / "missing.json", live=False)

    def test_video_requires_audio_rights_before_ffmpeg(self):
        with self.assertRaises(PermissionError):
            create_short(self.clean, self.root / "video",
                         script="An original introduction", use_tts=True, voice_rights=False)


if __name__ == "__main__":
    unittest.main()
