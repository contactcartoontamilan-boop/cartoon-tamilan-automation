"""Offline V14 P0 story-ingestion and visual-safety regression tests."""
from __future__ import annotations

import json
import io
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch
import unittest
from pathlib import Path

from PIL import Image

from ct_v14_story_ingest import (
    collect_full_story, discover_chapters, discover_latest_owned_story,
    diagnostic_summary, draft_source_excerpt, main, save_draft,
)
from ctos.creative import CTA_BY_KIND, SIZES, _contained_art
from ctos.platforms import PLATFORM_IMAGE


STORY = "https://cartoontamilan.in/novel/amrutha-ulaga-perangadi/"
C1 = STORY + "chapter-1/"
C2 = STORY + "chapter-2/"
OTHER = "https://cartoontamilan.in/novel/other-story/chapter-9/"


class FakeResponse:
    def __init__(self, html):
        self.text = html
        self.content = html.encode("utf-8")
        self.status_code = 200
        self.headers = {"content-type": "text/html"}

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append(url)
        if url not in self.pages:
            raise AssertionError("Unexpected network request: " + url)
        return FakeResponse(self.pages[url])


class FullStoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.tamil = ("அம்ருதா தனது நண்பர்களுடன் காட்டின் வழியாக பயணித்தாள். "
                      "அங்கே ஒரு புதிய பாதையை கண்டுபிடித்தாள். ") * 30
        self.pages = {
            STORY: ('<html><a href="chapter-1/">அத்தியாயம் 1</a>'
                    '<a href="' + OTHER + '">Chapter 9</a></html>'),
            C1: ('<div class="chapter-content">' + self.tamil + '</div>'
                 '<a href="../chapter-2/">அடுத்த அத்தியாயம்</a>'),
            C2: '<div class="chapter-content">' + self.tamil + '</div>',
        }

    def test_follows_owned_chapters_and_creates_verbatim_draft(self):
        session = FakeSession(self.pages)
        collected = collect_full_story(STORY, session=session, max_pages=10)
        self.assertEqual(collected["chapters_extracted"], 2)
        self.assertEqual(session.requested, [STORY, C1, C2])
        self.assertNotIn(OTHER, session.requested)
        self.assertFalse(collected["published"])
        self.assertIn("unverified", collected["completeness"])
        draft = draft_source_excerpt(collected, target_words=180, scene_count=8)
        self.assertEqual(draft["storyboard"]["word_count"], 180)
        self.assertEqual(draft["storyboard"]["scene_count"], 8)
        self.assertEqual(draft["draft_type"], "verbatim_source_excerpt_not_summary")
        self.assertFalse(draft["approved_for_video"])
        self.assertTrue(draft["narration"].startswith("அம்ருதா தனது"))
        manifest = save_draft(collected, draft, self.root / "preview")
        self.assertFalse(manifest["video_generated"])
        self.assertFalse(manifest["published"])
        self.assertTrue((self.root / "preview" / "narration_draft_ta.txt").is_file())
        self.assertEqual(
            json.loads((self.root / "preview" / "manifest.json").read_text(
                encoding="utf-8"))["review_status"],
            "needs_human_story_and_rights_review")

    def test_auto_discover_uses_existing_owned_story_source(self):
        def fake(*, limit):
            self.assertEqual(limit, 10)
            return [{"link": "https://evil.test/novel/x/"},
                    {"link": STORY, "title": "Original"}]
        self.assertEqual(discover_latest_owned_story(fake), STORY)

    def test_cross_story_and_external_links_not_followed(self):
        html = ('<a href="https://evil.test/novel/chapter-3">Chapter 3</a>'
                '<a href="' + OTHER + '">Chapter 9</a>'
                '<a href="chapter-1/">அத்தியாயம் 1</a>')
        self.assertEqual(discover_chapters(STORY, html), [C1])

    def test_landing_diagnostics_report_structure_not_story_prose(self):
        session = FakeSession(self.pages)
        collected = collect_full_story(STORY, session=session)
        signals = collected["landing_page_signals"]
        self.assertEqual(signals["anchor_count"], 2)
        self.assertIn("/novel/other-story/chapter-9/", signals["novel_path_examples"])
        self.assertEqual(signals["selector_characters"]["article"], 0)
        self.assertGreater(signals["html_bytes"], 0)
        self.assertNotIn(self.tamil[:30], json.dumps(signals, ensure_ascii=False))

    def test_chapter_card_diagnostics_show_only_same_site_paths(self):
        from ct_v14_story_ingest import landing_page_signals
        html = ('<div class="ctdu-chapter-cards">'
                '<a href="/novel/amrutha-ulaga-perangadi/chapter-1/?token=private">'
                'அத்தியாயம் ஒன்று</a>'
                '<a href="https://example.org/private">External</a>'
                '<button data-chapter-id="42">Read</button>'
                '</div>')
        result = landing_page_signals(STORY, html)
        card = result["chapter_card_signals"]
        self.assertEqual(card["containers"], 1)
        self.assertEqual(card["anchors"], 2)
        self.assertEqual(card["buttons"], 1)
        self.assertIn("data-chapter-id", card["data_attribute_names"])
        self.assertEqual(card["same_site_link_paths"], [
            "/novel/amrutha-ulaga-perangadi/chapter-1/"])
        self.assertNotIn("token=private", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("example.org", json.dumps(card, ensure_ascii=False))

    def test_client_rendered_page_signals_without_exposing_script_text(self):
        html = ('<html><head><title>Story</title></head><body>'
                '<main><section class="story-reader">' + self.tamil + '</section></main>'
                '<script>self.__next_f.push(["chapter secret token"])</script>'
                '</body></html>')
        from ct_v14_story_ingest import landing_page_signals
        result = landing_page_signals(STORY, html)
        self.assertTrue(result["framework_signals"]["next_flight"])
        self.assertGreater(result["selector_characters"]["main"], 100)
        self.assertTrue(result["candidate_containers"])
        self.assertGreater(result["script_keyword_counts"]["chapter"], 0)
        self.assertNotIn("secret token", json.dumps(result, ensure_ascii=False))
        self.assertNotIn(self.tamil[:30], json.dumps(result, ensure_ascii=False))

    def test_slug_suffixed_chapter_link_without_crossing_story_boundary(self):
        sibling = STORY.rstrip("/") + "-chapter-3/"
        other = STORY.rstrip("/") + "-other-chapter-3/"
        html = ('<a href="' + sibling + '">Chapter 3</a>'
                '<a href="' + other + '">Chapter 4</a>')
        self.assertEqual(discover_chapters(STORY, html), [sibling])

    def test_inspect_reports_short_text_without_traceback(self):
        fake_collected = {
            "story_url": STORY, "chapters": [], "chapters_extracted": 0,
            "pages_examined": 0, "chapter_links_discovered": 0,
            "landing_readable_words": 0, "extracted_words": 0,
            "failures": [], "completeness": "unverified",
            "published": False,
        }
        out = io.StringIO()
        with patch("ct_v14_story_ingest.collect_full_story", return_value=fake_collected):
            with redirect_stdout(out):
                code = main(["--story-url", STORY, "--inspect"])
        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "diagnostic_only")
        self.assertEqual(result["chapters_extracted"], 0)
        self.assertFalse(result["published"])

    def test_failed_draft_prints_actionable_diagnostics(self):
        fake_collected = {
            "story_url": STORY, "chapters": [], "chapters_extracted": 0,
            "pages_examined": 0, "chapter_links_discovered": 0,
            "landing_readable_words": 0, "extracted_words": 0,
            "failures": [], "completeness": "unverified",
            "published": False,
        }
        out = io.StringIO()
        with patch("ct_v14_story_ingest.collect_full_story", return_value=fake_collected):
            with redirect_stdout(out):
                code = main(["--story-url", STORY, "--words", "180"])
        self.assertEqual(code, 2)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "insufficient_or_invalid_chapter_text")
        self.assertEqual(result["diagnostics"]["extracted_words"], 0)

    def test_max_pages_honest_truncation(self):
        result = collect_full_story(STORY, session=FakeSession(self.pages), max_pages=1)
        self.assertEqual(result["chapters_extracted"], 1)
        self.assertTrue(result["more_links_unread"])

    def test_short_source_fails_instead_of_inventing_plot(self):
        data = {"chapters": [{"url": C1, "text": "ஒரு கதை.",
                              "sha256": "abc"}]}
        with self.assertRaisesRegex(ValueError, "Not enough real chapter words"):
            draft_source_excerpt(data, target_words=180)

    def test_external_source_rejected_before_network(self):
        with self.assertRaises(ValueError):
            collect_full_story("https://evil.test/novel/steal/", session=FakeSession({}))
        with self.assertRaises(ValueError):
            collect_full_story("http://cartoontamilan.in/novel/story/", session=FakeSession({}))


