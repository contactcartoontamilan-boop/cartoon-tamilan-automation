"""Offline V10 checks. No model server, social network, or live website required."""
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image, features

from art_direction_v10 import concept_prompt
from premium_poster_v10 import make_premium_poster, _fade_artwork
from social_copy_v10 import premium_copy
from story_approvals_v10 import initialize
from campaign_v10 import build_premium_campaign, run_v10
from poster_generator import find_font, latin_font

STORY = {
    "id": "123abc", "kind": "story", "title": "வியூகம்: நட்சத்திரங்களின் பாதை",
    "link": "https://cartoontamilan.in/novel/viyugam/"
}


class PremiumV10Tests(unittest.TestCase):
    def test_prompt_no_hallucinated_canon(self):
        prompt = concept_prompt(STORY["title"], genre="unverified")
        self.assertIn("Conceptual promotional", prompt)
        self.assertIn("NO text", prompt)
        self.assertNotIn("verified character design notes", prompt.lower())

    def test_prompt_can_use_verified_notes(self):
        prompt = concept_prompt("Story", genre="romance", style="cinematic_3d",
                                character_notes="black jacket, blue eyes",
                                world_notes="seaside town")
        self.assertIn("black jacket, blue eyes", prompt)
        self.assertIn("seaside town", prompt)
        self.assertIn("3D-rendered", prompt)

    def test_captions_track_real_readers(self):
        copy = premium_copy(STORY, {"genres":["fantasy"], "intro_ta":"சோதனை அறிமுகம்",
                                   "intro_en":"Verified synopsis"})
        self.assertIn("#FantasyNovel", copy["instagram"]["caption"])
        self.assertIn("utm_source=facebook", copy["facebook"]["caption"])
        self.assertIn("link in our profile bio", copy["instagram"]["caption"])
        self.assertEqual(copy["copy_source"], "reviewed_synopsis")

    def test_approval_defaults_disabled_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"approvals.json"
            data = initialize(stories=[STORY], path=target)
            self.assertFalse(data[STORY["link"]]["v10_visual_policy_approved"])
            self.assertFalse(data[STORY["link"]]["v10_automatic_ai_approved"])
            data[STORY["link"]]["premium_theme"]="cosmic"
            target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            updated = initialize(stories=[STORY], path=target)
            self.assertEqual(updated[STORY["link"]]["premium_theme"], "cosmic")

    def test_source_title_is_hidden_below_matte(self):
        source = Image.new("RGB", (1080, 1350), (255, 255, 255))
        result = _fade_artwork(source)
        self.assertEqual(result.getpixel((450, 200))[:3], (255,255,255))
        self.assertEqual(result.getpixel((450, 1000))[:3], (13,7,34))

    def test_render_real_jpeg_and_size(self):
        if not features.check("raqm"):
            self.skipTest("Tamil shaping needs RAQM")
        try:
            find_font()
            latin_font()
        except RuntimeError:
            self.skipTest("Required Tamil/Latin fonts unavailable")
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            draft = base / "story.json"
            draft.write_text(json.dumps({"item":STORY}, ensure_ascii=False), encoding="utf-8")
            art = base / "original.png"
            Image.new("RGB", (960, 1440), "#6d4c91").save(art)
            result = make_premium_poster(draft, art, base / "poster.jpg")
            with Image.open(result) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (1080, 1350))

    def test_cover_campaign_is_review_only(self):
        with tempfile.TemporaryDirectory() as folder:
            def fake_cover(draft, output):
                path = Path(output)
                path.mkdir(parents=True, exist_ok=True)
                target = path/"cover.png"
                Image.new("RGB", (800, 1100), "#47557b").save(target)
                return target
            def fake_poster(draft, art, dest, theme="royal"):
                Image.new("RGB",(1080,1350), "#4b3574").save(dest, "JPEG")
                return dest
            pack = build_premium_campaign(
                STORY, date(2026,11,12), "cover", folder, cover_fetcher=fake_cover,
                poster_maker=fake_poster)
            self.assertFalse(pack["actual_new_art_generated"])
            self.assertEqual(pack["status"], "draft_review_required")
            self.assertTrue(Path(pack["poster"]).is_file())
            self.assertIn("facebook", pack)
            self.assertTrue(Path(pack["poster"]).with_name("social_pack.json").exists())

    def test_ai_campaign_passes_story_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def fake_ai(prompt, output):
                calls.append(prompt)
                output = Path(output)
                Image.new("RGB",(800,1100), "#347a80").save(output)
                return output
            def fake_poster(draft, art, dest, theme="royal"):
                Image.new("RGB",(1080,1350), "#373556").save(dest, "JPEG")
                return dest
            record = {"genres":["isekai"], "verified_world_notes":"magic portals",
                      "premium_theme":"cosmic"}
            pack = build_premium_campaign(STORY, date(2026,11,12), "comfyui",
                                          folder, approval=record,
                                          image_generator=fake_ai, poster_maker=fake_poster,
                                          synopsis_fetcher=lambda _: "A verified source preview of magical portals")
            self.assertTrue(pack["actual_new_art_generated"])
            self.assertEqual(pack["visual_theme"], "cosmic")
            self.assertIn("magic portals", calls[0])
            self.assertIn("source preview of magical portals", calls[0])
            self.assertFalse(pack["synopsis_is_editorially_verified"])

    def test_publishing_requires_visual_approval(self):
        with self.assertRaises(ValueError):
            build_premium_campaign(STORY, date(2026,11,12), approval={},
                                   publish=True)
        with self.assertRaises(ValueError):
            build_premium_campaign(STORY, date(2026,11,12),
                                   art_mode="comfyui", approval={
                                       "v10_visual_policy_approved":True
                                   }, publish=True)

    def test_safe_preview_export(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            def fake_campaign(item, day, art_mode, outdir, approval=None, publish=False):
                target = source / "daily" / "poster.jpg"
                target.parent.mkdir(parents=True,exist_ok=True)
                Image.new("RGB", (1080, 1350), "purple").save(target, "JPEG")
                return {"poster":str(target)}
            with patch("campaign_v9.load_approvals", return_value={}):
                report = run_v10(limit=1, discovery_func=lambda limit:[STORY],
                                 campaign_builder=fake_campaign,
                                 outdir=str(source/"campaign"),
                                 export_dir=source/"phone")
            self.assertEqual(len(report["prepared"]), 1)
            self.assertEqual(len(report["published"]), 0)
            self.assertTrue(report["dry_run"])
            self.assertEqual(len(report["exported_jpgs"]),1)


if __name__ == "__main__":
    unittest.main()
