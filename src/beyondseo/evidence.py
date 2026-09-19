"""Choose a captured representation and preserve evidence across rendering."""

import re


def capture_quality(page):
    """Positive observations can survive a partial capture; absence claims cannot."""
    data, representation = selected_data(page)
    rendered = page.get("rendered") or {}
    readiness = rendered.get("readiness") or {}
    usable = bool(data) and not page.get("error") and 200 <= page.get("status", 0) < 300
    limits = []
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
    rendered = page.get("rendered") or {}
    data = rendered.get("data")
    if isinstance(data, dict) and data and not rendered.get("error"):
        return data, "rendered"
    return page.get("data") or {}, "http"


def combined_index_signals(page):
    from .extract import index_signals

    data, representation = selected_data(page)
    url = page.get("final_url") or page.get("url", "")
    headers = page.get("headers") or {}
    status = page.get("status", 0)
    signals = index_signals(data, headers, status, url)
    raw = index_signals(page.get("data") or {}, headers, status, url)
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
