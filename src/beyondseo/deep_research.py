"""Portable research plans and conservative comparison of captured reputation evidence.

The assistant executes host browser tools. This module plans that work and checks
its outputs; it never pretends a browser or search task ran because it was planned.
"""

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from .engine import write_json
from .network import normalize_url, utcnow
from .reputation import assess, host
from .research import NON_SPECIFIC_MARKETS, research_queries
from .review import read_json, save_report

FAMILIES = ("brand_mentions", "domain_mentions", "reviews", "project_references", "partnerships")
ROUTES = ["host_browser_google", "host_search", "duckduckgo-html", "bing-rss", "supplied_evidence"]


def reputation_queries(target, brand, market=None, language=None):
    domain = host(target)
    # Normalize quotes in names to avoid accidentally creating malformed query syntax.
    name = brand.replace('"', " ").strip() or domain
    terms = (
        f'"{name}" company' if name.casefold() == domain else f'"{name}"',
        f'"{domain}"',
        f'"{name}" reviews',
        f'"{name}" "case study"',
        f'"{name}" partners',
    )
    return [
        {
            "family": family,
            "query": f"{term} -site:{domain}",
            "market": market,
            "language": language,
            "google_url": "https://www.google.com/search?"
            + urlencode({"q": f"{term} -site:{domain}"}),
        }
        for family, term in zip(FAMILIES, terms)
    ]


def research_plan(profile, out, brand=None, selection=None, source_limit=30):
    if profile.get("status") != "reviewed":
        raise ValueError("Review the website's business profile before planning deep research.")
    if not 5 <= source_limit <= 100:
        raise ValueError("Use a shared source limit from 5 to 100.")
    target = normalize_url(profile.get("target", ""))
    if not target:
        raise ValueError("Profile needs a valid target.")
    fields = profile.get("fields", {})
    brief = profile.get("brief", {}).get("fields", {})
    markets = brief.get("markets") or fields.get("markets", [])
    languages = brief.get("search_languages") or fields.get("search_languages", [])
    if not languages:
        languages = fields.get("website_languages", [])
    specific = [m for m in markets if m["key"].casefold() not in NON_SPECIFIC_MARKETS]
    market = specific[0]["value"] if specific else None
    language = languages[0]["value"] if languages else None
    cohort = [{"target": target, "brand": brand or host(target), "role": "client"}]
    if selection:
        if host(selection.get("client")) != host(target):
            raise ValueError("Competitor selection belongs to a different client.")
        for item in selection.get("direct_competitors", [])[:5]:
            cohort.append(
                {
                    "target": item["website"],
                    "brand": item.get("brand") or host(item["website"]),
                    "role": "direct_competitor",
                }
            )
    for item in cohort:
        item["queries"] = reputation_queries(item["target"], item["brand"], market, language)
    result = {
        "schema_version": 1,
        "created_at": utcnow(),
        "client": target,
        "status": "planned_not_executed",
        "market": market,
        "language": language,
        "route_order": ROUTES,
        "browser_record": {
            "required": [
                "host",
                "tool",
                "backend",
                "profile_mode",
                "execution_location",
                "navigation_status",
                "evidence",
            ],
            "guidance": "Record the actual managed/local/remote browser. Installed executable alone is not control. Do not attach to personal profiles, copy cookies or change host access to make a search work.",
        },
        "competitor_queries": research_queries(profile)[:6],
        "query_guidance": "Agent: review natural buyer wording before searching. Lead with category/service phrases and useful questions grounded in the brief. Rewrite needs_review seeds in the requested language. Discovery queries are hypotheses, not recommended SEO keywords or measured demand; recommend page targets only after inspecting intent and fit.",
        "budgets": {
            "candidate_pool_goal": 15,
            "candidate_profile_page_limit": 4,
            "final_direct_competitor_goal": 5,
            "reputation_query_samples_per_site": len(FAMILIES),
            "source_limit_per_site": source_limit,
            "native_requests_per_site": 48,
            "native_seconds_per_site": 180,
        },
        "protocol": {
            "query_families": list(FAMILIES),
            "max_capture_age_days": 7,
            "max_cohort_span_days": 2,
            "max_coverage_difference": 0.10,
            "model": "1.1",
            "source_selection": "Consolidate all discovered URLs before checking. Diversify publishers and query families; do not preselect only favorable links. Retain unchecked candidates in coverage.",
        },
        "cohort": cohort,
        "visibility_task": {
            "search": "Use the same buyer-intent queries/provider/context for client and candidates. Retain observed result order, query, date and location/language; do not call this a general ranking.",
            "ai_readiness": "Compare equivalent service pages: initial/rendered answers, crawl access, index signals, entity consistency, visible proof and structured data. Readiness does not prove AI inclusion.",
            "ai_visibility": "Only record actual AI-answer observations when a permitted surface is available: exact prompt, engine, date and cited URLs. Otherwise mark not measured. No new subscription is required.",
        },
        "limits": [
            "These are effort budgets, not completed searches or a complete backlink index.",
            "Respect explicit smaller user limits. Label their result as a limited study.",
            "Select fewer than five competitors when the evidence does not support five.",
            "Markets/languages beyond the first cohort need separate comparable runs; other profile context is retained in the original profile.",
            "An unknown market does not become the domain's country or the website language.",
        ],
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "research-plan.json", result)
    for index, item in enumerate(cohort):
        write_json(out / f"reputation-queries-{index}.json", item["queries"])
    return result


