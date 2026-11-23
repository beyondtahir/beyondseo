"""A permitted supplied capture can continue an audit when native DNS is unavailable."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo.evidence import capture_quality, import_captures
from beyondseo.findings import audit_report
from beyondseo.research import profile, verify_reference
from beyondseo.review import read_json, read_pages


class CaptureImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.manifest = self.root / "captures.json"
        self.out = self.root / "snapshot"
        (self.root / "home.html").write_text(
            '<html lang="en"><head><title>Example agency</title>'
            "<title>Conflicting title</title></head><body><main><h1>AI services</h1>"
            "<p>We implement AI assistants for retailers in Pakistan.</p>"
            '<script type="application/ld+json">{"@type":"Organization"}</script>'
            "</main></body></html>",
            encoding="utf-8",
        )
        self.record = {
            "url": "https://example.com/",
            "captured_at": "2026-01-15T12:30:00Z",
            "method": "host_browser_dom",
            "tool": "fixture browser",
            "access_context": "public",
            "html_path": "home.html",
            "complete": True,
        }

    def manifest_for(self, records=None):
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "target": "https://example.com/",
                    "captures": records if records is not None else [self.record],
                }
            ),
            encoding="utf-8",
        )

    def test_dns_blocked_audit_and_profile_continue_without_fabricating_http(self):
        self.manifest_for()
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("fixture DNS denied")) as dns:
            result = import_captures(self.manifest, self.out)
            packet = profile(self.out, self.root / "profile")
            report = audit_report(self.out, self.root / "audit")
        dns.assert_not_called()
        self.assertEqual(result["native_requests"], 0)
        self.assertEqual(result["inspected"], 1)
        page = read_pages(self.out)[0]
        self.assertEqual(page["status"], 0)
        self.assertEqual(page["headers"], {})
        self.assertFalse(page["imported_capture"]["http_status_observed"])
        self.assertEqual(packet["page_evidence"][0]["title"], "Example agency")
        self.assertIn("multiple_titles", {finding["code"] for finding in report["findings"]})
        self.assertTrue(report["crawl_coverage"]["coverage_limited"])
        self.assertTrue(
            all(
                f["evidence_refs"][0]["representation"] == "host_browser_dom"
                for f in report["findings"]
            )
        )

    def test_import_cannot_create_missing_content_schema_or_reachability_claims(self):
        self.manifest_for()
        import_captures(self.manifest, self.out)
        page = read_pages(self.out)[0]
        self.assertTrue(capture_quality(page)["usable"])
        self.assertFalse(capture_quality(page)["absence_supported"])
        codes = {item["code"] for item in read_json(self.out / "issues.json")}
        self.assertNotIn("missing_description", codes)
        self.assertNotIn("canonical_not_declared", codes)
        self.assertIn("capture_incomplete", codes)
        reference = {"url": page["url"], "quote": "We implement AI assistants for retailers"}
        self.assertEqual(
            verify_reference(reference, {page["url"]: page})["representation"], "host_browser_dom"
        )
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            verify_reference(reference, {page["url"]: page}, require_complete=True)
        self.assertEqual(read_json(self.out / "robots.json"), {})
        readiness = read_json(self.out / "readiness.json")
        self.assertIsNone(readiness["pages"][0]["in_observed_sitemap"])
        self.assertIsNone(readiness["sitemap_urls_observed"])
        self.assertIsNone(readiness["pages"][0]["index_signals_selected"]["indexability_candidate"])

    def test_challenge_html_is_not_accepted_as_website_content(self):
        (self.root / "home.html").write_text(
            '<title>Just a moment...</title><div class="cf-chl-test">Checking browser</div>'
        )
        self.manifest_for()
        result = import_captures(self.manifest, self.out)
        self.assertEqual(result["inspected"], 0)
        self.assertIn("Challenge", read_pages(self.out)[0]["error"])

    def test_observed_200_does_not_invent_header_or_indexability_evidence(self):
        self.record["http_status"] = 200
        self.manifest_for()
        import_captures(self.manifest, self.out)
        readiness = read_json(self.out / "readiness.json")["pages"][0]
        self.assertIsNone(readiness["index_signals_http"])
        selected = readiness["index_signals_selected"]
        self.assertIsNone(selected["x_robots_tag"])
        self.assertIsNone(selected["indexability_candidate"])
        self.assertFalse(selected["headers_observed"])

    def test_native_crawl_monitor_and_compare_cannot_overwrite_import(self):
        from beyondseo.engine import Crawler
        from beyondseo.monitor import watch
        from beyondseo.network import Config
        from beyondseo.review import compare

        self.manifest_for()
        import_captures(self.manifest, self.out)
        before = (self.out / "pages.jsonl").read_bytes()
        config = Config("https://example.com/")
        for operation in (
            lambda: Crawler(config, self.out, resume=True),
            lambda: watch(config, self.out, cycles=1, interval=60),
            lambda: compare(self.out, self.out, self.root / "comparison"),
        ):
            with self.assertRaisesRegex(ValueError, "requires native crawl snapshots"):
                operation()
        self.assertEqual(before, (self.out / "pages.jsonl").read_bytes())
        self.assertFalse((self.out / "crawl.sqlite3").exists())
        self.assertFalse((self.out / "watch.json").exists())

    def test_write_failure_does_not_leave_an_incomplete_output_folder(self):
        self.manifest_for()
        with patch("beyondseo.engine.write_json", side_effect=OSError("fixture disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                import_captures(self.manifest, self.out)
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.root.glob(".beyondseo-capture-*")))
        self.assertTrue((self.root / "home.html").exists())

    def test_cli_import_to_audit_and_branded_html_preserves_limits(self):
        self.manifest_for()
        source = Path(__file__).resolve().parents[1] / "src"
        env = dict(os.environ, PYTHONPATH=str(source))

        def cli(*args, expected=0):
            result = subprocess.run(
                [sys.executable, "-m", "beyondseo", *map(str, args)],
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
            return result

        cli("capture-import", "--input", self.manifest, "--out", self.out)
        cli("entity-review", "--crawl", self.out, "--out", self.root / "entity")
        cli("audit", "--crawl", self.out, "--offline", "--out", self.root / "audit")
        cli(
            "present",
            "--audit",
            self.root / "audit/audit.json",
            "--format",
            "html",
            "--out",
            self.root / "report",
        )
        report = read_json(self.root / "audit/audit.json")
        self.assertTrue(report["crawl_coverage"]["coverage_limited"])
        self.assertEqual(report["crawl_coverage"]["native_requests"], 0)
        html = next((self.root / "report").glob("*.html")).read_text(encoding="utf-8")
        self.assertIn("BeyondSEO", html)
        self.assertIn("Supplied page capture", html)

    def test_failed_capture_does_not_become_a_success_or_missing_content(self):
        self.record.update(error="Browser navigation permission denied", html_path=None)
        self.manifest_for()
        result = import_captures(self.manifest, self.out)
        self.assertEqual(result["status"], "no_usable_captures")
        self.assertEqual(result["inspected"], 0)
        self.assertFalse(capture_quality(read_pages(self.out)[0])["usable"])
        codes = {item["code"] for item in read_json(self.out / "issues.json")}
        self.assertEqual(codes, {"fetch_failed"})

    def test_authenticated_or_unrelated_pages_are_refused(self):
        for changes in (
            {"access_context": "authenticated"},
            {"url": "https://other.example/"},
            {"final_url": "https://other.example/login"},
        ):
            with self.subTest(changes=changes):
                self.manifest_for([{**self.record, **changes}])
                with self.assertRaises(ValueError):
                    import_captures(self.manifest, self.out)
                self.assertFalse(self.out.exists())

    def test_import_preserves_native_snapshot_and_refuses_duplicate_urls(self):
        self.manifest_for([self.record, self.record])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            import_captures(self.manifest, self.out)
        self.assertFalse(self.out.exists())
        self.manifest_for()
        self.out.mkdir()
        (self.out / "native-error.txt").write_text("keep native DNS evidence")
        with self.assertRaisesRegex(ValueError, "existing evidence"):
            import_captures(self.manifest, self.out)
        self.assertEqual((self.out / "native-error.txt").read_text(), "keep native DNS evidence")

    def test_path_escape_and_unknown_method_are_refused_before_writes(self):
        for changes in (
            {"html_path": "../secret.html"},
            {"method": "search_snippet"},
            {"http_status": True},
            {"captured_at": "2026-01-15"},
        ):
            with self.subTest(changes=changes):
                self.manifest_for([{**self.record, **changes}])
                with self.assertRaises(ValueError):
                    import_captures(self.manifest, self.out)
                self.assertFalse(self.out.exists())

    def test_symlinked_html_is_not_imported(self):
        try:
            (self.root / "linked.html").symlink_to(self.root / "home.html")
        except OSError:
            self.skipTest("Host does not permit symlink creation")
        self.record["html_path"] = "linked.html"
        self.manifest_for()
        with self.assertRaisesRegex(ValueError, "symlink"):
            import_captures(self.manifest, self.out)


if __name__ == "__main__":
    unittest.main()
