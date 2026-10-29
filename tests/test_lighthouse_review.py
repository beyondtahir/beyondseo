"""Deterministic offline Lighthouse evidence and report tests."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from beyondseo.cli import main
from beyondseo.review import lighthouse_review


class LighthouseReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "input.json"
        self.out = self.root / "review"

    def write(self, value):
        self.source.write_text(json.dumps(value), encoding="utf-8")

    def test_lab_data_never_claims_real_user_inp(self):
        self.write(
            {
                "requestedUrl": "https://example.com/",
                "finalUrl": "https://example.com/",
                "fetchTime": "2026-01-01T00:00:00Z",
                "lighthouseVersion": "12.0",
                "configSettings": {"formFactor": "mobile"},
                "categories": {"performance": {"score": 0.8}},
                "audits": {
                    "largest-contentful-paint": {"numericValue": 1800, "displayValue": "1.8 s"},
                    "total-blocking-time": {"numericValue": 100, "displayValue": "100 ms"},
                    "cumulative-layout-shift": {"numericValue": 0.02, "displayValue": "0.02"},
                },
            }
        )
        result = lighthouse_review(self.source, self.out)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["performance_score_0_to_100"], 80)
        self.assertIn("not INP", result["limits"])
        self.assertEqual(result["metrics"][0]["value"], 1800)
        self.assertEqual(result["metrics"][3]["status"], "not_measured")
        self.assertIn("not real-user field data", (self.out / "lighthouse-review.md").read_text())

    def test_failed_run_withholds_even_preexisting_scores(self):
        self.write(
            {
                "runtimeError": {"code": "NO_FCP"},
                "categories": {"performance": {"score": 0.99}},
                "audits": {"largest-contentful-paint": {"numericValue": 1000}},
            }
        )
        result = lighthouse_review(self.source, self.out)
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["performance_score_0_to_100"])
        self.assertTrue(
            all(row["value"] is None and row["status"] == "run_failed" for row in result["metrics"])
        )

    def test_bad_numbers_and_not_applicable_are_not_measurements(self):
        self.write(
            {
                "audits": {
                    "largest-contentful-paint": {"numericValue": -1},
                    "cumulative-layout-shift": {
                        "numericValue": 0.2,
                        "scoreDisplayMode": "notApplicable",
                    },
                    "total-blocking-time": {"numericValue": True},
                },
                "categories": {"performance": {"score": 2}},
            }
        )
        result = lighthouse_review(self.source, self.out)
        self.assertTrue(all(row["value"] is None for row in result["metrics"]))
        self.assertIsNone(result["performance_score_0_to_100"])

    def test_pagespeed_wrapper_and_branded_report(self):
        self.write(
            {
                "lighthouseResult": {
                    "audits": {
                        "largest-contentful-paint": {"numericValue": 1200, "displayValue": "1.2 s"}
                    }
                }
            }
        )
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                main(["lighthouse-review", "--input", str(self.source), "--out", str(self.out)]), 0
            )
            self.assertEqual(
                main(
                    [
                        "present",
                        "--lighthouse",
                        str(self.out / "lighthouse-review.json"),
                        "--out",
                        str(self.root / "report"),
                        "--format",
                        "html",
                    ]
                ),
                0,
            )
        html = (self.root / "report/report.html").read_text()
        self.assertIn("1.2 s", html)
        self.assertIn("not real-user field data", html)
        self.assertIn("not INP", html)

    def test_missing_report_or_duplicate_output_fails(self):
        self.write({"audits": {}})
        lighthouse_review(self.source, self.out)
        with self.assertRaisesRegex(ValueError, "already exists"):
            lighthouse_review(self.source, self.out)
        self.write({"not_a_report": True})
        with self.assertRaisesRegex(ValueError, "Lighthouse audits"):
            lighthouse_review(self.source, self.root / "bad")


if __name__ == "__main__":
    unittest.main()
