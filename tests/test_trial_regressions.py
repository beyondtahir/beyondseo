import csv
import json
import tempfile
import threading
import unittest
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from beyondseo.backlinks import mention_evidence, verify_source
from beyondseo.engine import Crawler
from beyondseo.evidence import combined_index_signals, missing_content, selected_data
from beyondseo.extract import extract, page_findings
from beyondseo.network import Config


def page(raw, rendered=None):
    result = {
        "url": "https://example.com/",
        "final_url": "https://example.com/",
        "status": 200,
        "headers": {},
        "error": "",
        "data": extract(raw, "https://example.com/"),
    }
    if rendered is not None:
        result["rendered"] = {"data": extract(rendered, "https://example.com/"), "error": ""}
    return result


class RepresentationTests(unittest.TestCase):
    def test_rendered_metadata_drives_findings(self):
        record = page(
            "<title>Shell</title><script></script>",
            '<title>Real article</title><meta name="description" content="Article description"><h1>Article</h1><main>Useful article text</main>',
        )
        codes = {r["code"] for r in page_findings(record)}
        self.assertNotIn("missing_h1", codes)
        self.assertNotIn("missing_meta_description", codes)
        self.assertEqual(selected_data(record)[1], "rendered")

    def test_failed_render_falls_back_but_empty_success_does_not(self):
        record = page("<title>Raw</title><main>Original</main>", "<body></body>")
        self.assertEqual(selected_data(record)[1], "rendered")
        record["rendered"]["error"] = "navigation_failed"
        self.assertEqual(selected_data(record)[1], "http")

    def test_raw_noindex_survives_render(self):
        record = page(
            '<meta name="robots" content="noindex"><main>Original</main>',
            "<title>Public</title><main>Public text</main>",
        )
        result = combined_index_signals(record)
        self.assertTrue(result["googlebot_noindex_observed"])
        self.assertFalse(result["indexability_candidate"])

    def test_missing_content_200_is_heuristic_and_not_indexable_candidate(self):
        record = page("<title>App</title>", "<main>Story not found</main>")
        self.assertEqual(missing_content(record)["representation"], "rendered")
        self.assertEqual(missing_content(record)["confidence"], "heuristic")
        self.assertFalse(combined_index_signals(record)["indexability_candidate"])
        self.assertIn("missing_content_candidate", {i["code"] for i in page_findings(record)})

    def test_legitimate_article_about_404_not_flagged(self):
        record = page(
            "<title>How to fix a 404 page</title><h1>Fixing missing pages</h1><main>A page not found error can be fixed. Follow this guide.</main>"
        )
        self.assertIsNone(missing_content(record))
        long_article = page(
            "<title>404 guide</title><h1>404</h1><main>Page not found "
            + "technical explanation " * 150
            + "</main>"
        )
        self.assertIsNone(missing_content(long_article))

    def test_brand_matching_has_word_boundaries(self):
        self.assertFalse(mention_evidence({"text": "Examples are helpful"}, ["Example"]))
        self.assertTrue(mention_evidence({"text": "Meet EXAMPLE today."}, ["Example"]))