class VisualSafetyTests(unittest.TestCase):
    def test_all_platform_ctas_are_defined(self):
        self.assertEqual(set(CTA_BY_KIND), set(SIZES))
        self.assertIn("LINK IN BIO", CTA_BY_KIND["instagram_feed"])
        self.assertIn("LINK IN POST", CTA_BY_KIND["facebook_feed"])
        self.assertNotIn("LINK IN BIO", CTA_BY_KIND["pinterest_pin"])
        self.assertEqual(PLATFORM_IMAGE["telegram"], "facebook_feed")

    def test_contain_preserves_both_edges_of_wide_cover(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "cover.png"
            art = Image.new("RGB", (800, 400), "green")
            for x in range(0, 120):
                for y in range(400):
                    art.putpixel((x, y), (255, 0, 0))
            for x in range(680, 800):
                for y in range(400):
                    art.putpixel((x, y), (0, 0, 255))
            art.save(source)
            rendered, bbox = _contained_art(source, (1080, 1350), 100, 650, "#101229")
            self.assertEqual(bbox[0], 0)
            self.assertEqual(bbox[2], 1080)
            center_y = (bbox[1] + bbox[3]) // 2
            self.assertEqual(rendered.getpixel((30, center_y))[:3], (255, 0, 0))
            self.assertEqual(rendered.getpixel((1050, center_y))[:3], (0, 0, 255))


if __name__ == "__main__":
    unittest.main()
