"""Persistent bounded crawl, sitemap discovery, evidence export, and link analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__
from .diagnostics import classify_access, summarize_access
from .evidence import combined_index_signals, missing_content, selected_data
from .extract import extract, index_signals, page_findings
from .network import RobotsCache, Transport, normalize_url, origin, utcnow


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def csv_value(value):
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        value = "'" + value
    return value


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: csv_value(v) for k, v in row.items()})


def parse_sitemap(body):
    sanitized = body.replace(b"\0", b"").upper()
    if b"<!DOCTYPE" in sanitized or b"<!ENTITY" in sanitized:
        raise ValueError("Sitemap DTD/entities are not supported")
    root = ET.fromstring(body)
    kind = root.tag.rsplit("}", 1)[-1]
    if kind not in ("urlset", "sitemapindex"):
        raise ValueError("Expected sitemap urlset or sitemapindex")
    records = []
    for node in root:
        if node.tag.rsplit("}", 1)[-1] not in ("url", "sitemap"):
            continue
        fields = {c.tag.rsplit("}", 1)[-1]: (c.text or "").strip() for c in node}
        if fields.get("loc"):
            records.append(fields)
    return kind, records


class Crawler:
    def __init__(self, config, out, resume=False, selectors=None):
        self.config = config
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.selectors = selectors or {}
        self.skips = Counter()
        self.sitemap_evidence = []
        self.log = lambda s: print(s, file=sys.stderr, flush=True)
        self.db = sqlite3.connect(str(self.out / "crawl.sqlite3"))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS urls (url TEXT PRIMARY KEY,depth INTEGER,source TEXT,state TEXT DEFAULT 'pending',reason TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS pages (url TEXT PRIMARY KEY,payload TEXT);
        CREATE TABLE IF NOT EXISTS sitemap_urls (url TEXT,sitemap TEXT,lastmod TEXT,PRIMARY KEY(url,sitemap));""")
        old = self.meta("config")
        if old and not resume:
            raise ValueError(
                "Output already contains a crawl. Use --resume or a new output directory."
            )
        semantic = asdict(config)
        for key in ("max_pages", "workers", "delay", "timeout", "retries"):
            semantic.pop(key)
        signature = {"config": semantic, "selectors": self.selectors, "schema_version": 1}
        if old and old != signature:
            raise ValueError(
                "Resume configuration differs. Only page budget, workers, delay, timeout and retries may change."
            )
        if not old:
            self.setmeta("config", signature)
            self.setmeta("started_at", utcnow())
        self.transport = Transport(config)
        self.robots = RobotsCache(self.transport)
        self.db.execute("UPDATE urls SET state='pending' WHERE state='fetching'")
        self.db.commit()

    def meta(self, key):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def setmeta(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))
        self.db.commit()

    def enqueue(self, raw, depth, source):
        url = normalize_url(raw, drop_tracking=self.config.drop_tracking)
        reason = "invalid_url" if not url else self.config.exclusion(url)
        if not reason and depth > self.config.max_depth:
            reason = "depth_limit"
        if reason:
            self.skips[reason] += 1
            return
        old = self.db.execute("SELECT depth FROM urls WHERE url=?", (url,)).fetchone()
        if old:
            if depth < old[0]:
                self.db.execute("UPDATE urls SET depth=? WHERE url=?", (depth, url))
            return
        if self.db.execute("SELECT COUNT(*) FROM urls").fetchone()[0] >= self.config.max_discovered:
            self.skips["discovery_limit"] += 1
            return
        p = urlsplit(url)
        if p.query:
            path = p.scheme + "://" + p.netloc + p.path
            count = sum(
                1
                for (u,) in self.db.execute("SELECT url FROM urls")
                if u.split("?", 1)[0] == path and "?" in u
            )
            if count >= self.config.max_query_variants:
                self.skips["query_variant_limit"] += 1
                return
        self.db.execute("INSERT INTO urls(url,depth,source) VALUES (?,?,?)", (url, depth, source))

    def discover_sitemaps(self):
        if self.meta("sitemaps_complete") or not self.config.sitemaps:
            return
        root = origin(self.config.url)
        robots = self.robots.get(self.config.url)
        q = deque(
            robots.sitemaps
            + [root + "/sitemap.xml", root + "/sitemap_index.xml", root + "/wp-sitemap.xml"]
        )
        seen = set()
        while q and len(seen) < self.config.max_sitemaps:
            raw = q.popleft()
            url = normalize_url(raw, root, self.config.drop_tracking)
            if not url or url in seen or not self.config.in_scope(url):
                continue
            seen.add(url)
            r = self.transport.fetch(url, self.robots.allowed, self.robots.delay)
            info = {
                "url": url,
                "status": r.status,
                "error": r.error,
                "fetched_at": r.fetched_at,
                "sha256": hashlib.sha256(r.body).hexdigest(),
                "redirects": r.redirects,
                "entries": 0,
                "http_events": r.http_events,
                "access": classify_access(r.status, r.headers, r.body, r.error),
            }
            if r.status == 200 and not r.error:
                try:
                    kind, items = parse_sitemap(r.body)
                    info["kind"] = kind
                    info["entries"] = len(items)
                    folder = self.out / "sitemap-evidence"
                    folder.mkdir(exist_ok=True)
                    name = hashlib.sha256(url.encode()).hexdigest() + ".xml"
                    (folder / name).write_bytes(r.body)
                    info["xml_path"] = "sitemap-evidence/" + name
                    for item in items:
                        target = normalize_url(item["loc"], drop_tracking=self.config.drop_tracking)
                        if not target or not self.config.in_scope(target):
                            continue
                        if kind == "sitemapindex":
                            q.append(target)
                        else:
                            total = self.db.execute("SELECT COUNT(*) FROM sitemap_urls").fetchone()[
                                0
                            ]
                            if total >= self.config.max_discovered:
                                self.skips["sitemap_entry_limit"] += 1
                                break
                            self.db.execute(
                                "INSERT OR IGNORE INTO sitemap_urls VALUES (?,?,?)",
                                (target, url, item.get("lastmod", "")),
                            )
                            self.enqueue(target, 0, "sitemap")
                except (ET.ParseError, ValueError) as e:
                    info["error"] = str(e)
            self.sitemap_evidence.append(info)
        if q:
            self.skips["sitemap_limit"] += len(q)
        self.setmeta("sitemap_evidence", self.sitemap_evidence)
        self.setmeta("sitemaps_complete", True)
        self.db.commit()

    def fetch_page(self, url, depth):
        r = self.transport.fetch(url, self.robots.allowed, self.robots.delay)
        page = {
            "url": url,
            "depth": depth,
            "final_url": r.final_url,
            "status": r.status,
            "headers": r.headers,
            "redirects": r.redirects,
            "error": r.error,
            "attempts": r.attempts,
            "elapsed_ms": r.elapsed_ms,
            "fetched_at": r.fetched_at,
            "body_bytes": len(r.body),
            "body_sha256": hashlib.sha256(r.body).hexdigest(),
            "data": None,
            "html_path": None,
            "http_events": r.http_events,
            "access": classify_access(r.status, r.headers, r.body, r.error),
            "withheld_url": r.withheld_url,
            "robots_decision": self.robots.decision(r.withheld_url) if r.withheld_url else None,
        }
        ctype = r.headers.get("content-type", "").lower().split(";")[0].strip()
        html = ctype in ("text/html", "application/xhtml+xml") or (
            not ctype and r.body.lstrip().lower().startswith((b"<!doctype html", b"<html"))
        )
        if r.body and html:
            if self.config.save_html:
                name = hashlib.sha256(url.encode()).hexdigest() + ".html"
                folder = self.out / "html"
                folder.mkdir(exist_ok=True)
                (folder / name).write_bytes(r.body)
                page["html_path"] = "html/" + name
            # Error pages remain evidence but do not contribute content recommendations or discovery.
            if 200 <= r.status < 300 and not r.error:
                page["data"] = extract(r.body, r.final_url, r.headers, self.selectors)
                page["index_signals"] = index_signals(
                    page["data"], r.headers, r.status, r.final_url
                )
        return page

    def run(self):
        self.setmeta("last_configuration", asdict(self.config))
        self.enqueue(self.config.url, 0, "seed")
        self.db.commit()
        self.discover_sitemaps()
        count = self.db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        try:
            with ThreadPoolExecutor(max_workers=self.config.workers) as pool:
                while count < self.config.max_pages:
                    rows = self.db.execute(
                        "SELECT url,depth FROM urls WHERE state='pending' ORDER BY depth,rowid LIMIT ?",
                        (min(self.config.workers, self.config.max_pages - count),),
                    ).fetchall()
                    if not rows:
                        break
                    for url, _ in rows:
                        self.db.execute("UPDATE urls SET state='fetching' WHERE url=?", (url,))
                    self.db.commit()
                    # Consume in queue order: persistent results and frontier stay reproducible.
                    futures = [pool.submit(self.fetch_page, url, depth) for url, depth in rows]
                    for (url, depth), future in zip(rows, futures):
                        page = future.result()
                        from .render import needs_browser

                        browser_needed = self.config.render_mode == "browser" or (
                            self.config.render_mode == "auto" and needs_browser(page.get("data"))
                        )
                        if browser_needed and page.get("data") and not page["error"]:
                            from .render import render_page

                            page["rendered"] = render_page(page, self)
                        self.db.execute(
                            "INSERT OR REPLACE INTO pages VALUES (?,?)",
                            (url, json.dumps(page, ensure_ascii=False)),
                        )
                        self.db.execute(
                            "UPDATE urls SET state='done',reason=? WHERE url=?",
                            (page.get("error", ""), url),
                        )
                        d = page.get("data") or {}
                        if d:
                            for link in d.get("links", []):
                                self.enqueue(link["url"], depth + 1, "anchor")
                            for link in (
                                d.get("canonical", [])
                                + d.get("hreflang", [])
                                + d.get("pagination", [])
                            ):
                                if link.get("url"):
                                    self.enqueue(link["url"], depth + 1, "metadata")
                        rd = (page.get("rendered") or {}).get("data") or {}
                        for link in rd.get("links", []):
                            self.enqueue(link["url"], depth + 1, "rendered_anchor")
                        count += 1
                        self.db.commit()
                        self.log(
                            f"[{count}/{self.config.max_pages}] {page['status']} {url}"
                            + (f" — {page['error']}" if page["error"] else "")
                        )
        except KeyboardInterrupt:
            self.setmeta("interrupted", True)
        self.setmeta("last_run_at", utcnow())
        previous = self.meta("skips") or {}
        self.setmeta("skips", dict(Counter(previous) + self.skips))
        previous_robots = self.meta("robots") or {}
        previous_robots.update(self.robots.evidence)
        self.setmeta("robots", previous_robots)
        return self.export()

    def export(self):
        pages = [
            json.loads(row[0])
            for row in self.db.execute("SELECT payload FROM pages ORDER BY rowid")
        ]
        urls = [
            dict(zip(["url", "depth", "source", "state", "reason"], row))
            for row in self.db.execute("SELECT * FROM urls ORDER BY rowid")
        ]
        lookup = {p["url"]: p for p in pages}
        for p in pages:
            if not p["error"] and 200 <= p["status"] < 300:
                lookup.setdefault(p["final_url"], p)
        issues = []
        links = []
        incoming = defaultdict(set)
        groups = defaultdict(lambda: defaultdict(list))
        inventory = []
        # Count each final HTML document once for duplicates and outgoing graph edges.
        documents = {}
        for p in pages:
            p["selected_index_signals"] = combined_index_signals(p)
            p["missing_content"] = missing_content(p)
            data, _ = selected_data(p)
            if data:
                documents.setdefault(p["final_url"], p)
            issues.extend(page_findings(p))
            if p.get("rendered", {}).get("error"):
                issues.append(
                    {
                        "url": p["url"],
                        "code": "render_failed",
                        "severity": "medium",
                        "confidence": "observed",
                        "evidence": p["rendered"]["error"],
                        "action": "Inspect the local browser failure; raw HTML findings remain available.",
                    }
                )
        for final, p in documents.items():
            d, representation = selected_data(p)
            for key in ("title", "meta_description", "content_sha256"):
                if (
                    not p["missing_content"]
                    and d.get(key)
                    and (key != "content_sha256" or d.get("main_text"))
                ):
                    groups[key][d[key]].append(final)
            all_links = [(item, "raw") for item in (p.get("data") or {}).get("links", [])] + [
                (item, "rendered")
                for item in (p.get("rendered", {}).get("data") or {}).get("links", [])
            ]
            for link, representation in all_links:
                target = normalize_url(link["url"], drop_tracking=self.config.drop_tracking)
                internal = self.config.in_scope(target)
                dest = lookup.get(target)
                if internal:
                    incoming[target].add(final)
                links.append(
                    {
                        "source": final,
                        "target": target,
                        "anchor": link["anchor"],
                        "rel": link["rel"],
                        "representation": representation,
                        "internal": internal,
                        "target_status": dest["status"] if dest else None,
                        "target_error": dest["error"] if dest else None,
                        "checked": bool(dest),
                        "target_missing_content_candidate": bool(
                            dest and dest.get("missing_content")
                        ),
                    }
                )
                if (
                    internal
                    and dest
                    and (dest["status"] in (404, 410) or dest.get("missing_content"))
                    and not dest["error"]
                ):
                    issues.append(
                        {
                            "url": final,
                            "code": "internal_link_missing_content_candidate"
                            if dest.get("missing_content")
                            else "broken_internal_link",
                            "severity": "high",
                            "confidence": "heuristic"
                            if dest.get("missing_content")
                            else "observed",
                            "evidence": target
                            + " returned "
                            + str(dest["status"])
                            + (
                                " with a missing-content screen"
                                if dest.get("missing_content")
                                else ""
                            ),
                            "action": "Update or remove this internal link, or restore its intended destination.",
                        }
                    )
            for canonical in d["canonical"]:
                target = normalize_url(
                    canonical.get("url"), drop_tracking=self.config.drop_tracking
                )
                dest = lookup.get(target)
                if dest and (
                    dest["status"] >= 400
                    or dest.get("selected_index_signals", {}).get("googlebot_noindex_observed")
                    or dest.get("missing_content")
                ):
                    issues.append(
                        {
                            "url": final,
                            "code": "canonical_target_problem",
                            "severity": "high",
                            "confidence": "observed",
                            "evidence": target,
                            "action": "Review the canonical target: it returned an error or declares noindex.",
                        }
                    )
        for key, values in groups.items():
            for value, group in values.items():
                if len(group) > 1:
                    for url in group:
                        issues.append(
                            {
                                "url": url,
                                "code": "duplicate_" + key,
                                "severity": "medium",
                                "confidence": "observed",
                                "evidence": json.dumps(
                                    {"value": value, "urls": group}, ensure_ascii=False
                                ),
                                "action": "Review intent and URL variants before changing content or canonicalization.",
                            }
                        )
        sitemap_rows = [
            dict(zip(["url", "sitemap", "lastmod"], row))
            for row in self.db.execute("SELECT * FROM sitemap_urls")
        ]
        sm_urls = {s["url"] for s in sitemap_rows}
        # Reachability and click depth use the observed anchor graph, not sitemap discovery depth.
        graph = defaultdict(set)
        for item in links:
            if item["internal"]:
                graph[item["source"]].add(item["target"])
        start = lookup.get(self.config.url, {}).get("final_url", self.config.url)
        distance = {start: 0}
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for target in graph[u]:
                v = lookup.get(target, {}).get("final_url", target)
                if v not in distance:
                    distance[v] = distance[u] + 1
                    queue.append(v)
        for p in pages:
            d, representation = selected_data(p)
            final = p["final_url"]
            row = {
                k: p.get(k)
                for k in (
                    "url",
                    "final_url",
                    "status",
                    "error",
                    "fetched_at",
                    "elapsed_ms",
                    "body_bytes",
                    "html_path",
                )
            }
            row.update(
                {
                    "title": d.get("title"),
                    "representation": representation,
                    "initial_title": (p.get("data") or {}).get("title"),
                    "initial_word_count": (p.get("data") or {}).get("word_count"),
                    "missing_content_candidate": bool(p.get("missing_content")),
                    "meta_description": d.get("meta_description"),
                    "h1": d.get("headings", {}).get("h1", []),
                    "word_count": d.get("word_count"),
                    "schema_types": d.get("schema_types", []),
                    "canonical": d.get("canonical", []),
                    "inlinks_observed": len(incoming[p["url"]] | incoming[final]),
                    "outlinks": len(d.get("links", [])),
                    "click_depth_observed": distance.get(final),
                    "in_sitemap": p["url"] in sm_urls,
                    "indexability_candidate": p.get("selected_index_signals", {}).get(
                        "indexability_candidate"
                    ),
                }
            )
            inventory.append(row)
            if (
                d
                and p["url"] in sm_urls
                and final != start
                and not incoming[p["url"]]
                and not incoming[final]
            ):
                issues.append(
                    {
                        "url": p["url"],
                        "code": "orphan_candidate",
                        "severity": "medium",
                        "confidence": "heuristic",
                        "evidence": "Listed in sitemap; no inbound anchor found in this crawl.",
                        "action": "Verify against the remaining site, rendered links and other URL inventories before calling this a confirmed orphan.",
                    }
                )
        pending = sum(u["state"] in ("pending", "fetching") for u in urls)
        errors = sum(bool(p["error"]) or p["status"] >= 400 for p in pages)
        skips = self.meta("skips") or {}
        scope_limited = any(
            skips.get(k, 0) > 0
            for k in (
                "depth_limit",
                "discovery_limit",
                "query_variant_limit",
                "sitemap_entry_limit",
                "sitemap_limit",
                "excluded_pattern",
            )
        )
        issues = list({(i["url"], i["code"], i["evidence"]): i for i in issues}.values())
        render_errors = sum(bool(p.get("rendered", {}).get("error")) for p in pages)
        render_content_warnings = sum(
            bool(p.get("rendered", {}).get("content_warning")) for p in pages
        )
        render_javascript_error_pages = sum(
            bool(p.get("rendered", {}).get("javascript_errors")) for p in pages
        )
        render_readiness_warnings = sum(
            bool(p.get("rendered", {}).get("readiness", {}).get("selector_error"))
            or bool(p.get("rendered", {}).get("readiness", {}).get("deadline_reached"))
            for p in pages
        )
        sitemap_failures = [
            s
            for s in (self.meta("sitemap_evidence") or [])
            if s.get("error") or s["status"] not in (200, 404, 410)
        ]
        summary = {
            "schema_version": 1,
            "engine_version": __version__,
            "seed": self.config.url,
            "started_at": self.meta("started_at"),
            "exported_at": utcnow(),
            "configuration": self.meta("last_configuration") or asdict(self.config),
            "attempted_urls": len(pages),
            "html_documents": len(documents),
            "failed_or_http_error_urls": errors,
            "discovered_urls": len(urls),
            "pending_urls": pending,
            "sitemap_urls": len(sm_urls),
            "findings": len(issues),
            "severity_counts": dict(Counter(i["severity"] for i in issues)),
            "frontier_exhausted": pending == 0,
            "coverage_limited": bool(
                pending
                or errors
                or scope_limited
                or render_errors
                or render_content_warnings
                or render_javascript_error_pages
                or render_readiness_warnings
                or sitemap_failures
            ),
            "rendered_documents": sum(bool(p.get("rendered", {}).get("data")) for p in pages),
            "render_errors": render_errors,
            "render_content_warnings": render_content_warnings,
            "render_javascript_error_pages": render_javascript_error_pages,
            "render_readiness_warnings": render_readiness_warnings,
            "sitemap_fetch_failures": len(sitemap_failures),
            "discovery_skips": skips,
            "coverage_note": "This is the discovered, scoped sample. It cannot establish that all site URLs were found. Canonical/robots observations do not prove indexing.",
            "unmeasured": [
                "search rankings",
                "search volume",
                "organic traffic",
                "conversions",
                "complete inbound backlink profile",
                "Google-selected canonical",
                "actual indexing",
                "Core Web Vitals",
                "structured-data semantic validity",
            ],
        }
        summary["access_diagnostics"] = summarize_access(
            pages, self.meta("robots") or {}, self.meta("sitemap_evidence") or [], summary
        )
        write_json(
            self.out / "access.json",
            {
                "summary": summary["access_diagnostics"],
                "pages": [
                    {
                        "url": p["url"],
                        "status": p["status"],
                        "access": p.get("access"),
                        "robots_decision": p.get("robots_decision"),
                        "withheld_url": p.get("withheld_url", ""),
                        "http_events": p.get("http_events", []),
                    }
                    for p in pages
                ],
            },
        )
        write_json(self.out / "summary.json", summary)
        write_json(self.out / "robots.json", self.meta("robots") or {})
        write_json(
            self.out / "sitemaps.json",
            {"fetches": self.meta("sitemap_evidence") or [], "urls": sitemap_rows},
        )
        write_json(self.out / "issues.json", issues)
        from .review import export_readiness

        export_readiness(
            self.out, pages, summary, self.meta("robots") or {}, {"urls": sitemap_rows}
        )
        with (self.out / "pages.jsonl").open("w", encoding="utf-8") as f:
            for p in pages:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        content_folder = self.out / "content"
        content_folder.mkdir(exist_ok=True)
        with (self.out / "documents.jsonl").open("w", encoding="utf-8") as f:
            for p in pages:
                rendered = p.get("rendered") or {}
                data, representation = selected_data(p)
                if not data:
                    continue
                name = hashlib.sha256(p["url"].encode()).hexdigest()
                markdown = data.get("markdown", "")
                body = data.get("main_text", "")
                (content_folder / (name + ".md")).write_text(markdown, encoding="utf-8")
                (content_folder / (name + ".txt")).write_text(body + "\n", encoding="utf-8")
                document = {
                    "url": p["url"],
                    "final_url": p["final_url"],
                    "title": data["title"],
                    "description": data["meta_description"],
                    "representation": representation,
                    "text": body,
                    "markdown": markdown,
                    "word_count": data["word_count"],
                    "links": data["links"],
                    "markdown_path": "content/" + name + ".md",
                    "text_path": "content/" + name + ".txt",
                    "render_error": rendered.get("error", ""),
                    "render_warning": rendered.get("content_warning", ""),
                }
                f.write(json.dumps(document, ensure_ascii=False) + "\n")
        fields = [
            "url",
            "final_url",
            "status",
            "error",
            "title",
            "representation",
            "initial_title",
            "initial_word_count",
            "missing_content_candidate",
            "meta_description",
            "h1",
            "canonical",
            "word_count",
            "schema_types",
            "indexability_candidate",
            "in_sitemap",
            "inlinks_observed",
            "outlinks",
            "click_depth_observed",
            "elapsed_ms",
            "body_bytes",
            "fetched_at",
            "html_path",
        ]
        write_csv(self.out / "pages.csv", fields, inventory)
        write_csv(
            self.out / "links.csv",
            [
                "source",
                "target",
                "anchor",
                "rel",
                "representation",
                "internal",
                "target_status",
                "target_error",
                "target_missing_content_candidate",
                "checked",
            ],
            links,
        )
        write_csv(
            self.out / "issues.csv",
            ["url", "code", "severity", "confidence", "evidence", "action"],
            issues,
        )
        write_csv(self.out / "frontier.csv", ["url", "depth", "source", "state", "reason"], urls)

        def md(v):
            return (
                str(v)
                .replace("|", "\\|")
                .replace("\n", " ")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

        report = [
            "# BeyondSEO crawl report",
            "",
            f"Seed: {self.config.url}",
            "",
            f"Attempted {len(pages)} URLs; extracted {len(documents)} unique HTML documents; {pending} URLs remain queued; {errors} fetch/HTTP errors.",
            "",
            summary["coverage_note"],
            "",
            summary["access_diagnostics"]["assessment"],
            "",
            "Stop reasons: " + ", ".join(summary["access_diagnostics"]["stop_reasons"]),
            "",
            "Fetch elapsed time includes waits/retries and transfer. It is not TTFB or Core Web Vitals.",
            "",
            "## Findings",
            "",
            "| Severity | Finding | URL | Evidence | Action |",
            "|---|---|---|---|---|",
        ]
        order = {"high": 0, "medium": 1, "low": 2, "info": 3}
        for i in sorted(issues, key=lambda i: order.get(i["severity"], 4))[:100]:
            report.append(
                "| "
                + " | ".join(md(i[k]) for k in ("severity", "code", "url", "evidence", "action"))
                + " |"
            )
        if len(issues) > 100:
            report += [
                "",
                f"The first 100 findings are shown here; issues.csv contains all {len(issues)}.",
            ]
        report += [
            "",
            "## Evidence files",
            "",
            "pages.jsonl contains extraction, headers, timestamps and hashes. pages.csv is the page inventory; links.csv records observed edges and check status. robots.json, sitemaps.json, frontier.csv and crawl.sqlite3 preserve scope and recovery evidence.",
            "",
            "## Not measured",
            "",
            ", ".join(summary["unmeasured"]) + ".",
            "",
        ]
        (self.out / "report.md").write_text("\n".join(report), encoding="utf-8")
        return summary

    def close(self):
        self.db.close()
