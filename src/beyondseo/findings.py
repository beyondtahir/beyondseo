"""Material audit findings with capture evidence, impact and acceptance checks."""

from pathlib import Path

from .engine import write_json
from .evidence import capture_quality
from .network import utcnow
from .research import evidence_index, host, verify_reference
from .review import read_json, read_pages

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
    for row in rows:
        lines += [
            f"## {row.get('code', 'Reviewed finding')} — {row['priority']}",
            "",
            "URLs: " + ", ".join(row["affected_urls"]),
            "",
            row["observation"],
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
    (Path(out) / "audit.md").write_text("\n".join(lines), encoding="utf-8")
    return result
