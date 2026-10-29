"""Controlled local form-to-link trial; never posts to a real publishing platform."""

import html
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from beyondseo import offsite
from beyondseo.network import utcnow


class PublishingFormTests(unittest.TestCase):
    def test_actual_browser_submission_then_native_exact_link_verification(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Optional Playwright runtime unavailable")
        posted = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == "/robots.txt":
                    content = "User-agent: *\nAllow: /".encode()
                elif self.path == "/write":
                    content = b'<form method="post" action="/submit"><label>Title<input name="title"></label><label>Article<textarea name="body"></textarea></label><button>Publish local fixture</button></form>'
                elif self.path == "/articles/1" and posted:
                    content = (
                        "<!doctype html><html><head><title>Local fixture article</title></head><body><main><h1>"
                        + html.escape(posted["title"])
                        + "</h1><article><p>"
                        + html.escape(posted["body"])
                        + '</p><a href="https://example.com/service" rel="nofollow">Supporting resource</a></article></main></body></html>'
                    ).encode()
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/plain" if self.path == "/robots.txt" else "text/html; charset=utf-8",
                )
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def do_POST(self):
                values = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
                posted.update(title=values["title"][0], body=values["body"][0])
                self.send_response(303)
                self.send_header("Location", "/articles/1")
                self.end_headers()

        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            base = f"http://127.0.0.1:{server.server_port}"
            plan = root / "plan.json"
            plan.write_text(
                json.dumps(
                    {
                        "website": "https://example.com",
                        "tasks": [
                            {
                                "site_id": "local-fixture",
                                "format": "article",
                                "posting_url": base + "/write",
                                "target_page": "https://example.com/service",
                            }
                        ],
                    }
                )
            )
            campaign = root / "campaign"
            offsite.initialise(plan, campaign)

            def event(name, **fields):
                path = root / "event.json"
                path.write_text(json.dumps({"event": name, **fields}))
                return offsite.record(campaign, "post-001", path)

            event(
                "authorize",
                scope="standing_campaign",
                user_instruction="Synthetic harness authority for this local test form only; no real account or public platform.",
            )
            event(
                "rules",
                source_url=base + "/rules",
                checked_at=utcnow(),
                ai_policy="allowed",
                submission_permitted=True,
                notes="Local test form permits this fixture; no live platform policy claim.",
            )
            event("account_ready")
            article = {
                "title": "How a useful service page answers a buyer's first questions",
                "reader": "Small business owners",
                "author_voice": "Plain practical explanation, without invented experience",
                "unique_angle": "A buyer's decision before a sales call",
                "opening_answer": "Explain the problem, the deliverable and the evidence before asking the visitor to book a call.",
                "body": " ".join(
                    [
                        "A useful service page helps a buyer decide whether the offer fits their situation. Start with a clear answer: explain the problem you solve, the work you deliver and the evidence supporting your claims before asking someone to book a call.",
                        "Describe the practical outcome in familiar language. A visitor should understand what is included, what they must provide and which decisions remain theirs. Avoid replacing that detail with a long list of fashionable terms.",
                        "Explain the process with honest limits. State the stages, likely dependencies and how the buyer can judge the result. If timing depends on access or the quality of existing information, say so. Do not invent a delivery guarantee.",
                        "Add proof that belongs to the business. A documented example, a clear demonstration or a factual explanation of a method is more useful than an unsupported claim of leadership. Get permission before using a customer's story.",
                        "Answer the questions people actually ask before contacting you. Keep the answer near the relevant service detail and link to a genuinely useful supporting resource. An accordion can preserve a concise layout when it remains accessible.",
                        "Finally, offer one understandable next step. Tell the reader what happens after an enquiry and what information will help the conversation. Review the live page after editing so the title, answer, links and small-screen layout still work together.",
                    ]
                ),
                "source_urls": ["https://example.com/service"],
            }
            path = root / "article.json"
            path.write_text(json.dumps(article))
            staged = offsite.set_draft(campaign, "post-001", path)
            event("approve", digest=staged["digest"])
            self.assertEqual(
                offsite.preflight(campaign, "post-001")["status"], "ready_for_host_submission"
            )
            with sync_playwright() as runtime:
                try:
                    browser = runtime.chromium.launch()
                except Exception as exc:
                    self.skipTest("Optional Chromium unavailable: " + type(exc).__name__)
                try:
                    page = browser.new_page()
                    page.goto(base + "/write")
                    page.get_by_label("Title").fill(article["title"])
                    page.get_by_label("Article").fill(article["body"])
                    page.get_by_role("button", name="Publish local fixture").click()
                    page.wait_for_url(base + "/articles/1")
                    self.assertEqual(page.locator("h1").inner_text(), article["title"])
                finally:
                    browser.close()
            self.assertEqual(posted["body"], article["body"])
            event(
                "submitted", receipt="Observed redirect and matching title on controlled local form"
            )
            event("published", public_url=base + "/articles/1")
            checked = offsite.verify(
                campaign, "post-001", root / "verify", mode="http", allow_private=True
            )
            self.assertEqual(checked["status"], "verified")
            self.assertTrue(checked["exact_target_observed"])
            self.assertEqual(checked["capture"]["target_links"][0]["rel"], ["nofollow"])


if __name__ == "__main__":
    unittest.main()
