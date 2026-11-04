"""Material audit findings with capture evidence, impact and acceptance checks."""

import re
from pathlib import Path

from .engine import write_json
from .evidence import capture_quality
from .network import utcnow
from .reports import (
    group_findings,
    group_observation,
    next_actions,
    page_count,
    readable_observation,
    scope_warning,
    validate_report,
)
from .research import evidence_index, host, verify_reference
from .review import read_json, read_pages

COMPETITOR_POOL_TARGET = 15
MIN_CHECKED_SOURCES = 10
DIRECT_COMPETITOR_TARGET = 5
CHECKS = {
    "duplicate_meta_description": (
        "Different service or trust pages share the same extracted summary, which may obscure their distinct purpose for prospective customers.",
        "Inspect all description tags, remove conflicting defaults where appropriate, and recrawl the listed URLs. Each intended service/page summary should accurately describe that page; a search engine's chosen snippet remains separate.",
    ),
    "javascript_content": (
        "Visitors and non-rendering consumers may receive different service information.",
        "Fetch this URL without JavaScript and with the browser. Confirm the core offer, heading and contact route are available in both if server rendering is implemented.",
    ),
    "missing_title": (
        "The page topic is not identified by a document title in this capture.",
        "Recrawl this URL and confirm one nonempty document title matching the page's offer; SVG titles do not count.",
    ),
    "multiple_titles": (
        "Competing document titles make the intended page label ambiguous.",
        "Inspect the document head and recrawl; retain one intended HTML title, excluding SVG labels.",
    ),
    "missing_h1": (
        "Customers need a clear visible heading explaining this page's purpose.",
        "Inspect the visible page and recrawl; the intended primary heading must match its customer question.",
    ),
    "missing_description": (
        "A page-specific summary can explain the offer to people considering a visit.",
        "Recrawl and verify a unique, accurate meta description; search engines may choose a different snippet.",
    ),
    "jsonld_syntax_error": (
        "Malformed JSON-LD cannot reliably express the page's entities.",
        "Parse every JSON-LD block on this URL without errors, then validate the chosen type against visible content.",
    ),
    "multiple_canonicals": (
        "Several canonical tags can send mixed signals about which address is the main version of this page.",
        "Inspect the rendered head and recrawl; this page should declare one canonical that names its intended public URL.",
    ),
    "multiple_meta_descriptions": (
        "Several descriptions leave the page's intended summary unclear, and a shared default can hide what makes it different.",
        "Inspect the rendered head and recrawl; this page should have one accurate description of its own.",
    ),
    "image_dimensions_review": (
        "Images without declared space can make the page shift while it loads, which is frustrating for visitors. This observation does not measure layout shift.",
        "Add width and height or reserved CSS space, recrawl, then measure layout shift with Lighthouse or field data.",
    ),
    "sitemap_url_conflict": (
        "A sitemap should list the addresses you want found; a conflict suggests the sitemap and the page disagree.",
        "Compare the sitemap entry with the captured response and recrawl; keep only intended canonical pages in the sitemap.",
    ),
    "multiple_h1_review": (
        "Several main headings can make the page's main topic less clear to readers. This alone does not establish an SEO defect.",
        "Review the visible page and recrawl; the heading structure should make the page's main topic clear.",
    ),
    "canonical_elsewhere": (
        "A canonical signals consolidation, which should agree with the intended public URL.",
        "Fetch the declared canonical and this URL; check redirects, status and consistent self-canonical declarations on the preferred page.",
    ),
    "canonical_target_redirects": (
        "Canonical signals point through a redirect instead of directly to the preferred page.",
        "Recrawl source and canonical destination; the declared canonical should return 200 directly when consolidation is intended.",
    ),
    "capture_incomplete": (
        "Missing answers or markup cannot be assessed from an incomplete capture.",
        "Resolve the recorded access/render limitation; repeat this URL and check browser readiness before making absence claims.",
    ),
    "fetch_failed": (
        "This run could not inspect the page; its content and visibility remain unknown.",
        "Repeat this exact URL after addressing the recorded failure and confirm a usable response in access.json.",
    ),
    "render_failed": (
        "JavaScript content was not verified in this run.",
        "Run doctor, address its exact browser error and recapture this page; retain any usable initial HTML evidence.",
    ),
}
ABSENCE = {
    "missing_title",
    "missing_description",
    "missing_h1",
    "canonical_not_declared",
    "missing_image_alt",
    "missing_content_candidate",
    "content_gap",
    "schema_missing",
}


