# Complete SEO house workflow

Use this workflow for a general website audit, SEO strategy or growth plan. An unqualified request to audit a website includes backlink/reputation review, named competitor comparison and a practical execution plan. Follow [the audit delivery standard](../../references/audit-delivery.md); an explicitly focused request keeps its narrower scope. The crawler supplies observations for the complete skill's strategic work.

A complete audit accounts for every area below. Mark an area as assessed, partially assessed, not assessed or not applicable, with the reason and the next evidence needed. Missing account data should limit the relevant conclusions, not silently remove that area from the report.

## 1. Establish the business brief

Use the supplied website, market, services/products, audience, conversion goal, competitors, budget and capacity. Infer routine context from the website and label assumptions. Ask only for missing information that materially changes the plan; continue the website review meanwhile.

Create a page inventory separating commercial pages, supporting content, trust/proof pages, local pages and conversion paths. Identify the pages most connected to the business goal. Keep branded search, nonbranded search queries and business inquiries distinct.

## 2. Cover the whole practice

Paths below are relative to `playbooks/`. Use the matching section of [industry guidance](../industry-playbooks/README.md) and [reporting guidance](../reporting/README.md) when relevant.

| Area | Review | Required decision/output | Specialist references |
|---|---|---|---|
| Technical SEO | Discovery, statuses, redirects, robots, noindex, canonical declarations, sitemaps, JavaScript and available performance evidence | Prioritized fixes by affected URL/template and a verification method | `audit/technical-seo-audit.md`, `audit/crawlability-indexing.md`, `audit/page-speed-core-web-vitals.md` |
| On-page SEO | Titles, descriptions, headings, intent, page structure and relevance | Page-specific metadata/heading/content changes | `audit/on-page-seo-audit.md` |
| Architecture and internal links | Navigation, commercial/support relationships, observed depth and orphan candidates | Pages to add, consolidate or improve; source-to-target internal links with reasons | `audit/internal-linking-audit.md`, `strategy/content-hub-strategy.md` |
| Keywords and intent | Existing topics, supplied query evidence, customer questions and business value | Keyword/question-to-page map with an action for each selected cluster | `keyword-research/keyword-discovery.md`, `keyword-research/keyword-to-page-map.md` |
| Content and E-E-A-T | Completeness, original experience, expert proof, authorship, freshness and usefulness | Content briefs, proof to obtain and refresh/consolidation decisions | `audit/content-quality-audit.md`, `audit/eeat-ylym-audit.md` |
| Structured data | Existing declarations, syntax and visible-content fit | Relevant schema recommendations and separate validation steps | `audit/schema-audit.md` |
| AEO | Customer definitions, comparisons, costs, processes, risks and follow-up questions | Exact answer blocks mapped to relevant pages, supported by evidence | `aeo-geo/answer-engine-optimization.md`, `aeo-geo/conversation-seo-framework.md` |
| GEO | Source-worthiness, original information, cited proof and captured answer-engine observations | Citation-readiness improvements; dated visibility observations only when collected | `aeo-geo/generative-engine-optimization.md`, `aeo-geo/geo-ai-citation-optimization.md` |
| Entity SEO | Organization/person identity, consistent names, relationships, profiles and proof | Entity map, profile/page consistency fixes and supported sameAs/schema recommendations | `entity-seo/entity-seo-knowledge-graph.md` |
| Authority and authority for answers | Topical coverage, first-hand proof, relevant external recognition and credible references | Research/assets to build, expert contributions, topical clusters and outreach opportunities | `aeo-geo/topical-authority.md`, `aeo-geo/citations-and-source-worthiness.md`, `backlink-system/digital-pr-system.md` |
| REO / reputation | Reviews, case studies, media mentions, trust pages, claims and brand consistency | Proof improvements, review/mention work and factual response recommendations | `reputation-seo/reputation-proof-stack.md`, `reputation-seo/third-party-authority-article-system.md` |
| Local SEO | Real service areas, NAP, local pages, profile/review evidence and local competition | Local page/profile/citation actions, or a reason local SEO does not apply | `local-seo/google-business-profile.md`, `local-seo/nap-citation-audit.md` |
| Backlinks and digital PR | Supplied links, relevant prospects, the saved source catalog, partnerships and editorial fit | Named source URLs, target pages, proposed assets, outreach/posting actions and validation status | `backlink-system/free-paid-backlink-source-library.md`, `backlink-system/backlink-quality-scoring.md` |
| Competitors | Comparable page types, topics, proof, answers, links and observed search evidence | Specific gaps and defensible opportunities, with comparator URLs | `competitor-research/competitor-matrix.md`, `competitor-research/content-gap-analysis.md` |
| Conversion | Offers, calls to action, contact/booking journeys, forms and trust near decisions | Page-specific conversion improvements and a measurement plan | `audit/conversion-seo-audit.md` |
| Measurement | Supplied search/analytics/profile exports, event definitions and baseline availability | KPI definitions, dated baseline, review cadence and remaining data requests | `integrations/google-search-console.md`, `integrations/google-analytics.md`, `reporting/README.md#monthly-progress-report` |

REO here is the project's shorthand for reputation optimization. “Authority AEO” describes credible proof and external recognition that support answers. These are practice labels; do not invent a search-engine metric or proprietary ranking system from them.

