import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo.reports import PDFUnavailable, asset, export_report, from_audit, validate_report

ROOT = Path(__file__).resolve().parents[1]
PDF_READY = bool(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"))


def sample():
    return json.loads((ROOT / "examples/report-content.json").read_text())


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
        markup = (self.out / "report.html").read_text()
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
        path.write_text("keep me")
        with self.assertRaisesRegex(ValueError, "already exists"):
            export_report(sample(), self.out)
        self.assertEqual(path.read_text(), "keep me")

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
        block = report["sections"][1]["blocks"][0]
        self.assertEqual(block["limits"], finding["uncertainty"])
        self.assertEqual(block["urls"], finding["affected_urls"])
        self.assertEqual(block["captured_at"], finding["captured_at"])
        self.assertEqual(block["acceptance"], finding["acceptance_check"])
        self.assertNotIn('"score"', json.dumps(report))

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
        self.assertIn("مثال", (self.out / "report.html").read_text())
        self.assertFalse((self.out / "report.pdf").exists())
