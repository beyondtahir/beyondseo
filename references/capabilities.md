# BeyondSEO — functionality and skill map

This describes BeyondSEO’s crawler and the SEO workflows included in the project. The implementation status below distinguishes executable features from agent-guided workflows.

BeyondSEO is a complete SEO house supported by its own website crawler. The main workflow covers the full website strategy across SEO, AEO, GEO, entity, authority, REO/reputation, local visibility, backlinks and conversion, and produces a practical execution plan. The Python program collects observations; the skill applies specialist methods and business context. Start with [the complete SEO workflow](../playbooks/core/seo-house-workflow.md).

The saved backlink catalog includes all 27 original source records across six platforms and nine categories. Complete plans review this list and use relevant exact URLs in recommendations after appropriate checks. [Browse the catalog](../docs/backlink-source-catalog.md).

## Website crawler and scraper: implemented

| Function | What it does |
|---|---|
| Website discovery | Starts from a URL, reads robots/sitemaps, follows in-scope page links, and records discovered URLs |
| Sitemap processing | Handles XML URL sets, sitemap indexes, namespaces and gzip content, retaining URL membership and lastmod |
| Crawl controls | Page/depth/discovery/query limits, host allowlists, exclusion patterns, concurrency and request spacing |
| HTTP handling | Records status codes, redirects, loops, errors, response headers, timestamps, byte counts and hashes |
| Access diagnostics | Separates server denials, rate limits, recognizable challenge responses, robots decisions and local crawl limits |
| Retry evidence | Preserves individual HTTP attempts, including an initial 429 followed by a successful retry |
| Robots handling | Respects directives by default with a recorded explicit override for authorized crawling; treats an unavailable robots file separately from a public resource denial; defers on network/server failure and rate limits |
| HTML extraction | Titles, descriptions, meta/Open Graph fields, H1–H6, language, canonicals, hreflang, links, images, forms and JSON-LD |
| Content extraction | Body/main text, word counts, content hashes and custom CSS-selected fields; supports repeated listing cards |
| Custom scraping | Named fields such as product name, price, article title, author or selected link attributes using a JSON selector file |
| JavaScript comparison | Automatic fallback or explicit browser mode captures a second DOM representation and discovers rendered links |
| Content readiness and scrolling | Waits for a visible CSS element, samples text/link stability and performs bounded viewport scrolling |
| Readable documents | Markdown and plain-text files, plus structured documents with their source representation |
| Screenshots | Optional 1440 × 1000 browser viewport PNGs |
| Website dependencies | Public dependency loading or explicit asset/API host allowlists; supported public GET and CORS OPTIONS requests preserve needed origin-bound headers without logging their values |
| Rendering diagnostics | Records locally blocked resources, request failures, JavaScript errors and empty-content warnings |
| Internal link graph | Observed inbound/outbound links, anchors/rel attributes, checked target status and observed click depth |
| Technical findings | Uses successful rendered content for metadata/duplicate checks; preserves raw noindex; flags missing-content screens behind HTTP 200 and links pointing to them, alongside other technical candidates |
| Resume | SQLite persists processed pages and the pending queue; a resumed run can raise the page budget without refetching completed pages |
| Evidence/reporting | Raw HTML, sitemap XML, JSONL, CSV inventories, issue tables, access diagnostics and Markdown reports |
| Terminal feedback | Colorama styles interactive progress; machine-readable output remains plain |

The command-line interface is documented in `crawler.md`. The crawler does not submit forms or perform publishing actions. Resume continues the same snapshot; a fresh run is needed to refresh completed pages.

## Review and implementation: implemented

See [operations](../docs/operations.md) for readiness reports, source-page backlink checks, snapshot comparisons, bounded repeat audits and reviewed local/SFTP/FTPS content-file changes. Changes retain original bytes, verify reviewed hashes and refuse to overwrite later edits during rollback. Remote adapters need compatible hosting; database/CMS editing and arbitrary third-party account automation remain separate.

## Reputation discovery and rating: implemented

The [native reputation system](reputation.md) prepares a five-page discovery plan, imports saved search HTML or source CSVs, verifies backlinks and page mentions, follows bounded redirect hosts and checks late JavaScript links. It calculates the BeyondSEO Reputation Score with its sensitivity range, confidence and transparent rubric. Own-site sources are excluded; repeated publishers are grouped and related sources cannot supply independent proof. Live search collection uses available browser/search access or supplied evidence; no unattended search-engine collector is included.

## SEO workflows included

These are agent workflows supported by the reference library. They are available for analysis and planning; their presence does not mean the standalone Python script automatically completes every task.