def _date(value):
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("Capture dates need an explicit timezone.")
    return date


def compare_reputation(plan, entries, out, now=None):
    """Rank only a matched, adequately reviewed cohort; always retain usable results."""
    now = now or datetime.now(timezone.utc)
    if any(item.get("role") not in ("client", "direct_competitor") for item in plan["cohort"]):
        raise ValueError(
            "Reputation ranking requires a direct-competitor cohort; keep benchmarks separate."
        )
    clients = [item for item in plan["cohort"] if item.get("role") == "client"]
    if len(clients) != 1 or host(clients[0]["target"]) != host(plan["client"]):
        raise ValueError("Plan needs exactly one matching client.")
    cohort = {host(item["target"]): item for item in plan["cohort"]}
    if len(cohort) != len(plan["cohort"]):
        raise ValueError("Cohort contains duplicate websites.")
    rows, reasons, methods, dates, factors = [], [], [], [], []
    seen = set()
    for entry in entries:
        verification, discovery = entry["verification"], entry["discovery"]
        domain = host(verification.get("target"))
        if domain not in cohort or domain in seen:
            raise ValueError("Evidence target is duplicated or outside the planned cohort.")
        if host(discovery.get("target")) != domain:
            raise ValueError("Discovery and source verification targets differ.")
        seen.add(domain)
        item = cohort[domain]
        local_reasons, method = [], []
        if discovery.get("candidate_budget_reached"):
            local_reasons.append(
                "Discovery candidate pool was truncated; remaining coverage is unknown."
            )
        for spec in item["queries"]:
            attempts = [
                a
                for a in discovery.get("attempts", [])
                if a.get("query") == spec["query"]
                and a.get("requested_market") == spec.get("market")
                and a.get("requested_language") == spec.get("language")
            ]
            successful = [
                a
                for a in attempts
                if a.get("status") in ("results", "empty_results", "no_relevant_results")
            ]
            if not successful:
                local_reasons.append("No completed discovery sample for " + spec["family"])
                continue
            # More samples for one brand cannot silently qualify as matched coverage.
            method.append(
                (
                    spec["family"],
                    tuple(
                        sorted(
                            (
                                a.get("provider", ""),
                                a.get("origin", "native"),
                                str(a.get("actual_market")),
                                str(a.get("actual_language")),
                                str(a.get("personalized")),
                                str(a.get("search_page")),
                            )
                            for a in successful
                        )
                    ),
                )
            )
            for attempt in successful:
                try:
                    dates.append(_date(attempt["captured_at"]))
                except (KeyError, ValueError):
                    local_reasons.append("Discovery capture date is unavailable or invalid.")
        known_urls = {normalize_url(c["url"]) for c in discovery.get("candidates", [])}
        known_urls.update(normalize_url(r["source_url"]) for r in verification["results"])
        known_urls.discard(None)
        total = max(
            len(known_urls), verification.get("sources_supplied", 0), len(verification["results"])
        )
        checked = len({normalize_url(r["source_url"]) for r in verification["results"]})
        if checked > plan["budgets"]["source_limit_per_site"]:
            local_reasons.append("Source checks exceeded the shared per-site limit.")
        for source in verification["results"]:
            try:
                dates.append(_date(source["checked_at"]))
            except (KeyError, ValueError):
                local_reasons.append("A source capture date is unavailable or invalid.")
        assessment = assess(
            {
                **verification,
                "sources_supplied": total,
                "sources_remaining": max(0, total - checked),
            },
            requested_search_pages=len(item["queries"]),
        )
        if assessment["confidence"] != "moderate within this sample":
            local_reasons.append("Insufficient reviewed evidence for an ordinal comparison.")
        if assessment["model_version"] != plan["protocol"]["model"]:
            local_reasons.append("Scoring model differs from the planned model.")
        factor = assessment["evidence_adjustment"]["factors"]
        factors.append((factor["conclusive_link_checks"], factor["reviewed_source_dimensions"]))
        methods.append(sorted(method))
        rows.append(
            {
                "target": item["target"],
                "role": item["role"],
                "score": assessment["score"],
                "score_range": assessment["score_range"],
                "confidence": assessment["confidence"],
                "score_status": assessment["score_status"],
                "rank": None,
                "observed_link_pages": assessment["observed_link_pages"],
                "independent_editorial_groups": assessment[
                    "independent_editorial_publisher_groups"
                ],
                "coverage": assessment["coverage"],
                "limits": sorted(set(local_reasons)),
                "evidence_files": entry.get("evidence_files", {}),
            }
        )
        reasons.extend(domain + ": " + reason for reason in sorted(set(local_reasons)))
    if seen != set(cohort):
        reasons.append("Some planned cohort websites have no evidence.")
    if len(rows) < 2:
        reasons.append("At least two comparable websites are required.")
    if methods and any(method != methods[0] for method in methods[1:]):
        reasons.append(
            "Actual providers, contexts or discovery sample counts differ across websites."
        )
    if factors and any(
        max(f[i] for f in factors) - min(f[i] for f in factors)
        > plan["protocol"]["max_coverage_difference"]
        for i in (0, 1)
    ):
        reasons.append("Verification or source-review coverage differs materially across websites.")
    if not dates or any(
        (now - d).total_seconds() < -300
        or (now - d).total_seconds() > plan["protocol"]["max_capture_age_days"] * 86400
        for d in dates
    ):
        reasons.append("Capture dates are missing, stale or in the future.")
    if (
        dates
        and (max(dates) - min(dates)).total_seconds()
        > plan["protocol"]["max_cohort_span_days"] * 86400
    ):
        reasons.append("Captures fall outside the shared comparison time window.")
    if not reasons:
        ordered = sorted(rows, key=lambda r: (-r["score"], host(r["target"])))
        ambiguous = any(
            a["score"] != b["score"] and a["score_range"][0] < b["score_range"][1]
            for a, b in zip(ordered, ordered[1:])
        )
        if ambiguous:
            reasons.append("Sensitivity ranges overlap; a clear ordering is not supported.")
        else:
            prior_score, rank = None, 0
            for index, row in enumerate(ordered, 1):
                if row["score"] != prior_score:
                    rank = index
                row["rank"] = rank
                prior_score = row["score"]
            rows = ordered
    result = {
        "created_at": utcnow(),
        "client": plan["client"],
        "status": "ranked_within_sample" if not reasons else "comparison_only",
        "rank_meaning": "Relative supported reputation evidence within this matched sample; not Google rank, AI visibility, DA/DR or business quality.",
        "ranking_withheld_reasons": reasons,
        "sites": rows,
        "limitations": "Recorded host observations and source reviews remain attributable judgments. Matching effort does not create an unbiased or complete backlink index. Unread sources are unknown, not poor quality.",
    }
    lines = [
        "# Your reputation evidence compared",
        "",
        result["rank_meaning"],
        "",
        "| Website | Evidence points | Confidence | Observed linking pages | Within-sample position |",
        "|---|---:|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['target']} | {row['score'] if row['score'] is not None else 'withheld'} | {row['confidence']} | {row['observed_link_pages']} | {row['rank'] or 'not established'} |"
        )
    lines += ["", "## What limits this comparison", ""] + ["- " + reason for reason in reasons]
    lines += [
        "",
        result["limitations"],
        "",
        "Source URLs and captures remain in the linked evidence files; this overview focuses on standing and gaps, not a backlink dump.",
    ]
    return save_report(Path(out), "reputation-comparison", result, lines)


def comparison_from_manifest(path, out):
    path = Path(path).resolve()
    manifest = read_json(path)

    def read_relative(name):
        return read_json(path.parent / name)

    plan = read_relative(manifest["plan"])
    entries = []
    for item in manifest["sites"]:
        entries.append(
            {
                "verification": read_relative(item["verification"]),
                "discovery": read_relative(item["discovery"]),
                "evidence_files": item,
            }
        )
    return compare_reputation(plan, entries, out)
