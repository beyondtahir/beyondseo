"""Host DOM observations preserve access, timestamps and public-proof boundaries."""

import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo.backlinks import import_browser_evidence
from beyondseo.cli import main
from beyondseo.reputation import assess


class HostBrowserEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = {
            "kind": "source_page",
            "url": "https://publisher.example/article",
            "final_url": "https://publisher.example/article",
            "captured_at": "2026-10-01T12:00:00+00:00",
            "browser": "Permitted Chrome via host tools",
            "visibility": "public_logged_out",
            "access_state": "content",
            "title": "A source article",
            "text": "Example Brand is mentioned in this observed article.",
            "links": [
                {
                    "url": "https://example.com/service",
                    "anchor": "Example Brand service",
                    "rel": ["nofollow"],
                }
            ],
        }

    def run_import(self, captures=None, name="result"):
        path = self.root / "input.json"
        path.write_text(
            json.dumps({"captures": captures if captures is not None else [self.capture]})
        )
        with patch(
            "socket.create_connection",
            side_effect=AssertionError("Importer must not make a network request"),
        ):
            return import_browser_evidence(
                path, "https://example.com", self.root / name, "Example Brand"
            )

    def test_public_dom_link_retains_actual_attributes_without_http_or_freshness_claim(self):
        result = self.run_import()
        row = result["results"][0]
        self.assertEqual(row["verification"], "link_observed")
        self.assertEqual(row["target_links"][0]["rel"], ["nofollow"])
        self.assertIsNone(row["status"])
        self.assertEqual(row["checked_at"], self.capture["captured_at"])
        self.assertEqual(result["checked_at"], self.capture["captured_at"])
        self.assertEqual(result["capture_source"], "host_browser")
        self.assertTrue(result["operator_recorded"])
        self.assertEqual(result["network_requests"], 0)
        self.assertFalse(result["browser_launched"])
        self.assertEqual(result["observed_link_pages"], 1)
        self.assertIsNone(row["source_index_signals"]["googlebot_noindex_observed"])
        self.assertEqual(row["source_index_signals"]["schema_status"], "not_assessed")
        self.assertNotIn("total_backlinks", result)
        self.assertNotIn("domain_authority", result)
        saved = json.loads((self.root / "result/backlinks.json").read_text())
        self.assertEqual(saved["results"][0]["capture_source"], "host_browser")
        if os.name != "nt":
            self.assertEqual((self.root / "result/backlinks.json").stat().st_mode & 0o777, 0o600)

    def test_authenticated_and_unknown_visibility_never_become_public_link_or_mention_proof(self):
        for visibility, verdict in [
            ("authenticated", "link_visible_in_authenticated_session"),
            ("unknown", "unverified_access"),
        ]:
            capture = {**self.capture, "visibility": visibility}
            result = self.run_import([capture], visibility)
            self.assertEqual(result["observed_link_pages"], 0)
            self.assertEqual(result["observed_mention_pages"], 0)
            self.assertEqual(result["results"][0]["verification"], verdict)
            score = assess(result)
            self.assertFalse(
                any(r["observed_link"] or r["observed_mention"] for r in score["sources"])
            )

    def test_challenge_login_wall_and_missing_access_state_do_not_establish_content_or_absence(
        self,
    ):
        for state in ("challenge", "login_wall", "unknown", None):
            capture = {
                **self.capture,
                "access_state": state,
                "title": "Performing security verification",
                "text": "Example Brand performing security verification",
            }
            if state is None:
                capture.pop("access_state")
            result = self.run_import([capture], str(state))
            row = result["results"][0]
            self.assertEqual(result["observed_link_pages"], 0)
            self.assertEqual(row["verification"], "unverified_access")
            self.assertEqual(row["target_links"], [])
            self.assertEqual(row["brand_mentions"], [])
            self.assertIsNone(row["missing_content_candidate"])
            self.assertIsNone(row["status"])
            self.assertEqual(row["access_state"], state or "unknown")

    def test_absent_snapshot_link_is_not_a_conclusive_whole_page_negative(self):
        capture = {**self.capture, "links": [], "text": "A small supplied excerpt"}
        result = self.run_import([capture])
        self.assertEqual(
            result["results"][0]["verification"], "no_target_link_observed_in_snapshot"
        )
        self.assertTrue(result["results"][0]["coverage_limited"])
        self.assertEqual(result["results"][0]["robots_decision"], "unknown")

    def test_snippets_search_results_and_mislabeled_known_serps_are_rejected(self):
        for index, kind in enumerate(("search_results", "snippet", "search_snippet")):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "source_page"):
                self.run_import([{**self.capture, "kind": kind}], f"bad-{index}")
        with self.assertRaisesRegex(ValueError, "search-results URL"):
            self.run_import(
                [
                    {
                        **self.capture,
                        "url": "https://www.google.com/search?q=brand",
                        "final_url": None,
                    }
                ],
                "serp",
            )

    def test_duplicates_keep_all_provenance_and_choose_latest_actual_capture(self):
        older = copy.deepcopy(self.capture)
        newer = {
            **self.capture,
            "url": "https://publisher.example/old-route",
            "captured_at": "2026-10-02T12:00:00+02:00",
            "visibility": "authenticated",
            "title": "Newer observation",
        }
        result = self.run_import([newer, older])
        self.assertEqual(result["duplicates_consolidated"], 1)
        self.assertEqual(result["observations_imported"], 2)
        self.assertEqual(result["sources_checked"], 1)
        row = result["results"][0]
        self.assertEqual(row["title"], "Newer observation")
        self.assertEqual(row["checked_at"], newer["captured_at"])
        self.assertEqual(row["verification"], "link_visible_in_authenticated_session")
        self.assertEqual(result["observed_link_pages"], 0)
        self.assertEqual(
            {p["captured_at"] for p in row["provenance"]},
            {older["captured_at"], newer["captured_at"]},
        )
        raw = json.loads((self.root / "result/browser-captures.json").read_text())
        self.assertEqual(len(raw["captures"]), 2)

    def test_invalid_dates_urls_unknown_fields_and_bounds_fail_before_output(self):
        variants = [
            {**self.capture, "captured_at": "2026-10-01"},
            {**self.capture, "captured_at": "not-a-date"},
            {**self.capture, "captured_at": "2099-10-01T00:00:00Z"},
            {**self.capture, "url": "https://user:password@publisher.example/page"},
            {**self.capture, "url": "https://publisher.example/login?access_token=private"},
            {**self.capture, "url": "file:///private/file"},
            {**self.capture, "cookies": "must not be imported"},
            {**self.capture, "status": 200},
            {**self.capture, "text": "x" * 100001},
        ]
        for index, capture in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.run_import([capture], f"bad-{index}")
            self.assertFalse((self.root / f"bad-{index}").exists())
        for captures in ([], [self.capture] * 31):
            with self.assertRaises(ValueError):
                self.run_import(captures)

    def test_own_site_links_are_not_counted_as_external_backlinks(self):
        result = self.run_import(
            [{**self.capture, "url": "https://example.com/about", "final_url": None}]
        )
        self.assertEqual(result["observed_link_pages"], 0)
        self.assertEqual(result["results"][0]["verification"], "same_site_link_observed")

    def test_cli_imports_source_observations_and_rejects_a_snippet_without_output(self):
        source = self.root / "observations.json"
        source.write_text(json.dumps([self.capture]))
        out = self.root / "cli-output"
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = main(
                [
                    "browser-evidence",
                    "--input",
                    str(source),
                    "--target",
                    "https://example.com",
                    "--brand",
                    "Example Brand",
                    "--out",
                    str(out),
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["observed_link_pages"], 1)
        source.write_text(json.dumps([{**self.capture, "kind": "search_snippet"}]))
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = main(
                [
                    "browser-evidence",
                    "--input",
                    str(source),
                    "--target",
                    "https://example.com",
                    "--out",
                    str(self.root / "bad-cli"),
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("source_page", stderr.getvalue())
        self.assertFalse((self.root / "bad-cli").exists())


if __name__ == "__main__":
    unittest.main()
