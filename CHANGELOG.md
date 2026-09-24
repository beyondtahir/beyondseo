# Changelog

## 2.9.1 — Saved audits, without leftover file locks

25 September 2026

- Close database connections immediately after reading saved audit counts and report configuration. This fixes the Windows file-lock failure found in the 2.9.0 release tests.
- Strengthen the continuation regression to verify that database connections are closed on every platform, without relying on garbage collection.
- All 2.9.0 audit, coverage and verification improvements remain included.



## 2.9.0 — Know your website better. Fix it with confidence.

25 September 2026

Get a more focused audit, understand what was actually checked and continue the review without starting again. This release strengthens the checks behind your existing SEO workflows.

- Choose a homepage check, a standard 15-page priority sample, a deeper/custom cap or exact URLs. Continue a saved sample with an explicit additional budget.
- See inspected, partial, blocked and pending coverage; sitemap discovery does not pretend every listed URL was checked.
- Inspect sitemap/HTTP conflicts, HTML hreflang relationships, duplicate description tags, JSON-LD duplicates/identity conflicts and image attributes with evidence and clear limits.
- Execute filesystem and local JavaScript readiness probes; optionally check target DNS, robots, sitemaps and live page access separately. A dependency flag no longer stands alone as proof of networking.
- Require a passing PHP syntax check before staging/applying supported PHP content edits. Keep framework checks and post-change crawl/visual verification separate.
- Fixed JSON-LD-only pages being treated as possible executable JavaScript shells.

Validation: 249 automated tests passed locally, with one platform-specific skip. A separate local end-to-end trial checked page selection, a website edit, desktop/mobile layout preservation and rollback. Private trial data is not included. Real PHP lint execution and fresh imports on every assistant were not tested for this release; PHP checks require an available PHP runtime. See [setup](docs/setup.md) and [website work](docs/website-work.md) for the limits and verification steps.

## 2.8.0 — Your SEO plan, put into action

19 September 2026

- Ask your agent to carry out approved on-site improvements while protecting your website's design, short copy and business facts.
- Follow the work through an optional private branded dashboard, with a saved plan, progress, effort estimates and checked results.
- Keep off-site recommendations alongside website work: relevant posting links, topics, outlines and suggested dates. Publishing remains in your hands.
- Revisit your website through bounded reviews, with pause/resume and protection against overlapping runs. Automatic scheduling still needs a supported agent or host scheduler.
- Install into more coding-agent and website-builder workflows while preserving existing project rules, settings and other skills.
- Prepare reviewed HTML and sitemap changes with the existing backup, verification and rollback workflow.
- Get clearer browser warnings that identify render deadlines and failed selector waits. Partial evidence stays partial.
- Fixed progress updates marked “blocked” incorrectly stopping otherwise successful dashboard command sequences.

The complete SEO, AEO/GEO, competitor research, backlink library and branded reporting workflow remains included. The upload bundle contains 200 files including its installation receipt. Automated regression checks passed locally (238 passed, one platform-specific skip); live host coverage varies. See [installation and runtime guidance](docs/agent-installation.md) for prerequisites. No universal compatibility, automatic hosted worker or ranking guarantee is claimed.

## 2.7.1

- Fixed the hosted skill upload exceeding the observed 200-file limit. Consolidated reporting and industry references into indexed resources while preserving their full guidance; native code, catalog, templates and report assets remain bundled.
- Count the installation receipt when validating upload size and reject oversized packages before creating an archive.
- Added a regression for the exact 200/201-file upload boundary and verified that rejected packages leave no incomplete archive behind.
- Updated direct-upload steps for Claude Desktop and ChatGPT Work, plus specific guidance for browser-download and DNS failures. Skill registration and successful live crawling remain separate checks.
- Published a ready-to-upload skill ZIP with a SHA-256 checksum and a dated roundup of the previous 24 hours of improvements.

## 2.7.0

