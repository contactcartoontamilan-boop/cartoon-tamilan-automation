"""Offline V14 FB/Instagram/X publisher tests. Never contact social APIs."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ctos.creative import SIZES
from ctos.platforms import PLATFORM_IMAGE
from ct_v14_social_queue import prepare_social_queue
from ct_v14_social_publish import (load_drafts, run, publish_x_image, main)

URL = "https://cartoontamilan.in/novel/amrutha-ulaga-perangadi/"


class FakeResponse:
    def __init__(self, code, payload=None):
        self.status_code = code
        self.payload = payload

    def json(self):
        if self.payload is None:
            raise ValueError("Empty response")
        return self.payload


class FakeXHTTP:
    def __init__(self, pending=False):
        self.calls = []
        self.pending = pending

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if url.endswith("/initialize"):
            return FakeResponse(201, {"data": {"id": "1234567890"}})
        if url.endswith("/append"):
            return FakeResponse(204)  # X append may succeed with no JSON body.
        if url.endswith("/finalize"):
            return FakeResponse(200, {"data": {"id": "1234567890",
                                "processing_info": {"state": "pending", "check_after_secs": 1}
                                if self.pending else None}})
        if url.endswith("/tweets"):
            return FakeResponse(201, {"data": {"id": "9876543210"}})
        raise AssertionError("Unexpected POST: " + url)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(200, {"data": {"processing_info": {"state": "succeeded"}}})


class PublishTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bundle = self.root / "2026-11-13" / "story1"
        media = self.bundle / "media"
        media.mkdir(parents=True)
        assets = {}
        for variant, size in SIZES.items():
            path = media / (variant + ".jpg")
            Image.new("RGB", size, "#304b84").save(path, "JPEG")
            assets[variant] = "media/" + variant + ".jpg"
        manifest = {"story": {"title": "அம்ருதா", "link": URL},
                    "assets": assets, "published": False,
                    "status": "draft_review_required"}
        (self.bundle / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        posts = []
        for platform in ("instagram", "facebook", "x"):
            variant = PLATFORM_IMAGE[platform]
            image = media / (variant + ".jpg")
            posts.append({
                "platform": platform, "story_title": "அம்ருதா",
                "story_url": URL,
                "image_file": str(image.relative_to(self.root)),
                "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                "caption": "புதிய தமிழ் கதை! " + URL,
                "status": "draft_review_required", "published": False,
            })
        self.preview = {"published": False, "live_publishing": False,
                        "requires_human_review": True,
                        "story_manifests": [str((self.bundle / "manifest.json").relative_to(self.root))],
                        "posts": posts}
        self.save_preview()
        prepare_social_queue(self.root)
        self.journal = self.root / "test_journal.sqlite3"

    def save_preview(self):
        (self.root / "image_post_preview.json").write_text(
            json.dumps(self.preview, ensure_ascii=False), encoding="utf-8")

    def test_dry_run_does_not_call_api_or_write_journal(self):
        with patch("ct_v14_social_publish._publish") as sender:
            result = run(self.root, journal=self.journal)
            sender.assert_not_called()
        self.assertEqual(result["status"], "dry_run_only")
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual({p["platform"] for p in result["items"]},
                         {"facebook", "instagram", "x"})
        self.assertFalse(self.journal.exists())

    def test_missing_credentials_and_live_flags_block_all(self):
        with patch("ct_v14_social_publish._require_approved"):
            with self.assertRaises(PermissionError):
                run(self.root, live=True, confirm="PUBLISH_REVIEWED_POSTS",
                    journal=self.journal)
        self.assertFalse(self.journal.exists())

    def test_missing_manual_approval_blocks_live(self):
        with patch("ct_v14_social_publish._require_live_access"):
            with self.assertRaises(PermissionError):
                run(self.root, live=True, confirm="PUBLISH_REVIEWED_POSTS",
                    journal=self.journal)
        self.assertFalse(self.journal.exists())

    def test_modified_image_rejected_before_any_publish(self):
        image = self.bundle / "media" / "instagram_feed.jpg"
        Image.new("RGB", SIZES["instagram_feed"], "red").save(image, "JPEG")
        with self.assertRaisesRegex(ValueError, "changed"):
            load_drafts(self.root)

    def test_tampered_queue_caption_and_identity_rejected(self):
        path = self.root / "social_queue.json"
        queue = json.loads(path.read_text(encoding="utf-8"))
        queue["image_post_queue"][0]["caption"] = "New unreviewed copy"
        path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "identity"):
            load_drafts(self.root)

    def test_success_then_idempotent_no_duplicate(self):
        calls = []
        def sender(item):
            calls.append(item["platform"])
            return {"id": str(100 + len(calls))}
        with patch("ct_v14_social_publish._require_approved"), patch(
                "ct_v14_social_publish._require_live_access"):
            first = run(self.root, live=True, journal=self.journal, sender=sender)
            second = run(self.root, live=True, journal=self.journal, sender=sender)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(r["status"] == "published" for r in first["results"]))
        self.assertTrue(all(r["status"] == "already_attempted" for r in second["results"]))
        with sqlite3.connect(self.journal) as conn:
            count = conn.execute("SELECT count(*) FROM deliveries").fetchone()[0]
        self.assertEqual(count, 3)

    def test_failed_call_marked_uncertain_and_not_retried(self):
        calls = []
        def sender(item):
            calls.append(item["platform"])
            if item["platform"] == "instagram":
                raise TimeoutError("simulated network timeout")
            return {"id": "12345"}
        with patch("ct_v14_social_publish._require_approved"), patch(
                "ct_v14_social_publish._require_live_access"):
            first = run(self.root, live=True, journal=self.journal, sender=sender)
            second = run(self.root, live=True, journal=self.journal, sender=sender)
        self.assertEqual(first["status"], "needs_reconciliation")
        self.assertEqual(first["results"][1]["status"], "uncertain")
        self.assertEqual(calls.count("instagram"), 1)
        self.assertEqual(second["results"][1]["previous_status"], "uncertain")

    def test_live_preflight_all_before_first_send(self):
        calls = []
        def block_x(item, confirm):
            if item["platform"] == "x":
                raise ValueError("X not authorized")
        with patch("ct_v14_social_publish._require_approved"), patch(
                "ct_v14_social_publish._require_live_access", side_effect=block_x):
            with self.assertRaisesRegex(ValueError, "not authorized"):
                run(self.root, live=True, journal=self.journal,
                    sender=lambda i: calls.append(i))
        self.assertEqual(calls, [])
        self.assertFalse(self.journal.exists())

    def test_x_image_chunked_upload_and_post(self):
        http = FakeXHTTP()
        image = self.bundle / "media" / "x_landscape.jpg"
        result = publish_x_image(image, "Tamil story", session=http, auth=object())
        self.assertEqual(result["id"], "9876543210")
        self.assertEqual(len(http.calls), 4)
        self.assertTrue(http.calls[0][1].endswith("/initialize"))
        self.assertTrue(http.calls[1][1].endswith("/append"))
        self.assertEqual(http.calls[1][2]["data"]["segment_index"], 0)
        self.assertTrue(http.calls[-1][1].endswith("/tweets"))
        self.assertEqual(http.calls[-1][2]["json"]["media"]["media_ids"], ["1234567890"])

    def test_x_processing_waits_for_success(self):
        http = FakeXHTTP(pending=True)
        image = self.bundle / "media" / "x_landscape.jpg"
        result = publish_x_image(image, "Tamil story", session=http, auth=object(),
                                 sleeper=lambda seconds: None)
        self.assertEqual(result["id"], "9876543210")
        self.assertEqual([c[0] for c in http.calls], ["POST", "POST", "POST", "GET", "POST"])

    def test_x_caption_limit_blocks_network(self):
        http = FakeXHTTP()
        image = self.bundle / "media" / "x_landscape.jpg"
        with self.assertRaisesRegex(ValueError, "280-character"):
            publish_x_image(image, "a" * 281, session=http, auth=object())
        self.assertEqual(http.calls, [])

    def test_cli_default_is_dry_run(self):
        with patch("builtins.print") as output:
            self.assertEqual(main(["--outdir", str(self.root)]), 0)
            self.assertEqual(output.call_count, 1)


if __name__ == "__main__":
    unittest.main()
