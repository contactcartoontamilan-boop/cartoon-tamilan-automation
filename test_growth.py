import csv
import json
import tempfile
import unittest
from pathlib import Path

from growth_engine import make_campaign, tracked_link, generate
from growth_analytics import summarize_csv


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.draft = {"item": {
            "kind": "story", "id": "abc123", "title": "தமிழ் கதை",
            "link": "https://cartoontamilan.in/novel/chapter-one?ref=home"
        }}

    def test_tracking_preserves_query(self):
        url = tracked_link(self.draft["item"]["link"], "facebook", "story_abc123")
        self.assertIn("ref=home", url)
        self.assertIn("utm_source=facebook", url)
        self.assertIn("utm_campaign=story_abc123", url)

    def test_reject_external_target(self):
        with self.assertRaises(ValueError):
            tracked_link("https://evil.example/story", "facebook", "campaign")

    def test_five_platform_drafts(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "drafts", Path(d) / "campaigns"
            src.mkdir()
            (src / "a.json").write_text(json.dumps(self.draft, ensure_ascii=False), encoding="utf-8")
            result = generate(src, out)
            self.assertEqual(len(result), 1)
            campaigns = json.loads(result[0].read_text(encoding="utf-8"))
            self.assertEqual(len(campaigns), 5)
            self.assertTrue(all(c["status"] == "draft_review_required" for c in campaigns))

    def test_no_fabricated_traffic(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "stats.csv"
            file.write_text("date,pageviews,source,story_url\n", encoding="utf-8")
            self.assertEqual(summarize_csv(file)["status"], "no_data")

    def test_analytics_rollup(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "stats.csv"
            file.write_text(
                "date,pageviews,source,story_url\n"
                "2026-11-10,40,instagram,https://cartoontamilan.in/story-a\n"
                "2026-11-10,30,google,https://cartoontamilan.in/story-a\n"
                "2026-11-11,80,facebook,https://cartoontamilan.in/story-b\n",
                encoding="utf-8"
            )
            report = summarize_csv(file)
            self.assertEqual(report["latest_pageviews"], 80)
            self.assertEqual(report["remaining_to_target"], 9920)

    def test_no_negative_views(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "stats.csv"
            file.write_text("date,pageviews,source,story_url\n2026-11-11,-1,fb,\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                summarize_csv(file)


if __name__ == "__main__":
    unittest.main()