- Added offline branded PDF and HTML reports with the existing BeyondSEO logo, editorial cover, linked contents, evidence tables, source notes and action roadmaps. Normal setup includes the free PDF renderer; HTML stays available when PDF rendering is unavailable.
- Added report integration checks for embedded assets, pagination, navigation, long tables, escaped content, mobile layout and precise partial-output handling.

- Use reviewed buyer phrases and customer questions for discovery instead of mechanically stacking service labels; validate their profile/brief basis and distinguish hypotheses from keyword recommendations and measured demand.
- Added browser-first deep-research plans, five reputation query families and shared competitor/source budgets, with evidence-based comparison instead of a backlink-list-only report.
- Added cohort reputation comparison that recalculates source evidence and withholds ordinal positions when methods, dates, sample coverage or confidence differ.
- Preserve actual native result-page and multi-query provenance through reputation assessment; do not invent missing host pagination.
- Order strongest source examples by supported quality points instead of optimistic unknown-dimension midpoints; headline scoring model 1.1 remains unchanged.
- Added release hygiene checks for client captures, private identifiers and machine-specific paths; live research stays outside the repository.

- Recognize an unavailable host search provider without attributing it to Google or a remote denial; retain its unknown underlying cause and use the next permitted source.
- Require final competitor classifications to use reviewed evidence, retain known conflicts and use exact discovered domains; keep briefs for uninspected pages conditional.
- Do not promote broad international/global delivery overlap into a direct geographic competitor match.
- Let an older default Python hand off to an already installed compatible runtime before checking the engine version requirement.
- Corrected older capability descriptions to include the implemented native discovery adapters and explain browser choices across agent hosts.
- Preserve an existing local virtualenv during a backed-up skill update; restore the previous installation if preservation fails.
- Added explicit `--include-www` scope support for ordinary www/non-www redirects while retaining robots, TLS and address checks. Exact-host crawling remains available.
- Reject malformed source CSV quoting instead of silently corrupting search-query provenance; native discovery exports remain the preferred input.
- Clarified model authentication, tool execution and website/search access as separate diagnostic layers, and documented use of packaged commands to avoid unnecessary inline-code approvals.

## 2.6.0

- Added shared, bounded discovery for reputation and competitor work: permitted native DuckDuckGo HTML/Bing RSS, recorded host search/browser results, saved HTML and existing source CSVs. Failures, empty results, parser errors, query context and fallback attempts remain visible; duplicates retain provenance.
- Added reviewed business profiles, profile-derived queries and service/customer-first competitor selection. Offices, markets and languages stay separate; direct competitors, benchmarks, search leads and rejected candidates are labeled.
- Added evidence-based audit reports with exact URLs, dates, observations, business context, actions, priority rationale and acceptance checks. Failed/partial captures cannot establish missing content or markup.
- Fixed SVG accessibility titles being counted as document titles. Missing or denied browser runtime no longer aborts usable HTTP audit work.
- Added separate environment/search diagnostics, installed-browser detection and explicit, idempotent free Chromium setup. Host browser control remains a separately verified capability.
- Added deterministic discovery, relevance, evidence and browser-setup regressions. The reputation scoring model remains 1.1; no paid service or API key was introduced.


## 2.5.2

- Make printed follow-up commands safe to paste into PowerShell when paths contain spaces or special characters.

## 2.5.1

- Add a complete upload bundle with a matching `beyondseo/` folder, concise metadata and a SHA-256 checksum.
- Add host-specific installation commands, profile/workspace options, repeat-install detection and backed-up updates.
- Support a separate approved runtime directory for hosted or read-only skill mounts.
- Separate skill registration from HTTP/browser readiness, with specific guidance for HTTP 422, permission and scan errors.
- Keep developer fixtures in the repository; distribute the runtime, playbooks, catalog and documentation in the skill bundle.
- Clarify package permissions and use dedicated credential paths in the optional hosting example.

## 2.5.0

