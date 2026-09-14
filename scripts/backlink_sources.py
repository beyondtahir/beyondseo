#!/usr/bin/env python3
"""Browse posting sites or draft a website-specific backlink prospect plan; no API calls."""

import argparse
import csv
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "playbooks/backlink-system/posting-sites.json"


def load_sources(platform="", category="", kind="", status="", path=CATALOG):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        r
        for r in rows
        if (not platform or platform.casefold() in (r["name"].casefold(), r["id"].casefold()))
        and (not category or any(category.casefold() in t.casefold() for t in r["topics"]))
        and (not kind or kind == r["kind"])
        and (not status or status == r["review_status"])
    ]


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError("Profile must be a JSON object")
    for name in ("website", "business", "audience"):
        if not isinstance(profile.get(name), str) or not profile[name].strip():
            raise ValueError(f"Profile requires {name}")
    validate_url(profile["website"])
    tags = profile.get("topics")
    if (
        not isinstance(tags, list)
        or not tags
        or any(not isinstance(t, str) or not t.strip() for t in tags)
    ):
        raise ValueError("Profile requires nonempty topics, such as technology, business or travel")
    for field in ("markets", "assets"):
        if not isinstance(profile.get(field, []), list) or any(
            not isinstance(t, str) for t in profile.get(field, [])
        ):
            raise ValueError(f"{field} must be a list of strings")
    pages = profile.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Profile requires pages with actual target URLs and specific topics")
    for p in pages:
        if not isinstance(p, dict) or not isinstance(p.get("topic"), str) or not p["topic"].strip():
            raise ValueError("Every target page requires a specific topic")
        validate_url(p.get("url", ""))
        if p.get("status", "provided") not in ("existing", "planned", "provided"):
            raise ValueError("Page status must be existing, planned or provided")
    capacity = profile.get("posts_per_week", 2)
    if type(capacity) is not int or not 1 <= capacity <= 7:
        raise ValueError("posts_per_week must be an integer from 1 to 7 reflecting actual capacity")
    if profile.get("start_date"):
        date.fromisoformat(profile["start_date"])


def validate_url(value):
    if not isinstance(value, str):
        raise ValueError("Target URL must be a string")
    p = urlsplit(value)
    if (
        p.scheme not in ("http", "https")
        or not p.hostname
        or p.username is not None
        or p.password is not None
    ):
        raise ValueError("Use an HTTP(S) target URL without credentials")
    if any(c.isspace() for c in value) or p.port == 0:
        raise ValueError("Use a valid URL without whitespace or an invalid port")


def writing_outline(site, topic, audience):
    """Give the actual format its own brief instead of assigning an article everywhere."""
    kind = site["kind"]
    common = "Use verified facts and original evidence; never invent results or customer stories."
    if kind == "answer":
        return [
            f"Find an existing, relevant question about {topic} and answer it directly.",
            f"Explain the key decision for {audience}, with a concrete example.",
            common,
            "Disclose your affiliation. Include a link only when it supports the answer and the rules permit it.",
        ]
    if kind in ("community", "professional_community", "community_submission"):
        return [
            f"Choose a specific community or discussion where {topic} is relevant; check its rules first.",
            "Write a short, useful description of the actual lesson or working demonstration.",
            common,
            "Disclose involvement, ask one useful question and respond to discussion. Do not copy an article into unrelated threads.",
        ]
    if kind == "curation":
        return [
            f"Create a focused reading collection about {topic} for {audience}.",
            "Select useful independent reading as well as your original resource.",
            "Add a short note explaining what each item helps the reader do; link to original publishers.",
            "Keep the collection selective and updated; do not turn it into repeated self-promotion.",
        ]
    if kind in ("code_resource", "owned_resource"):
        return [
            f"Publish the useful {topic} resource itself before promoting it.",
            "Explain its purpose, prerequisites, steps to use it and a reproducible example.",
            common,
            "Include limitations, maintenance information and relevant project documentation links.",
        ]
    if kind == "social_article":
        return [
            f"Explain one part of {topic} using an original diagram, screenshot or visual example.",
            f"Write a short caption and accessible explanation for {audience}.",
            common,
            "Credit sources and offer a relevant supporting resource where permitted.",
        ]
    return [
        f"Answer the main question about {topic} directly.",
        f"Explain the decision criteria that matter to {audience}.",
        common,
        "Explain limitations and when another option is better.",
        "Offer the relevant supporting resource only where the platform permits it.",
    ]


