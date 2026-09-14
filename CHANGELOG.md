# Changelog

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
