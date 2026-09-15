"""BeyondSEO's transparent, sample-based reputation assessment."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode, urlsplit

from .backlinks import check_sources
from .engine import write_csv
from .network import normalize_url, utcnow
from .review import read_json, save_report

MODEL_VERSION = "1.1"
LOW_CONFIDENCE_CEILING = 49.0
RELEVANCE = {"high": 25, "medium": 15, "low": 5}
RELATIONSHIP = {"independent": 20, "third_party_profile": 10, "affiliated": 5, "owned": 0}
CONTEXT = {"editorial": 15, "directory": 10, "user_generated": 5, "owned": 0}
SOURCE_FIELDS = [
    "URL",
    "engine",
    "query",
    "search_page",
    "result_order",
    "observed_at",
    "source_snapshot",
    "relevance",
    "relationship",
    "context",
    "reviewed_by",
    "reviewed_at",
    "review_evidence",
]


def host(url):
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


def publisher_key(url):
    name = host(url)
    # Conservatively pool common publishing platforms; these are host families,
    # not a claim to have resolved every registrable domain or editorial owner.
    for suffix in ("medium.com", "dev.to", "forem.com", "substack.com", "blogspot.com"):
        if name == suffix or name.endswith("." + suffix):
            return suffix
    return name


def source_score(row, target, related_hosts=()):
    final_host = host(row.get("final_url") or row["source_url"])
    same_site = final_host == host(target) or final_host.endswith("." + host(target))
    verified_target_links = [
        link for link in row.get("target_links", []) if host(link.get("url")) == host(target)
    ]
    observed_link = row.get("verification") == "link_observed" and bool(verified_target_links)
    observed_mention = (
        bool(row.get("brand_mentions")) and row.get("mention_status") == "observed_in_page"
    )
    observed_link = observed_link and not same_site
    eligible = (
        (observed_link or observed_mention)
        and not row.get("missing_content_candidate")
        and not same_site
    )
    meta = row.get("discovery") or {}
    # Judgements require an attributable review note; unknown is an interval,
    # never silently a bad quality verdict.
    reviewed = all(
        str(meta.get(k, "")).strip() for k in ("reviewed_by", "reviewed_at", "review_evidence")
    )
    relationship = meta.get("relationship", "unknown") if reviewed else "unknown"
    related = [host(target), *(h.lower().removeprefix("www.").rstrip(".") for h in related_hosts)]
    if any(final_host == h or final_host.endswith("." + h) for h in related if h):
        relationship = "owned"
    relevance = meta.get("relevance", "unknown") if reviewed else "unknown"
    context = meta.get("context", "unknown") if reviewed else "unknown"
    rels = {v.lower() for link in verified_target_links for v in link.get("rel", [])}
    sponsored = "sponsored" in rels or str(meta.get("paid", "")).lower() in ("true", "yes")
    points = {
        "observed_evidence": (40 if observed_link else 25 if observed_mention else 0, 40),
        "topic_relevance": (RELEVANCE.get(relevance), 25),
        "relationship": (RELATIONSHIP.get(relationship), 20),
        "context": (CONTEXT.get(context), 15),
    }
    if sponsored:
        points["relationship"] = (0, 20)
        relationship = "sponsored"
    low = sum(v for v, maximum in points.values() if v is not None)
    high = low + sum(maximum for v, maximum in points.values() if v is None)
    assessed = sum(maximum for v, maximum in points.values() if v is not None)
    return {
        "source_url": row["source_url"],
        "final_url": row.get("final_url"),
        "publisher_group": publisher_key(row.get("final_url") or row["source_url"]),
        "eligible_evidence": eligible,
        "excluded_reason": "same_site_source" if same_site else "",
        "observed_link": observed_link,
        "observed_mention": observed_mention and not same_site,
        "quality_estimate": round((low + high) / 2, 1) if eligible else None,
        "supported_quality_points": low if eligible else None,
        "quality_range": [low, high] if eligible else None,
        "assessed_weight_percent": assessed if eligible else 0,
        "relationship": relationship,
        "context": context,
        "relevance": relevance,
        "independent_editorial_evidence": eligible
        and relationship == "independent"
        and context == "editorial"
        and not sponsored,
        "independence_unknown": eligible
        and relationship in ("unknown", "independent")
        and context in ("unknown", "editorial")
        and not (relationship == "independent" and context == "editorial"),
        "dimensions": {
            k: {"points": v, "maximum": m, "status": "unknown" if v is None else "assessed"}
            for k, (v, m) in points.items()
        },
        "review_attribution": {
            k: meta.get(k) for k in ("reviewed_by", "reviewed_at", "review_evidence")
        },
        "verification": row.get("verification"),
        "representation": row.get("representation"),
        "target_links": verified_target_links,
        "brand_mentions": row.get("brand_mentions", []),
        "source_index_signals": row.get("source_index_signals", {}),
        "discovery": meta,
        "access_error": row.get("error"),
    }


def assess(verification, related_hosts=(), requested_search_pages=5):
    if not 1 <= requested_search_pages <= 20:
        raise ValueError("Search-page budget must be between 1 and 20.")
    # Imported evidence may repeat a source. Repetition must not improve coverage.
    unique = {}
    for row in verification["results"]:
        key = normalize_url(row["source_url"]) or row["source_url"]
        unique.setdefault(key, row)
    duplicates = len(verification["results"]) - len(unique)
    verification = {**verification, "results": list(unique.values())}
    scored = [
        source_score(r, verification["target"], related_hosts) for r in verification["results"]
    ]
    groups = {}
    for row in scored:
        if not row["eligible_evidence"]:
            continue
        key = row["publisher_group"]
        if key not in groups or row["quality_estimate"] > groups[key]["quality_estimate"]:
            groups[key] = row
    ranked = sorted(groups.values(), key=lambda r: (-r["quality_estimate"], r["source_url"]))
    top = ranked[:5]
    readable = sum(
        r.get("verification") in ("link_observed", "no_link_in_captured_content")
        for r in verification["results"]
    )
    search_pages = sorted(
        {
            (
                str(r["discovery"].get("engine", "")),
                str(r["discovery"].get("query", "")),
                str(r["discovery"].get("search_page", "")),
            )
            for r in scored
            if r["discovery"].get("search_page")
            and r["discovery"].get("engine")
            and r["discovery"].get("query")
            and r["discovery"].get("observed_at")
        }
    )
    independently_reviewed = sum(r["independent_editorial_evidence"] for r in ranked)
    unknown_independence = sum(r["independence_unknown"] for r in ranked)
    breadth = 25 * min(len(groups) / 5, 1)
    independent_low = 15 * min(independently_reviewed / 3, 1)
    independent_high = 15 * min((independently_reviewed + unknown_independence) / 3, 1)
    if top:
        low = 0.6 * sum(r["quality_range"][0] for r in top) / len(top) + breadth + independent_low
        high = 0.6 * sum(r["quality_range"][1] for r in top) / len(top) + breadth + independent_high
        score_range = [round(low, 1), round(high, 1)]
        estimate = round((low + high) / 2, 1)
    elif readable:
        estimate, score_range = 0.0, [0.0, 0.0]
    else:
        estimate, score_range = None, None
    checked = len(scored)
    capture_fraction = readable / checked if checked else 0
    supplied = verification.get("sources_supplied", checked)
    remaining = verification.get("sources_remaining", 0)
    candidate_count = max(
        checked,
        supplied if isinstance(supplied, int) else checked,
        checked + (remaining if isinstance(remaining, int) and remaining > 0 else 0),
    )
    verification_fraction = readable / candidate_count if candidate_count else 0
    reviewed_weight = sum(r["assessed_weight_percent"] for r in top) / len(top) if top else 0
    search_coverage = min(len(search_pages) / requested_search_pages, 1) if search_pages else None
    factors = {
        "conclusive_link_checks": verification_fraction,
        "reviewed_source_dimensions": reviewed_weight / 100,
        "publisher_breadth": min(len(groups) / 5, 1),
        "search_page_coverage": search_coverage,
    }
    support = min(value for value in factors.values() if value is not None)
    confidence = (
        "moderate within this sample"
        if len(groups) >= 5
        and verification_fraction >= 0.8
        and reviewed_weight >= 80
        and search_coverage == 1
        else "low"
    )
    ceiling = 100.0 if confidence == "moderate within this sample" else LOW_CONFIDENCE_CEILING
    sample_estimate, sample_range = estimate, score_range
    if sample_range is None or not readable:
        estimate, score_range = None, None
        confidence = "insufficient conclusive evidence"
        status = "withheld"
    else:
        # Unknown quality earns no headline points. Missing evidence reduces
        # supported assurance, without declaring unread sources poor quality.
        estimate = round(min(sample_range[0] * support, ceiling), 1)
        score_range = [estimate, round(min(sample_range[1] * support, ceiling), 1)]
        status = "provisional" if confidence == "low" else "assessed_within_sample"
    result = {
        "name": "BeyondSEO Reputation Score",
        "model_version": MODEL_VERSION,
        "target": verification["target"],
        "brand": verification.get("brand", ""),
        "checked_at": verification.get("checked_at", utcnow()),
        "assessment_type": "evidence_supported_sample_score",
        "score": estimate,
        "score_range": score_range,
        "score_status": status,
        "confidence": confidence,
        "sample_quality_estimate": sample_estimate,
        "sample_quality_range": sample_range,
        "range_meaning": "The headline uses supported lower-bound points after evidence adjustment, not the midpoint. The range varies unassessed rubric dimensions at the same coverage and ceiling; it is not a statistical confidence interval or an estimate of unseen web evidence.",
        "evidence_adjustment": {
            "factor": round(support, 6),
            "factors": {k: round(v, 6) if v is not None else None for k, v in factors.items()},
            "confidence_ceiling": ceiling,
            "limiting_factors": [k for k, v in factors.items() if v is None or v < 1],
            "policy": "Use the weakest measured evidence factor. Unknown search coverage keeps confidence low. Low-confidence headlines are capped at 49/100 for every site; no conclusive checks withholds the headline.",
        },
        "coverage": {
            "sources_checked": checked,
            "known_source_candidates": candidate_count,
            "sources_unchecked": candidate_count - checked,
            "duplicate_source_rows_ignored": duplicates,
            "conclusive_link_checks": readable,
            "conclusive_link_check_fraction": round(capture_fraction, 3),
            "partial_or_unverified_link_checks": checked - readable,
            "sources_with_positive_evidence": sum(r["eligible_evidence"] for r in scored),
            "requested_search_pages": requested_search_pages,
            "recorded_search_pages": [
                {"engine": e, "query": q, "page": p} for e, q, p in search_pages
            ],
            "search_page_count_is_imported_provenance": True,
            "unique_publisher_groups_with_evidence": len(groups),
            "assessed_weight_of_selected_sources_percent": round(reviewed_weight, 1),
        },
        "observed_link_pages": sum(r["observed_link"] for r in scored),
        "observed_mention_pages": sum(r["observed_mention"] for r in scored),
        "independent_editorial_publisher_groups": independently_reviewed,
        "estimated_total_backlinks": None,
        "total_backlinks_note": "No defensible whole-web total can be extrapolated from a ranked search sample. Counts below cover observed sources only.",
        "formula": "Supported sample points = 60% mean lower-bound source quality of the strongest five publisher groups + up to 25 points for five groups + up to 15 for three reviewed independent editorial groups. Headline = supported sample points × weakest evidence factor, capped at 49 when confidence is low.",
        "components": {
            "breadth_points": round(breadth, 1),
            "independent_proof_points_range": [independent_low, independent_high],
        },
        "top_backlinks": sorted(
            [r for r in scored if r["observed_link"]],
            key=lambda r: (-(r["quality_estimate"] or 0), r["source_url"]),
        )[:10],
        "top_mentions_without_links": sorted(
            [r for r in scored if r["observed_mention"] and not r["observed_link"]],
            key=lambda r: (-(r["quality_estimate"] or 0), r["source_url"]),
        )[:10],
        "sources": scored,
        "limitations": [
            "Search snippets are discovery hints, not verified backlinks.",
            "Search results are a biased and incomplete sample; position is not used as source authority.",
            "Unknown dimensions remain unknown and widen the range.",
            "The score measures supported evidence under a conservative rubric. Missing access reduces assurance; it does not prove a site's reputation is poor.",
            "The same rules apply to every brand. Search sampling and reviewer judgments can still be biased; this is not a statistically unbiased ranking model.",
            "Related/owned sources do not count as independent editorial proof.",
            "nofollow, ugc and sponsored values are recorded; none proves how an engine values the link.",
            "Host/platform grouping is conservative and not a complete ownership or registrable-domain database.",
            "The score does not measure sentiment, customer satisfaction, site traffic or future search ranking.",
            "An incomplete link check may still contain an observed mention. Positive evidence is retained; incomplete capture cannot establish link absence.",
        ],
    }
    return result


def export_assessment(result, out):
    out = Path(out)
    lines = [
        "# BeyondSEO Reputation Score",
        "",
        "**Conservative score for the evidence we could establish.**",
        "",
        f"Evidence-supported score: {result['score'] if result['score'] is not None else 'withheld'} / 100 — {result['score_status']}.",
        f"Sensitivity range: {result['score_range']}; confidence: {result['confidence']}.",
        "",
        result["range_meaning"],
        "",
        f"Observed links: {result['observed_link_pages']} source pages. Observed brand mentions: {result['observed_mention_pages']} pages (may overlap links).",
        f"Checked {result['coverage']['sources_checked']} sources: {result['coverage']['conclusive_link_checks']} conclusive link checks; {result['coverage']['partial_or_unverified_link_checks']} incomplete or unverified. Positive evidence was captured on {result['coverage']['sources_with_positive_evidence']} pages, including any partial captures.",
        f"Known source candidates: {result['coverage']['known_source_candidates']}; not yet checked: {result['coverage']['sources_unchecked']}. Unchecked known candidates remain in the verification-coverage denominator.",
        f"Requested search pages: {result['coverage']['requested_search_pages']}; recorded pages: {len(result['coverage']['recorded_search_pages'])}. Requested pages are not treated as completed searches.",
        "",
        result["total_backlinks_note"],
        "",
        "## How the score is calculated",
        "",
        result["formula"],
        "",
        f"Evidence factor: {result['evidence_adjustment']['factor']}; confidence ceiling: {result['evidence_adjustment']['confidence_ceiling']}/100. Limits: {', '.join(result['evidence_adjustment']['limiting_factors']) or 'none within the recorded sample'}.",
        "",
        f"Diagnostic sample quality before evidence adjustment: {result['sample_quality_estimate']}, range {result['sample_quality_range']}. This is not the headline score or an overall site rating.",
        "",
        "## Strongest observed backlink pages",
        "",
    ]
    lines += [
        f"- {r['source_url']} — supported source-quality points {r['supported_quality_points']}/100; possible rubric range {r['quality_range']}; {r['relationship']}; {r['representation']}."
        for r in result["top_backlinks"]
    ]
    if not result["top_backlinks"]:
        lines.append("No direct backlinks were established in this sample.")
    lines += ["", "## Mentions without an observed link", ""]
    lines += [
        f"- {r['source_url']} — mention observed in captured content; no direct link captured."
        for r in result["top_mentions_without_links"]
    ]
    lines += [
        "",
        "## Practical next steps",
        "",
        "- Resolve unread sources before interpreting their absence.",
        "- Review unknown relevance, relationship and publication context with dated evidence.",
        "- Improve factual profiles and seek genuine project references; prioritize useful independent proof.",
        "- Compare future snapshots using the same discovery method and query/locale; changed sampling can change the score.",
        "",
        "## Limits",
        "",
    ] + ["- " + s for s in result["limitations"]]
    save_report(out, "reputation", result, lines)
    fields = [
        "source_url",
        "final_url",
        "publisher_group",
        "verification",
        "observed_link",
        "observed_mention",
        "quality_estimate",
        "supported_quality_points",
        "quality_range",
        "assessed_weight_percent",
        "relationship",
        "context",
        "relevance",
        "representation",
        "access_error",
        "target_links",
    ]
    write_csv(out / "reputation-sources.csv", fields, result["sources"])
    return result


def reputation(
    sources,
    target,
    brand,
    out,
    limit=50,
    mode="auto",
    allow_private=False,
    aliases=(),
    related_hosts=(),
    requested_search_pages=5,
    evidence=None,
):
    if not normalize_url(target) or not brand.strip() or not 1 <= requested_search_pages <= 20:
        raise ValueError("Provide a target URL, a brand and a search-page budget between 1 and 20.")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose a new reputation output folder.")
    if evidence:
        verification = read_json(evidence)
        if host(verification.get("target")) != host(target):
            raise ValueError("Saved backlink evidence belongs to a different target.")
        if verification.get("brand", "").casefold() != brand.casefold():
            raise ValueError(
                "Saved backlink evidence must have been captured with this brand for mention verification."
            )
    else:
        verification = check_sources(
            sources, target, out / "verification", limit, mode, allow_private, True, brand, aliases
        )
    result = assess(verification, related_hosts, requested_search_pages)
    result["evidence_source"] = str(evidence) if evidence else "verification/backlinks.json"
    result["reused_evidence"] = bool(evidence)
    return export_assessment(result, out)


def search_plan(target, brand, out, pages=5):
    target = normalize_url(target)
    if not target or not brand.strip() or not 1 <= pages <= 20:
        raise ValueError("Provide a target URL, brand and a page budget between 1 and 20.")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose a new search-plan folder.")
    query = f'"{brand}" -site:{host(target)}'
    result = {
        "target": target,
        "brand": brand,
        "requested_pages": pages,
        "completed_pages": 0,
        "query": query,
        "created_at": utcnow(),
        "pages": [
            {
                "page": i + 1,
                "url": "https://www.google.com/search?" + urlencode({"q": query, "start": i * 10}),
                "status": "planned",
            }
            for i in range(pages)
        ],
        "note": "These are search navigation links, not scraped results or verified pagination. Use available search/browser access and record actual coverage. Stop at access challenges; import saved result pages or supply source URLs when pagination is unavailable.",
    }
    save_report(
        out,
        "search-plan",
        result,
        ["# Reputation discovery", "", result["note"], ""]
        + [f"- Page {r['page']}: {r['url']} — planned" for r in result["pages"]],
    )
    write_csv(out / "sources-template.csv", SOURCE_FIELDS, [])
    return result


def import_search_html(paths, target, query, captured_at, out, engine="Google"):
    """Import public result snapshots without claiming to have run live searches."""
    target = normalize_url(target)
    if not paths or len(paths) > 20 or not target or not query.strip() or not captured_at.strip():
        raise ValueError("Supply 1–20 saved result pages, target, query and capture timestamp.")
    from .discovery import discover

    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Choose a new search-import folder.")
    original_time = captured_at
    if len(captured_at) == 10:
        captured_at += "T00:00:00+00:00"
    provider = {"Google": "google", "Bing": "bing", "DuckDuckGo": "duckduckgo-html"}.get(
        engine, engine.lower()
    )
    discovered = discover(
        [],
        out,
        target=target,
        offline=True,
        saved=[
            {"path": str(path), "provider": provider, "query": query, "captured_at": captured_at}
            for path in paths
        ],
    )
    rows = []
    for candidate in discovered["candidates"]:
        provenance = candidate["provenance"]
        for observation in provenance:
            observation["search_page"] = next(
                (
                    i
                    for i, path in enumerate(paths, 1)
                    if str(path) == observation.get("source_snapshot")
                ),
                None,
            )
            observation["timestamp_precision"] = "date" if len(original_time) == 10 else "timestamp"
        first = provenance[0]
        rows.append(
            {
                "URL": candidate["url"],
                "engine": engine,
                "query": query,
                "search_page": first["search_page"],
                "result_order": first.get("result_order"),
                "observed_at": original_time,
                "source_snapshot": first.get("source_snapshot"),
                "provenance": provenance,
            }
        )
    write_csv(out / "sources.csv", SOURCE_FIELDS + ["provenance"], rows)
    result = {
        "input_kind": "supplied_search_html",
        "engine_declared_by_operator": engine,
        "snapshots_imported": len(paths),
        "attempts": discovered["attempts"],
        "candidate_urls": len(rows),
        "captured_at_supplied": captured_at,
        "note": "Extracted result-heading links from supplied HTML. Result order is not a verified search rank; snippets do not establish mentions or backlinks. No live search was performed by this command.",
    }
    return save_report(
        out,
        "search-import",
        result,
        [
            "# Imported search candidates",
            "",
            result["note"],
            "",
            f"Imported {len(rows)} unique candidate URLs from {len(paths)} snapshots.",
        ],
    )
