# The complete BeyondSEO house

BeyondSEO combines specialist SEO methods, a backlink/source library, reporting templates and its own collection engine. Its main job is to produce a practical plan for the whole website: what to fix, what to build, where to earn relevant recognition, and how to measure progress.

## How to use the skill

Load the repository's [SKILL.md](../SKILL.md) in a compatible skill-capable agent and supply the website and business goal. The complete workflow is [defined here](../playbooks/core/seo-house-workflow.md). For example:

> Audit my website for technical/on-page SEO, AEO, GEO, entity, authority, reputation, local SEO, backlinks and conversion. Use the included backlink catalog where relevant. Give me page-level recommendations, content briefs and an executable 90-day plan.

The workflow evaluates each applicable area and marks missing evidence. It uses the crawler for website observations and supplied search, analytics, profile or backlink exports for measurements those observations cannot establish.

A focused request, such as “review this service page's answers and entity proof,” can use the relevant specialists without producing a full-site report.

## What the complete plan contains

| Deliverable | Detail |
|---|---|
| Coverage and evidence | Which areas/pages were assessed, findings, confidence, exclusions and missing evidence |
| Technical and on-page actions | Affected URLs/templates, recommended changes, priorities and verification steps |
| Keyword and question map | Selected query/intent clusters, current or proposed target pages and next actions |
| Content and internal linking | Page briefs, original proof needed, answer sections and source-to-target links |
| AEO and GEO plan | Useful direct answers, source-worthy content and clearly labeled observed visibility |
| Entity, authority and REO | Identity/profile consistency, credible proof, topical gaps, reviews and relevant recognition |
| Local plan | Service-area/profile/citation recommendations where the business has local intent |
| Backlink/prospect table | Named websites and exact URLs, relevance, target page, proposed content/action and verification status |
| Execution roadmap | 30/60/90-day priorities, owner roles, dependencies, effort and acceptance checks |
| Measurement | Dated baseline where available, KPI definitions, review dates and unresolved data needs |

See the [complete plan template](../playbooks/templates/complete-seo-plan.md) and [roadmap method](../playbooks/strategy/seo-roadmap-generator.md).

## Your included backlink list

The catalog contains **206 website/community entries** from 241 visible PDF rows and 237 distinct URL strings. [Browse every entry](backlink-source-catalog.md). Public posting guidance has been reviewed for 22 destinations; the remaining pool needs qualification.

```sh
python3 scripts/backlink_sources.py --platform Medium
python3 scripts/backlink_sources.py --category technology --status guidance_reviewed
python3 scripts/backlink_sources.py --profile ../client-runs/business.json --limit 20 --out ../client-runs/posting-plan
```

Use [the example profile](../examples/posting-profile.json) and [practical posting guide](backlink-posting-guide.md). A backlink request should produce 15 or 20 relevant source recommendations when supported, explaining where, what, how and when to publish. Each has a title/action, outline, specific target page, route, free terms, eligibility, link restrictions and follow-up check. Different formats receive different briefs. The helper reports a shortfall if too few qualify; the assistant researches additional appropriate sources.

The helper reads supplied facts and documented routes. It does not crawl the business, create accounts, publish, measure current DA/DR or confirm acquired links. The skill completes website review, current-rule checks and the requested writing. Original sheet DR values remain unverified and do not rank the suggestions.

The library is one input to an authority plan. Relevant associations, partners, industry publications, local citations, original studies and independent recognition can provide evidence that an owned publication cannot.

## Terms used in this project

| Term | Meaning in BeyondSEO |
|---|---|
| SEO | Website discovery, relevance, quality and useful search visibility |
| AEO | Helping a page answer the audience's actual questions clearly and accurately |
| GEO | Source-worthiness for generative answers, with actual mentions/citations measured separately |
| Entity SEO | Clear, consistent organization/person identity and supported relationships |
| Authority / authority AEO | Topical depth, original proof and credible external recognition supporting the site's answers |
| REO / reputation | Reviews, case studies, public claims, trust assets and accurate third-party evidence |

The terminology organizes the practice. It does not imply that each label is an independently measurable search-engine score or that implementing a checklist guarantees ranking or inclusion.

## The crawler's place

The command-line engine supplies raw/rendered pages, structured observations and technical finding candidates. It can operate independently, but its crawl report is not the complete strategic deliverable. The skill combines that evidence with the specialist workflows and business context.

The executable source has behavioral tests. The SEO methods are reviewed playbooks, not automatically proven business outcomes. Ranking, traffic, lead and authority claims still need dated evidence. See the [measurement boundaries](../references/measurement-boundaries.md).