def material_findings(issues, pages, profile=None, summary=None):
    index = evidence_index(pages)
    result = []
    context = None
    if profile and profile.get("status") == "reviewed":
        context = ", ".join(c["value"] for c in profile["fields"].get("core_services", [])[:3])
    for issue in issues:
        page = index.get(issue["url"], {})
        quality = capture_quality(page)
        if issue["code"] in ABSENCE and not quality["absence_supported"]:
            continue
        impact, acceptance = CHECKS.get(
            issue["code"],
            (
                "Review this recorded signal in the context of the page's intended customer journey.",
                "Apply the stated action on the affected URL, recrawl it, and compare this exact evidence and issue code with the prior capture.",
            ),
        )
        classification = {
            "observed": "verified_fact",
            "heuristic": "hypothesis",
            "review": "inference",
        }.get(issue.get("confidence"), "inference")
        limits = list(quality["limits"])
        limits.append(
            "Observation applies to captured representations; rankings, indexing and AI citations were not measured."
        )
        if summary and summary.get("coverage_limited"):
            limits.append("The crawl did not establish complete website coverage.")
        if not context:
            limits.append(
                "Business profile not yet reviewed; business-specific impact needs interpretation."
            )
        result.append(
            {
                **issue,
                "affected_urls": [issue["url"]],
                "observation": issue["evidence"],
                "captured_at": quality["captured_at"],
                "claim_type": classification,
                "why_it_matters": impact,
                "business_relevance": f"Relevant to customers evaluating {context}."
                if context
                else None,
                "recommended_action": issue["action"],
                "priority": {"high": "P1", "medium": "P2", "low": "P3", "info": "review"}.get(
                    issue["severity"], "review"
                ),
                "priority_rationale": "Based on observed access/content impact; review business importance before scheduling. Informational signals are not automatically defects.",
                "acceptance_check": acceptance,
                "uncertainty": limits,
                "evidence_refs": [
                    {
                        "url": issue["url"],
                        "captured_at": quality["captured_at"],
                        "representation": issue.get("representation") or quality["representation"],
                        "body_sha256": page.get("body_sha256"),
                        "html_path": page.get("html_path"),
                        "rendered_html_path": (page.get("rendered") or {}).get("html_path"),
                    }
                ],
            }
        )
    return result


def audit_report(crawl, out, profile=None, discovery=None, reviewed_findings=()):
    pages, summary = read_pages(crawl), read_json(Path(crawl) / "summary.json")
    if profile and host(profile.get("target", "")) != host(summary["seed"]):
        raise ValueError("Business profile belongs to a different audit target.")
    issues = read_json(Path(crawl) / "issues.json")
    rows = material_findings(issues, pages, profile, summary)
    index = evidence_index(pages)
    for item in reviewed_findings:
        required = (
            "affected_urls",
            "observation",
            "claim_type",
            "why_it_matters",
            "recommended_action",
            "priority",
            "priority_rationale",
            "acceptance_check",
            "uncertainty",
            "evidence_refs",
        )
        if any(key not in item for key in required):
            raise ValueError("Reviewed finding is missing a required evidence/acceptance field.")
        if item["claim_type"] not in ("verified_fact", "inference", "hypothesis"):
            raise ValueError("Unsupported finding claim type.")
        if not item["evidence_refs"] or not item["affected_urls"]:
            raise ValueError("Material findings need affected URLs and evidence references.")
        for url in item["affected_urls"]:
            if url not in index:
                raise ValueError("Affected URL was not inspected: " + url)
        refs = [
            verify_reference(ref, index, require_complete=item.get("absence_claim", False))
            for ref in item["evidence_refs"]
        ]
        if item.get("absence_claim"):
            if any(
                not capture_quality(index[url])["absence_supported"]
                for url in item["affected_urls"]
            ):
                raise ValueError("Absence finding includes an incomplete affected page.")
        rows.append(
            {
                **item,
                "evidence_refs": refs,
                "captured_at": sorted({ref["captured_at"] for ref in refs if ref["captured_at"]}),
            }
        )
    result = {
        "target": summary["seed"],
        "created_at": utcnow(),
        "findings": rows,
        "discovery_status": discovery.get("status") if discovery else "not_run",
        "discovery_coverage": discovery
        or {"note": "Discovery unavailable or not run; website evidence remains usable."},
        "crawl_coverage": summary,
        "business_profile": profile,
        "unmeasured": summary.get("unmeasured", [])
        + ["AI citations", "competitor authority advantage"],
        "note": "No traffic, authority, keyword volume, complete backlink total or ranking is inferred from these captures.",
        "scope_warning": scope_warning(profile, discovery),
    }
    Path(out).mkdir(parents=True, exist_ok=True)
    write_json(Path(out) / "audit.json", result)
    lines = [
        "# Website audit",
        "",
        result["note"],
        "",
        f"Search discovery: {result['discovery_status']}",
        "",
    ]
    if result["scope_warning"]:
        lines += ["**Not a complete audit yet.** " + result["scope_warning"], ""]
    groups = group_findings(rows)
    if groups:
        lines += ["## Start here", ""]
        lines += [
            f"{number}. **{group['title']}** ({page_count(group)}, "
            f"{group['priority']}): {group['recommended_action']}"
            for number, group in enumerate(next_actions(groups), 1)
        ]
        lines.append("")
    for row in groups:
        lines += [
            f"## {row['title']} — {row['priority']}",
            "",
            "URLs: " + ", ".join(row["affected_urls"]),
            "",
            group_observation(row),
            "",
            f"Evidence date: {row['captured_at']}; {row['claim_type']}.",
            "",
            row["why_it_matters"],
            "",
            "Action: " + row["recommended_action"],
            "",
            "Verify: " + row["acceptance_check"],
            "",
            "Limits: " + str(row["uncertainty"]),
            "",
        ]
        if len(row["occurrences"]) > 1:
            lines += ["All observations:", ""]
            lines += [
                f"- {', '.join(item['urls'])}: {readable_observation(item['observation'])}"
                for item in row["occurrences"]
            ]
            lines.append("")
    (Path(out) / "audit.md").write_text("\n".join(lines), encoding="utf-8")
    return result


