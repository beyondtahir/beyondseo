"""Bounded search leads shared by reputation and competitor research.

Host tools execute in the host, not inside Python. Their recorded responses use
the same attempt contract as native providers; no search result verifies a page.
"""

from __future__ import annotations

import hashlib
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from .diagnostics import failure_detail
from .engine import write_csv, write_json
from .network import Config, RobotsCache, Transport, normalize_url, utcnow

PROVIDERS = ("duckduckgo-html", "bing-rss")
SUCCESS = {"results", "empty_results", "no_relevant_results"}
NOTE = (
    "Search results and snippets are unverified leads. Verify source pages with the native "
    "crawler. This bounded sample is not a complete backlink index, a ranking measurement, "
    "or proof of authority. A failed search source does not require a paid tool."
)


def timestamp(value):
    if not value or datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("Use an ISO capture timestamp including its timezone.")
    return value


def parse_search(body, provider):
    """Recognize supported structures; an arbitrary 200 page is not zero results."""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    soup = BeautifulSoup(text, "html.parser")
    if soup.select_one('#challenge-form, form[action*="anomaly"], #captcha-form'):
        return "provider_challenge", [], "Search response contains a challenge form."
    rows = []
    if provider == "bing-rss":
        try:
            if "<!ENTITY" in text.upper() or "<!DOCTYPE" in text.upper():
                raise ValueError("Unsupported XML declarations")
            root = ET.fromstring(text)
            channel = root.find("channel") if root.tag == "rss" else None
            if channel is None:
                raise ValueError("Expected RSS channel")
            for node in channel.findall("item"):
                rows.append(
                    {
                        "url": node.findtext("link"),
                        "title": node.findtext("title", ""),
                        "snippet": node.findtext("description", ""),
                    }
                )
            if not rows:
                return "empty_results", [], "Recognized RSS channel contains no items."
        except (ET.ParseError, ValueError) as exc:
            return "parse_failed", [], str(exc)
    else:
        selectors = {
            "duckduckgo-html": "a.result__a",
            "bing": "li.b_algo h2 a",
            "google": "a:has(h3)",
        }
        key = provider.lower()
        if key not in selectors:
            return "parse_failed", [], "Unsupported saved search format: " + provider
        for a in soup.select(selectors[key]):
            raw = a.get("href", "")
            parsed = urlsplit(urljoin("https://www.google.com/", raw))
            params = parse_qs(parsed.query)
            if key == "google" and parsed.path == "/url":
                raw = (params.get("q") or params.get("url") or [raw])[0]
            elif key == "duckduckgo-html" and "uddg" in params:
                raw = params["uddg"][0]
            else:
                raw = urljoin("https://html.duckduckgo.com/", raw)
            container = a.find_parent(class_="result")
            snippet = container.select_one(".result__snippet") if container else None
            rows.append(
                {
                    "url": raw,
                    "title": a.get_text(" ", strip=True),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                }
            )
        empty = soup.select_one(".no-results, .no-results__message, #b_results .b_no")
        if not rows and empty:
            return "empty_results", [], empty.get_text(" ", strip=True)[:500]
        if not rows:
            return (
                "parse_failed",
                [],
                "No supported result structure or explicit empty-results marker.",
            )
    valid = []
    for i, row in enumerate(rows, 1):
        url = normalize_url(row.get("url") or "")
        if url:
            valid.append({**row, "url": url, "result_order": i})
    return (
        ("results", valid, "")
        if valid
        else ("parse_failed", [], "Result structures found, but no valid destination URLs.")
    )


class RequestBudget:
    def __init__(self, limit=16, seconds=90):
        self.limit, self.used = limit, 0
        self.deadline = time.monotonic() + seconds

    def take(self):
        if self.used >= self.limit or time.monotonic() >= self.deadline:
            raise ValueError("discovery_request_budget_exhausted")
        self.used += 1