class TrialHandler(BaseHTTPRequestHandler):
    policy = "allow"
    hits = Counter()

    def log_message(self, *args):
        pass

    def do_GET(self):
        TrialHandler.hits[self.path] += 1
        status, body, headers = 200, "", {}
        other = f"http://localhost:{self.server.server_port}"
        if self.path == "/robots.txt":
            headers["Content-Type"] = "text/plain"
            body = "User-agent: *\nDisallow:\n"
            if self.policy == "deny":
                body = "User-agent: *\nDisallow: /\n"
            elif self.policy == "unavailable":
                status = 503
            elif self.policy == "redirect" and self.headers["Host"].startswith("127.0.0.1"):
                status, headers["Location"] = 302, other + "/robots.txt"
        elif self.path == "/redirect":
            status, headers["Location"] = 302, other + "/link"
        elif self.path == "/loop":
            status, headers["Location"] = 302, "/loop"
        elif self.path == "/link":
            body = '<title>Directory</title><main>Example services <a href="https://example.com/" rel="nofollow">Website</a></main>'
        elif self.path == "/late":
            body = (
                "<title>Directory</title><h1>Directory entry</h1><main>"
                + "Substantial initial content. " * 150
                + '</main><script>setTimeout(()=>{document.querySelector("main").innerHTML+=\'<a href="https://example.com/">Example website</a>\'},100)</script>'
            )
        elif self.path == "/failed":
            body = '<title>App</title><div id="root"></div><script>throw new Error("Application failed")</script>'
        elif self.path == "/":
            body = '<title>Shared shell</title><script>document.title="Home"</script><h1>Home</h1><a href="/one">One</a><a href="/two">Two</a><a href="/missing">Missing</a>'
        elif self.path in ("/one", "/two"):
            name = self.path[1:]
            body = f'<title>Shared shell</title><script>document.title="{name}"</script><main><h1>{name}</h1>Distinct content for {name}</main>'
        elif self.path == "/missing":
            body = '<title>Shared shell</title><div id="root"></div><script>document.querySelector("#root").innerHTML="<main>Story not found</main>"</script>'
        else:
            status = 404
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", headers.pop("Content-Type", "text/html; charset=utf-8"))
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class TrialRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), TrialHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.root = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        TrialHandler.policy = "allow"
        TrialHandler.hits.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def verify(self, path, **kwargs):
        return verify_source(
            self.root + path,
            "example.com",
            self.out / "verify",
            allow_private=True,
            brand="Example",
            **kwargs,
        )

    def crawl(self, path, **kwargs):
        cfg = Config(
            self.root + path, allow_private=True, sitemaps=False, retries=0, delay=0, **kwargs
        )
        crawler = Crawler(cfg, self.out / "crawl")
        crawler.log = lambda _: None
        try:
            crawler.run()
        finally:
            crawler.close()
        return [
            json.loads(line) for line in (self.out / "crawl/pages.jsonl").read_text().splitlines()
        ]

    def test_robots_rule_and_unavailable_policy_are_distinct(self):
        TrialHandler.policy = "deny"
        result = self.crawl("/link", max_pages=1)[0]
        self.assertEqual(result["error"], "robots_rule_disallowed")
        self.assertEqual(TrialHandler.hits["/link"], 0)
        TrialHandler.policy = "unavailable"
        self.out = self.out / "unavailable"
        result = self.crawl("/link", max_pages=1)[0]
        self.assertEqual(result["error"], "robots_unavailable")
        self.assertEqual(TrialHandler.hits["/link"], 0)
        self.assertEqual(result["robots_decision"]["policy_status"], 503)

    def test_robots_scope_limit_is_not_a_disallow(self):
        TrialHandler.policy = "redirect"
        result = self.crawl("/link", max_pages=1)[0]
        self.assertEqual(result["error"], "robots_scope_limited")
        self.assertEqual(TrialHandler.hits["/link"], 0)

    def test_backlink_follows_observed_host_redirect(self):
        result = self.verify("/redirect", mode="http")
        self.assertEqual(result["verification"], "link_observed")
        self.assertEqual(len(result["attempt_history"]), 2)
        self.assertIn("localhost", result["final_url"])

    def test_backlink_resolves_robots_redirect_scope(self):
        TrialHandler.policy = "redirect"
        result = self.verify("/link", mode="http")
        self.assertEqual(result["verification"], "link_observed")
        self.assertEqual(result["attempt_history"][0]["error"], "robots_scope_limited")

    def test_followup_can_be_disabled_and_loop_is_reported(self):
        result = self.verify("/redirect", mode="http", follow_redirects=False)
        self.assertEqual(result["error"], "redirect_out_of_scope")
        self.assertEqual(TrialHandler.hits["/link"], 0)
        self.out = self.out / "loop"
        result = self.verify("/loop", mode="http")
        self.assertEqual(result["access"]["code"], "redirect_loop")

    def test_auto_verifies_late_link_on_text_rich_page(self):
        result = self.verify("/late")
        self.assertEqual(result["verification"], "link_observed")
        self.assertEqual(result["representation"], "rendered")
        self.assertEqual([r["mode"] for r in result["attempt_history"]], ["auto", "browser"])

    def test_broken_javascript_does_not_establish_link_absence(self):
        result = self.verify("/failed")
        self.assertEqual(result["verification"], "unverified_access")

    def test_export_uses_rendered_titles_and_flags_missing_destination(self):
        self.crawl(
            "/",
            max_pages=4,
            render_mode="browser",
            render_wait_ms=50,
            render_settle_ms=0,
            scroll_steps=0,
        )
        issues = json.loads((self.out / "crawl/issues.json").read_text())
        codes = [i["code"] for i in issues]
        self.assertNotIn("duplicate_title", codes)
        self.assertEqual(codes.count("missing_content_candidate"), 1)
        self.assertIn("internal_link_missing_content_candidate", codes)
        with (self.out / "crawl/pages.csv").open(encoding="utf-8-sig") as stream:
            inventory = list(csv.DictReader(stream))
        one = next(r for r in inventory if r["url"].endswith("/one"))
        self.assertEqual(one["title"], "one")
        self.assertEqual(one["initial_title"], "Shared shell")
