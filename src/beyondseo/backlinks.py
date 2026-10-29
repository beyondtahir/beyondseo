"""Verify discovered pages, preserving access and rendering limits."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

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


def import_browser_evidence(input_path, target, out, brand="", aliases=()):
    """Import bounded operator-recorded source DOM observations, never search snippets.

    Input is a capture list or {"captures": [...]}. Captures have kind, url,
    optional final_url, captured_at, browser, visibility, access_state, title,
    text and links ({url, anchor, rel}). Missing access_state remains unknown.
    This importer launches no browser and makes no network/account requests.
    """
    from .projects import write_private

    def clean_url(value):
        if not isinstance(value, str) or len(value) > 4096:
            raise ValueError("Browser evidence needs bounded HTTP(S) URLs.")
        parsed = urlsplit(value)
        normal = normalize_url(value, drop_tracking=False)
        sensitive = {
            "password",
            "pass",
            "token",
            "access_token",
            "refresh_token",
            "session",
            "sessionid",
            "code",
            "key",
            "auth",
        }
        if (
            not normal
            or parsed.username is not None
            or parsed.password is not None
            or any(k.casefold() in sensitive for k, _ in parse_qsl(parsed.query))
        ):
            raise ValueError(
                "Use clean HTTP(S) browser URLs without credentials or authentication parameters."
            )
        return normal

    def bounded_text(value, label, maximum, empty=True):
        if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
            raise ValueError(f"{label} needs text of at most {maximum} characters.")
        return value

    target = clean_url(target)
    target_host = urlsplit(target).hostname.removeprefix("www.")
    bounded_text(brand, "Brand", 200)
    if not isinstance(aliases, (list, tuple)) or len(aliases) > 20:
        raise ValueError("Use at most 20 brand aliases.")
    aliases = [bounded_text(a, "Alias", 200, False) for a in aliases]
    path = Path(input_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 5_000_000:
        raise ValueError("Use a regular browser-evidence JSON file no larger than 5 MB.")
    try:
        supplied = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Browser evidence must be bounded valid JSON.") from None
    if isinstance(supplied, dict):
        if set(supplied) != {"captures"}:
            raise ValueError(
                "Browser evidence object supports captures only; omit credentials and session data."
            )
        supplied = supplied["captures"]
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 30:
        raise ValueError("Import 1–30 actual source-page captures.")
    allowed = {
        "kind",
        "url",
        "final_url",
        "captured_at",
        "browser",
        "visibility",
        "access_state",
        "title",
        "text",
        "links",
    }
    captures, dates = [], []
    for raw in supplied:
        if not isinstance(raw, dict) or raw.keys() - allowed:
            raise ValueError(
                "Source captures contain unsupported fields; never import cookies, passwords or invented HTTP status."
            )
        if raw.get("kind") != "source_page":
            raise ValueError(
                "Only source_page DOM captures qualify; search results and snippets are discovery leads."
            )
        source = clean_url(raw.get("url"))
        final = clean_url(raw["final_url"]) if raw.get("final_url") is not None else None
        for address in (source, final):
            if not address:
                continue
            parsed = urlsplit(address)
            host = parsed.hostname or ""
            search_path = parsed.path.rstrip("/")
            google_results = (
                re.fullmatch(r"(?:www\.)?google\.[a-z]{2,3}(?:\.[a-z]{2})?", host)
                and search_path == "/search"
            )
            other_results = (
                (host == "bing.com" or host.endswith(".bing.com"))
                and search_path == "/search"
                or (host == "duckduckgo.com" or host.endswith(".duckduckgo.com"))
                and "q" in dict(parse_qsl(parsed.query))
                or host == "search.brave.com"
                and search_path == "/search"
                or host == "search.yahoo.com"
                and search_path == "/search"
            )
            if google_results or other_results:
                raise ValueError(
                    "A search-results URL is a discovery lead, not a source-page backlink capture."
                )
        stamp = bounded_text(raw.get("captured_at"), "Capture timestamp", 80, False)
        try:
            observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Use a timezone-aware ISO capture timestamp.") from None
        if observed.tzinfo is None or observed > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError(
                "Capture timestamps need a timezone and cannot assert a future observation."
            )
        browser = bounded_text(raw.get("browser"), "Observed browser/backend", 200, False)
        visibility = raw.get("visibility")
        access = raw.get("access_state", "unknown")
        if visibility not in {"public_logged_out", "authenticated", "unknown"}:
            raise ValueError("Record public_logged_out, authenticated or unknown visibility.")
        if access not in {"content", "challenge", "login_wall", "unknown"}:
            raise ValueError("Record content, challenge, login_wall or unknown access_state.")
        title = bounded_text(raw.get("title"), "Observed title", 1000)
        body = bounded_text(raw.get("text"), "Observed text", 100_000)
        links = raw.get("links")
        if not isinstance(links, list) or len(links) > 500:
            raise ValueError("Each source capture supports at most 500 observed DOM links.")
        checked_links = []
        for link in links:
            if not isinstance(link, dict) or set(link) != {"url", "anchor", "rel"}:
                raise ValueError("DOM links require exactly url, anchor and observed rel fields.")
            href = clean_url(link["url"])
            anchor = bounded_text(link["anchor"], "Observed anchor", 2000)
            rel = link["rel"].split() if isinstance(link["rel"], str) else link["rel"]
            if not isinstance(rel, list) or len(rel) > 20:
                raise ValueError("Observed rel must be a string or at most 20 attribute tokens.")
            rel = [bounded_text(v, "Observed rel token", 100, False) for v in rel]
            checked_links.append({"url": href, "anchor": anchor, "rel": rel})
        captures.append(
            {
                "kind": "source_page",
                "url": source,
                "final_url": final,
                "captured_at": stamp,
                "browser": browser,
                "visibility": visibility,
                "access_state": access,
                "title": title,
                "text": body,
                "links": checked_links,
            }
        )
        dates.append(observed)
    # Pool repeated source/final identities without losing older provenance.
    # Unioning alias observations is conservative when a redirect destination changes.
    parents = list(range(len(captures)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    identities = {}
    for index, capture in enumerate(captures):
        for address in {capture["url"], capture["final_url"]} - {None}:
            if address in identities:
                parents[find(index)] = find(identities[address])
            else:
                identities[address] = index
    groups = {}
    for index in range(len(captures)):
        groups.setdefault(find(index), []).append(index)
    results = []
    for indices in groups.values():
        selected = max(indices, key=lambda i: (dates[i], i))
        capture = captures[selected]
        content = capture["access_state"] == "content"
        public = content and capture["visibility"] == "public_logged_out"
        authenticated = content and capture["visibility"] == "authenticated"
        links = target_links(capture, target_host) if content else []
        same_site = (urlsplit(capture["final_url"] or capture["url"]).hostname or "").removeprefix(
            "www."
        ) == target_host
        if public and links and not same_site:
            verdict = "link_observed"
        elif public and links:
            verdict = "same_site_link_observed"
        elif authenticated and links:
            verdict = "link_visible_in_authenticated_session"
        elif public:
            verdict = "no_target_link_observed_in_snapshot"
        else:
            verdict = "unverified_access"
        mentions = mention_evidence(capture, [brand, *aliases]) if content else []
        provenance = [
            {
                "capture_source": "host_browser",
                "operator_recorded": True,
                "url": captures[i]["url"],
                "final_url": captures[i]["final_url"],
                "captured_at": captures[i]["captured_at"],
                "browser": captures[i]["browser"],
                "visibility": captures[i]["visibility"],
                "access_state": captures[i]["access_state"],
                "capture_ordinal": i + 1,
            }
            for i in indices
        ]
        results.append(
            {
                "source_url": capture["url"],
                "final_url": capture["final_url"],
                "status": None,
                "http_status_evidence": "not observed by this import",
                "checked_at": capture["captured_at"],
                "capture_source": "host_browser",
                "operator_recorded": True,
                "browser": capture["browser"],
                "visibility": capture["visibility"],
                "access_state": capture["access_state"],
                "verification": verdict,
                "representation": "host_browser_dom_snapshot",
                "coverage_limited": True,
                "target_links": links,
                "brand_mentions": mentions,
                "mention_status": "observed_in_page"
                if public and mentions
                else "visible_in_authenticated_session"
                if authenticated and mentions
                else "unverified",
                "source_index_signals": {
                    "robots_policy_status": "unknown",
                    "googlebot_noindex_observed": None,
                    "canonical_elsewhere": None,
                    "indexability_candidate": None,
                    "indexing_status": "not_verified",
                    "schema_status": "not_assessed",
                },
                "error": "" if content else "browser_" + capture["access_state"],
                "access": {
                    "state": capture["access_state"],
                    "visibility": capture["visibility"],
                    "basis": "operator-recorded browser observation",
                },
                "robots_decision": "unknown",
                "missing_content_candidate": None,
                "title": capture["title"],
                "main_excerpt": capture["text"][:500],
                "independent_endorsement": "not_assessed",
                "discovery": {"provenance": provenance},
                "provenance": provenance,
                "evidence_folder": ".",
                "capture_ordinal": selected + 1,
                "coverage_note": "Only supplied DOM observations were imported. Missing links/text in this snapshot do not establish whole-page absence, indexing, robots permission or missing schema.",
            }
        )
    out = Path(out).expanduser().absolute()
    if out.is_symlink() or out.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError(
            "Keep browser evidence in a regular private output folder outside the skill/source."
        )
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Choose a fresh private browser-evidence output folder.")
    latest = max(range(len(captures)), key=lambda i: dates[i])
    result = {
        "target": target,
        "brand": brand,
        "checked_at": captures[latest]["captured_at"],
        "imported_at": utcnow(),
        "capture_source": "host_browser",
        "operator_recorded": True,
        "observations_imported": len(captures),
        "duplicates_consolidated": len(captures) - len(results),
        "sources_supplied": len(results),
        "sources_checked": len(results),
        "sources_remaining": 0,
        "observed_link_pages": sum(r["verification"] == "link_observed" for r in results),
        "observed_mention_pages": sum(r["mention_status"] == "observed_in_page" for r in results),
        "authenticated_link_pages": sum(
            r["verification"] == "link_visible_in_authenticated_session" for r in results
        ),
        "unverified_pages": sum(
            r["verification"]
            not in {
                "link_observed",
                "same_site_link_observed",
                "no_target_link_observed_in_snapshot",
            }
            for r in results
        ),
        "browser_launched": False,
        "network_requests": 0,
        "results": results,
        "note": "Operator-recorded source-page DOM evidence, not an independent live HTTP check or a complete backlink index. Only content observed in a public logged-out capture can support public links. Authenticated/challenged/unknown captures do not prove public backlinks. The recorded capture dates remain the observation dates; import time does not refresh them. This adapter grants no browser or account permissions.",
    }
    out.mkdir(parents=True, mode=0o700, exist_ok=True)
    write_private(
        out / "browser-captures.json",
        json.dumps({"captures": captures}, ensure_ascii=False, indent=2) + "\n",
    )
    write_private(out / "backlinks.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# Host-browser backlink observations",
        "",
        result["note"],
        "",
        f"Imported {len(captures)} observations for {len(results)} distinct source identities. Public link observations: {result['observed_link_pages']}; authenticated-session link observations: {result['authenticated_link_pages']}.",
        "",
    ]
    lines += [
        f"- {r['source_url']} — {r['verification']}; captured {r['checked_at']}; HTTP status unknown."
        for r in results
    ]
    write_private(out / "backlinks.md", "\n".join(lines) + "\n")
    return result
