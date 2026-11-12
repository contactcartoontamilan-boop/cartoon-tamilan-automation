import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from auto_story_marketing import discover_from_html, build, clean_story_title, poster_headline

HTML = """
<html><body>
<section><h2>Trending / Popular Anime</h2>
 <div class="novel-card"><a href="/original-novel-one" title="வியூகம்: நட்சத்திரங்களின் பாதை">வியூகம்: நட்சத்திரங்களின் பாதை</a><small>Completed · Adventure</small></div>
 <div class="novel-card"><a href="/original-novel-two" title="டிஜிட்டல் இதயங்கள்">டிஜிட்டல் இதயங்கள்</a><small>Ongoing · Game-World</small></div>
</section>
<section><h2>Latest Updates</h2>
 <article><a href="/kodansha-licenses-manga">Kodansha licenses new manga</a><span>Read More</span></article>
</section>
<section><a href="/episode-121">Episode 121 அகாடமி</a></section>
</body></html>
"""


class DiscoveryTests(unittest.TestCase):
    def test_clean_story_title(self):
        self.assertEqual(clean_story_title("வியூகம்: நட்சத்திரங்களின் பாதை Completed · CT Admin Adventure"), "வியூகம்: நட்சத்திரங்களின் பாதை")
        self.assertLessEqual(len(poster_headline("ஒரு நீண்ட கதையின் பெயர் " * 20)), 90)

    def test_finds_only_story_cards(self):
        items = discover_from_html(HTML)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item["kind"] == "story" for item in items))
        self.assertTrue(all("kodansha" not in item["link"] for item in items))

    def test_reject_external_links(self):
        html = '<div class="novel-card"><a href="https://evil.example/novel">Some novel</a><small>Ongoing</small></div>'
        self.assertEqual(discover_from_html(html), [])

    def test_empty_html(self):
        self.assertEqual(discover_from_html("<html></html>"), [])

    def test_end_to_end_with_mocked_cover_and_poster(self):
        response = Mock(status_code=200, text=HTML)
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        def fake_cover(draft, directory):
            directory = Path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / "cover.png"
            path.write_bytes(b"fake-test-cover")
            return path

        def fake_poster(draft, output, **kwargs):
            Path(output).write_bytes(b"fake-test-poster")

        with tempfile.TemporaryDirectory() as folder:
            report = build(folder, 10, session=session, cover_fetcher=fake_cover, poster_maker=fake_poster)
            self.assertEqual(report["discovered"], 2)
            self.assertEqual(len(report["success"]), 2)
            self.assertEqual(len(report["failed"]), 0)
            self.assertFalse(report["published"])


if __name__ == "__main__":
    unittest.main()
