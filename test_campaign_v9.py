import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, features
from campaign_v9 import (select_stories, get_approval, create_campaign,
                         publish_pack, publish_media_url, check_publish_ready)
from comfyui_art_v9 import load_workflow, story_prompt, base_url
from story_approvals_v9 import sync_approvals


URL = "https://cartoontamilan.in/novel/test-story/"
STORY = {"kind": "story", "title": "நட்சத்திரக் கதை", "link": URL, "id": "test"}


class CampaignV9Tests(unittest.TestCase):
    def test_rotation(self):
        stories = [{**STORY, "link": URL + str(n)} for n in range(3)]
        a = select_stories(stories, date(2026, 11, 12), 2)
        b = select_stories(stories, date(2026, 11, 13), 2)
        self.assertEqual(len(a), 2)
        self.assertNotEqual(a[0]["link"], b[0]["link"])

    def test_approval_is_explicit(self):
        self.assertIsNone(get_approval(STORY, {}))
        self.assertIsNone(get_approval(STORY, {URL: {"rights_confirmed": True}}))
        record = {"rights_confirmed": True, "copy_reviewed": True,
                  "intro_ta": "சோதனை கதை", "intro_en": "Test story"}
        self.assertEqual(get_approval(STORY, {URL: record}), record)

    def test_approval_sync_defaults_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "approved.json"
            records = sync_approvals([STORY], path)
            self.assertFalse(records[URL]["rights_confirmed"])
            self.assertFalse(records[URL]["copy_reviewed"])
            self.assertIn("intro_ta", records[URL])

    def test_creates_no_publish_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fake_cover(draft, path):
                p = Path(path)
                p.mkdir(parents=True, exist_ok=True)
                target = p / "cover.png"
                Image.new("RGB", (900, 1200), "#303858").save(target)
                return target
            def fake_poster(draft, artwork, destination):
                Image.new("RGB", (1080, 1350), "#48386e").save(destination, "JPEG")
            pack = create_campaign(STORY, date(2026,11,12),
                                   outdir=tmp, cover_fetcher=fake_cover,
                                   poster_maker=fake_poster)
            self.assertTrue(Path(pack["poster"]).exists())
            self.assertEqual(pack["status"], "draft_review_required")
            self.assertIn("utm_source=facebook", pack["facebook"]["link"])
            self.assertIn("#CartoonTamilan", pack["instagram"]["caption"])

    def test_live_publish_disabled_by_default(self):
        with patch.dict(os.environ, {"DRY_RUN": "true", "AUTO_PUBLISH_APPROVED": "false"}):
            with self.assertRaises(ValueError):
                check_publish_ready()

    def test_per_platform_dedup(self):
        flags = {"DRY_RUN":"false", "AUTO_PUBLISH_APPROVED":"true",
                 "PUBLISH_FACEBOOK":"true", "PUBLISH_INSTAGRAM":"true",
                 "META_PAGE_ID":"123", "META_PAGE_ACCESS_TOKEN":"fake",
                 "INSTAGRAM_USER_ID":"456"}
        with patch.dict(os.environ, flags), tempfile.TemporaryDirectory() as tmp:
            calls = []
            def facebook(url, caption):
                calls.append("fb")
                return {"id":"123_456"}
            def instagram(url, caption):
                calls.append("ig")
                return {"id":"987"}
            pack = {"copyright_checked": True, "copy_reviewed": True,
                    "poster": "not_accessed",
                    "facebook": {"caption": "Hello"},
                    "instagram": {"caption": "Vanakkam"}}
            journal = Path(tmp) / "state.json"
            for _ in range(2):
                result = publish_pack(STORY, pack, journal=journal,
                    media_publisher=lambda path: "https://assets.example/test.jpg",
                    fb_func=facebook, ig_func=instagram, day=date(2026,11,12))
            self.assertEqual(calls, ["fb", "ig"])
            self.assertEqual(result["facebook"]["status"], "published")
            self.assertEqual(result["instagram"]["status"], "published")

    def test_public_host_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            poster = Path(temp) / "poster.jpg"
            Image.new("RGB", (1080, 1350), "#23116a").save(poster, "JPEG")
            head = Mock(status_code=200, headers={"content-type":"image/jpeg"})
            head.raise_for_status.return_value = None
            session = Mock()
            session.head.return_value = head
            url = publish_media_url(poster, str(Path(temp) / "site"),
                                    "https://media.cartoontamilan.in/posters",
                                    session=session)
            self.assertTrue(url.endswith(".jpg"))
            self.assertTrue(list((Path(temp)/"site").glob("*.jpg")))

    def test_comfy_workflow_requires_real_model(self):
        with tempfile.TemporaryDirectory() as temp:
            wf = Path(temp) / "workflow.json"
            wf.write_text(json.dumps({
                "6":{"inputs":{"text":"old"}}, "4":{"inputs":{"ckpt_name":"old"}},
                "3":{"inputs":{"seed":1}}}), encoding="utf-8")
            modified = load_workflow(wf, "new prompt", checkpoint="licensed.safetensors", seed=42)
            self.assertEqual(modified["6"]["inputs"]["text"], "new prompt")
            self.assertEqual(modified["4"]["inputs"]["ckpt_name"], "licensed.safetensors")
            self.assertEqual(modified["3"]["inputs"]["seed"], 42)
            self.assertNotIn("REPLACE", modified["4"]["inputs"]["ckpt_name"])

    def test_comfy_endpoint_must_be_local(self):
        with patch.dict(os.environ, {"COMFYUI_URL":"https://evil.example"}):
            with self.assertRaises(ValueError):
                base_url()


if __name__ == "__main__":
    unittest.main()
