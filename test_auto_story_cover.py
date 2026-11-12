import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from auto_story_cover import cover_from_html, image_candidate, load_draft, auto_cover, resolve_draft, draft_from_story_url


class AutoCoverTests(unittest.TestCase):
    def test_explicit_story_url_rejects_untrusted_host(self):
        with self.assertRaises(ValueError):
            draft_from_story_url("https://another-site.example/novel")

    def test_explicit_story_url_writes_draft(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            original = os.getcwd()
            try:
                os.chdir(temp)
                path = draft_from_story_url("https://cartoontamilan.in/novel-one", "சொந்த கதை")
                data = load_draft(path)
                self.assertEqual(data["item"]["title"], "சொந்த கதை")
            finally:
                os.chdir(original)

    def test_og_cover(self):
        html = '<meta property="og:image" content="/media/cover.jpg">'
        self.assertEqual(cover_from_html(html, "https://cartoontamilan.in/story"),
                         "https://cartoontamilan.in/media/cover.jpg")

    def test_featured_img(self):
        html = '<section class="story-cover"><img data-src="/media/book.webp"></section>'
        self.assertEqual(cover_from_html(html, "https://cartoontamilan.in/story"),
                         "https://cartoontamilan.in/media/book.webp")

    def test_lazy_loaded_cover(self):
        html = '<div class="novel-cover"><img data-original="/media/lazy.jpg"></div>'
        self.assertEqual(cover_from_html(html, "https://cartoontamilan.in/story"), "https://cartoontamilan.in/media/lazy.jpg")

    def test_srcset_last_image(self):
        html = '<article><img srcset="/small.jpg 400w, /large.jpg 1200w"></article>'
        self.assertEqual(cover_from_html(html, "https://cartoontamilan.in/story"), "https://cartoontamilan.in/large.jpg")

    def test_external_image_rejected(self):
        self.assertIsNone(image_candidate("https://untrusted.example/cover.jpg",
                                          "https://cartoontamilan.in/story"))

    def test_load_draft_rejects_non_story(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "draft.json"
            path.write_text(json.dumps({"item": {"kind": "news", "link": "https://cartoontamilan.in/post"}}))
            with self.assertRaises(ValueError):
                load_draft(path)

    @patch("auto_story_cover.download_image")
    def test_end_to_end_uses_cover(self, download):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "draft.json"
            path.write_text(json.dumps({"item": {
                "kind": "story", "link": "https://cartoontamilan.in/story",
                "title": "தமிழ் கதை", "image_url": "https://cartoontamilan.in/cover.png"
            }}, ensure_ascii=False), encoding="utf-8")
            result = auto_cover(path, Path(temp) / "covers")
            self.assertEqual(result.suffix, ".png")
            self.assertTrue(result.with_suffix(".rights.json").exists())
            download.assert_called_once()

    def test_resolve_latest_story(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "output"
            folder.mkdir()
            (folder / "a.json").write_text(json.dumps({"item": {"kind": "story", "link": "https://cartoontamilan.in/story"}}))
            import os
            old = os.getcwd()
            try:
                os.chdir(temp)
                self.assertEqual(resolve_draft("latest"), "output/a.json")
            finally:
                os.chdir(old)

    def test_no_image_reports_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "draft.json"
            path.write_text(json.dumps({"item": {"kind": "story", "link": "https://cartoontamilan.in/story"}}))
            response = Mock(status_code=200, headers={"Content-Type": "text/html"}, text="<html></html>")
            response.raise_for_status.return_value = None
            session = Mock()
            session.get.return_value = response
            with self.assertRaisesRegex(RuntimeError, "No same-site cover"):
                auto_cover(path, Path(temp) / "covers", session=session)


if __name__ == "__main__":
    unittest.main()