| Skill area | What the workflow covers | Evidence it needs |
|---|---|---|
| Full-site SEO audit | Combine technical, on-page, content, keyword, competitor, local, authority and conversion findings into priorities | Crawl plus whatever performance/market evidence the requested sections require |
| Technical SEO | Crawlability, indexing signals, status codes, redirects, canonicals, robots, sitemaps, internal links and JavaScript checks | Raw/rendered crawl; actual indexing needs separate evidence |
| On-page SEO | Review titles, descriptions, heading hierarchy, intent alignment, content structure and relevant internal links | Page content and the intended audience/query; observed SERPs when making SERP claims |
| Content quality and E-E-A-T | Review experience/expertise evidence, authorship, review dates, originality, completeness, proof and useful answer coverage | Extracted content and verifiable business/expert evidence |
| Schema planning | Inspect current structured data, find syntax problems and propose markup suited to visible page content | JSON-LD/HTML; semantic validation remains a separate check |
| Keyword research | Discover candidate topics, classify intent, cluster keywords, defend existing winners and select business-relevant opportunities | Content can suggest topics; demand/ranking claims need dated query/keyword evidence |
| Keyword-to-page mapping | Assign a target to an existing page, new service/product page, support article, local page or other appropriate action | Page inventory, business priorities and available query evidence |
| Competitor analysis | Compare service pages, content clusters, FAQs, proof, metadata, internal links and conversion paths; identify gaps | Separate scoped crawls of named competitors; ranking/authority comparisons need separate data |
| Local SEO | Review website NAP, service areas, local pages, citations, review strategy and Google Business Profile improvement plans | Website observations and supplied local/profile/review evidence |
| Backlink audit and prospect review | Assess supplied backlinks, relevance, anchors, placements, risk, referring-domain gaps and potential prospects | Supplied backlink/prospect lists and accessible source pages; not inferred from outbound links |
| Authority and digital PR | Plan relevant associations, partnerships, editorial coverage, resource pages, founder interviews and useful third-party articles | Real business proof and identifiable relevant opportunities |
| AEO — answer engine optimization | Design clear definitions, direct answers, FAQs, process/cost/risk explanations and comparison sections | Actual page content and audience questions |
| GEO — generative engine optimization | Review source-worthiness, citation-ready material, proof, clarity and potential content improvements | Page evidence; actual AI mentions/citations require observed answers |
| Entity SEO | Clarify organization/person identity, profiles, service relationships, structured data and consistent descriptions | Website declarations and verified profiles/proof |
| Reputation SEO | Review proof pages, reviews, media references, third-party articles and consistency of brand claims | Supplied or directly inspected evidence; broad mention discovery is not automated |
| Conversation SEO | Map full customer questions and decision paths, objections, follow-up questions and comparisons | Customer/sales questions, supplied reviews and content evidence |
| Conversion SEO | Review calls to action, service-specific journeys, trust placement, forms and potential friction | Rendered pages; conversion performance needs analytics or business records |
| Growth planning | Build 30/60/90-day priorities, content hubs, service-page plans and traffic-to-inquiry scenarios | Baselines, resources and explicitly stated assumptions |
| Reporting and proposals | Create client reports, proposals, developer briefs, content briefs, keyword maps, content calendars, issue logs and roadmaps | Verified findings, task scope and appropriate business context |

The 500-query growth model uses “queries” to mean business inquiries/leads. That is different from search queries in Google Search Console. Future reports should use the clearer term for each measurement.

## Industry playbooks retained

Eight brief industry playbooks cover:

1. Agencies.
2. AI and SaaS companies.
3. Dental practices.
4. Ecommerce.
5. Education and courses.
6. Local businesses.
7. Medical practices.
8. Real estate.

They adapt page strategy, proof, local relevance and conversion focus. They are concise guidance, not separate trained models or completed industry automation systems. Report templates, example report structures and the backlink source library were also retained.

## Functions needing separate evidence or further engineering

| Capability | Current position |
|---|---|
| Search volume and rankings | No search/rank database is implemented; use supplied dated evidence |
| Complete inbound backlink graph | No web-wide backlink index is implemented |
| Traffic, conversions and GBP performance | The website crawler cannot observe private account measurements; supplied exports can support analysis |
| Search-engine/Maps/social product scraping | No dedicated collectors are implemented |
| AI-answer visibility/history | Readiness review is available; actual visibility needs captured answer evidence |
| Core Web Vitals and performance audits | HTTP elapsed time is recorded; Lighthouse/field measurement is not implemented |
| Complete schema validation | JSON parsing is implemented; semantic and rich-result validation is separate |
| Authenticated workflows | No account login, session import, consent-click or form-submission automation |
| Interaction-heavy harvesting | Bounded scrolling is available; no general click recipes or unlimited infinite-scroll engine |
| PDF/media analysis | No downloaded PDF/image/video extraction pipeline |
| Refresh and monitoring | Fresh snapshot comparisons and bounded foreground watch loops are implemented; installing a scheduler or sending notifications is separate |
| Large distributed service | The current engine runs locally with bounded queues and in-memory reporting |

No hosted scraping provider, plugin or external skill is needed to run the native crawler. BeautifulSoup and Colorama are ordinary local Python libraries; Playwright and Chromium are optional local rendering components. A website's own externally hosted scripts or public content API are website dependencies, not outsourced scraping services.
