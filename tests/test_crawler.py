import gzip
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from beyondseo import __version__
from beyondseo.diagnostics import challenge_signal
from beyondseo.engine import Crawler, csv_value, parse_sitemap
from beyondseo.extract import extract, index_signals
from beyondseo.network import Config, RobotsRules, Transport, addresses, normalize_url


class Handler(BaseHTTPRequestHandler):
    hits = Counter()
    robots_status = 200
    received_headers = {}

    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        Handler.hits["OPTIONS"] += 1
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.end_headers()

    def do_POST(self):
        Handler.hits["POST"] += 1
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        Handler.hits[self.path] += 1
        p = urlsplit(self.path).path
        status = 200
        ctype = "text/html; charset=utf-8"
        headers = {}
        host = f"http://127.0.0.1:{self.server.server_port}"
        if p == "/robots.txt":
            status = Handler.robots_status
            ctype = "text/plain"
            body = f"User-agent: *\nDisallow: /private\nAllow: /private/public\nDisallow: /secret\nSitemap: {host}/map.xml"
        elif p == "/map.xml":
            ctype = "application/xml"
            body = f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{host}/nested.xml.gz</loc></sitemap></sitemapindex>'
        elif p == "/nested.xml.gz":
            ctype = "application/xml"
            body = f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{host}/orphan</loc><lastmod>2026-09-01</lastmod></url></urlset>'
            body = gzip.compress(body.encode())
        elif p in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/missing"):
            status = 404
            body = "<title>Not found</title>"
        elif p == "/":
            body = """<html lang="en"><title>Home</title><meta name="description" content="Local fixture"><h1>Home</h1><main><p>Home content</p></main>
            <a href="/a#top">A</a><a href="/a?utm_source=test">tracked A</a><a href="/old">old</a><a href="/new">new</a><a href="/missing">missing</a><a href="/private">private</a><a href="/private/public">allowed</a><a href="/redirect-secret">redirect</a><a href="http://outside.invalid/">external</a><a href="/loop">loop</a><a href="/noindex">noindex</a><a href="/product?id=1">p1</a><a href="/product?id=2">p2</a><a href="/product?id=3">p3</a></html>"""
        elif p == "/a":
            body = '<title>Duplicate</title><h1>A</h1><main>Same article text</main><img src="x.jpg"><img src="y.jpg" alt=""><script type="application/ld+json">{"@type":"Product"}</script>'
        elif p == "/old":
            status = 301
            headers["Location"] = "/new"
            body = ""
        elif p == "/new":
            body = "<title>Duplicate</title><h1>New</h1><main>Same article text</main>"
        elif p == "/redirect-secret":
            status = 302
            headers["Location"] = "/secret"
            body = ""
        elif p == "/outside":
            status = 302
            headers["Location"] = "http://outside.invalid/"
            body = ""
        elif p == "/loop":
            status = 302
            headers["Location"] = "/loop"
            body = ""
        elif p == "/noindex":
            headers["X-Robots-Tag"] = "googlebot: noindex, nofollow"
            body = "<title>No index</title><h1>No</h1>"
        elif p == "/retry":
            status = 429 if Handler.hits[self.path] == 1 else 200
            headers["Retry-After"] = "0"
            body = "<title>Retry</title><h1>Retry</h1>"
        elif p == "/later":
            status = 429
            headers["Retry-After"] = "300"
            body = "Retry later"
        elif p == "/requires-header":
            Handler.received_headers = dict(self.headers)
            body = "<title>Header check</title>"
        elif p == "/credential-redirect":
            status = 302
            headers["Location"] = f"http://localhost:{self.server.server_port}/requires-header"
            body = ""
        elif p == "/denied":
            status = 403
            body = "<title>Forbidden</title>"
        elif p == "/challenge":
            headers["cf-mitigated"] = "challenge"
            body = "<title>Just a moment...</title><div>Checking browser</div>"
        elif p == "/challenge-body":
            body = '<title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/check"></script>'
        elif p == "/huge":
            body = "X" * 10000
        elif p == "/gzip-bomb":
            body = gzip.compress(b"X" * 10000)
            headers["Content-Encoding"] = "gzip"
        elif p == "/js":
            body = """<title>Before</title><div id="app"></div><script>document.title='Rendered';document.querySelector('#app').innerHTML='<main><h1>JavaScript heading</h1><a href="/rendered-link">Link</a></main>';fetch('/side-effect',{method:'POST'});</script>"""
        elif p == "/js-broken":
            body = '<title>App</title><div id="root"></div><script>throw new Error("fixture application failed")</script>'
        elif p == "/js-lazy":
            body = """<title>Lazy</title><main><h1>Lazy content</h1><div style="height:2400px"></div></main><script>window.addEventListener('scroll',()=>{if(!document.querySelector('#lazy')){let p=document.createElement('p');p.id='lazy';p.textContent='Content revealed after scrolling';document.querySelector('main').appendChild(p)}})</script>"""
        elif p == "/js-external":
            body = f'<title>Dependencies</title><main id="app"></main><script src="http://localhost:{self.server.server_port}/public-script.js"></script>'
        elif p == "/public-script.js":
            ctype = "application/javascript"
            body = 'document.querySelector("#app").innerHTML="<h1 class=loaded>External dependency content</h1>";'
        elif p == "/utf8":
            body = "<title>اردو café</title><h1>اردو</h1>"
        else:
            body = f"<title>{p}</title><h1>{p}</h1><main>Different content for {p}</main>"
        body = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CrawlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.root = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        Handler.hits.clear()
        Handler.robots_status = 200
        Handler.received_headers = {}
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, path="/", **kwargs):
        options = dict(url=self.root + path, allow_private=True, delay=0, retries=0, workers=2)
        options.update(kwargs)
        return Config(**options)

    def crawl(self, config, resume=False):
        c = Crawler(config, self.out, resume=resume)
        c.log = lambda _: None
        try:
            return c.run()
        finally:
            c.close()

    def test_discovery_evidence_and_findings(self):
        s = self.crawl(self.config(max_pages=40, max_query_variants=2))
        self.assertEqual(s["engine_version"], __version__)
        self.assertEqual(
            json.loads((self.out / "summary.json").read_text())["engine_version"], __version__
        )
        issues = json.loads((self.out / "issues.json").read_text())
        codes = {i["code"] for i in issues}
        self.assertIn("broken_internal_link", codes)
        self.assertIn("orphan_candidate", codes)
        self.assertIn("duplicate_title", codes)
        self.assertEqual(Handler.hits["/private"], 0)
        self.assertEqual(Handler.hits["/secret"], 0)
        self.assertEqual(Handler.hits["/private/public"], 1)
        self.assertEqual(Handler.hits["/a?utm_source=test"], 0)
        self.assertEqual(Handler.hits["/product?id=3"], 0)
        self.assertEqual(s["sitemap_urls"], 1)
        self.assertTrue(s["coverage_limited"])
        records = [json.loads(item) for item in (self.out / "pages.jsonl").read_text().splitlines()]
        a = next(p for p in records if p["url"].endswith("/a"))
        self.assertEqual(a["data"]["schema_types"], ["Product"])
        self.assertEqual(a["data"]["images"][1]["alt"], "")
        import hashlib

        self.assertEqual(
            hashlib.sha256((self.out / a["html_path"]).read_bytes()).hexdigest(), a["body_sha256"]
        )
        dup = next(i for i in issues if i["code"] == "duplicate_title")
        self.assertEqual(len(json.loads(dup["evidence"])["urls"]), 2)

    def test_resume_budget_does_not_refetch_completed_seed(self):
        first = self.crawl(self.config(max_pages=2, sitemaps=False))
        self.assertEqual(first["attempted_urls"], 2)
        self.assertGreater(first["pending_urls"], 0)
        second = self.crawl(self.config(max_pages=40, sitemaps=False), resume=True)
        self.assertGreater(second["attempted_urls"], 2)
        self.assertEqual(Handler.hits["/"], 1)
        with self.assertRaises(ValueError):
            Crawler(self.config("/other"), self.out, resume=True)

    def test_redirect_boundaries_and_loop(self):
        t = Transport(self.config())
        outside = t.fetch(self.root + "/outside")
        self.assertEqual(outside.error, "redirect_out_of_scope")
        loop = t.fetch(self.root + "/loop")
        self.assertEqual(loop.error, "redirect_loop")

    def test_body_and_decompression_limits(self):
        t = Transport(self.config(max_bytes=1000))
        self.assertIn("response_too_large", t.fetch(self.root + "/huge").error)
        self.assertIn("decompressed_response_too_large", t.fetch(self.root + "/gzip-bomb").error)

    def test_retry_after(self):
        t = Transport(self.config(retries=1))
        with patch("beyondseo.network.time.sleep") as wait:
            r = t.fetch(self.root + "/retry")
            self.assertEqual(r.status, 200)
            self.assertEqual(r.attempts, 2)
            r = t.fetch(self.root + "/later")
            self.assertEqual(r.attempts, 1)
            self.assertEqual(r.status, 429)
            self.assertFalse(any(call.args and call.args[0] > 30 for call in wait.call_args_list))

    def test_robots_longest_group_and_percent_rules(self):
        r = RobotsRules(
            "User-agent: *\nDisallow: /\nUser-agent: BeyondSEO\nDisallow: /private\nAllow: /private/public\nUser-agent: BeyondSEO\nDisallow: /*?id=*$\nDisallow: /caf%C3%A9\n"
        )
        self.assertTrue(r.allowed(self.root + "/a"))
        self.assertFalse(r.allowed(self.root + "/private"))
        self.assertTrue(r.allowed(self.root + "/private/public"))
        self.assertFalse(r.allowed(self.root + "/product?id=2"))
        self.assertFalse(r.allowed(self.root + "/café"))
        r = RobotsRules("User-agent: *\nDisallow: /same\nAllow: /same\n")
        self.assertTrue(r.allowed(self.root + "/same"))

    def test_url_normalization_preserves_semantics(self):
        self.assertEqual(
            normalize_url("https://Example.COM:443/X%7Ey/%2f?id=2&id=1&utm_source=x#top"),
            "https://example.com/X~y/%2F?id=2&id=1",
        )
        self.assertIsNone(normalize_url("javascript:alert(1)"))
        self.assertIsNone(normalize_url("http://user:pass@example.com"))
        self.assertNotEqual(
            normalize_url("https://example.com/a"), normalize_url("https://example.com/a/")
        )

    def test_private_address_default(self):
        with self.assertRaises(ValueError):
            addresses(self.root)
        self.assertTrue(addresses(self.root, True))
        r = Transport(Config(self.root, retries=0, delay=0)).fetch(self.root)
        self.assertIn("private_or_nonpublic_address", r.error)
        self.assertEqual(Handler.hits["/"], 0)

    def test_sitemap_namespaces_gzip_and_entities(self):
        kind, rows = parse_sitemap(
            b'<urlset xmlns="x"><url><loc>https://example.com/?a=1&amp;b=2</loc></url></urlset>'
        )
        self.assertEqual(kind, "urlset")
        self.assertTrue(rows[0]["loc"].endswith("a=1&b=2"))
        with self.assertRaises(ValueError):
            parse_sitemap(b'<!DOCTYPE x [<!ENTITY y "foo">]><urlset/>')

    def test_extraction_base_encoding_schema_and_selectors(self):
        d = extract(
            b"""<html><head><base href="/base/"><title>T</title><link rel="canonical" href="c"><script type="application/ld+json">{"@graph":[{"@type":["Product","Thing"]}]}</script><script type="application/ld+json">bad</script></head><body><nav>Navigation</nav><main><h1>Hello <em>World</em></h1><span class="price">$10</span><a href="p">P</a><p hidden>secret text</p></main></body></html>""",
            self.root + "/",
            selectors={
                "price": ".price",
                "href": {"selector": "a", "attribute": "href", "all": False},
            },
        )
        self.assertEqual(d["headings"]["h1"], ["Hello World"])
        self.assertEqual(d["canonical"][0]["url"], self.root + "/base/c")
        self.assertEqual(d["custom"]["price"], ["$10"])
        self.assertEqual(d["custom"]["href"], "p")
        self.assertNotIn("secret text", d["main_text"])
        self.assertNotIn("Navigation", d["main_text"])
        self.assertEqual(d["schema_types"], ["Product", "Thing"])
        self.assertEqual(len(d["jsonld_errors"]), 1)
        d = extract(
            "<title>اردو café</title>".encode(),
            self.root,
            {"content-type": "text/html; charset=utf-8"},
        )
        self.assertEqual(d["title"], "اردو café")

    def test_agent_specific_noindex(self):
        d = extract('<meta name="bingbot" content="noindex"><title>A</title>', self.root)
        self.assertFalse(
            index_signals(d, {"x-robots-tag": "bingbot: noindex"}, 200, self.root)[
                "googlebot_noindex_observed"
            ]
        )
        self.assertTrue(
            index_signals(d, {"x-robots-tag": "googlebot: noindex"}, 200, self.root)[
                "googlebot_noindex_observed"
            ]
        )
        self.assertTrue(
            index_signals(d, {"x-robots-tag": "none"}, 200, self.root)["googlebot_noindex_observed"]
        )

    def test_csv_formula_and_cli_single_scrape(self):
        self.assertEqual(csv_value('=HYPERLINK("x")'), '\'=HYPERLINK("x")')
        script = Path(__file__).resolve().parents[1] / "scripts/crawl.py"
        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "scrape",
                self.root + "/utf8",
                "--out",
                str(self.out),
                "--allow-private",
                "--delay",
                "0",
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["attempted_urls"], 1)
        self.assertEqual(Handler.hits["/map.xml"], 0)

    def test_repeated_article_grid_is_not_truncated(self):
        d = extract(
            "<body><nav>nav</nav><article>First product</article><article>Second product</article><footer>foot</footer></body>",
            self.root,
        )
        self.assertIn("First product", d["main_text"])
        self.assertIn("Second product", d["main_text"])
        self.assertNotIn("nav", d["main_text"])
        self.assertEqual(d["word_count"], 4)
        d = extract(
            '<body><div role="main"><article>First product</article><article>Second product</article></div></body>',
            self.root,
        )
        self.assertEqual(d["word_count"], 4)

    def test_robots_server_failure_does_not_crawl(self):
        Handler.robots_status = 503
        s = self.crawl(self.config(max_pages=2, sitemaps=False))
        self.assertEqual(Handler.hits["/"], 0)
        self.assertEqual(s["html_documents"], 0)
        self.assertTrue(s["coverage_limited"])
        r = json.loads((self.out / "robots.json").read_text())
        self.assertTrue(r[self.root]["blocked"])

    def test_exclusions_and_discovery_limits(self):
        s = self.crawl(
            self.config(
                sitemaps=False, max_pages=30, max_discovered=5, exclude=["/private", "/old"]
            )
        )
        self.assertLessEqual(s["discovered_urls"], 5)
        self.assertTrue(s["coverage_limited"])
        self.assertEqual(Handler.hits["/old"], 0)
        self.assertEqual(Handler.hits["/private"], 0)

    def test_report_regeneration_is_offline_and_keeps_budget(self):
        self.crawl(self.config(max_pages=2, sitemaps=False))
        before = dict(Handler.hits)
        c = Crawler(self.config(max_pages=999, sitemaps=False), self.out, resume=True)
        try:
            s = c.export()
        finally:
            c.close()
        self.assertEqual(dict(Handler.hits), before)
        self.assertEqual(s["configuration"]["max_pages"], 2)

    def test_nonstandard_json_constants_rejected(self):
        d = extract('<script type="application/ld+json">{"value": NaN}</script>', self.root)
        self.assertEqual(len(d["jsonld_errors"]), 1)

    def test_invalid_configuration_and_css_fail_before_crawl(self):
        with self.assertRaises(ValueError):
            self.config(delay=float("nan"))
        with self.assertRaises(ValueError):
            self.config(timeout=float("inf"))
        selector = self.out / "selectors.json"
        selector.write_text(json.dumps({"bad": "["}))
        script = Path(__file__).resolve().parents[1] / "scripts/crawl.py"
        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "scrape",
                self.root,
                "--out",
                str(self.out / "bad"),
                "--selectors",
                str(selector),
                "--allow-private",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 2)
        self.assertIn("Invalid selector", r.stderr)
        self.assertEqual(sum(Handler.hits.values()), 0)

    def test_http_200_challenge_is_saved_but_not_analyzed_as_site(self):
        s = self.crawl(self.config("/challenge", max_pages=1, sitemaps=False))
        self.assertEqual(s["html_documents"], 0)
        self.assertEqual(s["access_diagnostics"]["remote_denial_or_challenge_pages"], 1)
        p = json.loads((self.out / "pages.jsonl").read_text().splitlines()[0])
        self.assertEqual(p["status"], 200)
        self.assertEqual(p["access"]["code"], "challenge_response")
        self.assertTrue((self.out / p["html_path"]).exists())
        self.assertIsNone(p["data"])
        issues = json.loads((self.out / "issues.json").read_text())
        self.assertFalse(any(i["code"] == "missing_h1" for i in issues))

    def test_denial_and_page_budget_are_different_outcomes(self):
        s = self.crawl(self.config("/denied", max_pages=1, sitemaps=False))
        self.assertEqual(s["access_diagnostics"]["page_access_counts"]["http_access_denied"], 1)
        self.assertNotIn("configured_page_limit", s["access_diagnostics"]["stop_reasons"])
        with tempfile.TemporaryDirectory() as tmp:
            c = Crawler(self.config(max_pages=2, sitemaps=False), Path(tmp))
            c.log = lambda _: None
            try:
                s = c.run()
            finally:
                c.close()
        self.assertIn("configured_page_limit", s["access_diagnostics"]["stop_reasons"])
        self.assertEqual(s["access_diagnostics"]["remote_denial_or_challenge_pages"], 0)

    def test_recovered_rate_limit_is_retained_in_history(self):
        with patch("beyondseo.network.time.sleep"):
            s = self.crawl(self.config("/retry", retries=1, max_pages=1, sitemaps=False))
        self.assertEqual(s["html_documents"], 1)
        self.assertEqual(s["access_diagnostics"]["http_429_attempts_recorded"], 1)
        p = json.loads((self.out / "pages.jsonl").read_text().splitlines()[0])
        self.assertEqual([e["status"] for e in p["http_events"]], [429, 200])

    def test_challenge_heuristic_does_not_flag_normal_article(self):
        self.assertIsNone(
            challenge_signal(
                {}, b"<title>How CAPTCHA works</title><p>Cloudflare captcha access denied</p>"
            )
        )
        self.assertEqual(
            challenge_signal(
                {},
                b'<title>Just a moment...</title><script src="/cdn-cgi/challenge-platform/check"></script>',
            )["confidence"],
            "heuristic",
        )

    def test_browser_headers_are_origin_bound_and_not_logged(self):
        t = Transport(self.config(allow_hosts=["localhost"]))
        headers = {
            "authorization": "Bearer fixture-value",
            "apikey": "fixture-public-key",
            "cookie": "must-not-forward",
        }
        r = t.fetch(self.root + "/requires-header", request_headers=headers)
        self.assertEqual(Handler.received_headers.get("Authorization"), "Bearer fixture-value")
        self.assertIsNone(Handler.received_headers.get("Cookie"))
        self.assertNotIn("fixture-value", json.dumps(r.http_events))
        r = t.fetch(self.root + "/credential-redirect", request_headers=headers)
        self.assertEqual(r.status, 200)
        self.assertIsNone(Handler.received_headers.get("Authorization"))
        self.assertIsNone(Handler.received_headers.get("Apikey"))

    def test_readonly_cors_options_allowed_but_post_not_sent(self):
        t = Transport(self.config())
        self.assertEqual(t.fetch(self.root + "/requires-header", method="OPTIONS").status, 204)
        self.assertEqual(Handler.hits["OPTIONS"], 1)
        r = t.fetch(self.root + "/requires-header", method="POST")
        self.assertIn("unsupported_http_method", r.error)
        self.assertEqual(Handler.hits["POST"], 0)

    def test_unavailable_403_robots_does_not_imply_sitewide_denial(self):
        Handler.robots_status = 403
        s = self.crawl(self.config("/utf8", max_pages=1, sitemaps=False))
        self.assertEqual(s["html_documents"], 1)
        self.assertEqual(Handler.hits["/utf8"], 1)
        r = json.loads((self.out / "robots.json").read_text())[self.root]
        self.assertFalse(r["blocked"])
        self.assertEqual(r["policy_availability"], "unavailable")

    def test_empty_render_and_javascript_error_limit_coverage(self):
        import importlib.util

        if not importlib.util.find_spec("playwright"):
            self.skipTest("Optional Playwright is not installed")
        s = self.crawl(
            self.config("/js-broken", max_pages=1, sitemaps=False, render=True, render_wait_ms=100)
        )
        self.assertTrue(s["coverage_limited"])
        self.assertEqual(s["render_content_warnings"], 1)
        self.assertEqual(s["render_javascript_error_pages"], 1)
        self.assertEqual(s["access_diagnostics"]["remote_denial_or_challenge_pages"], 0)
        self.assertIn("incomplete", s["access_diagnostics"]["assessment"])

    def test_optional_local_render(self):
        import importlib.util

        if not importlib.util.find_spec("playwright"):
            self.skipTest("Optional Playwright is not installed")
        self.crawl(self.config("/js", max_pages=1, sitemaps=False, render=True, render_wait_ms=100))
        p = json.loads((self.out / "pages.jsonl").read_text().splitlines()[0])
        r = p["rendered"]
        self.assertFalse(r["error"], r["error"])
        self.assertEqual(r["data"]["title"], "Rendered")
        self.assertEqual(r["data"]["headings"]["h1"], ["JavaScript heading"])
        self.assertEqual(Handler.hits["POST"], 0)
        self.assertGreater(r["blocked_requests"], 0)
        self.assertTrue(
            any(
                e["reason"] == "non_get_method" and e["source"] == "local"
                for e in r["blocked_request_log"]
            )
        )
        self.assertTrue(any(item["url"].endswith("/rendered-link") for item in r["data"]["links"]))


if __name__ == "__main__":
    unittest.main()
