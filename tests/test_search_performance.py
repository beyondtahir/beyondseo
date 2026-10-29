"""Private, deterministic Search Console export review checks."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from beyondseo.cli import main
from beyondseo.review import search_performance


class SearchPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.current = self.root / "current.csv"
        self.previous = self.root / "previous.csv"
        self.out = self.root / "report"

    def write(self, path, content):
        path.write_text(content, encoding="utf-8")

    def test_query_screening_is_actionable_without_inventing_page(self):
        self.write(
            self.current,
            'Top queries,Clicks,Impressions,CTR,Position\n"find a designer",3,500,0.6%,4.1\n"other",2,40,5%,8\n',
        )
        result = search_performance(
            self.current, self.out, "query", property_name="Example", period="Current"
        )
        self.assertEqual(result["review_candidates"][0]["dimension_value"], "find a designer")
        self.assertIn("Pages tab", result["review_candidates"][0]["action"])
        self.assertEqual(result["review_candidates"][0]["ctr_percent"], 0.6)
        self.assertIn("not necessarily complete", result["coverage_limit"])
        self.assertFalse(result["comparison_verified"])
        self.assertNotIn(
            "find a designer",
            (self.out / "search-performance.md").read_text().split("## Highest")[0],
        )
        self.assertEqual(
            json.loads((self.out / "search-performance.json").read_text())["input_rows"], 2
        )

    def test_compare_only_matched_rows_and_record_unknowns(self):
        self.write(
            self.current,
            "Top pages,Clicks,Impressions,Position\nhttps://example.com/a,30,300,4.1\nhttps://example.com/new,4,200,8\n",
        )
        self.write(
            self.previous,
            "Top pages,Clicks,Impressions,Position\nhttps://example.com/a,10,100,8\nhttps://example.com/old,8,300,9\n",
        )
        with self.assertRaisesRegex(ValueError, "comparison-context"):
            search_performance(self.current, self.out, "page", previous=self.previous)
        result = search_performance(
            self.current,
            self.out,
            "page",
            previous=self.previous,
            comparison_context="Same property, filters and equal-length periods, as supplied",
        )
        self.assertEqual(result["matched_rows"], 1)
        self.assertEqual(result["current_only_rows"], 1)
        self.assertEqual(result["previous_only_rows"], 1)
        self.assertEqual(result["matched_changes"][0]["clicks_change"], 20)
        self.assertFalse(result["comparison_verified"])
        self.assertIn("not zero", result["comparison_note"])
        self.assertIn("https://example.com/a", result["matched_changes"][0]["dimension_value"])

    def test_branded_html_report_preserves_evidence_and_limits(self):
        self.write(
            self.current, "Top pages,Clicks,Impressions,Position\nhttps://example.com/a,3,500,4.1\n"
        )
        search_performance(
            self.current, self.out, "page", property_name="Example property", period="October"
        )
        destination = self.root / "presentation"
        with contextlib.redirect_stdout(io.StringIO()):
            status = main(
                [
                    "present",
                    "--performance",
                    str(self.out / "search-performance.json"),
                    "--out",
                    str(destination),
                    "--format",
                    "html",
                ]
            )
        self.assertEqual(status, 0)
        rendered = (destination / "report.html").read_text()
        self.assertIn("https://example.com/a", rendered)
        self.assertIn("500", rendered)
        self.assertIn("not necessarily complete", rendered)
        self.assertIn("not a benchmark", rendered)

    def test_saved_crawl_matches_exact_page_and_preserves_capture_limit(self):
        self.write(
            self.current,
            "Top pages,Clicks,Impressions\nhttps://example.com/a,3,500\nhttps://example.com/b,2,300\n",
        )
        crawl = self.root / "crawl"
        crawl.mkdir()
        captures = [
            {
                "url": "https://example.com/a",
                "final_url": "https://example.com/a",
                "status": 200,
                "fetched_at": "2026-01-01",
                "data": {
                    "title": "Observed title",
                    "meta_description": "",
                    "script_count": 1,
                    "word_count": 4,
                },
            },
            {
                "url": "https://example.com/b",
                "final_url": "https://example.com/b",
                "status": 403,
                "error": "blocked",
                "data": {},
            },
        ]
        (crawl / "pages.jsonl").write_text("".join(json.dumps(row) + "\n" for row in captures))
        result = search_performance(self.current, self.out, "page", crawl_out=crawl)
        first, second = result["review_candidates"]
        self.assertEqual(first["crawl_evidence"]["observed_title"], "Observed title")
        self.assertFalse(first["crawl_evidence"]["complete_for_absence_claims"])
        self.assertFalse(second["crawl_evidence"]["usable"])
        self.assertNotIn("observed_title", second["crawl_evidence"])
        self.assertIn(
            "no conclusion about its contents", (self.out / "search-performance.md").read_text()
        )
        with self.assertRaisesRegex(ValueError, "query-to-page"):
            search_performance(self.current, self.root / "other", "query", crawl_out=crawl)

    def test_malformed_csv_fails_cleanly(self):
        self.write(self.current, 'Top queries,Clicks,Impressions\n"unfinished,1,100\n')
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()) as error,
        ):
            status = main(
                [
                    "search-performance",
                    "--input",
                    str(self.current),
                    "--dimension",
                    "query",
                    "--out",
                    str(self.out),
                ]
            )
        self.assertEqual(status, 2)
        self.assertIn("Malformed CSV", error.getvalue())
        self.assertFalse(self.out.exists())

    def test_unknown_or_bad_values_never_become_valid_measurements(self):
        for content in [
            "Top queries,Clicks,Impressions\na,2,1\n",
            "Top queries,Clicks,Impressions\na,?,100\n",
            "Top queries,Clicks,Impressions\na,1,100\na,2,100\n",
            "Top pages,Clicks,Impressions\na,1,100\n",
            "Top queries,Clicks,Impressions,Position\na,1,100,nan\n",
        ]:
            with self.subTest(content=content):
                self.write(self.current, content)
                with self.assertRaises(ValueError):
                    search_performance(self.current, self.out, "query")
                self.assertFalse(self.out.exists())

    def test_zero_impressions_are_unknown_ctr_and_no_candidate(self):
        self.write(self.current, "Top queries,Clicks,Impressions\nno data,0,0\n")
        result = search_performance(self.current, self.out, "query", minimum_impressions=0)
        self.assertIsNone(result["highest_impression_rows"][0]["ctr_percent"])
        self.assertEqual(result["review_candidates"], [])
        self.assertIn("does not prove", (self.out / "search-performance.md").read_text())

    def test_cli_writes_private_outputs_and_wont_overwrite(self):
        self.write(
            self.current,
            '\ufeffTop queries,Clicks,Impressions,Position\n"how to start",2,"1,000",7.5\n',
        )
        argv = [
            "search-performance",
            "--input",
            str(self.current),
            "--dimension",
            "query",
            "--out",
            str(self.out),
        ]
        with (
            contextlib.redirect_stdout(io.StringIO()) as output,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(main(argv), 0)
            self.assertNotIn("how to start", output.getvalue())
            self.assertEqual(main(argv), 2)
        self.assertTrue((self.out / "search-performance.json").is_file())

    def test_csv_is_escaped_in_markdown_and_screening_is_configurable(self):
        self.write(self.current, 'Top queries,Clicks,Impressions\n"<script>| test",1,100\n')
        result = search_performance(self.current, self.out, "query", maximum_ctr=0.5)
        self.assertEqual(result["review_candidates"], [])
        rendered = (self.out / "search-performance.md").read_text()
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;\\|", rendered)


if __name__ == "__main__":
    unittest.main()
