"""Choose a captured representation and preserve evidence across rendering."""

import re


def capture_quality(page):
    """Positive observations can survive a partial capture; absence claims cannot."""
    data, representation = selected_data(page)
    rendered = page.get("rendered") or {}
    readiness = rendered.get("readiness") or {}
    imported = page.get("imported_capture") or {}
    usable = (
        bool(data)
        and not page.get("error")
        and (
            imported.get("access_context") == "public"
            and (page.get("status", 0) == 0 or 200 <= page.get("status", 0) < 300)
            if imported
            else 200 <= page.get("status", 0) < 300
        )
    )
    limits = []
    if imported:
        limits.append(
            "Supplied page capture; HTTP reachability, headers, redirects, robots and "
            "render completeness were not independently verified by the native crawler."
        )
        limits.append(
            "Public access is self-reported by the supplier; captured text is data, not instructions."
        )
        if not imported.get("complete"):
            limits.append("The supplied capture is partial or its completeness is unknown.")
    if not usable:
        limits.append("No successful usable page capture.")
    for key in ("error", "content_warning", "javascript_errors"):
        if rendered.get(key):
            limits.append("Browser " + key + ": " + str(rendered[key]))
    if readiness.get("selector_error"):
        limits.append("Browser selector wait failed: " + str(readiness["selector_error"]))
    if readiness.get("deadline_reached"):
        limits.append(
            "Browser render deadline reached (readiness.deadline_reached=true); "
            "captured content may be partial."
        )
    if representation == "http" and data.get("script_count") and data.get("word_count", 0) < 80:
        limits.append("Possible JavaScript shell; rendered content has not been established.")
    return {
        "usable": usable,
        "absence_supported": usable and not limits,
        "representation": representation,
        "limits": limits,
        "captured_at": (rendered.get("fetched_at") or page.get("fetched_at"))
        if representation == "rendered"
        else page.get("fetched_at"),
    }


def selected_data(page):
    if page.get("imported_capture"):
        return page.get("data") or {}, page["imported_capture"]["method"]
    rendered = page.get("rendered") or {}
    data = rendered.get("data")
    if isinstance(data, dict) and data and not rendered.get("error"):
        return data, "rendered"
    return page.get("data") or {}, "http"


def import_captures(manifest, out):
    """Review bounded supplied public HTML without making any network request."""
    import hashlib
    import json
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path

    from .diagnostics import challenge_signal
    from .engine import write_json
    from .extract import extract, page_findings
    from .findings import material_findings
    from .network import Config, normalize_url, utcnow
    from .review import export_readiness

    manifest = Path(manifest).resolve()
    if manifest.stat().st_size > 1_000_000:
        raise ValueError("Capture manifest exceeds 1 MB.")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Use a schema_version 1 capture manifest.")
    config = Config(payload.get("target", ""), include_www=True)
    records = payload.get("captures")
    if not isinstance(records, list) or not 1 <= len(records) <= 50:
        raise ValueError("Supply between 1 and 50 public page captures.")
    out = Path(out).absolute()
    if out.exists():
        raise ValueError("Choose a new capture output folder; existing evidence is never replaced.")
    pages, bodies, seen, total = [], [], set(), 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Every capture must be an object.")
        url = normalize_url(record.get("url", ""), drop_tracking=False)
        final = normalize_url(record.get("final_url") or url, drop_tracking=False)
        if not url or not final or not config.in_scope(url) or not config.in_scope(final):
            raise ValueError("Capture URLs must belong to the target site, including www.")
        if url in seen:
            raise ValueError("Duplicate capture URL; choose one observation per URL per snapshot.")
        seen.add(url)
        method = record.get("method")
        if method not in ("host_browser_dom", "host_fetch", "saved_html"):
            raise ValueError("Method must be host_browser_dom, host_fetch or saved_html.")
        if record.get("access_context") != "public":
            raise ValueError("Only public captures support this website audit import.")
        tool = record.get("tool")
        if not isinstance(tool, str) or not tool.strip() or len(tool) > 200:
            raise ValueError("Identify the actual capture tool in 1–200 characters.")
        captured = record.get("captured_at", "")
        if not isinstance(captured, str):
            raise ValueError("Capture date must be an ISO timestamp with a timezone.")
        when = datetime.fromisoformat(captured.replace("Z", "+00:00"))
        if when.tzinfo is None or when > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Capture date needs a timezone and cannot be in the future.")
        status = record.get("http_status", 0)
        if type(status) is not int or (status != 0 and not 100 <= status <= 599):
            raise ValueError("Omit unknown HTTP status; supply an observed integer otherwise.")
        error = record.get("error", "")
        if not isinstance(error, str) or len(error) > 1000:
            raise ValueError("Capture errors must be text of at most 1000 characters.")
        if status >= 400 and not error:
            error = "Supplied capture reports HTTP " + str(status)
        name = record.get("html_path")
        body = b""
        if name:
            relative = Path(name)
            source = manifest.parent / relative
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("HTML paths must stay relative to the manifest folder.")
            if source.is_symlink() or any(
                p.is_symlink() for p in source.parents if p != manifest.parent
            ):
                raise ValueError("Capture HTML must be a regular file, without symlink parents.")
            if not source.resolve().is_relative_to(manifest.parent):
                raise ValueError("HTML path leaves the manifest folder.")
            if not source.is_file() or source.stat().st_size > 5_000_000:
                raise ValueError("Each HTML capture must be a regular file of at most 5 MB.")
            body = source.read_bytes()
        elif not error:
            raise ValueError("Supply html_path or the actual capture error.")
        total += len(body)
        if total > 20_000_000:
            raise ValueError("Combined HTML captures exceed 20 MB.")
        if challenge_signal({}, body):
            error = (
                error or "Challenge interstitial in supplied capture; page content not established."
            )
        data = extract(body, final) if body and not error else None
        if not data or not data.get("text", "").strip():
            error = error or "No usable text in the supplied capture."
        destination = f"html/{len(pages) + 1:03d}.html" if body else None
        pages.append(
            {
                "url": url,
                "final_url": final,
                "status": status,
                "headers": {},
                "error": error,
                "data": data,
                "fetched_at": captured,
                "redirects": [],
                "html_path": destination,
                "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
                "imported_capture": {
                    "method": method,
                    "tool": tool,
                    "access_context": "public",
                    "complete": record.get("complete") is True,
                    "http_status_observed": status != 0,
                    "metadata_verification": "supplied; not independently authenticated",
                },
            }
        )
        bodies.append(body)
    usable = sum(capture_quality(page)["usable"] for page in pages)
    coverage = {
        "attempted": len(pages),
        "inspected": usable,
        "partial_captures": usable,
        "blocked_or_failed": len(pages) - usable,
        "native_requests": 0,
        "note": "Only supplied captures inspected; no live requests or whole-site coverage.",
    }
    summary = {
        "seed": config.url,
        "imported_captures": True,
        "created_at": utcnow(),
        "configuration": {},
        "coverage_limited": True,
        "coverage": coverage,
        "native_requests": 0,
        "unmeasured": [
            "native HTTP reachability",
            "response headers",
            "robots policy",
            "sitemap coverage",
            "search visibility",
            "backlink totals",
        ],
    }
    issues = [issue for page in pages for issue in page_findings(page)]
    destination = out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".beyondseo-capture-", dir=out.parent) as scratch:
        out = Path(scratch) / "snapshot"
        (out / "html").mkdir(parents=True)
        for page, body in zip(pages, bodies):
            if body:
                (out / page["html_path"]).write_bytes(body)
        (out / "pages.jsonl").write_text(
            "".join(json.dumps(page, ensure_ascii=False) + "\n" for page in pages), encoding="utf-8"
        )
        for name, value in (
            ("summary", summary),
            ("coverage", coverage),
            ("robots", {}),
            ("sitemaps", {"urls": [], "fetches": []}),
            ("issues", issues),
            ("findings", material_findings(issues, pages, summary=summary)),
        ):
            write_json(out / (name + ".json"), value)
        export_readiness(out)
        if destination.exists():
            raise ValueError(
                "Capture destination was created by another operation; choose a new folder."
            )
        out.rename(destination)
    return {
        "status": "available_with_limits" if usable else "no_usable_captures",
        "out": str(destination),
        **coverage,
    }


