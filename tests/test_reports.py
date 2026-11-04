import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo.reports import (
    PDFUnavailable,
    asset,
    export_report,
    from_audit,
    group_findings,
    next_actions,
    readable_observation,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]
PDF_READY = bool(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"))


def sample():
    return json.loads((ROOT / "examples/report-content.json").read_text(encoding="utf-8"))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_product_logo_is_the_exact_existing_asset(self):
        self.assertEqual(
            asset("beyondseo-logo.png"), (ROOT / "assets/beyondseo-logo.png").read_bytes()
        )

    def test_html_is_self_contained_and_treats_content_as_text(self):
        data = sample()
        data["client"] = '<script>alert("x")</script>'
        data["sections"][0]["blocks"][0]["text"] = (
            '<img src="https://evil.test/pixel"><b>literal</b>'
        )
        result = export_report(data, self.out, "html")
        markup = (self.out / "report.html").read_text(encoding="utf-8")
        self.assertEqual(result["status"], "complete")
        self.assertIn("Content-Security-Policy", markup)
        self.assertIn("data:image/png;base64,", markup)
        self.assertNotIn('<img src="https:', markup)
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;b&gt;literal&lt;/b&gt;", markup)
        self.assertEqual(data["client"], '<script>alert("x")</script>')

    def test_missing_pdf_dependency_preserves_html_and_reports_precise_limit(self):
        with patch("beyondseo.reports.pdf_report", side_effect=PDFUnavailable("missing reportlab")):
            result = export_report(sample(), self.out)
        self.assertEqual(result["status"], "html_only")
        self.assertIn("missing reportlab", result["pdf_limitation"])
        self.assertTrue((self.out / "report.html").is_file())
        self.assertFalse((self.out / "report.pdf").exists())

    def test_html_remains_readable_at_phone_width_without_external_requests(self):
        if not importlib.util.find_spec("playwright"):
            self.skipTest("Install the browser extra for responsive layout checks.")
        from playwright.sync_api import Error, sync_playwright

        export_report(sample(), self.out, "html")
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except Error as error:
                self.skipTest(f"Local Chromium unavailable: {error}")
            try:
                page = browser.new_page(viewport={"width": 390, "height": 844})
                external = []
                page.on(
                    "request",
                    lambda request: (
                        external.append(request.url)
                        if request.url.startswith(("http://", "https://"))
                        else None
                    ),
                )
                page.goto((self.out / "report.html").as_uri())
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 390)
                self.assertTrue(
                    page.evaluate("[...document.images].every(i => i.naturalWidth > 0)")
                )
                self.assertEqual(external, [])
                self.assertEqual(page.locator(".finding dd").count(), 9)
                label_widths = page.locator(".bars-chart label").evaluate_all(
                    "nodes => nodes.map(n => n.getBoundingClientRect().width)"
                )
                self.assertTrue(label_widths)
                self.assertTrue(all(width >= 195 for width in label_widths))
            finally:
                browser.close()

    def test_failed_explicit_overwrite_does_not_leave_a_stale_pdf(self):
        (self.out / "report.pdf").write_bytes(b"old client's output")
        with patch(
            "beyondseo.reports.pdf_report", side_effect=PDFUnavailable("unsupported script")
        ):
            result = export_report(sample(), self.out, overwrite=True)
        self.assertEqual(result["status"], "html_only")
        self.assertFalse((self.out / "report.pdf").exists())

    def test_existing_output_is_preserved_without_explicit_overwrite(self):
        path = self.out / "report.html"
        path.write_text("keep me", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            export_report(sample(), self.out)
        self.assertEqual(path.read_text(encoding="utf-8"), "keep me")

    def test_metrics_require_sources_and_bars_reject_nonfinite_or_negative_values(self):
        data = sample()
        del data["sections"][0]["blocks"][1]["source"]
        with self.assertRaisesRegex(ValueError, "source"):
            validate_report(data)
        for value in (float("nan"), float("inf"), -1, True):
            data = sample()
            data["sections"][7]["blocks"][1]["items"][0]["value"] = value
            with self.assertRaisesRegex(ValueError, "nonnegative"):
                validate_report(data)

    def test_malformed_tables_and_incomplete_findings_fail_before_output(self):
        data = sample()
        data["sections"][1]["blocks"][0]["rows"][0].pop()
        with self.assertRaisesRegex(ValueError, "column count"):
            export_report(data, self.out)
        data = sample()
        del data["sections"][5]["blocks"][0]["limits"]
        with self.assertRaisesRegex(ValueError, "Finding needs"):
            export_report(data, self.out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_audit_adapter_keeps_evidence_and_never_creates_a_score(self):
        finding = {
            "affected_urls": ["https://example.com/services"],
            "observation": "Observed capture limitation",
            "claim_type": "inference",
            "why_it_matters": "Coverage unknown",
            "recommended_action": "Recapture",
            "priority": "P2",
            "priority_rationale": "Needs inspection",
            "acceptance_check": "Complete capture",
            "uncertainty": ["Partial render"],
            "captured_at": "2026-01-01",
            "evidence_refs": [{"url": "https://example.com/services"}],
        }
        report = from_audit(
            {"target": "https://example.com", "created_at": "2026-01-01", "findings": [finding]}
        )
        self.assertEqual(report["sections"][0]["title"], "Start here")
        block = report["sections"][2]["blocks"][0]
        self.assertEqual(block["limits"], finding["uncertainty"])
        self.assertEqual(block["urls"], finding["affected_urls"])
        self.assertEqual(block["captured_at"], finding["captured_at"])
        self.assertEqual(block["acceptance"], finding["acceptance_check"])
        self.assertNotIn('"score"', json.dumps(report))
        finding["business_relevance"] = "Customers need to understand the service before buying."
        large = from_audit(
            {
                "target": "https://example.com",
                "created_at": "2026-01-01",
                "findings": [
                    {
                        **finding,
                        "code": "repeat",
                        "url": "https://e.test/",
                        "observation": f"Observation {i}",
                    }
                    for i in range(101)
                ],
            }
        )
        export_report(large, self.out, "html")
        retained = [
            block
            for section in large["sections"]
            for block in section["blocks"]
            if block["type"] == "finding"
        ]
        # One issue on one page is one card; the appendix counts its observations.
        self.assertEqual(len(retained), 1)
        self.assertIn("Seen 101 times on 1 page", retained[0]["observation"])
        self.assertIn(finding["business_relevance"], retained[0]["impact"])
        self.assertIn("101 times", (self.out / "report.html").read_text(encoding="utf-8"))

    def test_audit_report_groups_repeats_and_leads_with_actions(self):
        def row(code, url, priority, action="Fix it", claim="verified_fact"):
            return {
                "code": code,
                "url": url,
                "affected_urls": [url],
                "observation": f"{code} on {url}",
                "why_it_matters": "It matters.",
                "recommended_action": action,
                "priority": priority,
                "priority_rationale": "Observed",
                "acceptance_check": "Recrawl",
                "uncertainty": ["Sample only"],
                "captured_at": "2026-01-01",
                "claim_type": claim,
                "evidence_refs": [{"url": url}],
            }

        urls = [f"https://example.com/{i}" for i in range(12)]
        rows = [row("javascript_content", urls[0], "review", "Check it")]
        rows += [row("image_dimensions_review", url, "P3") for url in urls for _ in range(2)]
        rows += [
            row("multiple_canonicals", urls[0], "P2"),
            row("multiple_canonicals", urls[1], "P2"),
        ]
        rows.append(row("multiple_canonicals", urls[2], "P2", claim="hypothesis"))
        rows.append({**row(None, urls[3], "P1"), "code": None, "title": "Reviewed A"})
        rows.append({**row(None, urls[4], "P1"), "code": None, "title": "Reviewed B"})
        report = from_audit(
            {
                "target": "https://example.com",
                "created_at": "2026-01-01",
                "findings": rows,
                "scope_warning": "No discovery.",
            }
        )
        validate_report(report)
        by_title = {s["title"]: s for s in report["sections"]}
        cards = [b for b in by_title["Findings & actions"]["blocks"] if b["type"] == "finding"]
        # Reviewed findings stay separate; each coded issue becomes one card, in priority order.
        self.assertEqual(
            [c["title"] for c in cards],
            [
                "Reviewed A",
                "Reviewed B",
                "More than one canonical tag",
                "Images without width and height",
                "Main content needs JavaScript to appear",
            ],
        )
        self.assertEqual(cards[2]["claim_type"], "hypothesis")
        images = cards[3]
        self.assertIn("Seen 24 times on 12 pages", images["observation"])
        self.assertEqual(len(images["urls"]), 11)
        self.assertIn("2 more", images["urls"][-1])
        actions = by_title["Start here"]["blocks"][1]["rows"]
        self.assertEqual(actions[0][1], "Reviewed A")
        self.assertEqual(actions[3][3], "12")
        self.assertEqual(len(actions), 5)
        appendix = by_title["Evidence appendix"]["blocks"][1]["rows"]
        # Twelve image pages plus three canonical pages: one row per page and issue.
        self.assertEqual(len(appendix), 15)
        self.assertTrue(any(urls[11] in r[1] for r in appendix))
        warning = by_title["Scope & evidence"]["blocks"][1]
        self.assertEqual(warning["title"], "Not a complete audit yet")

    def test_recorded_lists_are_shown_in_plain_words(self):
        tags = [
            {"raw": "/a", "url": "https://example.com/a"},
            {"raw": "/", "url": "https://example.com/"},
        ]
        self.assertEqual(
            readable_observation(json.dumps(tags)),
            "2 tags pointing to 2 addresses: https://example.com/a, https://example.com/",
        )
        self.assertEqual(readable_observation('["One", "Two"]'), "2 values: “One” | “Two”")
        for unchanged in ("Plain text", "[not json", "[]", '[{"other": 1}]'):
            self.assertEqual(readable_observation(unchanged), unchanged)

    def test_review_fixes_keep_evidence_visible(self):
        base = {
            "why_it_matters": "It matters.",
            "recommended_action": "Fix it",
            "priority_rationale": "Observed",
            "acceptance_check": "Recrawl",
            "uncertainty": ["Sample only"],
            "claim_type": "verified_fact",
            "evidence_refs": [],
            "observation": "Seen",
        }
        urls = [f"https://example.com/{i}" for i in range(14)]
        many = {**base, "title": "Many pages", "priority": "P1", "affected_urls": urls}
        report = from_audit({"target": urls[0], "created_at": "2026-01-01", "findings": [many]})
        self.assertIn(urls[13], json.dumps(report))
        self.assertIn(
            "1 observation on 14 pages comes down to 1 separate issue.", json.dumps(report)
        )
        # Coded reviewed findings stay separate.
        one = {**base, "code": "content_gap", "priority": "P1", "affected_urls": urls[:1]}
        groups = group_findings([{**one, "title": "Pricing"}, {**one, "title": "Refunds"}])
        self.assertEqual([g["title"] for g in groups], ["Pricing", "Refunds"])
        # Priority labels outside P0-P3 rank above informational items.
        mixed = [
            {**base, "title": label, "priority": label, "affected_urls": urls[:1]}
            for label in ("review", "P3", "High", "Custom", "P2 / High")
        ]
        self.assertEqual(
            [g["priority"] for g in group_findings(mixed)],
            ["High", "P2 / High", "P3", "Custom", "review"],
        )
        # Merged cards show the whole capture range.
        crawl = {**base, "code": "x", "url": urls[0], "priority": "P2", "affected_urls": urls[:1]}
        dated = group_findings(
            [{**crawl, "captured_at": "2026-01-01"}, {**crawl, "captured_at": "2026-06-30"}]
        )
        self.assertEqual(dated[0]["captured_at"], "2026-01-01 to 2026-06-30")
        # Older saved audits still get the warning.
        report = from_audit({"target": urls[0], "created_at": "2026-01-01", "findings": [crawl]})
        self.assertIn("Not a complete audit yet", json.dumps(report))
        self.assertEqual(
            readable_observation('{"src": "https://e.test/a.png", "width": null}'),
            "Image: https://e.test/a.png",
        )

    def test_review_items_only_fill_remaining_next_actions(self):
        groups = [{"priority": "review"}, {"priority": "P3"}, {"priority": "P1"}]
        ordered = next_actions(groups, 2)
        self.assertEqual([g["priority"] for g in ordered], ["P3", "P1"])

    @unittest.skipUnless(PDF_READY, "Install reportlab and pypdf for PDF integration checks.")
    def test_pdf_content_navigation_brand_and_no_blank_pages(self):
        from pypdf import PdfReader

        result = export_report(sample(), self.out)
        self.assertEqual(result["status"], "complete")
        pdf = PdfReader(self.out / "report.pdf")
        self.assertEqual(pdf.metadata.author, "BeyondSEO")
        self.assertEqual(len(pdf.outline), 9)
        for page in pdf.pages:
            self.assertGreater(len(page.extract_text()), 140, "Unexpected empty overflow page")
            self.assertAlmostEqual(float(page.mediabox.width), 595.276, places=2)
        content = "\n".join(p.extract_text() for p in pdf.pages)
        self.assertIn("Acceptance check".upper(), content)
        self.assertIn("Uncertainty & coverage".upper(), content)
        self.assertIn("https://example.com/services", content)
        self.assertNotIn("\u25a0", content)
        self.assertTrue(pdf.pages[0].images)
        for link in pdf.outline:
            number = pdf.get_destination_page_number(link)
            self.assertIn(link.title[4:], pdf.pages[number].extract_text().replace("\n", " "))

    @unittest.skipUnless(PDF_READY, "Install reportlab and pypdf for PDF integration checks.")
    def test_long_table_paginated_without_losing_last_row(self):
        from pypdf import PdfReader

        data = sample()
        data["sections"] = [
            {
                "title": "Detailed evidence",
                "blocks": [
                    {
                        "type": "table",
                        "columns": ["Page", "Observation"],
                        "rows": [
                            [f"Page {i}", "A long preserved observation. " * 8] for i in range(75)
                        ],
                    }
                ],
            }
        ]
        export_report(data, self.out, "pdf")
        pages = PdfReader(self.out / "report.pdf").pages
        self.assertGreater(len(pages), 4)
        content = "\n".join(p.extract_text() for p in pages)
        self.assertIn("Page 74", content)
        self.assertGreater(content.count("Observation"), 3)

    @unittest.skipUnless(PDF_READY, "Install reportlab and pypdf for PDF integration checks.")
    def test_pdf_contents_escapes_markup_and_complex_script_preserves_html(self):
        from pypdf import PdfReader

        data = sample()
        data["sections"] = copy.deepcopy(data["sections"][:1])
        data["sections"][0]["title"] = "<b>literal & safe</b>"
        export_report(data, self.out)
        self.assertIn(
            "<b>literal & safe</b>", PdfReader(self.out / "report.pdf").pages[1].extract_text()
        )
        data["client"] = "مثال"
        result = export_report(data, self.out, overwrite=True)
        self.assertEqual(result["status"], "html_only")
        self.assertIn("مثال", (self.out / "report.html").read_text(encoding="utf-8"))
        self.assertFalse((self.out / "report.pdf").exists())
