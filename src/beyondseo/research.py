"""Evidence packets, reviewed business profiles and transparent competitor selection.

Semantic judgments belong to the reviewing assistant/person, not keyword counts.
Every site claim must point to a native capture. Matching keys are reviewer-defined
categories shared across the brief; scores describe that judgment, not market rank.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from .engine import write_json
from .evidence import capture_quality, selected_data
from .network import normalize_url, utcnow
from .review import read_json, read_pages

FIELDS = (
    "business_category",
    "business_model",
    "core_services",
    "secondary_services",
    "customer_types",
    "industries",
    "offices",
    "markets",
    "website_languages",
    "search_languages",
    "positioning",
    "differentiators",
    "commercial_intent",
)
WEIGHTS = {
    "core_services": 40,
    "customer_types": 25,
    "markets": 15,
    "website_languages": 5,
    "business_model": 10,
    "evidence_quality": 5,
}
NON_AGENCIES = {"directory", "marketplace", "publisher", "training", "software_product"}


def host(url):
    return (urlsplit(url).hostname or "").removeprefix("www.")


def normalized_text(value):
    return re.sub(r"\s+", " ", value).strip()


def evidence_index(pages):
    result = {}
    for p in pages:
        for url in (p["url"], p.get("final_url")):
            if url:
                result[normalize_url(url)] = p
    return result


def verify_reference(reference, index, *, require_complete=False):
    url = normalize_url(reference.get("url", ""))
    page = index.get(url)
    if not page or not capture_quality(page)["usable"]:
        raise ValueError("Reference needs a successful native capture: " + str(url))
    quality = capture_quality(page)
    if require_complete and not quality["absence_supported"]:
        raise ValueError("Incomplete capture cannot support an absence claim: " + url)
    data, representation = selected_data(page)
    quote = normalized_text(reference.get("quote", ""))
    field = reference.get("field")
    if field:
        if field not in ("language", "title", "meta_description", "schema_types", "headings"):
            raise ValueError("Unsupported evidence field: " + field)
        if reference.get("value") != data.get(field):
            raise ValueError("Evidence field does not match capture: " + url)
    elif len(quote) < 12 or quote not in normalized_text(
        data.get("text", "") + " " + data.get("main_text", "")
    ):
        raise ValueError("Evidence quote must match native captured text: " + url)
    return {
        **reference,
        "url": url,
        "captured_at": quality["captured_at"],
        "representation": representation,
        "capture_limits": quality["limits"],
        "body_sha256": page.get("body_sha256"),
        "interpretation": "Observed website statement; independently proving the claim is separate.",
    }


def page_role(url):
    path = urlsplit(url).path.lower()
    if path in ("", "/"):
        return "homepage"
    for role, pattern in (
        ("about", "about|company|team"),
        ("contact", "contact|location|office"),
        ("case_or_portfolio", "case|portfolio|project|demo"),
        ("industry", "industr|sector"),
        ("service", "service|solution|automat|agent"),
        ("service_area", "area|countr|region"),
    ):
        if re.search(pattern, path):
            return role
    return "other"


def profile(crawl, out, brief=None, review=None):
    pages = read_pages(crawl)
    summary = read_json(Path(crawl) / "summary.json")
    target = summary["seed"]
    brief = brief or {}
    index = evidence_index(pages)
    packet, discovered = [], {}
    for p in pages:
        data, _ = selected_data(p)
        packet.append(
            {
                "url": p["url"],
                "final_url": p.get("final_url"),
                "role": page_role(p["url"]),
                "quality": capture_quality(p),
                "title": data.get("title"),
                "headings": data.get("headings"),
                "main_text": data.get("main_text"),
                "language": data.get("language"),
                "schema_types": data.get("schema_types"),
            }
        )
        for link in data.get("links", []):
            url = link["url"]
            if host(url) == host(target) and normalize_url(url) not in index:
                role = page_role(url)
                if role != "other":
                    discovered[url] = {"url": url, "role": role, "anchor": link.get("anchor", "")}
    result = {
        "schema_version": 1,
        "target": target,
        "created_at": utcnow(),
        "status": "needs_review",
        "brief": brief,
        "fields": {k: [] for k in FIELDS},
        "unknowns": list(FIELDS),
        "contradictions": [],
        "confidence": "low",
        "page_evidence": packet,
        "uninspected_relevant_pages": list(discovered.values()),
        "coverage": {
            "pages": len(pages),
            "limited": summary.get("coverage_limited", True),
            "roles_observed": sorted({p["role"] for p in packet}),
        },
        "review_guidance": "Read home, about, contact, main services and relevant cases/markets. Inspect uninspected relevant pages as needed. Keep office, market and language separate. Supply reviewed claims and source quotes; do not infer markets from language or TLD.",
    }
    if review:
        if not review.get("reviewed_by") or not review.get("reviewed_at"):
            raise ValueError("Profile review needs reviewed_by and reviewed_at.")
        if host(review.get("target", "")) != host(target):
            raise ValueError("Profile review target does not match crawl.")
        for field in FIELDS:
            for claim in review.get("fields", {}).get(field, []):
                if not claim.get("value") or not claim.get("key") or not claim.get("evidence"):
                    raise ValueError(
                        "Each profile claim needs value, matching key and evidence: " + field
                    )
                refs = []
                for ref in claim["evidence"]:
                    if host(ref.get("url", "")) != host(target):
                        raise ValueError("Business profile evidence must belong to this website.")
                    refs.append(verify_reference(ref, index))
                result["fields"][field].append(
                    {
                        **claim,
                        "evidence": refs,
                        "claim_type": "inference",
                        "confidence": claim.get("confidence", "medium"),
                    }
                )
        # Explicit user context is preserved alongside site evidence, never silently overwritten.
        result.update(
            status="reviewed",
            reviewed_by=review["reviewed_by"],
            reviewed_at=review["reviewed_at"],
            unknowns=review.get("unknowns", []) + [k for k in FIELDS if not result["fields"][k]],
            contradictions=review.get("contradictions", []),
            confidence=review.get("confidence", "medium"),
        )
        for field, claims in brief.get("fields", {}).items():
            if field in FIELDS and claims and result["fields"][field]:
                user_keys = {c["key"].casefold() for c in claims}
                site_keys = {c["key"].casefold() for c in result["fields"][field]}
                if user_keys.isdisjoint(site_keys):
                    result["contradictions"].append(
                        {
                            "field": field,
                            "user": claims,
                            "site": result["fields"][field],
                            "resolution": "Preserve the user brief; clarify the conflict before treating site positioning as the goal.",
                        }
                    )
        if not result["fields"]["business_model"] or not result["fields"]["core_services"]:
            result["status"] = "needs_review"
    result["queries"] = research_queries(result) if result["status"] == "reviewed" else []
    Path(out).mkdir(parents=True, exist_ok=True)
    write_json(Path(out) / "profile.json", result)
    write_json(Path(out) / "queries.json", result["queries"])
    return result


def values(profile, field, use_brief=False):
    source = profile.get("fields", {}).get(field, [])
    if use_brief:
        source = profile.get("brief", {}).get("fields", {}).get(field) or source
    return {c["key"].casefold() for c in source}


def research_queries(profile):
    fields = profile["fields"]
    brief = profile.get("brief", {}).get("fields", {})
    markets = brief.get("markets") or fields["markets"]
    languages = (
        brief.get("search_languages") or fields["search_languages"] or fields["website_languages"]
    )
    services = fields["core_services"][:4]
    customers = fields["customer_types"][:2]
    queries = []
    for service in services:
        for market in markets[:2] or [{"value": "", "key": "unknown"}]:
            for language in languages[:2] or [{"value": "", "key": "unknown"}]:
                audience = (
                    customers[len(queries) % len(customers)]["value"] if customers else "business"
                )
                intent = (
                    "agency"
                    if "implementation" in service["value"].lower()
                    else "implementation agency"
                )
                if "agency" not in values(profile, "business_model"):
                    intent = (
                        fields["business_model"][0]["value"]
                        if fields["business_model"]
                        else "provider"
                    )
                query = (
                    f"{service['value']} {intent} for {audience.lower()} {market['value']}".strip()
                )
                item = {
                    "query": query,
                    "market": market["value"] or None,
                    "language": language["value"] or None,
                    "basis": {"service": service["key"], "customer": audience},
                    "localization": "Requested context only; provider coverage must be reported separately.",
                }
                if item not in queries:
                    queries.append(item)
    return queries[:8]


def select_competitors(client, candidates, out, limit=5, discovery=None):
    if client.get("status") != "reviewed":
        raise ValueError(
            "Review the client's evidence-backed business profile before selecting competitors."
        )
    if not 1 <= limit <= 20:
        raise ValueError("Competitor limit must be 1–20.")
    selected, rejected, seen = [], [], set()
    for candidate in candidates:
        domain = host(candidate.get("target", ""))
        if domain in seen or domain == host(client["target"]):
            continue
        seen.add(domain)
        reasons = []
        fields = candidate.get("fields", {})
        if candidate.get("status") != "reviewed":
            reasons.append("Candidate profile has not been reviewed against native captures.")
        for conflict in candidate.get("contradictions", []):
            if isinstance(conflict, dict) and conflict.get("blocking"):
                reasons.append(
                    "Unresolved comparison conflict: " + str(conflict.get("observation", conflict))
                )
        model = values(candidate, "business_model")
        client_model = values(client, "business_model", True)
        shared = {
            field: sorted(values(client, field, True) & values(candidate, field))
            for field in WEIGHTS
            if field != "evidence_quality"
        }
        if model & NON_AGENCIES and not model & client_model:
            reasons.append("Different business model: " + ", ".join(sorted(model)))
        if not shared["core_services"]:
            reasons.append(
                "No evidence-backed core service overlap; shared keywords are insufficient."
            )
        if not shared["customer_types"]:
            reasons.append("No established overlap in customer types/commercial intent.")
        if not shared["business_model"]:
            reasons.append("Comparable business model not established.")
        if not fields.get("commercial_intent"):
            reasons.append("Service sales/commercial intent not established in captured pages.")
        if reasons:
            rejected.append(
                {
                    "website": candidate.get("target"),
                    "reasons": reasons,
                    "evidence_gaps": candidate.get("unknowns", []),
                }
            )
            continue
        # An international agency without verified target-market overlap is a benchmark.
        kind = "direct_business_competitor" if shared["markets"] else "aspirational_benchmark"
        scores = {}
        for field in shared:
            denominator = len(values(client, field, True))
            scores[field] = round(WEIGHTS[field] * len(shared[field]) / max(1, denominator), 1)
        refs = [
            ref
            for claims in fields.values()
            for claim in claims
            for ref in claim.get("evidence", [])
        ]
        complete = sum(
            not ref.get("capture_limits") and bool(ref.get("captured_at")) for ref in refs
        )
        scores["evidence_quality"] = round(
            WEIGHTS["evidence_quality"] * complete / max(1, len(refs)), 1
        )
        gaps = list(candidate.get("unknowns", []))
        gaps += ["Review conflict: " + str(c) for c in candidate.get("contradictions", [])]
        if not shared["markets"]:
            gaps.append("No verified overlap with the requested target market; benchmark only.")
        if not shared["website_languages"]:
            gaps.append("Website-language overlap not established; not a geographic exclusion.")
        difference = {
            field: sorted(values(candidate, field) - values(client, field, True))
            for field in shared
        }
        selected.append(
            {
                "website": urlsplit(candidate["target"]).scheme
                + "://"
                + urlsplit(candidate["target"]).netloc
                + "/",
                "discovery_entry_page": candidate["target"],
                "classification": kind,
                "relevance_score": round(sum(scores.values()), 1),
                "score_components": scores,
                "why_comparable": shared,
                "important_differences": difference,
                "services": fields.get("core_services", []),
                "markets": fields.get("markets", []),
                "supporting_pages": sorted({ref["url"] for ref in refs}),
                "evidence": refs,
                "confidence": "medium" if scores["evidence_quality"] == 5 else "low",
                "evidence_gaps": gaps,
                "reviewed_by": candidate.get("reviewed_by"),
            }
        )
    selected.sort(key=lambda c: (-c["relevance_score"], c["website"]))
    direct = [r for r in selected if r["classification"] == "direct_business_competitor"]
    benchmarks = [r for r in selected if r["classification"] == "aspirational_benchmark"]
    observations = []
    if discovery:
        for candidate in discovery.get("candidates", []):
            observations.append(
                {
                    "website": candidate["url"],
                    "classification": "search_result_lead",
                    "observations": candidate["provenance"],
                    "note": "Query-specific discovery lead; a direct competitor or ranking claim needs separate evidence.",
                }
            )
    result = {
        "client": client["target"],
        "created_at": utcnow(),
        "candidate_profiles_evaluated": len(seen),
        "direct_competitors": direct[:limit],
        "aspirational_benchmarks": benchmarks[:limit],
        "other_qualified": direct[limit:] + benchmarks[limit:],
        "rejected": rejected,
        "search_observations": observations,
        "weights": WEIGHTS,
        "method": "Reviewer-assigned service/customer/market keys are matched after business-model and commercial-intent gates. Points measure overlap with this brief; they are not an objective market, ranking or authority metric. Office location and English language do not define the served market.",
        "limitations": "Selection covers reviewed candidates only. No quota is filled with mismatches. Website claims are not independent endorsements; evidence gaps and localization remain visible.",
    }
    Path(out).mkdir(parents=True, exist_ok=True)
    write_json(Path(out) / "competitors.json", result)
    return result
