"""Deterministic audit-depth, diagnostics and verification regressions."""

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from beyondseo.cli import main
from beyondseo.doctor import check_environment
from beyondseo.engine import Crawler
from beyondseo.extract import extract, page_findings
from beyondseo.network import Config, Transport
from beyondseo.publishing import LocalStore, apply_change, stage


class DepthValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.hits = []

    def tearDown(self):
        self.tmp.cleanup()

    def response(self, url, **kwargs):
        self.hits.append(url)
        path = urlsplit(url).path
        headers = {"content-type": "text/html"}
        if path == "/robots.txt":
            return 200, {}, b"User-agent: *\nDisallow: /private\n"
        if "sitemap" in path:
            if path == "/sitemap.xml":
                paths = [
                    "/private",
                    "/missing",
                    "/about",
                    "/contact",
                    "/services",
                    "/portfolio",
                ] + [f"/blog/{n}" for n in range(30)]
                return (
                    200,
                    {"content-type": "application/xml"},
                    (
                        "<urlset>"
                        + "".join(f"<url><loc>https://example.test{p}</loc></url>" for p in paths)
                        + "</urlset>"
                    ).encode(),
                )
            return 404, {}, b""
        if path == "/missing":
            return 404, headers, b"<title>Gone</title>"
        html = (
            f"<title>{path}</title><main><h1>Service {path}</h1>Useful customer information.</main>"
        )
        if path == "/":
            html += '<a href="/about">About us</a><a href="/contact">Contact</a>'
        return 200, headers, html.encode()

    def test_standard_budget_priority_and_coverage(self):
        out = self.root / "standard"
        with (
            patch.object(Transport, "once", side_effect=self.response),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                main(
                    [
                        "crawl",
                        "https://example.test",
                        "--out",
                        str(out),
                        "--mode",
                        "http",
                        "--delay",
                        "0",
                        "--quiet",
                    ]
                ),
                0,
            )
        summary = json.loads((out / "summary.json").read_text())
        self.assertEqual(summary["attempted_urls"], 15)
        self.assertGreater(summary["coverage"]["pending"], 0)
        pages = [json.loads(line)["url"] for line in (out / "pages.jsonl").read_text().splitlines()]
        self.assertEqual(pages[0], "https://example.test/")
        for path in ("/about", "/contact", "/services", "/portfolio"):
            self.assertIn("https://example.test" + path, pages)
        self.assertNotIn("https://example.test/robots.txt", pages)
        self.assertNotIn("https://example.test/sitemap.xml", pages)

    def test_exact_urls_and_continue_never_fetch_other_pages(self):
        out = self.root / "selected"
        common = [
            "crawl",
            "https://example.test",
            "--out",
            str(out),
            "--only-url",
            "/contact",
            "--only-url",
            "/about",
            "--mode",
            "http",
            "--delay",
            "0",
            "--quiet",
        ]
        with (
            patch.object(Transport, "once", side_effect=self.response),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(common + ["--max-pages", "1"]), 0)
            first = json.loads((out / "summary.json").read_text())
            self.assertEqual(first["attempted_urls"], 1)
            self.assertEqual(main(common + ["--resume", "--next-pages", "1"]), 0)
        pages = [json.loads(line)["url"] for line in (out / "pages.jsonl").read_text().splitlines()]
        self.assertEqual(set(pages), {"https://example.test/contact", "https://example.test/about"})
        self.assertEqual(self.hits.count("https://example.test/contact"), 1)
        self.assertEqual(self.hits.count("https://example.test/about"), 1)
        self.assertNotIn("https://example.test/", self.hits)

    def test_failures_consume_budget_and_sitemap_members_stay_unverified(self):
        config = Config(
            "https://example.test",
            selected_urls=["/private", "/missing"],
            max_pages=2,
            delay=0,
            retries=0,
        )
        with patch.object(Transport, "once", side_effect=self.response):
            crawler = Crawler(config, self.root / "blocked")
            try:
                crawler.log = lambda _: None
                summary = crawler.run()
            finally:
                crawler.close()
        self.assertEqual(summary["coverage"]["attempted"], 2)
        self.assertEqual(summary["coverage"]["inspected"], 0)
        self.assertEqual(summary["coverage"]["blocked_or_failed"], 2)
        maps = json.loads((self.root / "blocked/sitemaps.json").read_text())["urls"]
        by_url = {m["url"]: m for m in maps}
        self.assertEqual(by_url["https://example.test/about"]["verification"], "not_inspected")
        issues = json.loads((self.root / "blocked/issues.json").read_text())
        conflicts = [i for i in issues if i["code"] == "sitemap_url_conflict"]
        self.assertEqual([i["url"] for i in conflicts], ["https://example.test/missing"])

    def test_quick_keeps_discovery_but_inspects_one_page(self):
        out = self.root / "quick"
        with (
            patch.object(Transport, "once", side_effect=self.response),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(
                main(
                    [
                        "crawl",
                        "https://example.test",
                        "--audit-depth",
                        "quick",
                        "--out",
                        str(out),
                        "--mode",
                        "http",
                        "--delay",
                        "0",
                        "--quiet",
                    ]
                ),
                0,
            )
        summary = json.loads((out / "summary.json").read_text())
        self.assertEqual(summary["attempted_urls"], 1)
        self.assertGreater(summary["sitemap_urls"], 1)
        self.assertNotIn("https://example.test/about", self.hits)

    def test_bad_selected_url_rejected_before_fetch(self):
        with self.assertRaisesRegex(ValueError, "Selected URLs"):
            Config("https://example.test", selected_urls=["https://outside.test/"])

    def test_deeper_checks_do_not_claim_complete_schema_or_layout_shift(self):
        html = '<title>Service</title><h1>Service</h1><main>Content</main><img src="hero.webp" loading="lazy" fetchpriority="high"><link rel="alternate" hreflang="en" href="/en"><link rel="alternate" hreflang="en" href="/other">'
        schema = '<script type="application/ld+json">{"@type":"Organization","@id":"#company","name":"One"}</script>'
        html += (
            schema
            + schema
            + '<script type="application/ld+json">{"@id":"#company","name":"Two"}</script>'
        )
        record = {
            "url": "https://example.test/",
            "final_url": "https://example.test/",
            "status": 200,
            "error": "",
            "headers": {},
            "data": extract(html, "https://example.test/"),
        }
        findings = {i["code"]: i for i in page_findings(record)}
        self.assertTrue(
            {
                "jsonld_duplicate_block",
                "jsonld_entity_conflict",
                "image_dimensions_review",
                "image_loading_conflict",
                "hreflang_conflicting_target",
            }
            <= findings.keys()
        )
        self.assertIn("do not prove CLS", findings["image_dimensions_review"]["action"])
        record["rendered"] = {"error": "TimeoutError"}
        self.assertNotIn("image_dimensions_review", {i["code"] for i in page_findings(record)})

    def test_hreflang_no_return_check_requires_complete_target(self):
        def response(url, **kwargs):
            if url.endswith("robots.txt"):
                return 200, {}, b"User-agent: *\nAllow: /"
            body = "<title>Service</title><main>Content</main>"
            if url.endswith("/en"):
                body += '<link rel="alternate" hreflang="fr" href="/fr">'
            else:
                body += '<script src="/application.js"></script>'
            return 200, {"content-type": "text/html"}, body.encode()

        config = Config(
            "https://example.test/en",
            selected_urls=["/en", "/fr"],
            max_pages=2,
            sitemaps=False,
            delay=0,
        )
        with patch.object(Transport, "once", side_effect=response):
            crawler = Crawler(config, self.root / "languages")
            try:
                crawler.log = lambda _: None
                crawler.run()
                first = json.loads((crawler.out / "issues.json").read_text())
                self.assertNotIn("hreflang_relationship_review", {i["code"] for i in first})
                row = json.loads(
                    crawler.db.execute(
                        "SELECT payload FROM pages WHERE url=?", ("https://example.test/fr",)
                    ).fetchone()[0]
                )
                row["data"]["script_count"] = 0  # Second, complete captured representation fixture.
                crawler.db.execute(
                    "UPDATE pages SET payload=? WHERE url=?", (json.dumps(row), row["url"])
                )
                crawler.db.commit()
                crawler.export()
                second = json.loads((crawler.out / "issues.json").read_text())
                self.assertIn("hreflang_relationship_review", {i["code"] for i in second})
            finally:
                crawler.close()

    def test_doctor_filesystem_denial_is_separate(self):
        environment = {
            "http_ready": True,
            "browser_ready": True,
            "checks": {},
            "runtime_checks": {},
        }
        with (
            patch("beyondseo.doctor.environment_report", return_value=environment),
            patch(
                "beyondseo.doctor.tempfile.TemporaryDirectory",
                side_effect=PermissionError("permission denied"),
            ),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(check_environment(), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["runtime_checks"]["filesystem"]["status"], "BLOCKED")
        self.assertEqual(report["runtime_checks"]["target_http"]["status"], "NOT_TESTED")

    def test_doctor_dns_denial_is_not_ready(self):
        environment = {
            "http_ready": True,
            "browser_ready": True,
            "checks": {},
            "runtime_checks": {},
        }
        with (
            patch("beyondseo.doctor.environment_report", return_value=environment),
            patch("beyondseo.network.addresses", side_effect=OSError("name or service not known")),
            patch.object(Transport, "once") as fetch,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(check_environment("https://example.test/"), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["runtime_checks"]["dns"]["failure"]["code"], "dns_failure")
        self.assertEqual(report["runtime_checks"]["sitemap"]["status"], "NOT_TESTED")
        fetch.assert_not_called()

    def test_doctor_without_target_makes_no_network_readiness_claim(self):
        environment = {
            "http_ready": True,
            "browser_ready": True,
            "checks": {},
            "runtime_checks": {},
        }
        with (
            patch("beyondseo.doctor.environment_report", return_value=environment),
            patch.object(Transport, "once") as fetch,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(check_environment(), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["runtime_checks"]["target_http"]["status"], "NOT_TESTED")
        fetch.assert_not_called()

    def test_php_gate_prevents_write_without_runtime_and_failed_recheck(self):
        site = self.root / "site"
        site.mkdir()
        target = site / "service.php"
        target.write_text('<?php echo "Before"; ?>')
        draft = self.root / "draft.php"
        draft.write_text('<?php echo "After"; ?>')
        store = LocalStore(site)
        plan = self.root / "plan"
        with patch("beyondseo.publishing.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "PHP verification blocked"):
                stage(store, "service.php", draft, plan)
        self.assertFalse(plan.exists())
        passed = subprocess.CompletedProcess([], 0, "No syntax errors", "")
        failed = subprocess.CompletedProcess([], 255, "", "Parse error")
        with (
            patch("beyondseo.publishing.shutil.which", return_value="php"),
            patch("beyondseo.publishing.subprocess.run", side_effect=[passed, failed]) as run,
        ):
            result = stage(store, "service.php", draft, plan)
            with self.assertRaisesRegex(ValueError, "PHP syntax check failed"):
                apply_change(store, plan, result["plan_sha256"])
        self.assertIn("Before", target.read_text())
        self.assertEqual(run.call_args_list[0].args[0][1:3], ["-n", "-l"])


if __name__ == "__main__":
    unittest.main()
