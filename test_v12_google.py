import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from v12_google import (ga4_daily_pageviews, export_ga4_csv, search_console_queries,
                        pagespeed_mobile, refresh_google_token)


class GoogleReadOnlyTests(unittest.TestCase):
    def test_ga4_response_is_real_observed_date_and_count(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "rows": [
                {"dimensionValues": [{"value": "20261111"}],
                 "metricValues": [{"value": "73"}]}
            ]
        }
        session = Mock()
        session.post.return_value = response
        rows = ga4_daily_pageviews("1234", "test_token", "2026-11-11", "2026-11-12",
                                   session=session)
        self.assertEqual(rows[0]["date"], "2026-11-11")
        self.assertEqual(rows[0]["pageviews"], 73)
        self.assertIn("analyticsdata.googleapis.com", session.post.call_args.args[0])
        with tempfile.TemporaryDirectory() as folder:
            csv_path = export_ga4_csv(rows, Path(folder)/"ga4.csv")
            self.assertIn("2026-11-11,73,ga4", csv_path.read_text(encoding="utf-8"))

    def test_ga4_no_data_does_not_overwrite_existing_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"stats.csv"
            path.write_text("existing important data", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_ga4_csv([], path)
            self.assertEqual(path.read_text(encoding="utf-8"), "existing important data")

    def test_search_console_property_guard(self):
        with self.assertRaises(ValueError):
            search_console_queries("sc-domain:notmywebsite.com", "token",
                                   "2026-11-10", "2026-11-12")
        result = Mock()
        result.raise_for_status.return_value = None
        result.json.return_value = {"rows": [{"keys": ["tamil novels"],
                                              "clicks": 7, "impressions": 150,
                                              "ctr": 0.0467, "position": 12.7}]}
        session = Mock()
        session.post.return_value = result
        rows = search_console_queries("sc-domain:cartoontamilan.in", "token",
                                      "2026-11-10", "2026-11-12",
                                      session=session)
        self.assertEqual(rows[0]["clicks"], 7)

    def test_pagespeed_does_not_invent_scores(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"lighthouseResult": {
            "categories": {"performance": {"score": 0.74},
                           "seo": {"score": 0.90}}}}
        session = Mock()
        session.get.return_value = response
        result = pagespeed_mobile("https://cartoontamilan.in/", session=session)
        self.assertEqual(result["scores"]["performance"], 74)
        self.assertIsNone(result["scores"]["accessibility"])
        with self.assertRaises(ValueError):
            pagespeed_mobile("https://evil.example/", session=session)

    def test_oauth_refresh_with_mock(self):
        res = Mock()
        res.raise_for_status.return_value = None
        res.json.return_value = {"access_token":"fresh_token"}
        session = Mock()
        session.post.return_value = res
        self.assertEqual(refresh_google_token("client","secret","refresh", session=session),
                         "fresh_token")


if __name__ == "__main__":
    unittest.main()