class SearchTransport(Transport):
    def __init__(self, config, budget):
        super().__init__(config)
        self.budget = budget

    def once(self, *args, **kwargs):
        self.budget.take()
        self.config.timeout = min(
            self.config.timeout, max(0.1, self.budget.deadline - time.monotonic())
        )
        return super().once(*args, **kwargs)


class NativeSearch:
    def __init__(self, provider, budget, timeout=12, snapshots=None):
        self.provider, self.snapshots = provider, snapshots
        self.base = {
            "duckduckgo-html": "https://html.duckduckgo.com/html/",
            "bing-rss": "https://www.bing.com/search",
        }[provider]
        self.transport = SearchTransport(
            Config(self.base, timeout=timeout, retries=0, delay=1, max_bytes=2_000_000), budget
        )
        self.robots = RobotsCache(self.transport)

    def __call__(self, spec):
        params = {"q": spec["query"]}
        if self.provider == "bing-rss":
            params["format"] = "rss"
        url = self.base + "?" + urlencode(params)
        r = self.transport.fetch(url, allowed=self.robots.allowed, delay_for=self.robots.delay)
        detail = failure_detail(r.error, status=r.status, headers=r.headers, body=r.body)
        result = {
            "provider": self.provider,
            "captured_at": r.fetched_at,
            "request_url": url,
            "status": detail["code"] if detail else "response_received",
            "failure": detail,
            "http_status": r.status,
            "http_events": r.http_events,
            "robots": self.robots.evidence,
            "results": [],
            "actual_market": None,
            "actual_language": None,
            "coverage": "One public result response; localization and pagination not verified.",
            "search_page": 1,
        }
        if r.body and self.snapshots:
            name = hashlib.sha256((url + r.fetched_at).encode()).hexdigest() + ".html"
            Path(self.snapshots).mkdir(parents=True, exist_ok=True)
            (Path(self.snapshots) / name).write_bytes(r.body)
            result["source_snapshot"] = "snapshots/" + name
            result["response_sha256"] = hashlib.sha256(r.body).hexdigest()
        if not detail:
            status, rows, evidence = parse_search(r.body, self.provider)
            result.update(status=status, results=rows)
            if status not in SUCCESS:
                result["failure"] = {"code": status, "evidence": evidence, "cause": "unknown"}
        return result


def consolidate(candidates):
    """Consolidate URL duplicates without dropping separate discovery observations."""
    merged = {}
    for item in candidates:
        url = normalize_url(item.get("url") or item.get("URL") or "")
        if not url:
            continue
        row = merged.setdefault(
            url, {"url": url, "verification": "unverified_lead", "provenance": []}
        )
        for observation in item.get("provenance", []):
            if observation not in row["provenance"]:
                row["provenance"].append(observation)
    return list(merged.values())