- Added a 206-entry publishing library with 241 traceable source rows and documented posting guidance for 22 destinations.
- Added website-specific shortlists of 15 or 20 sources, including topics, writing briefs, posting steps, eligibility, link rules and a calendar.
- Added topic, prerequisite, free-term and freshness filters, with clear research gaps when too few sources qualify.
- Added Markdown, CSV and JSON plan exports and an optional PDF importer that preserves visible rows and conflicting source claims.
- Kept source-sheet DR values separate from current measured authority and from the BeyondSEO Reputation Score.
- Refreshed the README, assistant setup and posting guide with clear examples and a development guide.

## 2.4.0

- Launched the branded GitHub project with MIT licensing, a documentation index, verified creator links and issue templates.
- Fixed crawl exports to use the same package version as the CLI.
- Closed the crawl database when initialization rejects an incompatible resume or an existing output directory, preventing Windows file locks.
- Made the FTPS fixture's replacement capability explicit on all operating systems and verified that unsupported replacements preserve the live file and recovery receipt.
- Added a local skill-folder installer with dry runs, checksum receipts and protection for existing destinations.
- Added an activation-free launcher that resolves its own runtime and works from other working directories.
- Documented Claude Code, Codex, ChatGPT Work, Hermes and OpenClaw setup with explicit validation and cloud limits.
- Added a friendly FAQ, example questions, capability overview and precise no-API-key / model-usage explanation.
- Clarified why a small observed sample cannot replicate a proprietary authority model; retained conservative scoring model 1.1.
- Added portability behavior tests for clean copying, path handling, existing files and launcher exit codes.

## 2.3.1

- Changed the reputation headline to supported lower-bound points adjusted for the weakest measured evidence factor; low-confidence results cannot reach 50/100.
- Kept the old sample-quality midpoint as diagnostic context and added explicit provisional/withheld states and adjustment factors.
- Prevented duplicate imported evidence and unrelated target links from inflating observed support.
- Made backlinks, named competitor comparisons and a practical 30/60/90-day plan explicit defaults for general website audits.
- Added a complete audit delivery standard and a worked example.
- Added behavioral coverage for conservative scoring and identical treatment of client/competitor evidence.

## 2.3.0

- Added BeyondSEO Reputation Score, its published rubric, sensitivity ranges, coverage and attributable source reviews.
- Added five-page discovery plans, saved search-result imports and native link/mention verification without a service account.
- Grouped repeated publishers; excluded same-site sources and separated owned/affiliated evidence from independent editorial proof.
- Added bounded cross-host backlink redirect follow-ups and automatic checks for late links on text-rich JavaScript pages.
- Switched SEO metadata, duplicates and page inventories to successful rendered content while preserving raw noindex evidence.
- Added heuristic missing-content detection for HTTP 200 screens and their referring internal links.
- Separated robots disallow, unavailable policy, robots scope limits and redirect loops.
- Removed external SEO metric dependencies and added regression tests for crawler behavior and reputation evidence boundaries.

## 2.2.0

- Added plain-language readiness reports, separate search-crawler robots observations and raw/rendered indexing evidence.
- Added supplied-backlink verification, snapshot comparisons and bounded review loops.
- Added staged single-file text updates with local/SFTP/FTPS transport, reviewed hashes, backups and guarded rollback.
- Compacted the main skill and added friendly reporting, answer writing and reputation workflows.
- Added a source library and seven additional reputation routes.
- Added behavioral coverage for comparisons, monitoring, backlink verification and publishing safeguards.

## 2.1.0

- Added automatic browser fallback and an explicit browser mode.
- Added public dependency loading, visible-element waits, bounded scrolling and viewport screenshots.
- Added Markdown/text documents and improved selection for pages with incomplete main landmarks.
- Added a recorded robots-policy override for authorized crawling.
- Added the installable `beyondseo` command, environment checks and a cross-platform setup script.
- Organized the SEO playbooks, examples, browser documentation and repository contribution files.
- Expanded regression coverage for browser behavior, content extraction and access diagnostics.

## 2.0.0

- Introduced the local HTTP crawler, BeautifulSoup extraction, SQLite resume and evidence exports.
- Added optional local Chromium observations and practical SEO finding candidates.
- Separated website observations from rankings, private analytics and backlink-index measurements.