CLAIM_WORDS = re.compile(r"(#\s?1\b|\bNo\.?\s?1\b|\bnumber one\b|\bleading\b|\bbest\b)", re.I)
ATTRIBUTION = re.compile(
    r"\b(describes?|calls?|claims?|states?|says?|presents?|markets?|self-|according|site's|its own)\b",
    re.I,
)


def _optional_json(path):
    try:
        return read_json(path)
    except (OSError, ValueError):
        return None


def _report_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _report_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _report_strings(item)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield str(value)


def _check_report(report, competitors, client_links):
    """Check the written report against the evidence; this cannot judge whether it is correct."""
    problems, warnings = [], []
    try:
        validate_report(report)
    except ValueError as error:
        problems.append("Report format: " + str(error))
    strings = list(_report_strings(report))
    body = "\n".join(strings)
    for row in (competitors or {}).get("direct_competitors", []):
        name = host(row.get("website", ""))
        if name and name not in body:
            problems.append(f"Direct competitor {name} is not named in the report.")
    if client_links:
        checked = client_links.get("sources_checked")
        number = rf"(?<![\d.]){checked}(?![\d.])"
        stated = rf"{number}[^.\n]{{0,40}}\bsources?\b|\bsources?\b[^.\n]{{0,40}}{number}"
        if checked is not None and not re.search(stated, body, re.I):
            problems.append(
                f"The evidence shows {checked} client sources checked, but the report does not state that."
            )
    if not all(re.search(rf"\b{day}\b", body) for day in (30, 60, 90)):
        problems.append("The report has no 30/60/90-day plan.")
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])|\n", body):
        words = re.sub(r"\S*/\S*", "", sentence)
        if CLAIM_WORDS.search(words) and not ATTRIBUTION.search(words):
            warnings.append(sentence.strip()[:160])
    return problems, warnings[:12]


