import json
import unittest

from test_crawler import CrawlerTests, Handler

from beyondseo.content import markdown_from_html
from beyondseo.extract import extract
from beyondseo.render import needs_browser


class BrowserFeatureTests(CrawlerTests):
    # Reuse the local server/fixtures; inherited cases are deliberately excluded below.
    def test_auto_mode_renders_shell_and_exports_content(self):
        s = self.crawl(
            self.config(
                "/js",
                max_pages=1,
                sitemaps=False,
                render_mode="auto",
                render_wait_ms=50,
                render_settle_ms=300,
                scroll_steps=0,
            )
        )
        self.assertEqual(s["rendered_documents"], 1)
        d = json.loads((self.out / "documents.jsonl").read_text().splitlines()[0])
        self.assertEqual(d["representation"], "rendered")
        self.assertIn("# JavaScript heading", d["markdown"])
        self.assertIn("JavaScript heading", (self.out / d["text_path"]).read_text())

    def test_auto_mode_leaves_static_content_in_http(self):
        s = self.crawl(self.config("/utf8", max_pages=1, sitemaps=False, render_mode="auto"))
        self.assertEqual(s["rendered_documents"], 0)

    def test_scrolling_collects_lazy_content(self):
        self.crawl(
            self.config(
                "/js-lazy",
                max_pages=1,
                sitemaps=False,
                render=True,
                render_wait_ms=50,
                render_settle_ms=0,
                scroll_steps=2,
            )
        )
        d = json.loads((self.out / "documents.jsonl").read_text().splitlines()[0])
        self.assertIn("Content revealed after scrolling", d["text"])

    def test_public_dependencies_and_visible_selector(self):
        self.crawl(
            self.config(
                "/js-external",
                max_pages=1,
                sitemaps=False,
                render=True,
                wait_for_selector=".loaded",
                render_wait_ms=50,
                render_settle_ms=0,
                scroll_steps=0,
            )
        )
        p = json.loads((self.out / "pages.jsonl").read_text().splitlines()[0])
        self.assertEqual(p["rendered"]["readiness"]["selector"], "visible")
        self.assertIn("External dependency content", p["rendered"]["data"]["text"])

    def test_allowlist_dependencies_remain_restricted(self):
        self.crawl(
            self.config(
                "/js-external",
                max_pages=1,
                sitemaps=False,
                render=True,
                render_asset_policy="allowlist",
                render_wait_ms=50,
                render_settle_ms=0,
                scroll_steps=0,
            )
        )
        p = json.loads((self.out / "pages.jsonl").read_text().splitlines()[0])
        self.assertEqual(Handler.hits["/public-script.js"], 0)
        self.assertTrue(
            any(
                b["reason"] == "asset_host_not_allowed"
                for b in p["rendered"]["blocked_request_log"]
            )
        )

    def test_explicit_robots_override_is_recorded(self):
        self.crawl(self.config("/private", max_pages=1, sitemaps=False, robots_policy="ignore"))
        self.assertEqual(Handler.hits["/private"], 1)
        evidence = json.loads((self.out / "robots.json").read_text())
        self.assertIn("override", evidence[self.root])
        s = json.loads((self.out / "summary.json").read_text())
        self.assertEqual(s["configuration"]["robots_policy"], "ignore")

    def test_selector_timeout_is_visible_in_readiness(self):
        self.crawl(
            self.config(
                "/js",
                max_pages=1,
                sitemaps=False,
                render=True,
                wait_for_selector="#never-arrives",
                timeout=5,
                scroll_steps=0,
                render_wait_ms=0,
            )
        )
        p = json.loads((self.out / "pages.jsonl").read_text().splitlines()[0])
        self.assertEqual(p["rendered"]["readiness"]["selector"], "timeout_or_error")

    def test_screenshot_is_local_png(self):
        self.crawl(
            self.config(
                "/js",
                max_pages=1,
                sitemaps=False,
                render=True,
                screenshot=True,
                render_wait_ms=50,
                render_settle_ms=0,
                scroll_steps=0,
            )
        )
        p = json.loads((self.out / "pages.jsonl").read_text().splitlines()[0])
        r = p["rendered"]
        self.assertFalse(r["error"], r["error"])
        self.assertTrue(
            (self.out / r["screenshot_path"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        )


class ContentTests(unittest.TestCase):
    def test_hero_only_main_does_not_discard_page(self):
        html = (
            "<body><main><h1>About us</h1></main><section>"
            + "Useful company history. " * 100
            + "</section></body>"
        )
        d = extract(html, "https://example.com")
        self.assertIn("company history", d["main_text"])
        self.assertEqual(d["main_text_method"], "body_without_common_boilerplate")

    def test_markdown_preserves_document_structure(self):
        html = '<nav>Navigation noise</nav><main><h1>Guide</h1><p>Hello <strong>world</strong>.</p><ul><li>First</li><li>Second</li></ul><a href="/next">Next</a><table><tr><th>Name</th><th>Value</th></tr><tr><td>One</td><td>2</td></tr></table><pre>a```b</pre></main>'
        md = markdown_from_html(html, "https://example.com/guide")
        for item in [
            "# Guide",
            "**world**",
            "- First",
            "[Next](https://example.com/next)",
            "| Name | Value |",
            "````",
        ]:
            self.assertIn(item, md)
        self.assertNotIn("Navigation noise", md)

    def test_render_decision_needs_script_evidence(self):
        self.assertFalse(needs_browser({"script_count": 0, "word_count": 3}))
        self.assertTrue(needs_browser({"script_count": 2, "word_count": 0}))


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for cls in (BrowserFeatureTests, ContentTests):
        for name in cls.__dict__:
            if name.startswith("test_"):
                suite.addTest(cls(name))
    return suite
