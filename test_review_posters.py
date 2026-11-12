import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from review_posters import export_posters


class ReviewPosterTests(unittest.TestCase):
    def test_export_contact_sheet_and_unique_files(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            entries = []
            for i in range(2):
                folder = base / f"story{i}"
                folder.mkdir()
                filename = folder / "poster.png"
                Image.new("RGB", (1080, 1350), (35 + i, 49, 79)).save(filename)
                entries.append({"title": f"Story {i}", "story_url": f"https://cartoontamilan.in/novel/story{i}",
                                "poster": str(filename)})
            report = base / "report.json"
            report.write_text(json.dumps({"success": entries}), encoding="utf-8")
            out = base / "previews"
            downloads = base / "downloads"
            summary = export_posters(report, out, downloads)
            self.assertEqual(summary["exported"], 2)
            self.assertTrue((out / "contact_sheet.png").is_file())
            self.assertTrue((downloads / "contact_sheet.png").is_file())
            self.assertEqual(len(list(downloads.glob("[0-9]*_*.png"))), 2)
            self.assertIn("story1", (out / "story_index.txt").read_text(encoding="utf-8"))

    def test_no_successful_posters(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            report = base / "report.json"
            report.write_text('{"success":[]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                export_posters(report, base / "preview")


if __name__ == "__main__":
    unittest.main()
