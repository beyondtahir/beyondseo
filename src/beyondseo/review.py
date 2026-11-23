"""Readable readiness observations and comparisons, using saved crawl evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .evidence import capture_quality, missing_content, selected_data
from .extract import index_signals
from .network import RobotsRules, origin, utcnow


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_pages(folder):
    return [
        json.loads(line)
        for line in (Path(folder) / "pages.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def save_report(out, name, result, lines):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / (name + ".json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / (name + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def readiness(pages, summary, robots, sitemaps):
    entries = []
    listed = {r["url"] for r in sitemaps.get("urls", [])}
    for page in pages:
        data, representation = selected_data(page)
        quality = capture_quality(page)
        url = page.get("final_url") or page["url"]
        observations = []

        def add(code, observation, why, action):
            if (
                code in {"main_content_empty", "title_missing", "h1_missing", "schema_review"}
                and not quality["absence_supported"]
            ):
                return
            observations.append(
                {
                    "code": code,
                    "observation": observation,
                    "why_it_matters": why,
                    "next_step": action,
                }
            )

        if page.get("error") or not 200 <= page.get("status", 0) < 300 or not data:
            add(
                "access_incomplete",
                "We did not capture usable page content.",
                "We cannot assess an unread page's answers or trust signals.",
                "Check access.json and the response, then repeat this page when access is available.",
            )
        else:
            if quality["limits"]:
                add(
                    "capture_incomplete",
                    "; ".join(quality["limits"]),
                    "A partial capture cannot establish missing answers or markup.",
                    "Resolve the recorded capture limitation and recapture this URL.",
                )
            missing = missing_content(page)
            if missing:
                add(
                    "missing_content_candidate",
                    "HTTP success returned a missing-content screen candidate.",
                    "A successful status alone does not establish that the intended page exists.",
                    "Inspect the saved text, repair referring links and return an appropriate status for missing pages.",
                )
            if not data.get("main_text"):
                add(
                    "main_content_empty",
                    "The captured page has no main text.",
                    "Important answers may be unavailable in this representation.",
                    "Inspect rendered HTML and dependency errors; provide accessible text for essential information.",
                )
            raw = page.get("data") or {}
            if (
                representation == "rendered"
                and data.get("word_count", 0) > raw.get("word_count", 0) + 50
            ):
                add(
                    "javascript_content",
                    "Substantial text arrived after JavaScript ran.",
                    "Different crawlers may see different content.",
                    "Compare the raw response with the full page; consider server-rendering important answers and links.",
                )
            if not data.get("title"):
                add(
                    "title_missing",
                    "The captured page has no title.",
                    "Its topic is harder to identify in search results and browser tabs.",
                    "Write a descriptive title matching this page's purpose.",
                )
            if not data.get("headings", {}).get("h1"):
                add(
                    "h1_missing",
                    "We found no H1 in the captured content.",
                    "A clear page heading can help visitors understand its purpose.",
                    "Review the visible structure and add a useful primary heading where appropriate.",
                )
            if data.get("jsonld_errors"):
                add(
                    "schema_syntax",
                    "At least one JSON-LD block could not be parsed.",
                    "Malformed structured data cannot reliably describe the page.",
                    "Fix the recorded syntax errors, then validate the intended schema against visible facts.",
                )
            if not data.get("schema_types") and not data.get("microdata_types"):
                add(
                    "schema_review",
                    "No JSON-LD or microdata types were observed.",
                    "Structured data may clarify real entities, but its absence does not establish an AI visibility problem.",
                    "Review relevant markup for this page; add only types and facts it actually supports.",
                )
        raw_signals = index_signals(
            page.get("data") or {}, page.get("headers") or {}, page.get("status", 0), url
        )
        selected_signals = index_signals(
            data, page.get("headers") or {}, page.get("status", 0), url
        )
        if (
            raw_signals["googlebot_noindex_observed"]
            or selected_signals["googlebot_noindex_observed"]
        ):
            add(
                "noindex_observed",
                "A noindex instruction was observed in the response or captured DOM.",
                "This can prevent the page from appearing in Google Search, including its AI features.",
                "Confirm whether the page should be public in search before changing this instruction.",
            )
        controls = (
            selected_signals["generic_meta"]
            + selected_signals["googlebot_meta"]
            + [selected_signals["x_robots_tag"]]
        )
        # Preserve exact header text; agent-specific headers need individual interpretation.
        snippet_controls = [
            v for v in controls if re.search(r"nosnippet|max-snippet\s*:\s*0(?:\D|$)", v, re.I)
        ]
        evidence = robots.get(origin(url))
        policies = {}
        for agent in ("Googlebot", "Bingbot"):
            policies[agent] = (
                None
                if not evidence or evidence.get("blocked")
                else RobotsRules(evidence.get("text", ""), agent=agent).allowed(url)
            )
        ai_purposes = {
            "OAI-SearchBot": "OpenAI search crawling",
            "GPTBot": "OpenAI model training crawling",
            "Claude-SearchBot": "Anthropic search crawling",
            "ClaudeBot": "Anthropic model-development crawling",
            "Google-Extended": "Google control for some Gemini training and grounding; not Google Search ranking",
        }
        ai_policies = {}
        for agent, purpose in ai_purposes.items():
            available = bool(
                evidence
                and not evidence.get("blocked")
                and not evidence.get("error")
                and evidence.get("status") == 200
                and not evidence.get("text_truncated")
                and len(evidence.get("text", "").encode("utf-8")) < 512_000
            )
            allowed = (
                RobotsRules(evidence.get("text", ""), agent=agent).allowed(url)
                if available
                else None
            )
            ai_policies[agent] = {
                "purpose": purpose,
                "observed_robots_rule": "permitted"
                if allowed is True
                else "restricted"
                if allowed is False
                else "unknown",
                "robots_url": evidence.get("url") if evidence else None,
                "robots_fetched_at": evidence.get("fetched_at") if evidence else None,
                "limit": "Declared robots policy for this path only; not an actual crawler request, WAF decision, indexing or AI citation.",
            }
        if any(v is False for v in policies.values()):
            add(
                "robots_restriction",
                "The saved robots file restricts this path for a checked search crawler.",
                "That crawler may be unable to discover current page content.",
                "Review the exact rule and its purpose; changing our crawl override does not change search-engine access.",
            )
        entries.append(
            {
                "url": page["url"],
                "final_url": url,
                "representation": representation,
                "status": page.get("status"),
                "main_words": data.get("word_count", 0),
                "body_words": data.get("body_word_count", 0),
                "in_observed_sitemap": page["url"] in listed or url in listed,
                "schema_types": data.get("schema_types", []),
                "microdata_types": data.get("microdata_types", []),
                "schema_errors": data.get("jsonld_errors", []),
                "robots_path_permissions": policies,
                "ai_robots_policy": ai_policies,
                "snippet_controls_to_review": snippet_controls,
                "index_signals_http": raw_signals,
                "index_signals_selected": selected_signals,
                "observations": observations,
            }
        )
    return {
        "schema_version": 1,
        "checked_at": summary.get("exported_at") or utcnow(),
        "seed": summary.get("seed"),
        "coverage_limited": summary.get("coverage_limited", True),
        "sitemap_urls_observed": len(listed),
        "sitemap_fetch_failures": summary.get("sitemap_fetch_failures", 0),
        "pages": entries,
        "not_measured": [
            "actual indexing",
            "AI answer inclusion",
            "competitor rankings",
            "independent reputation",
            "schema semantic validity",
        ],
        "interpretation": "These are access, text and markup observations. They do not measure an engine's trust, indexing or citations.",
    }


def export_readiness(out, pages=None, summary=None, robots=None, sitemaps=None):
    out = Path(out)
    result = readiness(
        pages if pages is not None else read_pages(out),
        summary if summary is not None else read_json(out / "summary.json"),
        robots if robots is not None else read_json(out / "robots.json"),
        sitemaps if sitemaps is not None else read_json(out / "sitemaps.json"),
    )
    lines = [
        "# Your website's search and answer readiness",
        "",
        "Here is what we could read, what needs attention, and what to do next.",
        "",
        result["interpretation"],
        "",
        f"Sitemap URLs observed: {result['sitemap_urls_observed']}. Coverage limited: {result['coverage_limited']}.",
        "",
        "Start with access problems on important pages, then review the content and proof that answer your customers' questions.",
    ]
    for p in result["pages"]:
        lines += [
            "",
            "## " + p["url"],
            "",
            f"Captured {p['main_words']} main-content words using {p['representation']}. Schema types: {', '.join(p['schema_types']) or 'none observed'}.",
        ]
        for item in p["observations"]:
            lines += [
                "",
                item["observation"]
                + " "
                + item["why_it_matters"]
                + " **Next:** "
                + item["next_step"],
            ]
        lines += [
            "",
            "AI-related robots policy (declared rules only): "
            + "; ".join(
                agent + ": " + item["observed_robots_rule"]
                for agent, item in p["ai_robots_policy"].items()
            )
            + ". Search access and training are separate choices; no actual bot visit, indexing or citation was measured.",
        ]
        if not p["observations"]:
            lines += [
                "",
                "No issue was flagged by these limited checks. Review answer quality, entity facts and independent proof separately.",
            ]
    return save_report(out, "readiness", result, lines)


def page_snapshot(page):
    data, representation = selected_data(page)
    signals = index_signals(
        data, page.get("headers") or {}, page.get("status", 0), page.get("final_url", page["url"])
    )
    return {
        "status": page.get("status"),
        "error": page.get("error", ""),
        "final_url": page.get("final_url"),
        "representation": representation,
        "title": data.get("title"),
        "description": data.get("meta_description"),
        "h1": data.get("headings", {}).get("h1", []),
        "content_hash": data.get("content_sha256"),
        "canonical": data.get("canonical", []),
        "noindex": signals["googlebot_noindex_observed"],
        "schema_types": data.get("schema_types", []),
        "schema_errors": data.get("jsonld_errors", []),
        "render_error": (page.get("rendered") or {}).get("error", ""),
    }


def compare(before, after, out):
    a, b = Path(before), Path(after)
    sa, sb = read_json(a / "summary.json"), read_json(b / "summary.json")
    if sa["seed"] != sb["seed"]:
        raise ValueError(
            "Snapshot comparison needs the same seed URL. Compare competitors in the SEO workflow."
        )
    left, right = ({p["url"]: page_snapshot(p) for p in read_pages(d)} for d in (a, b))
    changed = []
    for url in sorted(left.keys() & right.keys()):
        fields = {
            k: {"before": left[url][k], "after": right[url][k]}
            for k in left[url]
            if left[url][k] != right[url][k]
        }
        if fields:
            changed.append({"url": url, "fields": fields})
    old_issues, new_issues = (
        {(r["url"], r["code"]) for r in read_json(d / "issues.json")} for d in (a, b)
    )
    # A disappearing URL or failed observation must never count as a resolved issue.
    comparable = {
        u
        for u in left.keys() & right.keys()
        if left[u]["content_hash"]
        and right[u]["content_hash"]
        and not left[u]["error"]
        and not right[u]["error"]
        and left[u]["status"] == right[u]["status"] == 200
        and left[u]["representation"] == right[u]["representation"]
        and not left[u]["render_error"]
        and not right[u]["render_error"]
    }
    resolved = sorted(i for i in old_issues - new_issues if i[0] in comparable)
    result = {
        "checked_at": utcnow(),
        "seed": sa["seed"],
        "before_at": sa.get("exported_at"),
        "after_at": sb.get("exported_at"),
        "coverage_limited": bool(sa.get("coverage_limited") or sb.get("coverage_limited")),
        "configuration_changed": sa.get("configuration") != sb.get("configuration"),
        "changed_pages": changed,
        "newly_observed_urls": sorted(right.keys() - left.keys()),
        "not_reobserved_urls": sorted(left.keys() - right.keys()),
        "new_findings": [{"url": u, "code": c} for u, c in sorted(new_issues - old_issues)],
        "findings_no_longer_observed_on_comparable_pages": [
            {"url": u, "code": c} for u, c in resolved
        ],
        "note": "Not reobserved does not mean deleted. Findings no longer observed need acceptance checks; crawl scope and rendering can affect comparison.",
    }
    lines = [
        "# What changed since the last review",
        "",
        f"{len(changed)} pages changed; {len(result['new_findings'])} new findings; {len(resolved)} findings no longer observed on comparable pages.",
        "",
        result["note"],
        "",
        f"Coverage limited: {result['coverage_limited']}. Configuration changed: {result['configuration_changed']}.",
    ]
    for row in changed:
        lines += ["", "- " + row["url"] + ": " + ", ".join(row["fields"])]
    return save_report(out, "comparison", result, lines)


def search_performance(
    current,
    out,
    dimension,
    previous=None,
    property_name="",
    period="",
    previous_period="",
    comparison_context="",
    minimum_impressions=100,
    maximum_ctr=2.0,
    crawl_out=None,
):
    """Review a user's English-language Search Console table exports, entirely offline."""
    import csv
    import math

    aliases = {
        "query": {"top queries", "query", "queries"},
        "page": {"top pages", "page", "pages"},
        "country": {"country", "countries"},
        "device": {"device", "devices"},
        "date": {"date", "dates"},
    }
    if dimension not in aliases:
        raise ValueError("Choose query, page, country, device or date.")
    if crawl_out and dimension != "page":
        raise ValueError(
            "A saved crawl can only be matched to the page dimension; query exports do not establish a query-to-page mapping."
        )
    if (
        len(property_name) > 100
        or len(period) > 100
        or len(previous_period) > 100
        or len(comparison_context) > 1000
    ):
        raise ValueError(
            "Keep property and period labels under 100 characters and comparison context under 1,000 characters."
        )
    if minimum_impressions < 0 or not math.isfinite(maximum_ctr) or not 0 <= maximum_ctr <= 100:
        raise ValueError("Use a nonnegative impression threshold and CTR between 0 and 100.")
    if previous and not comparison_context.strip():
        raise ValueError(
            "A comparison needs --comparison-context describing property, filters and periods; matching them remains the user's responsibility."
        )

    def load(path):
        path = Path(path)
        if path.stat().st_size > 5_000_000:
            raise ValueError("CSV exceeds the 5 MB input limit.")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            fields = reader.fieldnames or []
            normalized = [str(f).strip().casefold() for f in fields]
            if len(set(normalized)) != len(normalized):
                raise ValueError("Duplicate CSV columns are not supported.")
            matches = [fields[i] for i, name in enumerate(normalized) if name in aliases[dimension]]
            if len(matches) != 1 or "clicks" not in normalized or "impressions" not in normalized:
                raise ValueError(
                    "Use an English Search Console CSV with the selected dimension, Clicks and Impressions columns. Comparison-style columns are not supported; export each period separately."
                )
            keys = {name: fields[normalized.index(name)] for name in ("clicks", "impressions")}
            if "position" in normalized:
                keys["position"] = fields[normalized.index("position")]
            rows = {}
            for line, record in enumerate(reader, 2):
                if None in record:
                    raise ValueError(f"Unexpected extra column in CSV row {line}.")
                label = (record.get(matches[0]) or "").strip()
                if not label or len(label) > 2048 or any(ord(c) < 32 for c in label):
                    raise ValueError(f"Invalid dimension value in CSV row {line}.")
                if label in rows:
                    raise ValueError(
                        f"Duplicate dimension value in CSV row {line}; export one row per {dimension}."
                    )
                values = {}
                for metric in ("clicks", "impressions"):
                    val = (record.get(keys[metric]) or "").strip()
                    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", val):
                        raise ValueError(
                            f"Invalid {metric} in CSV row {line}; use nonnegative whole numbers."
                        )
                    values[metric] = int(val.replace(",", ""))
                if values["clicks"] > values["impressions"]:
                    raise ValueError(
                        f"Clicks exceed impressions in CSV row {line}; inspect the export."
                    )
                if "position" in keys:
                    val = (record.get(keys["position"]) or "").strip()
                    if val:
                        try:
                            position = float(val)
                        except ValueError:
                            raise ValueError(f"Invalid position in CSV row {line}.") from None
                        if not math.isfinite(position) or position < 0:
                            raise ValueError(f"Invalid position in CSV row {line}.")
                        values["position"] = position
                values["ctr_percent"] = (
                    round(100 * values["clicks"] / values["impressions"], 2)
                    if values["impressions"]
                    else None
                )
                rows[label] = values
                if len(rows) > 50_000:
                    raise ValueError("CSV exceeds 50,000 rows.")
        if not rows:
            raise ValueError("The selected CSV contains no data rows.")
        return rows

    try:
        current_rows = load(current)
        prior_rows = load(previous) if previous else {}
    except csv.Error as exc:
        raise ValueError("Malformed CSV; export a fresh Search Console table.") from exc
    selected = sorted(current_rows.items(), key=lambda item: (-item[1]["impressions"], item[0]))
    crawl_pages = {}
    if crawl_out:
        for page in read_pages(crawl_out):
            for url in {page.get("url"), page.get("final_url")} - {None, ""}:
                crawl_pages.setdefault(url, []).append(page)
    opportunities = []
    if dimension in ("page", "query"):
        for name, values in selected:
            if (
                values["impressions"] < minimum_impressions
                or values["ctr_percent"] is None
                or values["ctr_percent"] > maximum_ctr
            ):
                continue
            action = (
                "Inspect this page's title, description, visible offer and search intent; compare its actual search appearance before proposing a targeted change."
                if dimension == "page"
                else "In Search Console, filter this query and inspect the Pages tab; compare the shown page and search intent before proposing a targeted change."
            )
            record = {
                "dimension_value": name,
                **values,
                "status": "review_candidate",
                "rationale": f"At least {minimum_impressions} reported impressions and CTR at or below {maximum_ctr:g}% in the supplied table; this is a user-adjustable screening rule, not a benchmark or proven defect.",
                "action": action,
                "verify": "Compare the same page or query, country, device, search type and similarly sized complete periods after the change. Record the change date and other factors.",
            }
            if crawl_out:
                captures = crawl_pages.get(name, [])
                if len(captures) == 1:
                    page = captures[0]
                    quality = capture_quality(page)
                    data, _ = selected_data(page)
                    record["crawl_evidence"] = {
                        "requested_url": page.get("url"),
                        "final_url": page.get("final_url"),
                        "status": page.get("status"),
                        "captured_at": quality["captured_at"],
                        "usable": quality["usable"],
                        "complete_for_absence_claims": quality["absence_supported"],
                        "representation": quality["representation"],
                        "limits": quality["limits"],
                    }
                    if quality["usable"]:
                        record["crawl_evidence"]["observed_title"] = data.get("title") or None
                        record["crawl_evidence"]["observed_description"] = (
                            data.get("meta_description") or None
                        )
                else:
                    record["crawl_evidence"] = {
                        "usable": False,
                        "reason": "No exact captured URL match"
                        if not captures
                        else "Multiple captures matched; review manually",
                    }
            opportunities.append(record)
            if len(opportunities) >= 15:
                break
    changes = []
    for name, values in current_rows.items():
        if name in prior_rows:
            old = prior_rows[name]
            changes.append(
                {
                    "dimension_value": name,
                    "current": values,
                    "previous": old,
                    "clicks_change": values["clicks"] - old["clicks"],
                    "impressions_change": values["impressions"] - old["impressions"],
                }
            )
    changes.sort(key=lambda row: (-abs(row["clicks_change"]), row["dimension_value"]))
    limitation = "These are exported table rows, not necessarily complete property totals. Search Console can omit anonymized queries and limit export rows. No causation, AI citations, conversions, revenue or complete rankings are established."
    result = {
        "schema_version": 1,
        "generated_at": utcnow(),
        "source": "User-supplied Google Search Console CSV",
        "property_label": property_name or "Not provided",
        "period_label": period or "Not provided",
        "dimension": dimension,
        "crawl_evidence_supplied": bool(crawl_out),
        "input_rows": len(current_rows),
        "previous_rows": len(prior_rows) if previous else None,
        "previous_period_label": previous_period or "Not provided",
        "comparison_context_user_provided": comparison_context or None,
        "comparison_verified": False,
        "matched_rows": len(changes) if previous else None,
        "current_only_rows": len(current_rows.keys() - prior_rows.keys()) if previous else None,
        "previous_only_rows": len(prior_rows.keys() - current_rows.keys()) if previous else None,
        "comparison_note": "Only matching rows are compared. Unmatched rows are unknown, not zero. The export does not prove matching dates, filters, property or causation.",
        "screening_rule": {
            "minimum_impressions": minimum_impressions,
            "maximum_ctr_percent": maximum_ctr,
            "note": "A configurable triage threshold, not a universal CTR benchmark.",
        },
        "highest_impression_rows": [{"dimension_value": key, **row} for key, row in selected[:15]],
        "review_candidates": opportunities,
        "matched_changes": changes[:15],
        "coverage_limit": limitation,
    }

    def safe(value):
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("|", "\\|")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", " ")
        )

    lines = [
        "# Search performance: what to review",
        "",
        f"Property: {safe(result['property_label'])}  ",
        f"Period: {safe(result['period_label'])}  ",
        f"Dimension: {dimension}; {len(current_rows)} rows supplied.",
        "",
        "## Coverage and limits",
        "",
        limitation,
        "",
        "## Highest-impression rows in this export",
        "",
        "| " + dimension.title() + " | Clicks | Impressions | CTR | Position |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in result["highest_impression_rows"]:
        ctr = "unknown" if row["ctr_percent"] is None else str(row["ctr_percent"]) + "%"
        lines.append(
            f"| {safe(row['dimension_value'])} | {row['clicks']} | {row['impressions']} | {ctr} | {row.get('position', 'unknown')} |"
        )
    lines += [
        "",
        "## Candidates for review",
        "",
        f"Screening rule: at least {minimum_impressions} impressions and CTR at or below {maximum_ctr:g}%. This is a configurable filter, not proof of a problem.",
    ]
    if not opportunities:
        lines.append(
            "No rows matched the selected screening rule, or this dimension is not a query/page. This does not prove performance is healthy."
        )
    for row in opportunities:
        lines += [
            "",
            "### " + safe(row["dimension_value"]),
            "",
            f"Observed: {row['clicks']} clicks, {row['impressions']} impressions, {row['ctr_percent']}% CTR.",
            "",
            "Next: " + row["action"],
            "",
            "Verify: " + row["verify"],
        ]
        evidence = row.get("crawl_evidence")
        if evidence:
            if evidence.get("usable"):
                lines += [
                    "",
                    f"Captured page evidence ({safe(evidence.get('captured_at') or 'date not recorded')}): title {safe(evidence.get('observed_title') or 'not observed')}; description {safe(evidence.get('observed_description') or 'not observed')}. Representation: {safe(evidence['representation'])}. Check capture limits before treating absence as a finding.",
                ]
            else:
                lines += [
                    "",
                    "Page capture unavailable or ambiguous; no conclusion about its contents can be made.",
                ]
    if previous:
        lines += [
            "",
            "## Comparison",
            "",
            "User-provided comparison context: " + safe(comparison_context),
            "",
            result["comparison_note"],
            f"Matched rows: {len(changes)}; current-only: {result['current_only_rows']}; previous-only: {result['previous_only_rows']}.",
        ]
        for row in changes[:15]:
            lines.append(
                f"- {safe(row['dimension_value'])}: clicks {row['previous']['clicks']} → {row['current']['clicks']}; impressions {row['previous']['impressions']} → {row['current']['impressions']}."
            )
    output = Path(out)
    if any(
        (output / name).exists() for name in ("search-performance.json", "search-performance.md")
    ):
        raise ValueError("Performance output already exists; choose a fresh output folder.")
    return save_report(output, "search-performance", result, lines)


def lighthouse_review(source, out):
    """Read a supplied Lighthouse JSON report without running a browser or network request."""
    import math

    path = Path(source)
    if path.stat().st_size > 10_000_000:
        raise ValueError("Lighthouse input exceeds 10 MB.")
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Expected a Lighthouse JSON object.")
    report = raw.get("lighthouseResult", raw)
    if not isinstance(report, dict) or not isinstance(report.get("audits"), dict):
        raise ValueError("Expected Lighthouse audits in a Lighthouse report or lighthouseResult.")
    runtime_error = report.get("runtimeError")
    warnings = report.get("runWarnings") or []
    if not isinstance(warnings, list):
        raise ValueError("Lighthouse runWarnings must be a list.")
    definitions = [
        (
            "largest-contentful-paint",
            "Largest Contentful Paint",
            "ms",
            "Review the reported LCP element, loading priority, server response and render path in the original report.",
        ),
        (
            "cumulative-layout-shift",
            "Cumulative Layout Shift",
            "score",
            "Inspect the reported layout-shift elements and reserve space for the affected content.",
        ),
        (
            "total-blocking-time",
            "Total Blocking Time",
            "ms",
            "Inspect the original report's long main-thread tasks and reduce or defer the relevant work.",
        ),
        (
            "first-contentful-paint",
            "First Contentful Paint",
            "ms",
            "Review server response and render-blocking resources in the original report.",
        ),
        (
            "speed-index",
            "Speed Index",
            "ms",
            "Inspect the filmstrip and resource timing in the original report.",
        ),
    ]
    audits = report["audits"]
    metrics = []
    for key, label, unit, action in definitions:
        audit = audits.get(key)
        metric = {
            "id": key,
            "label": label,
            "unit": unit,
            "status": "not_measured",
            "value": None,
            "display_value": None,
            "action": action,
        }
        if isinstance(audit, dict):
            mode = audit.get("scoreDisplayMode")
            value = audit.get("numericValue")
            if (
                mode not in ("error", "notApplicable", "manual", "informative")
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value >= 0
            ):
                metric.update(
                    status="observed",
                    value=value,
                    display_value=str(audit.get("displayValue") or "")[:200] or None,
                )
            elif mode == "error":
                metric["status"] = "measurement_error"
        metrics.append(metric)
    category = (report.get("categories") or {}).get("performance") or {}
    score = category.get("score") if isinstance(category, dict) else None
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
        or not 0 <= score <= 1
    ):
        score = None
    if runtime_error:
        score = None
        for metric in metrics:
            metric.update(status="run_failed", value=None, display_value=None)
    result = {
        "schema_version": 1,
        "generated_at": utcnow(),
        "source": "User-supplied Lighthouse JSON",
        "report_time": report.get("fetchTime") or None,
        "requested_url": report.get("requestedUrl") or None,
        "final_url": report.get("finalDisplayedUrl") or report.get("finalUrl") or None,
        "lighthouse_version": report.get("lighthouseVersion") or None,
        "form_factor": (report.get("configSettings") or {}).get("formFactor"),
        "status": "failed"
        if runtime_error
        else (
            "partial" if warnings or any(m["status"] != "observed" for m in metrics) else "observed"
        ),
        "runtime_error": runtime_error,
        "run_warnings": warnings,
        "performance_score_0_to_100": round(score * 100) if score is not None else None,
        "metrics": metrics,
        "limits": "Lighthouse is a lab snapshot of one run, not real-user field data. Total Blocking Time is not INP. Missing/error audits stay unmeasured. The supplied report and URL were not independently verified; no rankings or outcomes are established.",
    }
    output = Path(out)
    if any((output / name).exists() for name in ("lighthouse-review.json", "lighthouse-review.md")):
        raise ValueError("Lighthouse output already exists; choose a fresh output folder.")

    def safe(x):
        return (
            str(x).replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")
        )

    lines = [
        "# Lighthouse lab evidence",
        "",
        "The report is user supplied; the numbers below are lab observations, not field data.",
        "",
        result["limits"],
        "",
        "- URL: " + safe(result["final_url"] or "Not recorded"),
        "- Captured: " + safe(result["report_time"] or "Not recorded"),
        "- Run status: " + result["status"],
        "- Performance score: "
        + (
            str(result["performance_score_0_to_100"]) + "/100"
            if result["performance_score_0_to_100"] is not None
            else "Not measured"
        ),
        "",
        "| Metric | Result | Review |",
        "|---|---|---|",
    ]
    for metric in metrics:
        display = metric["display_value"] or (
            str(metric["value"]) + " " + metric["unit"]
            if metric["value"] is not None
            else metric["status"]
        )
        lines.append(
            "| "
            + safe(metric["label"])
            + " | "
            + safe(display)
            + " | "
            + (
                safe(metric["action"])
                if metric["status"] == "observed"
                else "Do not infer a result; inspect the original run."
            )
            + " |"
        )
    return save_report(output, "lighthouse-review", result, lines)