def host_attempts(path):
    """Read tool outputs recorded by the host; never pretend Python called a host tool."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    attempts = payload.get("attempts", [])
    if not isinstance(attempts, list) or len(attempts) > 100:
        raise ValueError("Host import needs at most 100 recorded attempts.")
    for row in attempts:
        for key in ("provider", "query", "captured_at", "status", "evidence"):
            if not row.get(key):
                raise ValueError("Host attempt needs " + key)
        timestamp(row["captured_at"])
        if row["status"] == "results" and not row.get("results"):
            raise ValueError("A successful host result must contain result URLs.")
        if row["status"] not in SUCCESS:
            # The raw tool evidence, not a claimed cause, determines classification.
            row["failure"] = failure_detail(
                row["evidence"], status=row.get("http_status", 0), context=row.get("stage", "host")
            )
            row["status"] = row["failure"]["code"]
        row["origin"] = "host_recorded"
        row["coverage"] = row.get(
            "coverage", "Host-returned sample; pagination/localization unknown."
        )
    return attempts


def discover(
    queries,
    out,
    target="",
    providers=PROVIDERS,
    host_records=(),
    candidates=(),
    saved=(),
    offline=False,
    max_requests=16,
    max_queries=8,
    max_candidates=100,
    timeout=12,
    seconds=90,
    cache=None,
    cache_ttl=86400,
    adapters=None,
):
    """Try recorded host responses then permitted native sources for each query.

    Native attempts have zero automatic retries: a failure advances to the next
    provider. The shared budget includes robots, redirects and every HTTP request.
    """
    if not (
        1 <= max_requests <= 100
        and 1 <= max_queries <= 20
        and 1 <= max_candidates <= 500
        and 1 <= timeout <= 30
        and 1 <= seconds <= 300
    ):
        raise ValueError("Discovery budgets exceed supported bounds.")
    if any(p not in PROVIDERS for p in providers) and adapters is None:
        raise ValueError("Unknown native search provider.")
    if not isinstance(queries, list) or len(saved) > 20:
        raise ValueError("Queries must be a list; at most 20 saved search pages can be imported.")
    if target and not normalize_url(target):
        raise ValueError("Discovery target must be a valid http(s) URL.")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    budget = RequestBudget(max_requests, seconds)
    adapters = (
        adapters
        if adapters is not None
        else {p: NativeSearch(p, budget, timeout, out / "snapshots") for p in providers}
    )
    target_host = (urlsplit(target).hostname or "").removeprefix("www.")
    attempts, leads = [], []
    provider_hosts = {
        "google.com",
        "www.google.com",
        "bing.com",
        "www.bing.com",
        "duckduckgo.com",
        "html.duckduckgo.com",
    }

    def add_attempt(row, spec, previous=None):
        row = {
            "actual_market": None,
            "actual_language": None,
            **row,
            "query": spec["query"],
            "requested_market": spec.get("market"),
            "requested_language": spec.get("language"),
            "fallback_from": previous,
            "attempted_at": utcnow(),
        }
        timestamp(row["captured_at"])
        rows = []
        for i, item in enumerate(row.get("results", []), 1):
            url = normalize_url(item.get("url") or "")
            host = (urlsplit(url or "").hostname or "").removeprefix("www.")
            if (
                not url
                or host in provider_hosts
                or (target_host and (host == target_host or host.endswith("." + target_host)))
            ):
                continue
            provenance = {
                k: v for k, v in row.items() if k not in ("results", "http_events", "robots")
            }
            provenance.update(
                result_order=item.get("result_order", i),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
            )
            rows.append({"url": url, "provenance": [provenance]})
        if row["status"] == "results" and not rows:
            row["status"] = "no_relevant_results"
        row["accepted_leads"] = len(rows)
        attempts.append(row)
        leads.extend(rows)
        return row["status"]

    for item in candidates:
        url = item if isinstance(item, str) else item.get("URL") or item.get("url")
        extra = {} if isinstance(item, str) else item
        leads.append(
            {
                "url": url,
                "provenance": [
                    {
                        "provider": "supplied",
                        "query": None,
                        "captured_at": None,
                        "imported_at": utcnow(),
                        "origin": "supplied_candidate",
                        "evidence": extra,
                        "coverage": "URL supplied; source page not yet checked.",
                    }
                ],
            }
        )
    for record in saved:
        spec = {
            "query": record["query"],
            "market": record.get("market"),
            "language": record.get("language"),
        }
        timestamp(record["captured_at"])
        path = Path(record["path"])
        if path.stat().st_size > 5_000_000:
            raise ValueError("Saved search HTML exceeds the 5 MB import limit.")
        body = path.read_bytes()
        status, rows, reason = parse_search(body, record["provider"])
        add_attempt(
            {
                "provider": record["provider"],
                "captured_at": record["captured_at"],
                "status": status,
                "results": rows,
                "origin": "saved_html",
                "source_snapshot": str(path),
                "response_sha256": hashlib.sha256(body).hexdigest(),
                "failure": None if status in SUCCESS else {"code": status, "evidence": reason},
                "coverage": "Supplied snapshot; freshness/localization not independently verified.",
                "search_page": record.get("search_page"),
            },
            spec,
        )
    for spec in queries[:max_queries]:
        if not isinstance(spec, dict) or not str(spec.get("query", "")).strip():
            raise ValueError("Each query needs nonempty query text.")
        previous, found = None, False
        records = [
            r
            for r in host_records
            if r["query"] == spec["query"]
            and r.get("requested_market") == spec.get("market")
            and r.get("requested_language") == spec.get("language")
        ]
        for row in records:
            state = add_attempt(row, spec, previous)
            previous = {"provider": row["provider"], "status": state}
            found |= state == "results"
        if found:
            continue
        if spec.get("query_review_status") == "needs_review":
            add_attempt(
                {
                    "provider": "query_preparation",
                    "origin": "query_review",
                    "status": "query_review_required",
                    "captured_at": utcnow(),
                    "results": [],
                    "failure": None,
                    "coverage": "No search executed for this generated seed. Agent: write a natural buyer query from the profile, mark it reviewed and continue. This is not a provider failure.",
                },
                spec,
                previous,
            )
            continue
        if offline:
            add_attempt(
                {
                    "provider": "native",
                    "status": "tool_unavailable",
                    "captured_at": utcnow(),
                    "results": [],
                    "failure": {
                        "code": "tool_unavailable",
                        "evidence": "Native search disabled for this run.",
                    },
                },
                spec,
                previous,
            )
            continue
        for provider, adapter in adapters.items():
            key = hashlib.sha256(json.dumps([provider, spec], sort_keys=True).encode()).hexdigest()
            cached = Path(cache) / (key + ".json") if cache else None
            row = None
            if cached and cached.exists():
                try:
                    entry = json.loads(cached.read_text(encoding="utf-8"))
                    age = (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(entry["captured_at"].replace("Z", "+00:00"))
                    ).total_seconds()
                    if 0 <= age <= cache_ttl and entry["status"] in SUCCESS:
                        row = {**entry, "cache_hit": True}
                except (ValueError, KeyError, TypeError):
                    pass
            if row is None:
                try:
                    row = adapter(spec)
                except Exception as exc:
                    failure = failure_detail(type(exc).__name__ + ": " + str(exc))
                    row = {
                        "provider": provider,
                        "status": failure["code"],
                        "failure": failure,
                        "captured_at": utcnow(),
                        "results": [],
                    }
                if cached and row["status"] in SUCCESS:
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    # Cache embeds response metadata, not a path into another run's artifacts.
                    write_json(cached, {k: v for k, v in row.items() if k != "source_snapshot"})
            state = add_attempt(row, spec, previous)
            previous = {"provider": provider, "status": state}
            if state == "results":
                break
    merged = consolidate(leads)
    limited = len(merged) > max_candidates
    merged = merged[:max_candidates]
    result = {
        "schema_version": 1,
        "created_at": utcnow(),
        "target": target,
        "status": "leads_available" if merged else "no_leads",
        "search_available": any(a["status"] in SUCCESS for a in attempts),
        "queries_requested": len(queries),
        "queries_processed": min(len(queries), max_queries),
        "queries_needing_review": sum(a["status"] == "query_review_required" for a in attempts),
        "attempts": attempts,
        "candidates": merged,
        "candidate_count": len(merged),
        "native_requests": budget.used,
        "request_budget": max_requests,
        "candidate_budget_reached": limited,
        "coverage_limited": True,
        "note": NOTE,
        "host_tool_availability": "recorded" if host_records else "not_observed_by_cli",
    }
    write_json(out / "discovery.json", result)
    rows = []
    for candidate in merged:
        first = candidate["provenance"][0]
        rows.append(
            {
                "URL": candidate["url"],
                "engine": first.get("provider"),
                "query": first.get("query"),
                "observed_at": first.get("captured_at"),
                "search_page": first.get("search_page"),
                "provenance": candidate["provenance"],
            }
        )
    write_csv(
        out / "sources.csv",
        ["URL", "engine", "query", "observed_at", "search_page", "provenance"],
        rows,
    )
    return result