def audit_check(run, report_path=None):
    """Compare a complete-audit folder with the stages the skill requires. Runs nothing else."""
    run = Path(run)
    notes = _optional_json(run / "stage-notes.json") or {}
    stages = {}

    def stage(name, status, detail):
        if status == "missing" and notes.get(name):
            status, detail = "failed_explained", str(notes[name])
        stages[name] = {"status": status, "detail": detail}

    coverage = _optional_json(run / "site/coverage.json")
    inspected = (coverage or {}).get("inspected", 0)
    partial = (coverage or {}).get("partial_captures", 0)
    stage(
        "crawl",
        "missing" if not inspected else "partial" if partial else "done",
        (
            f"{inspected} pages inspected, {partial} only partly captured."
            if coverage
            else "site/coverage.json not found."
        ),
    )
    profile_data = _optional_json(run / "business-reviewed/profile.json")
    reviewed = (profile_data or {}).get("status") == "reviewed"
    stage(
        "business_profile",
        "done" if reviewed else "missing",
        "Reviewed." if reviewed else "No reviewed business-reviewed/profile.json.",
    )
    entity = _optional_json(run / "entity/entity-review.json")
    stage(
        "entity_review",
        "done" if entity is not None else "missing",
        "Saved." if entity is not None else "entity/entity-review.json not found.",
    )
    discovery = _optional_json(run / "discovery/discovery.json")
    searched = bool(discovery) and (
        discovery.get("status") == "leads_available" or discovery.get("search_available")
    )
    stage(
        "search_discovery",
        "done" if searched else "missing",
        f"Status {discovery.get('status')}."
        if discovery
        else "discovery/discovery.json not found.",
    )
    competitors = _optional_json(run / "competitors/competitors.json")
    if competitors is None:
        stage("competitors", "missing", "competitors/competitors.json not found.")
    else:
        evaluated = competitors.get("candidate_profiles_evaluated", 0)
        direct = len(competitors.get("direct_competitors", []))
        thin = evaluated < COMPETITOR_POOL_TARGET and direct < DIRECT_COMPETITOR_TARGET
        stage(
            "competitors",
            "partial" if thin else "done",
            f"{evaluated} candidates reviewed, {direct} direct. "
            f"Target: about {COMPETITOR_POOL_TARGET} reviewed, aiming for {DIRECT_COMPETITOR_TARGET} direct."
            + (" Inspect more, or state why this is the limit." if thin else ""),
        )
    plan = _optional_json(run / "research-plan/research-plan.json")
    stage(
        "research_plan",
        "done" if plan else "missing",
        "Saved." if plan else "research-plan/research-plan.json not found.",
    )
    client_links = None
    for name in ("backlinks-reviewed.json", "backlinks.json"):
        client_links = client_links or _optional_json(run / "reputation/site-0/links" / name)
    checked = (client_links or {}).get("sources_checked", 0)
    stage(
        "client_backlinks",
        "missing" if not checked else "partial" if checked < MIN_CHECKED_SOURCES else "done",
        f"{checked} sources checked."
        + (
            " This is a small sample; state that limit."
            if 0 < checked < MIN_CHECKED_SOURCES
            else ""
        )
        if client_links
        else "reputation/site-0/links/backlinks.json not found.",
    )
    comparison = _optional_json(run / "comparison/reputation-comparison.json")
    cohort = len((plan or {}).get("cohort", []))
    compared = len((comparison or {}).get("sites", []))
    limited = comparison and (
        comparison.get("status") != "ranked_within_sample" or compared < cohort
    )
    stage(
        "reputation_comparison",
        "missing" if not comparison else "partial" if limited else "done",
        f"Status {comparison.get('status')}; {compared} of {cohort} planned sites compared."
        if comparison
        else "comparison/reputation-comparison.json not found.",
    )
    audit = _optional_json(run / "audit/audit.json")
    warning = (audit or {}).get("scope_warning")
    stage(
        "audit_export",
        "done" if audit and not warning else "missing",
        warning or ("Saved." if audit else "audit/audit.json not found."),
    )
    report_file = Path(report_path) if report_path else run / "report.json"
    report = _optional_json(report_file)
    problems, warnings = [], []
    if report is None:
        stage("report", "missing", f"{report_file.name} not found or not valid JSON.")
    else:
        problems, warnings = _check_report(report, competitors, client_links)
        stages["report"] = {
            "status": "failed" if problems else "done",
            "detail": " ".join(problems) or "Matches the checked evidence.",
        }
    statuses = {item["status"] for item in stages.values()}
    if statuses & {"missing", "failed"}:
        overall = "incomplete"
    elif statuses == {"done"}:
        overall = "complete"
    else:
        overall = "complete_with_limits"
    result = {
        "status": overall,
        "stages": stages,
        "unattributed_claims_to_review": warnings,
        "limits": "This checks that evidence exists and that key counts and names reach the report. "
        "It does not judge whether the analysis is correct.",
    }
    write_json(run / "audit-check.json", result)
    return result
