"""Read dynamic pages in a local Chromium browser with bounded network access."""

import hashlib
import time
from dataclasses import replace
from urllib.parse import urlsplit

from .extract import extract
from .network import RobotsCache, Transport, normalize_url, utcnow


def needs_browser(data):
    """A heuristic for HTTP responses that depend on scripts for their content."""
    return bool(
        data
        and data.get("script_count")
        and (data.get("word_count", 0) < 80 or not data.get("headings", {}).get("h1"))
    )


def render_page(page, crawler):
    from playwright.sync_api import sync_playwright

    c = crawler.config
    result = dict(
        fetched_at=utcnow(),
        error="",
        data=None,
        blocked_requests=0,
        requests=0,
        html_path=None,
        blocked_request_log=[],
        http_events=[],
        javascript_errors=[],
        scroll_steps_completed=0,
        readiness={},
    )
    config = replace(c, allow_hosts=sorted(set(c.allow_hosts + c.render_allow_hosts)))
    transport = Transport(config)
    transport.limiter = crawler.transport.limiter
    robots = RobotsCache(transport)
    deadline = time.monotonic() + c.timeout
    browser = None

    def remaining_ms():
        return max(1, int((deadline - time.monotonic()) * 1000))

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=c.headless)
                context = browser.new_context(
                    user_agent="BeyondSEO/2.1 (Chromium; +https://beyondtahir.com)",
                    viewport={"width": 1440, "height": 1000},
                    locale="en-US",
                    service_workers="block",
                    accept_downloads=False,
                )

                def route_request(route):
                    request = route.request
                    url = normalize_url(request.url, drop_tracking=False)

                    def block(reason, source="local"):
                        result["blocked_requests"] += 1
                        if len(result["blocked_request_log"]) < 100:
                            result["blocked_request_log"].append(
                                dict(
                                    url=request.url,
                                    resource_type=request.resource_type,
                                    method=request.method,
                                    reason=reason,
                                    source=source,
                                )
                            )
                        route.abort()

                    if not url:
                        block("invalid_url")
                        return
                    if request.method not in ("GET", "OPTIONS"):
                        block("non_get_method")
                        return
                    if request.resource_type == "document" and not c.in_scope(url):
                        block("document_out_of_scope")
                        return
                    if not config.in_scope(url):
                        if (
                            c.render_asset_policy == "public"
                            and request.resource_type != "document"
                        ):
                            # The transport still resolves/checks every address and redirect.
                            config.allow_hosts.append(urlsplit(url).hostname)
                        else:
                            block("asset_host_not_allowed")
                            return
                    if request.resource_type in ("media", "websocket"):
                        block("resource_type_disabled")
                        return
                    if not c.screenshot and request.resource_type in ("image", "font"):
                        block("resource_type_disabled")
                        return
                    if result["requests"] >= c.render_max_requests:
                        block("render_request_limit")
                        return
                    if time.monotonic() >= deadline:
                        block("render_time_limit")
                        return
                    result["requests"] += 1
                    config.timeout = max(0.1, min(c.timeout, remaining_ms() / 1000))
                    r = transport.fetch(
                        url,
                        robots.allowed,
                        robots.delay,
                        request_headers=request.all_headers(),
                        method=request.method,
                    )
                    result["http_events"].extend(r.http_events)
                    if r.error or not r.status:
                        block(
                            r.error or "request_failed",
                            "remote" if r.error == "challenge_response" else "request",
                        )
                        return
                    # Keep the browser's URL/base and origin semantics honest.
                    if r.redirects:
                        block("resource_redirect_disabled")
                        return
                    headers = {
                        k: v
                        for k, v in r.headers.items()
                        if k
                        not in (
                            "content-encoding",
                            "content-length",
                            "transfer-encoding",
                            "connection",
                            "set-cookie",
                        )
                    }
                    route.fulfill(status=r.status, headers=headers, body=r.body)

                context.route("**/*", route_request)
                context.route_web_socket("**/*", lambda ws: ws.close())
                tab = context.new_page()
                tab.on(
                    "pageerror",
                    lambda error: (
                        result["javascript_errors"].append(str(error))
                        if len(result["javascript_errors"]) < 20
                        else None
                    ),
                )
                tab.goto(page["final_url"], wait_until="domcontentloaded", timeout=remaining_ms())
                if c.wait_for_selector:
                    try:
                        tab.locator(c.wait_for_selector).first.wait_for(
                            state="visible", timeout=remaining_ms()
                        )
                        result["readiness"]["selector"] = "visible"
                    except Exception as e:
                        result["readiness"]["selector"] = "timeout_or_error"
                        result["readiness"]["selector_error"] = str(e)
                tab.wait_for_timeout(min(c.render_wait_ms, remaining_ms()))
                # Sample text and links, rather than waiting indefinitely for network idle.
                settle_end = min(deadline, time.monotonic() + c.render_settle_ms / 1000)
                last = None
                stable = 0
                while time.monotonic() < settle_end:
                    snapshot = tab.evaluate(
                        "() => [document.body?.innerText || '', document.links.length]"
                    )
                    stable = stable + 1 if snapshot == last else 0
                    last = snapshot
                    if stable >= 2:
                        break
                    tab.wait_for_timeout(min(250, remaining_ms()))
                result["readiness"]["text_stable_observed"] = stable >= 2
                for _ in range(c.scroll_steps):
                    if time.monotonic() >= deadline:
                        break
                    before = tab.evaluate(
                        "() => [window.scrollY, document.documentElement.scrollHeight]"
                    )
                    tab.evaluate(
                        "() => window.scrollBy(0, Math.max(600, window.innerHeight * 0.85))"
                    )
                    tab.wait_for_timeout(min(500, remaining_ms()))
                    result["scroll_steps_completed"] += 1
                    after = tab.evaluate(
                        "() => [window.scrollY, document.documentElement.scrollHeight]"
                    )
                    if before == after:
                        break
                result["readiness"]["deadline_reached"] = time.monotonic() >= deadline
                html = tab.content().encode("utf-8")
                if len(html) > c.max_bytes:
                    raise ValueError("rendered_html_too_large")
                result["final_url"] = tab.url
                result["data"] = extract(
                    html, tab.url, {"content-type": "text/html; charset=utf-8"}, crawler.selectors
                )
                result["body_sha256"] = hashlib.sha256(html).hexdigest()
                name = hashlib.sha256(page["url"].encode()).hexdigest()
                if c.save_html:
                    folder = crawler.out / "html"
                    folder.mkdir(exist_ok=True)
                    (folder / (name + ".rendered.html")).write_bytes(html)
                    result["html_path"] = "html/" + name + ".rendered.html"
                if c.screenshot:
                    tab.evaluate("() => window.scrollTo(0, 0)")
                    folder = crawler.out / "screenshots"
                    folder.mkdir(exist_ok=True)
                    # A viewport image has a bounded pixel budget even on infinite pages.
                    tab.screenshot(path=str(folder / (name + ".png")), timeout=remaining_ms())
                    result["screenshot_path"] = "screenshots/" + name + ".png"
                if not result["data"]["word_count"]:
                    result["content_warning"] = (
                        "No main text extracted from rendered DOM; inspect scripts, dependencies and the saved document."
                    )
                result["word_count_delta"] = (
                    result["data"]["word_count"] - page["data"]["word_count"]
                )
                result["title_changed"] = result["data"]["title"] != page["data"]["title"]
                result["limitations"] = (
                    "Bounded timed observation and scrolling; no form submissions, login, consent clicks, "
                    "media or WebSockets. Cookies and resource redirects are not forwarded. "
                    "Screenshots are viewport captures; external dependencies follow the selected asset policy."
                )
                context.close()
            finally:
                if browser:
                    browser.close()
    except Exception as e:
        result["error"] = type(e).__name__ + ": " + str(e)
    with crawler.robots.lock:
        crawler.robots.evidence.update(robots.evidence)
    return result