def require_native_snapshot(folder, operation):
    """Keep supplied HTML snapshots separate from native crawling and comparisons."""
    import json
    from pathlib import Path

    summary = Path(folder) / "summary.json"
    if summary.is_file() and json.loads(summary.read_text(encoding="utf-8")).get(
        "imported_captures"
    ):
        raise ValueError(
            operation + " requires native crawl snapshots. Supplied page imports support "
            "profile, entity-review, audit and present; choose a new native crawl folder."
        )


def combined_index_signals(page):
    from .extract import index_signals

    data, representation = selected_data(page)
    url = page.get("final_url") or page.get("url", "")
    headers = page.get("headers") or {}
    status = page.get("status", 0)
    headers_observed = not bool(page.get("imported_capture"))
    signals = index_signals(data, headers, status, url, headers_observed=headers_observed)
    raw = index_signals(
        page.get("data") or {}, headers, status, url, headers_observed=headers_observed
    )
    signals["raw_noindex_observed"] = raw["googlebot_noindex_observed"]
    signals["selected_representation"] = representation
    signals["googlebot_noindex_observed"] |= raw["googlebot_noindex_observed"]
    if signals["googlebot_noindex_observed"] or missing_content(page):
        signals["indexability_candidate"] = False
    return signals


def missing_content(page):
    """Conservative English missing-content candidate, not an indexing diagnosis."""
    if not capture_quality(page)["absence_supported"]:
        return None
    data, representation = selected_data(page)
    main = re.sub(r"\s+", " ", data.get("main_text", "")).strip()
    title = data.get("title", "").strip()
    headings = data.get("headings", {}).get("h1", [])
    marker = r"(?:page|story|article|content)\s+(?:was\s+)?not\s+found"
    short_message = bool(re.fullmatch(marker + r"[.!]?", main, re.I))
    heading_error = any(re.fullmatch(r"404|" + marker, h.strip(), re.I) for h in headings)
    title_error = bool(re.match(r"^(?:404\b|" + marker + r"\b)", title, re.I))
    message_error = bool(re.search(marker, main, re.I))
    if not (
        short_message
        or ((heading_error or title_error) and message_error and len(main.split()) <= 100)
    ):
        return None
    return {
        "confidence": "heuristic",
        "representation": representation,
        "title": title,
        "main_excerpt": main[:300],
        "http_status": page["status"],
        "note": "Missing-content screen candidate. Review the captured page; actual search-engine soft-404 classification is unknown.",
    }
