import unittest
from unittest.mock import Mock
from story_context_v10 import extract_synopsis, read_synopsis


class StoryContextV10Tests(unittest.TestCase):
    def test_extract_real_novel_synopsis(self):
        html = '<div class="novel-synopsis">இது ஒரு அசல் கதையின் அறிமுகம். <b>புதிய சாகச உலகம்</b> பற்றிய சிறிய விளக்கம் இங்கே உள்ளது.</div>'
        self.assertIn("புதிய சாகச", extract_synopsis(html))

    def test_does_not_invent_missing_synopsis(self):
        self.assertEqual(extract_synopsis('<html><h2>Original Stories</h2></html>'), "")

    def test_rejects_external_or_non_novel(self):
        for url in ("https://example.com/novel/one", "https://cartoontamilan.in/news/something"):
            with self.assertRaises(ValueError):
                read_synopsis(url)

    def test_read_synopsis_uses_site_html(self):
        response = Mock(status_code=200, text='<div class="novel-synopsis">A quiet magical world with an ancient forest and an original community of readers.</div>')
        response.raise_for_status.return_value = None
        response.headers = {"content-type":"text/html"}
        http = Mock()
        http.get.return_value = response
        value = read_synopsis("https://cartoontamilan.in/novel/example/", session=http)
        self.assertIn("magical world", value)
        self.assertFalse(http.get.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