Google's guidance for its search AI features builds on ordinary SEO fundamentals rather than requiring special AI markup. Separate content readiness from actual observed inclusion. See [Google's AI features guidance](https://developers.google.com/search/docs/appearance/ai-features).

## 3. Use the saved backlink website list

First establish current backlink and mention evidence through [native discovery and verification](../../references/reputation.md). Report the conservative headline, coverage and confidence; low-confidence scores remain below 50 and unsupported scores are withheld. Apply the same rules to clients and competitors. Keep existing links separate from future publishing opportunities.

Use the 206-entry catalog and [posting standard](../backlink-system/free-paid-backlink-source-library.md) for this business. The 241 original PDF rows are retained in `backlink-system/backlink-source-database.csv`; grouped destinations and reviewed guidance are in `backlink-system/posting-sites.json`. Distinct profile or article URLs on the same platform do not count as independent sites.

Provide 15 suitable sources, or 20 when requested and qualified; respect a different explicit count. The shortlist must give direct routes, business fit, content format, specific titles/actions and outlines, relevant target pages, allowed link placements, posting steps, eligibility, free terms, evidence dates and timing matched to capacity. Draft requested priority pieces using real facts. See [the practical guide](../../docs/backlink-posting-guide.md) for helper commands.

Refresh platform guidance and inspect the intended community or category before recommending execution. Exclude closed or ineligible routes. Research additional relevant primary sources when too few qualify; explain unresolved gaps instead of repeating unrelated websites. Do not transfer the same technology-platform list to a different industry.

Retain the PDF's DR values only as unverified source claims: no provider/date is supplied and some entries conflict. Do not relabel them DA or sort recommendations by them. Assess relevance, public accessibility, content standards, editorial independence and audience benefit using current evidence. A proposed placement is not a measured backlink, independent endorsement or promise of ranking value.

Use [additional reputation routes](../../docs/reputation-prospects.md) and suitable partner, industry and local opportunities where useful. Paid promotion needs a distinct referral/brand objective, current terms and appropriate link qualification. Preparing a plan does not authorize posting, outreach or purchases.

## 4. Turn findings into a page plan

Include a named [competitor comparison](../competitor-research/competitor-matrix.md) with exact pages, selection reasons, capture dates, relevant service/content/proof differences and actions for the client. Discover appropriate benchmarks when the user has not supplied them. Similar market positioning does not prove a ranking relationship. If access or discovery fails, retain the comparison section with the limitation and next evidence needed; do not invent a winner.

For each priority page, supply its current URL or proposed path, primary intent, query/question cluster, issue/opportunity, recommended title/H1 or content brief, answer coverage, evidence/proof needed, relevant schema, internal links, conversion step and success check. State which items are observed, inferred or proposed.

A plan may include existing-page fixes, new pages, consolidation, retirement or no change. Avoid choosing a fixed word count, arbitrary article quota or backlink quantity before evaluating intent, existing assets and capacity.

Keep authority and reputation work connected to real evidence: publish useful original information, obtain genuine permission for case studies, maintain accurate profiles and earn relevant recognition. Self-published support articles and independent editorial endorsements have different evidentiary weight.

## 5. Build the execution roadmap

Use `strategy/seo-roadmap-generator.md` and the 30/60/90-day playbooks. Sequence work by dependencies and business importance:

1. Restore access to important pages and reliable measurement where evidence shows a problem.
2. Improve high-value existing pages, intent coverage, conversion and internal links.
3. Build justified missing pages, answer coverage, proof and topical clusters.
4. Start relevant backlink, partner, local, editorial and reputation work.
5. Recheck changes and refine priorities using observed results.

Parallelize independent work conceptually in the schedule; do not make an unnecessary sitewide redesign a prerequisite for every improvement. State capacity and budget assumptions. Every action needs a URL or asset, reason, priority, owner, dependency, effort, timing and acceptance check.

## 6. Deliver a complete package

A complete website plan should contain:

- Business goal, scope, evidence and coverage matrix for the areas above.
- Executive priorities and a URL-based issue/action register.
- Keyword/question-to-page map, content briefs and internal-link plan.
- AEO/GEO, entity, authority and REO recommendations with distinct deliverables.
- Local actions when relevant.
- A named backlink/prospect table using suitable entries from the supplied catalog and separately verified prospects.
- Verified backlink/mention evidence and a conservative score when supported, alongside confidence and coverage.
- A named competitor matrix with source pages, observed gaps, client strengths and concrete responses.
- A sequenced 30/60/90-day roadmap with owners, dependencies and checks.
- KPI baseline/definitions, review cadence and unresolved evidence needs.

Use `templates/complete-seo-plan.md` for a consistent handoff. Do not finish a complete-SEO request with only the crawler's `report.md`. That report is input to the strategic work. A focused user request can use only the relevant sections.

## 7. Help implement and review

Use [the friendly advisor guide](friendly-advisor.md) to explain findings and provide real drafts. Follow [operations](../../docs/operations.md) to compare snapshots, run bounded reviews and apply authorized content changes with backups. Use [the reputation growth plan](../backlink-system/reputation-growth-plan.md) to choose relevant sources and distinguish controlled profiles from independent proof.