def publication_role(site):
    if site["kind"] == "editorial_article":
        return "Editorial submission; acceptance and the extent of independent review remain unconfirmed."
    if site["kind"] in (
        "article_directory",
        "community",
        "answer",
        "professional_community",
        "community_submission",
    ):
        return "A moderated contribution; moderation alone is not independent endorsement."
    return "An author-controlled publication, resource or collection; it does not establish independent endorsement."


def build_plan(profile, sites, limit=15, as_of=None):
    validate_profile(profile)
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Choose 1 to 20 sources; 15 is the usual first shortlist")
    today = as_of or date.today()
    start = date.fromisoformat(profile.get("start_date", today.isoformat()))
    topics = {t.casefold() for t in profile["topics"]}
    assets = {a.casefold() for a in profile.get("assets", [])}
    markets = {m.casefold() for m in profile.get("markets", [])}
    eligible, excluded, seen = [], [], set()
    for site in sites:
        reason = None
        if site["id"] in seen:
            continue
        seen.add(site["id"])
        if site["review_status"] != "guidance_reviewed":
            reason = site["review_status"]
        elif (
            not site.get("posting_url")
            or not site.get("review_sources")
            or not site.get("how_to_post")
        ):
            reason = "posting_route_not_documented"
        elif site["cost_status"] not in ("free_basic", "conditional_free", "free_recheck"):
            reason = "free_terms_not_established"
        elif (
            not site.get("reviewed_at")
            or not 0 <= (today - date.fromisoformat(site["reviewed_at"])).days <= 90
        ):
            reason = "guidance_needs_refresh"
        elif not ({t.casefold() for t in site["topics"]} & (topics | {"general"})):
            reason = "topic_mismatch"
        elif site["regions"] and not ({r.casefold() for r in site["regions"]} & markets):
            reason = "market_eligibility_unconfirmed"
        elif not {r.casefold() for r in site["requirements"]}.issubset(assets):
            reason = "required_asset_or_eligibility_missing"
        if reason:
            excluded.append({"site": site["id"], "reason": reason})
        else:
            eligible.append(site)
    priority = {"start": 0, "supporting": 1, "alternative": 2}
    eligible.sort(
        key=lambda s: (
            priority.get(s["readiness"], 3),
            -len({t.casefold() for t in s["topics"]} & topics),
            s["name"].casefold(),
        )
    )
    capacity = profile.get("posts_per_week", 2)
    tasks = []
    for i, site in enumerate(eligible[:limit]):
        page = profile["pages"][i % len(profile["pages"])]
        topic = page["topic"]
        due = start + timedelta(days=7 + (i // capacity) * 7 + (i % capacity) * (7 // capacity))
        angle = site["article_angle"].format(
            topic=topic,
            Topic=topic[:1].upper() + topic[1:],
            audience=profile["audience"],
            business=profile["business"],
        )
        tasks.append(
            {
                "position": i + 1,
                "site_id": site["id"],
                "website": site["name"],
                "posting_url": site["posting_url"],
                "format": site["kind"],
                "priority": site["readiness"],
                "why_this_site": f"{site['fit_note']} Planned for {profile['business']} and {profile['audience']}, using the supplied topic: {topic}.",
                "suggested_title_or_action": angle,
                "target_page": page["url"],
                "target_page_status": page.get("status", "provided"),
                "outline": writing_outline(site, topic, profile["audience"]),
                "anchor_guidance": f"Use a descriptive resource title or {profile['business']} where natural; follow this site's link-location rules.",
                "how_to_post": site["how_to_post"],
                "link_guidance": site["link_guidance"],
                "eligibility": site["eligibility"],
                "cost_status": site["cost_status"],
                "sheet_dr_values_unverified": site["sheet_dr_values"],
                "sheet_dr_conflict": site["sheet_dr_conflict"],
                "current_da": site["current_da"],
                "current_dr": site["current_dr"],
                "publication_role": publication_role(site),
                "authority_assessment": "Potential discovery and referral value depend on the actual audience, content and placement. No authority gain has been measured.",
                "guidance_checked_on": site["reviewed_at"],
                "guidance_sources": site["review_sources"],
                "suggested_week": 2 + i // capacity,
                "suggested_date": due.isoformat(),
                "timing_basis": "Capacity-based planning slot, not a ranking formula or automatic posting schedule.",
                "status": "proposed; account, exact placement and final free terms need checking",
                "before_posting": [
                    "Check the target page is public, useful and complete.",
                    "Confirm topic fit, current free terms, exact route and any account eligibility.",
                    "Review original facts, platform AI rules, authorship and the final draft.",
                    "Obtain task-specific publishing authorization if it is not already provided.",
                ],
                "after_posting": [
                    "Save the public post URL and publication date.",
                    "Use the native verifier to inspect the actual target link and rel attributes.",
                    "Check logged-out access, robots/noindex and canonical observations; record search indexing separately.",
                    "Review retention, referral traffic and useful responses after 14 and 30 days.",
                ],
            }
        )
    return {
        "business": profile["business"],
        "website": profile["website"],
        "profile_basis": profile.get(
            "evidence_basis", "User-supplied profile; no website crawl performed by this command."
        ),
        "created_on": today.isoformat(),
        "requested_sources": limit,
        "selected_sources": len(tasks),
        "shortfall": max(0, limit - len(tasks)),
        "catalog_sites_considered": len(seen),
        "excluded_summary": dict(Counter(x["reason"] for x in excluded)),
        "excluded": excluded,
        "tasks": tasks,
        "interpretation": "A shortlist of candidate publishing opportunities, not acquired backlinks. Guidance review does not verify account access, acceptance, a free commercial placement, dofollow, indexing or authority transfer. Research additional relevant sources when the shortlist is short; never pad it with ineligible entries.",
        "preparation_week": "Week 1: inspect the actual website, choose useful destination pages, confirm account eligibility and prepare the first two strong drafts. Choose among alternative owned blogs rather than creating all of them.",
    }


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def plan_markdown(plan):
    lines = [
        f"# Posting plan for {cell(plan['business'])}",
        "",
        plan["profile_basis"],
        "",
        f"**{plan['selected_sources']} proposed sources; {plan['requested_sources']} requested.**",
        plan["interpretation"],
        "",
        plan["preparation_week"],
        "",
        "DA is not available in this catalog. The PDF labels its numbers DR; their provider and measurement date are unknown. They are retained for provenance and never used to rank the shortlist.",
        "",
    ]
    if plan["shortfall"]:
        lines += [
            f"**Research gap: {plan['shortfall']} more suitable sources are needed.** Broaden primary-source research before presenting a complete list.",
            "",
        ]
    lines += [
        "| # | Website / route | Format | Proposed topic or action | Target page | Week | Cost status |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in plan["tasks"]:
        lines.append(
            f"| {t['position']} | [{cell(t['website'])}]({t['posting_url']}) | {t['format']} | {cell(t['suggested_title_or_action'])} | {t['target_page']} | {t['suggested_week']} | {t['cost_status']} |"
        )
    for t in plan["tasks"]:
        lines += [
            "",
            f"## {t['position']}. {cell(t['website'])}",
            "",
            t["why_this_site"],
            "",
            f"**Proposed title/action:** {cell(t['suggested_title_or_action'])}",
            f"**Target:** {t['target_page']} ({t['target_page_status']})",
            f"**Planning slot:** {t['suggested_date']} — {t['timing_basis']}",
            f"**Priority:** {t['priority']}. **Status:** {t['status']}",
            "",
            "What to write:",
            "",
        ]
        lines += [f"- {x}" for x in t["outline"]]
        lines += ["", "How to post:", ""] + [f"{i}. {x}" for i, x in enumerate(t["how_to_post"], 1)]
        lines += [
            "",
            f"**Links:** {t['link_guidance']}",
            f"**Eligibility:** {t['eligibility']}",
            f"**Publication role:** {t['publication_role']}",
            f"**Authority:** {t['authority_assessment']} Current DA/DR: not measured. Sheet DR: {t['sheet_dr_values_unverified']} (unverified{' and conflicting' if t['sheet_dr_conflict'] else ''}).",
            "",
            "Before posting:",
            "",
        ] + [f"- {x}" for x in t["before_posting"]]
        lines += ["", "After posting:", ""] + [f"- {x}" for x in t["after_posting"]]
        lines += [
            "",
            f"Guidance checked {t['guidance_checked_on']}: "
            + " · ".join(f"[Source {i}]({u})" for i, u in enumerate(t["guidance_sources"], 1)),
        ]
    return "\n".join(lines) + "\n"


def catalog_markdown(rows):
    lines = [
        "# Free article and posting-site catalog",
        "",
        f"{len(rows)} matching website/community entries. Original PDF rows are preserved separately; duplicate account and post URLs count once per site entry.",
        "",
        "Sheet DR values are unverified, sometimes conflicting, and are not DA. Guidance review checks documented routes, not successful account access or acquired links. Unreviewed entries require research.",
        "",
        "The source PDF contains 241 visible rows and 237 distinct URL strings. See the [raw rows](../playbooks/backlink-system/backlink-source-database.csv), [provenance](source-catalog-provenance.json) and [posting guide](backlink-posting-guide.md) for selection, writing, posting and verification steps.",
        "",
        "| Website | Type | Topics | Review | Free terms | Sheet DR (unverified) | Posting route |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        route = f"[Open]({r['posting_url']})" if r["posting_url"] else "Research first"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"[{cell(r['name'])}]({r['website_url']})",
                    r["kind"],
                    cell(", ".join(r["topics"])) or "Unclassified",
                    r["review_status"],
                    r["cost_status"],
                    cell(", ".join(map(str, r["sheet_dr_values"])))
                    + (" (conflict)" if r["sheet_dr_conflict"] else ""),
                    route,
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", default="")
    parser.add_argument(
        "--category", default="", help="Topic tag, e.g. technology, business, travel"
    )
    parser.add_argument(
        "--kind", default="", help="Article, community and other formats stay separate"
    )
    parser.add_argument("--status", default="", help="For example guidance_reviewed or unreviewed")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument(
        "--profile", type=Path, help="Website/business profile for a tailored shortlist"
    )
    parser.add_argument(
        "--limit", type=int, help="Requested shortlist size; default 15, maximum 20"
    )
    parser.add_argument("--out", type=Path, help="Save a plan outside the skill directory")
    args = parser.parse_args()
    try:
        rows = load_sources(args.platform, args.category, args.kind, args.status)
        if args.profile:
            plan = build_plan(
                json.loads(args.profile.read_text(encoding="utf-8")),
                rows,
                15 if args.limit is None else args.limit,
            )
            rendered = plan_markdown(plan)
            if args.out:
                args.out.mkdir(parents=True, exist_ok=True)
                (args.out / "posting-plan.json").write_text(
                    json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                (args.out / "posting-plan.md").write_text(rendered, encoding="utf-8")
                fields = [
                    "position",
                    "website",
                    "posting_url",
                    "format",
                    "why_this_site",
                    "suggested_title_or_action",
                    "outline",
                    "target_page",
                    "target_page_status",
                    "anchor_guidance",
                    "link_guidance",
                    "how_to_post",
                    "eligibility",
                    "publication_role",
                    "authority_assessment",
                    "current_da",
                    "current_dr",
                    "sheet_dr_values_unverified",
                    "sheet_dr_conflict",
                    "guidance_checked_on",
                    "guidance_sources",
                    "suggested_week",
                    "suggested_date",
                    "priority",
                    "cost_status",
                    "status",
                    "before_posting",
                    "after_posting",
                ]
                with (args.out / "posting-plan.csv").open(
                    "w", newline="", encoding="utf-8-sig"
                ) as f:
                    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    for task in plan["tasks"]:
                        row = {}
                        for key in fields:
                            value = task[key]
                            if isinstance(value, list):
                                value = "\n".join(str(item) for item in value)
                            if value is None:
                                value = "not measured"
                            if isinstance(value, str) and value.lstrip().startswith(
                                ("=", "+", "-", "@")
                            ):
                                value = "'" + value
                            row[key] = value
                        writer.writerow(row)
                print(
                    json.dumps(
                        {
                            "selected": plan["selected_sources"],
                            "requested": plan["requested_sources"],
                            "shortfall": plan["shortfall"],
                            "out": str(args.out),
                        }
                    )
                )
            else:
                print(
                    json.dumps(plan, ensure_ascii=False, indent=2)
                    if args.format == "json"
                    else rendered
                )
            return 0
        if args.out:
            parser.error("--out is used with --profile")
        if args.limit is not None:
            if args.limit < 1:
                raise ValueError("limit must be positive")
            rows = rows[: args.limit]
        rendered = (
            json.dumps(rows, ensure_ascii=False, indent=2)
            if args.format == "json"
            else catalog_markdown(rows)
        )
        print(rendered.rstrip())
        return 0 if rows else 1
    except (ValueError, OSError, TypeError, KeyError) as e:
        parser.error(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
