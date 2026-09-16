"""Verify discovered pages, preserving access and rendering limits."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from .engine import Crawler
from .evidence import capture_quality, combined_index_signals, missing_content, selected_data
from .network import Config, normalize_url, utcnow
from .review import read_json, read_pages, save_report


def source_rows(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, strict=True))
    except csv.Error as error:
        raise ValueError(
            "Malformed source CSV: "
            + str(error)
            + ". Use discovery's sources.csv or CSV doubled quotes, not JSON backslash escaping."
        ) from error
    result = {}
    for row in rows:
        if None in row:
            raise ValueError(
                "Source CSV has extra fields. Quote values containing commas correctly."
            )
        url = normalize_url(row.get("URL") or row.get("url") or "")
        if not url:
            raise ValueError("Source CSV needs a URL column with valid http(s) addresses.")
        provenance = row.get("provenance")
        if isinstance(provenance, str) and provenance:
            provenance = json.loads(provenance)
        provenance = provenance or [
            {k: v for k, v in row.items() if k not in ("URL", "url", "provenance") and v}
        ]
        if not isinstance(provenance, list) or any(
            not isinstance(item, dict) for item in provenance
        ):
            raise ValueError("Source provenance must be a JSON list of observations.")
        existing = result.setdefault(url, {**row, "URL": url, "provenance": []})
        for observation in provenance:
            if observation not in existing["provenance"]:
                existing["provenance"].append(observation)
    if not result:
        raise ValueError("Source CSV has no URLs.")
    return list(result.values())


def target_links(data, target_host):
    return [
        link
        for link in data.get("links", [])
        if (urlsplit(link["url"]).hostname or "").removeprefix("www.") == target_host
    ]


def mention_evidence(data, names):
    text = data.get("text") or data.get("main_text") or ""
    matches = []
    for name in dict.fromkeys(n.strip() for n in names if n and n.strip()):
        match = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I)
        if match:
            matches.append(
                {"name": name, "excerpt": text[max(0, match.start() - 90) : match.end() + 130]}
            )
    return matches


def verify_source(
    source,
    target_host,
    out,
    mode="auto",
    allow_private=False,
    follow_redirects=True,
    brand="",
    aliases=(),
):
    host = urlsplit(source).hostname
    allowed_hosts = {host.removeprefix("www."), "www." + host.removeprefix("www.")}
    mode_now = mode
    attempts = []
    # Bounded redirect-host expansion; no ordinary outgoing links are followed.
    for index in range(7):
        folder = Path(out) / f"attempt-{index + 1:02d}"
        config = Config(
            source,
            max_pages=1,
            workers=1,
            sitemaps=False,
            render_mode=mode_now,
            allow_hosts=sorted(allowed_hosts),
            allow_private=allow_private,
            render_max_requests=100,
        )
        crawler = Crawler(config, folder)
        try:
            crawler.log = lambda _: None
            summary = crawler.run()
        finally:
            crawler.close()
        page = next((p for p in read_pages(folder) if p["url"] == config.url), {})
        data, representation = selected_data(page)
        links = target_links(data, target_host)
        attempts.append(
            {
                "folder": folder.name,
                "error": page.get("error", ""),
                "status": page.get("status", 0),
                "representation": representation,
                "allowed_hosts": sorted(allowed_hosts),
                "mode": mode_now,
            }
        )
        redirects = list(page.get("redirects", []))
        if page.get("error") in ("robots_scope_limited", "robots_disallowed"):
            for policy in read_json(folder / "robots.json").values():
                if policy.get("error") == "redirect_out_of_scope":
                    redirects.extend(policy.get("redirects", []))
        if (
            follow_redirects
            and page.get("error")
            in ("redirect_out_of_scope", "robots_scope_limited", "robots_disallowed")
            and index < 5
        ):
            new_hosts = {
                urlsplit(r["target"]).hostname
                for r in redirects
                if r.get("target") and normalize_url(r["target"])
            } - allowed_hosts
            if new_hosts:
                allowed_hosts.update(new_hosts)
                continue
        # Check late links on scripted pages even when their initial text looks substantial.
        if (
            mode == "auto"
            and mode_now != "browser"
            and not links
            and not page.get("error")
            and data.get("script_count")
            and not page.get("rendered")
            and not missing_content(page)
        ):
            mode_now = "browser"
            continue
        break
    rendered = page.get("rendered") or {}
    missing = missing_content(page)
    usable = (
        bool(data) and not page.get("error") and 200 <= page.get("status", 0) < 300 and not missing
    )
    incomplete_render = bool(
        rendered.get("error")
        or rendered.get("content_warning")
        or rendered.get("javascript_errors")
        or capture_quality(page)["limits"]
    )
    if usable and links:
        verification = "link_observed"
    elif usable and not incomplete_render:
        verification = "no_link_in_captured_content"
    else:
        verification = "unverified_access"
    mentions = mention_evidence(data, [brand, *aliases]) if usable else []
    return {
        "source_url": source,
        "final_url": page.get("final_url"),
        "status": page.get("status"),
        "checked_at": utcnow(),
        "verification": verification,
        "representation": representation,
        "coverage_limited": summary["coverage_limited"] or incomplete_render,
        "target_links": links if usable else [],
        "brand_mentions": mentions,
        "mention_status": "observed_in_page"
        if mentions
        else "not_observed_in_capture"
        if usable
        else "unverified",
        "source_index_signals": combined_index_signals(page),
        "error": page.get("error", ""),
        "access": page.get("access"),
        "robots_decision": page.get("robots_decision"),
        "missing_content_candidate": missing,
        "render_error": rendered.get("error", ""),
        "render_warning": rendered.get("content_warning", ""),
        "title": data.get("title", ""),
        "main_excerpt": data.get("main_text", "")[:500],
        "independent_endorsement": "not_assessed",
        "evidence_folder": str(folder),
        "attempt_history": attempts,
    }


def check_sources(
    sources,
    target,
    out,
    limit=30,
    mode="auto",
    allow_private=False,
    follow_redirects=True,
    brand="",
    aliases=(),
):
    target = normalize_url(target)
    if not target or not 1 <= limit <= 500:
        raise ValueError("Supply a valid target URL and a source limit from 1 to 500.")
    inputs = source_rows(sources)
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose a new backlink-check output folder.")
    target_host = urlsplit(target).hostname.removeprefix("www.")
    results = []
    for row in inputs[:limit]:
        source = row["URL"]
        folder = out / "sources" / hashlib.sha256(source.encode()).hexdigest()[:20]
        result = verify_source(
            source, target_host, folder, mode, allow_private, follow_redirects, brand, aliases
        )
        result["evidence_folder"] = Path(result["evidence_folder"]).relative_to(out).as_posix()
        result["discovery"] = {k: v for k, v in row.items() if k != "URL" and v}
        results.append(result)
    result = {
        "target": target,
        "brand": brand,
        "checked_at": utcnow(),
        "sources_supplied": len(inputs),
        "sources_checked": len(results),
        "sources_remaining": max(0, len(inputs) - len(results)),
        "observed_link_pages": sum(r["verification"] == "link_observed" for r in results),
        "observed_mention_pages": sum(bool(r["brand_mentions"]) for r in results),
        "unverified_pages": sum(r["verification"] == "unverified_access" for r in results),
        "results": results,
        "note": "A supplied/search-result URL is a candidate. Links and mentions are verified separately in captured content. This is a bounded sample, not a complete backlink count or proof of indexing, endorsement or ranking value.",
    }
    lines = [
        "# Your backlink and mention evidence",
        "",
        f"Checked {len(results)} sources. Links observed on {result['observed_link_pages']} pages; access unverified on {result['unverified_pages']}.",
        "",
        result["note"],
        "",
    ]
    lines += [
        f"- {r['source_url']} — {r['verification']} ({r['representation']}; {r['error'] or 'response captured'})"
        for r in results
    ]
    return save_report(out, "backlinks", result, lines)
