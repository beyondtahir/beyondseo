"""Explain access failures without mistaking crawler limits for website blocking."""

import re
from collections import Counter


def challenge_signal(headers, body):
    if headers.get("cf-mitigated", "").strip().lower() == "challenge":
        return {
            "code": "challenge_response",
            "confidence": "observed",
            "evidence": "Response contains cf-mitigated: challenge.",
        }
    # A challenge-shaped title AND supporting interstitial markup are required.
    # Merely mentioning CAPTCHA, Cloudflare or robots in ordinary content is insufficient.
    text = body[:131072].decode("utf-8", "replace").lower()
    title = re.search(r"<title[^>]*>(.*?)</title\s*>", text, re.S)
    title = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
    interstitial = title in (
        "just a moment...",
        "just a moment",
        "attention required! | cloudflare",
        "verify you are human",
        "security verification",
        "access denied",
    )
    marker = any(
        s in text
        for s in (
            "/cdn-cgi/challenge-platform/",
            "cf-chl-",
            "cf_chl_opt",
            "g-recaptcha",
            "h-captcha",
            "cf-turnstile",
        )
    )
    if interstitial and marker:
        return {
            "code": "challenge_response",
            "confidence": "heuristic",
            "evidence": "Interstitial title and challenge markup found; review the saved response.",
        }
    return None


def classify_access(status, headers, body, error=""):
    if error in ("robots_rule_disallowed", "robots_unavailable", "robots_scope_limited"):
        explanations = {
            "robots_rule_disallowed": "A retrieved robots rule disallows this URL for the crawler.",
            "robots_unavailable": "The request was withheld because robots policy could not be retrieved. Inspect its status/error; no disallow rule is established.",
            "robots_scope_limited": "The robots file redirected outside the configured host scope. This is a local scope limit, not a robots disallow rule.",
        }
        return {"code": error, "confidence": "observed", "evidence": explanations[error]}
    if error in ("redirect_loop", "redirect_limit"):
        return {
            "code": error,
            "confidence": "observed",
            "evidence": "Redirect processing stopped: " + error,
        }
    challenge = challenge_signal(headers, body)
    if challenge:
        return challenge
    if error == "robots_disallowed":
        return {
            "code": "robots_policy",
            "confidence": "observed",
            "evidence": "Crawler policy did not permit this request. Inspect robots.json for a disallow rule or unavailable policy.",
        }
    if error in ("redirect_out_of_scope", "excluded_pattern"):
        return {"code": "local_scope", "confidence": "observed", "evidence": error}
    if error == "crawl_delay_exceeds_run_wait_budget":
        return {
            "code": "local_wait_budget",
            "confidence": "observed",
            "evidence": "Required crawl delay exceeds the local per-request wait budget.",
        }
    if status == 429:
        return {
            "code": "http_rate_limited",
            "confidence": "observed",
            "evidence": "Server returned HTTP 429; retry-after="
            + headers.get("retry-after", "not supplied"),
        }
    if status in (401, 403):
        return {
            "code": "http_access_denied",
            "confidence": "observed",
            "evidence": f"Server returned HTTP {status}; the response alone does not identify the reason.",
        }
    if error:
        return {"code": "request_failed", "confidence": "observed", "evidence": error}
    if status >= 500:
        return {
            "code": "server_error",
            "confidence": "observed",
            "evidence": f"HTTP {status} server error; not enough evidence to attribute it to bot blocking.",
        }
    if status >= 400:
        return {"code": "http_error", "confidence": "observed", "evidence": f"HTTP {status}"}
    return {
        "code": "response_received",
        "confidence": "observed",
        "evidence": f"HTTP {status} received; no supported denial/challenge marker detected.",
    }


def summarize_access(pages, robots, sitemap_fetches, summary):
    counts = Counter(
        (
            p.get("access")
            or classify_access(p["status"], p.get("headers", {}), b"", p.get("error", ""))
        )["code"]
        for p in pages
    )
    events = [e for p in pages for e in p.get("http_events", [])]
    events += [e for r in robots.values() for e in r.get("http_events", [])]
    events += [e for r in sitemap_fetches for e in r.get("http_events", [])]
    events += [e for p in pages for e in p.get("rendered", {}).get("http_events", [])]
    retry_429 = sum(e["status"] == 429 for e in events)
    http_denials = sum(e["status"] in (401, 403) for e in events)
    challenges = sum(bool(e.get("challenge_detected")) for e in events)
    remote = sum(
        counts[c] for c in ("http_access_denied", "http_rate_limited", "challenge_response")
    )
    discovery_codes = Counter(
        (r.get("access") or {}).get("code") for r in list(robots.values()) + sitemap_fetches
    )
    remote_discovery = sum(
        discovery_codes[c]
        for c in ("http_access_denied", "http_rate_limited", "challenge_response")
    )
    render_blocks = Counter(
        e["reason"] for p in pages for e in p.get("rendered", {}).get("blocked_request_log", [])
    )
    stop = []
    if (
        summary["pending_urls"]
        and summary["attempted_urls"] >= summary["configuration"]["max_pages"]
    ):
        stop.append("configured_page_limit")
    elif summary["pending_urls"]:
        stop.append("unfinished_frontier")
    else:
        stop.append("discovered_frontier_exhausted")
    for reason in (
        "depth_limit",
        "discovery_limit",
        "query_variant_limit",
        "sitemap_entry_limit",
        "sitemap_limit",
        "excluded_pattern",
    ):
        if summary["discovery_skips"].get(reason):
            stop.append(reason)
    if remote or remote_discovery or http_denials or challenges:
        assessment = "Access denial, rate limit or challenge was observed. Inspect affected URLs; this is not a whole-site conclusion."
    elif retry_429:
        assessment = (
            "At least one HTTP 429 was observed, including attempts that may have recovered."
        )
    elif any(
        counts[c]
        for c in (
            "robots_policy",
            "robots_rule_disallowed",
            "robots_unavailable",
            "robots_scope_limited",
        )
    ):
        assessment = "Some requests were withheld by robots policy. Inspect policy evidence before calling this a server block."
    elif (
        counts["request_failed"]
        or counts["server_error"]
        or summary["render_errors"]
        or summary.get("render_content_warnings")
        or summary.get("render_javascript_error_pages")
    ):
        assessment = "Some requests or rendering were incomplete; blocking is not established from those observations alone."
    else:
        assessment = "No supported access-denial or challenge signal was observed in this sample. This does not predict larger or later crawls."
    return {
        "assessment": assessment,
        "page_access_counts": dict(counts),
        "remote_denial_or_challenge_pages": remote,
        "remote_denial_or_challenge_discovery_responses": remote_discovery,
        "http_access_denied_attempts_recorded": http_denials,
        "challenge_attempts_recorded": challenges,
        "http_429_attempts_recorded": retry_429,
        "http_attempts_recorded": len(events),
        "stop_reasons": stop,
        "browser_restriction_counts": dict(render_blocks),
        "history_note": "Only instrumented HTTP attempts are counted, including recorded browser requests; legacy runs may lack attempt history.",
    }
