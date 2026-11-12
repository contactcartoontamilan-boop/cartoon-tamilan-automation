import unittest
from unittest.mock import Mock
from asset_selector import extract_post_image, choose_asset, same_site
from image_sources import search_public_domain


class AssetSelectionTests(unittest.TestCase):
    def test_site_host_validation(self):
        self.assertTrue(same_site("https://cartoontamilan.in/abc", "https://cartoontamilan.in"))
        self.assertFalse(same_site("https://cartoontamilan.in.evil.com/image.png", "https://cartoontamilan.in"))
        self.assertFalse(same_site("http://cartoontamilan.in/abc", "https://cartoontamilan.in"))

    def test_extract_og_image(self):
        html = '<meta property="og:image" content="/uploads/cover.jpg">'
        self.assertEqual(extract_post_image(html, "https://cartoontamilan.in/story", "https://cartoontamilan.in"),
                         "https://cartoontamilan.in/uploads/cover.jpg")

    def test_ignore_external_image(self):
        html = '<meta property="og:image" content="https://example.com/unlicensed.png">'
        self.assertIsNone(extract_post_image(html, "https://cartoontamilan.in/story", "https://cartoontamilan.in"))

    def test_openverse_cc0_only(self):
        http = Mock()
        response = Mock()
        response.json.return_value = {"results": [
            {"url": "https://images.example/public.jpg", "license": "cc0", "foreign_landing_url": "https://example.org/photo"},
            {"url": "https://images.example/restricted.jpg", "license": "by-nc", "foreign_landing_url": "https://example.org/restricted"}
        ]}
        http.get.return_value = response
        items = search_public_domain("illustrated mountains", session=http)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["requires_manual_rights_review"])

    def test_own_image_preferred(self):
        item = {"link": "https://cartoontamilan.in/story", "image_url": "https://cartoontamilan.in/cover.png"}
        result = choose_asset(item, "https://cartoontamilan.in", enable_openverse=False)
        self.assertEqual(result["origin"], "own_site")


if __name__ == "__main__":
    unittest.main()
