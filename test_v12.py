"""Offline V12 smoke/regression tests (no external APIs, no image model)."""
import csv
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from PIL import Image

from v12_strategy import make_brief, calendar, save_calendar
from v12_media import SIZES, create_variants, make_reel
from v12_seo import inspect_html, related_link_suggestions, owned_url
from v12_insights import summarize_campaigns
from v12_news import check_source, discover_news
from v12_story_reader import chapter_urls, extract_chapter_text, collect_chapters
from v12_ops import run
from v12_engagement import draft_replies

STORY = {
    "kind": "story", "title": "நட்சத்திரங்களின் பாதை",
    "link": "https://cartoontamilan.in/novel/natchathirangal-paathai/"
}


class V12Tests(unittest.TestCase):
    def test_content_calendar_no_fabricated_character(self):
        brief = make_brief(STORY, fmt="character_spotlight")
        self.assertEqual(brief["format"], "story_hook")
        self.assertFalse(brief["published"])
        self.assertFalse(brief["creative_direction"]["canon_verified"])
        self.assertIn("utm_source=instagram", brief["tracked_link"])
        self.assertEqual(len(calendar([STORY], days=3, posts_per_day=2)), 6)

    def test_content_calendar_verified_character(self):
        bible = {"verified": True, "synopsis": "A confirmed small adventure.",
                 "world_visuals": "Ancient forest", "characters": [
                     {"appearance": "silver armor, black hair"}]}
        brief = make_brief(STORY, bible=bible, fmt="character_spotlight")
        self.assertEqual(brief["format"], "character_spotlight")
        self.assertIn("silver armor", brief["creative_direction"]["character_appearances"][0])

    def test_media_refuses_unapproved_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cover.jpg"
            Image.new("RGB", (200, 250), "blue").save(path)
            with self.assertRaises(PermissionError):
                create_variants(path, "தமிழ் கதை", Path(tmp)/"out")
            with self.assertRaises(PermissionError):
                make_reel(path, Path(tmp)/"movie.mp4", voiceover="voice.mp3")

    def test_media_size_modes(self):
        self.assertEqual(SIZES["reel_cover"], (1080, 1920))
        self.assertEqual(SIZES["youtube_thumbnail"], (1280, 720))

    def test_seo_checks_missing_metadata(self):
        page = inspect_html(STORY["link"], "<html><title>Story</title><body><h1>தமிழ் கதை</h1></body></html>")
        self.assertIn("Missing meta description", page["issues"])
        self.assertIn("Missing canonical link", page["issues"])
        self.assertIn("Missing og:image for share preview", page["issues"])
        self.assertFalse(owned_url("https://example.com/novel/test/"))
        related = related_link_suggestions([STORY, {**STORY, "link":"https://cartoontamilan.in/novel/two/"}])
        self.assertEqual(len(related[STORY["link"]]), 1)

    def test_metrics_no_fabricated_views_and_real_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "metrics.csv"
            self.assertEqual(summarize_campaigns(file)["status"], "no_data")
            file.write_text(
                "date,channel,campaign,impressions,link_clicks,website_sessions,story_reads,hour_ist\n"
                "2026-11-12,instagram,story_x,200,30,24,12,19\n",
                encoding="utf-8",
            )
            result = summarize_campaigns(file)
            self.assertEqual(result["campaigns"][0]["story_reads"], 12)
            self.assertEqual(result["best_observed_hour_ist"], 19)
            self.assertIn("NOT daily pageviews", result["note"])

    def test_news_only_trusted_feeds(self):
        with self.assertRaises(PermissionError):
            check_source({"url":"https://example.org/rss"})
        with self.assertRaises(ValueError):
            check_source({"url":"http://official.example/rss","official_source_confirmed":True})
        feed = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>News</title>'
                b'<item><title>Official update</title><link>https://official.example/news</link></item>'
                b'</channel></rss>')
        response = Mock(content=feed, status_code=200)
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        found = discover_news([{"name":"Official", "url":"https://official.example/feed.xml",
                                "official_source_confirmed":True}], session=session)
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["image_rights_confirmed"])

    def test_story_chapter_only_same_domain(self):
        html = ('<a href="/chapter/one/">Chapter 1</a>'
                '<a href="https://elsewhere.example/chapter/two/">Chapter 2</a>')
        links = chapter_urls(STORY["link"], html)
        self.assertEqual(links, ["https://cartoontamilan.in/chapter/one/"])
        self.assertFalse(extract_chapter_text("<article>short</article>"))

    def test_chapter_extract_pure_and_unverified(self):
        text = "தமிழ் கதையின் எழுத்துக்கள் " * 14
        page = '<article class="chapter-content">' + text + '</article>'
        response_story = Mock(status_code=200, text='<a href="/chapter/one/">Chapter 1</a>',
                              content=b'<html></html>', headers={"content-type":"text/html"})
        response_chapter = Mock(status_code=200, text=page,
                                content=page.encode(), headers={"content-type":"text/html"})
        response_story.raise_for_status.return_value = None
        response_chapter.raise_for_status.return_value = None
        session = Mock()
        session.get.side_effect = [response_story, response_chapter]
        result = collect_chapters(STORY["link"], session=session)
        self.assertEqual(result["chapters_extracted"], 1)
        self.assertFalse(result["editorially_verified"])

    def test_comment_replies_are_drafts_not_sent(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "comments.csv"
            f.write_text("platform,comment_id,comment_text\ninstagram,123,Where is the link?\n", encoding="utf-8")
            result = draft_replies(f, Path(tmp)/"out.json")
            self.assertEqual(len(result["drafts"]), 1)
            self.assertFalse(result["drafts"][0]["sent"])

    def test_orchestrator_is_preview_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fake_campaign(**kwargs):
                return {"prepared": [{"title": STORY["title"], "poster": "fake.jpg"}],
                        "failed": [], "published": [], "dry_run": True}
            result = run(limit=1, outdir=str(Path(tmp)/"report"),
                         discover_fn=lambda limit: [STORY],
                         campaign_fn=fake_campaign)
            self.assertEqual(result["status"], "draft_ready_review_required")
            self.assertFalse(result["live_publishing"])
            self.assertTrue(Path(tmp, "report", "latest_health.json").exists())


if __name__ == "__main__":
    unittest.main()