def _entity_strings(value):
    """Retain explicit textual declarations; do not infer missing properties."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    if isinstance(value, dict) and isinstance(value.get("@value"), str):
        return [value["@value"]]
    return []


def _entity_identifier(value, page_url):
    from urllib.parse import urljoin

    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    return value if value.startswith("_:") else urljoin(page_url, value)


def _entity_relationship(value, page_url):
    values = value if isinstance(value, list) else [value]
    targets = []
    for entry in values:
        if isinstance(entry, str):
            if entry.startswith(("https://", "http://", "#", "/", "_:")):
                targets.append({"id": _entity_identifier(entry, page_url)})
            else:
                targets.append({"name": [entry]})
        elif isinstance(entry, dict):
            target = {}
            if isinstance(entry.get("@id"), str):
                target["id"] = _entity_identifier(entry["@id"], page_url)
            for key in ("@type", "name", "url"):
                strings = _entity_strings(entry.get(key))
                if strings:
                    target[key] = strings
            if target:
                targets.append(target)
    return targets


def _entity_equivalent_names(left, right):
    """Avoid treating case, punctuation or an abbreviated name as a defect."""
    suffixes = {"inc", "ltd", "limited", "llc", "corp", "corporation", "company"}
    for a in left:
        aa = set(re.findall(r"\w+", a.casefold())) - suffixes
        for b in right:
            bb = set(re.findall(r"\w+", b.casefold())) - suffixes
            if aa and bb and (aa <= bb or bb <= aa):
                return True
    return False


def _entity_property_signature(record, prop):
    from urllib.parse import urljoin, urlsplit, urlunsplit

    if prop == "publisher":
        result = set()
        for target in record["relationships"].get("publisher", []):
            if target.get("id"):
                result.add(target["id"])
            elif target.get("url"):
                result.update(urljoin(record["source_url"], value) for value in target["url"])
            else:
                result.update(
                    "name:" + value.strip().casefold() for value in target.get("name", [])
                )
        return result
    if prop == "name":
        return {
            v.strip().casefold() for v in record["name"] + record["alternate_name"] if v.strip()
        }
    result = set()
    for value in record["url"]:
        parts = urlsplit(urljoin(record["source_url"], value))
        if parts.scheme in {"http", "https"} and parts.hostname:
            result.add(
                urlunsplit(
                    (
                        parts.scheme.lower(),
                        parts.netloc.lower(),
                        parts.path.rstrip("/") or "/",
                        parts.query,
                        parts.fragment,
                    )
                )
            )
        else:
            result.add(value.strip())
    return result


def entity_review(crawl, out):
    """Inventory saved JSON-LD and propose identity reviews, never an authority score."""
    import html

    output = Path(out)
    if any((output / name).exists() for name in ("entity-review.json", "entity-review.md")):
        raise ValueError("Entity review already exists; choose a fresh output folder.")
    pages = read_pages(crawl)
    records, observations, candidates = [], [], []
    counts = {
        "page_records": len(pages),
        "usable_captures": 0,
        "partial_captures": 0,
        "unusable_captures": 0,
        "jsonld_blocks_observed": 0,
    }
    for page in pages:
        quality = capture_quality(page)
        data, representation = selected_data(page)
        source_url = page.get("final_url") or page.get("url")
        observation = {
            "url": source_url,
            "requested_url": page.get("url"),
            "captured_at": quality["captured_at"],
            "representation": representation,
            "capture_usable": quality["usable"],
            "capture_limits": list(quality["limits"]),
            "observed_definitions": 0,
            "jsonld_parse_errors": [],
            "inspection_limits": [],
        }
        observations.append(observation)
        if not quality["usable"]:
            counts["unusable_captures"] += 1
            continue
        counts["usable_captures"] += 1
        if quality["limits"]:
            counts["partial_captures"] += 1
        errors = data.get("jsonld_errors") or []
        if errors:
            observation["jsonld_parse_errors"] = errors
        blocks = data.get("jsonld", [])
        if not isinstance(blocks, list):
            observation["inspection_limits"].append(
                "Stored jsonld field is not a block list; inspect the original capture."
            )
            continue
        counts["jsonld_blocks_observed"] += len(blocks)
        stack = [(value, f"jsonld[{i}]", 0) for i, value in enumerate(blocks)]
        examined = 0
        while stack:
            node, path, depth = stack.pop()
            examined += 1
            if examined > 10000:
                observation["inspection_limits"].append(
                    "Stopped after 10000 stored JSON-LD nodes on this page."
                )
                break
            if depth > 64:
                observation["inspection_limits"].append(
                    "A stored JSON-LD branch exceeds the 64-level inspection bound."
                )
                continue
            if isinstance(node, list):
                stack.extend((v, f"{path}[{i}]", depth + 1) for i, v in enumerate(node))
                continue
            if not isinstance(node, dict):
                continue
            types = _entity_strings(node.get("@type"))
            names = _entity_strings(node.get("name"))
            urls = _entity_strings(node.get("url"))
            same_as = _entity_strings(node.get("sameAs"))
            # An @id-only relationship is a reference, not a new definition.
            if types or names or urls or same_as:
                raw_id = node.get("@id")
                ident = _entity_identifier(raw_id, source_url)
                relationships = {
                    key: _entity_relationship(node[key], source_url)
                    for key in (
                        "publisher",
                        "author",
                        "provider",
                        "instructor",
                        "founder",
                        "worksFor",
                        "affiliation",
                        "about",
                        "isPartOf",
                    )
                    if key in node
                }
                records.append(
                    {
                        "entity_id": ident,
                        "declared_id": raw_id if isinstance(raw_id, str) else None,
                        "identifier_scope": "document_blank_node"
                        if ident and ident.startswith("_:")
                        else "uri"
                        if ident
                        else "no_id_declared",
                        "types": types,
                        "name": names,
                        "alternate_name": _entity_strings(node.get("alternateName")),
                        "url": urls,
                        "same_as": same_as,
                        "relationships": relationships,
                        "source_url": source_url,
                        "requested_url": page.get("url"),
                        "captured_at": quality["captured_at"],
                        "representation": representation,
                        "capture_limited": bool(quality["limits"]),
                        "capture_limits": quality["limits"],
                        "evidence_path": path,
                    }
                )
                observation["observed_definitions"] += 1
            stack.extend(
                (value, path + "." + str(key), depth + 1)
                for key, value in node.items()
                if isinstance(value, (dict, list))
            )
    grouped = {}
    for row in records:
        if row["entity_id"] and row["identifier_scope"] == "uri":
            grouped.setdefault(row["entity_id"], []).append(row)
    for ident, declarations in sorted(grouped.items()):
        if len({r["source_url"] for r in declarations}) < 2:
            continue
        for prop in ("name", "url", "publisher"):
            pairs = []
            for i, left in enumerate(declarations):
                a = _entity_property_signature(left, prop)
                if not a:
                    continue
                for right in declarations[i + 1 :]:
                    if left["source_url"] == right["source_url"]:
                        continue
                    b = _entity_property_signature(right, prop)
                    if not b or a & b:
                        continue
                    if prop == "name" and _entity_equivalent_names(a, b):
                        continue
                    for row in (left, right):
                        evidence = {
                            "url": row["source_url"],
                            "captured_at": row["captured_at"],
                            "representation": row["representation"],
                            "capture_limited": row["capture_limited"],
                            "evidence_path": row["evidence_path"] + "." + prop,
                            "value": row["relationships"].get(prop)
                            if prop == "publisher"
                            else row[prop],
                        }
                        if evidence not in pairs:
                            pairs.append(evidence)
            if pairs:
                candidates.append(
                    {
                        "kind": "stable_id_property_variation",
                        "classification": "review_candidate",
                        "entity_id": ident,
                        "property": prop,
                        "observed_declarations": pairs,
                        "observation": f"The same declared entity ID has different non-overlapping {prop} values in saved page captures.",
                        "why_review": "The declarations may be legitimate alternate names, multiple websites/publishers or a change over time; they may also reflect inconsistent templates. A reviewer must establish the intended entity and facts.",
                        "recommended_action": "Compare these exact declarations and the visible business facts. Consolidate the source data if they describe the same intended identity; preserve distinct legitimate entities and supported relationships.",
                        "acceptance_check": "Recapture the affected pages after any authorised correction; intended identity properties and references agree with verified facts. Retain legitimate variants explicitly.",
                        "limits": "Observed variation is not a schema defect, an authority judgment or proof that an engine misidentified the business.",
                    }
                )
    limited = any(
        not row["capture_usable"]
        or row["capture_limits"]
        or row["inspection_limits"]
        or row["jsonld_parse_errors"]
        for row in observations
    )
    result = {
        "schema_version": 1,
        "created_at": utcnow(),
        "status": "partial" if limited else "review_available" if records else "no_observations",
        "scope": "Saved selected-representation JSON-LD declarations only; no network requests or full semantic Schema.org validation.",
        "coverage": {
            **counts,
            "entity_definitions_observed": len(records),
            "stable_uri_ids_observed": len(grouped),
        },
        "pages": observations,
        "entities": records,
        "review_candidates": candidates,
        "interpretation": [
            "Inventory counts describe declaration records, including nested/repeated schema objects, not unique businesses or people.",
            "Definitions on different pages may legitimately describe different people, organisations, products or relationships. Distinct IDs are not automatically duplicates or defects.",
            "Partial captures can support positive observed declarations; failed/partial captures do not establish missing schema or missing content.",
            "A property not returned on one page is not a conflicting value. Relative IDs are resolved against the captured page URL; blank-node identifiers remain document-scoped.",
            "SameAs and relationship URLs are observed declarations, not verified identity ownership or independent endorsements. Inspect their destinations separately when authorised.",
        ],
        "not_measured": [
            "authority",
            "AI citations",
            "rankings",
            "traffic",
            "complete website coverage",
            "complete semantic schema validity",
        ],
    }

    def safe(value):
        return html.escape(str(value)).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Saved entity declarations and review candidates",
        "",
        result["scope"],
        "",
        f"Saved page records: {len(pages)}. Observed definitions: {len(records)}. Review candidates: {len(candidates)}.",
        "",
        "These are review candidates, not confirmed defects or measured authority/AI visibility.",
        "",
        "| Entity ID | Type | Name | Declared URL | Source and capture date |",
        "|---|---|---|---|---|",
    ]
    for row in records:
        lines.append(
            "| "
            + " | ".join(
                safe(value)
                for value in (
                    row["entity_id"] or "No ID declared",
                    ", ".join(row["types"]),
                    ", ".join(row["name"]),
                    ", ".join(row["url"]),
                    f"{row['source_url']} — {row['captured_at'] or 'date unavailable'}",
                )
            )
            + " |"
        )
    lines += ["", "## Review candidates", ""]
    for row in candidates:
        lines += [
            "### " + safe(row["entity_id"]) + " — " + row["property"],
            "",
            row["observation"],
            "",
            row["why_review"],
            "",
        ]
        lines += [
            "- "
            + safe(e["url"])
            + " — "
            + safe(e["captured_at"])
            + ": "
            + safe(json.dumps(e["value"], ensure_ascii=False))
            for e in row["observed_declarations"]
        ]
        lines += [
            "",
            "Action: " + row["recommended_action"],
            "",
            "Check: " + row["acceptance_check"],
            "",
        ]
    if not candidates:
        lines += [
            "No cross-page variation met this conservative screening rule. This is not a complete identity or schema assessment.",
            "",
        ]
    lines += ["## Coverage and limits", ""] + ["- " + note for note in result["interpretation"]]
    for row in observations:
        limits = row["capture_limits"] + row["inspection_limits"]
        if row["jsonld_parse_errors"]:
            limits.append(
                "Captured JSON-LD parser errors: "
                + json.dumps(row["jsonld_parse_errors"], ensure_ascii=False)
            )
        if limits:
            lines.append("- " + safe(row["url"]) + ": " + safe("; ".join(limits)))
    return save_report(output, "entity-review", result, lines)
