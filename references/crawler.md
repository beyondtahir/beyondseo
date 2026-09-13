# Command reference

Run `beyondseo --help` or `beyondseo crawl --help` for the installed command. From a source checkout with dependencies installed, `python scripts/crawl.py` is also available. Setup is documented in [docs/setup.md](../docs/setup.md).

## Commands

| Command | Purpose |
|---|---|
| `crawl URL --out DIRECTORY` | Discover and process a bounded website queue |
| `scrape URL --out DIRECTORY` | Process one URL; sitemap discovery is disabled |
| `report --out DIRECTORY` | Regenerate exports from the local database without network access |
| `doctor` | Check installed packages and local Chromium |
| `--version` | Print the installed project version |

The output directory is required. A nonempty crawl database requires `--resume`. The output lock prevents concurrent commands from writing the same run. If a process is killed, check the PID in `crawl.lock` before removing that stale file.

Crawl/scrape/report exit codes: 0 means at least one unique HTML document was extracted, 1 means no HTML was extracted, and 2 means setup/configuration failed. A zero exit code does not guarantee complete coverage or a successful render. `doctor` returns 0 when HTTP and browser checks pass, otherwise 1.

## Scope and HTTP options

| Option | CLI default | Meaning |
|---|---:|---|
| `--max-pages` | 100 | Total processed URL records, including failed or withheld attempts; scrape fixes this at 1 |
| `--max-depth` | 6 | Discovery depth from the seed or sitemap URLs |
| `--max-discovered` | 10000 | Queue and sitemap membership cap |
| `--max-sitemaps` | 25 | Unique sitemap fetch cap |
| `--max-query-variants` | 20 | Query variants per origin/path |
| `--workers` | 4 | Concurrent HTTP page workers, maximum 32; browser pages run sequentially |
| `--delay` | 0.5 seconds | Minimum spacing per origin; robots crawl-delay may increase it |
| `--timeout` | 20 seconds | HTTP connection/read budget and browser observation budget |
| `--retries` | 2 | Retries after the initial transient failure |
| `--max-bytes` | 5000000 | Response/decompressed body and rendered HTML size cap |
| `--allow-host HOST` | none | Add an exact website hostname; repeat as needed |
| `--exclude REGEX` | none | Exclude matching full normalized URLs |
| `--robots respect\|ignore` | respect | Apply robots policy, or record an explicit authorized override |
| `--allow-private` | false | Permit nonpublic addresses for a deliberate local/staging crawl |
| `--no-sitemaps` | false | Disable sitemap discovery |
| `--keep-tracking` | false | Keep common tracking parameters in frontier identities |
| `--resume` | false | Continue the same snapshot |

The URL budget is not an HTTP request budget. Robots files, sitemaps, redirects, retries and browser resources make additional requests. Redirect chains are bounded. The transport identifies itself as BeyondSEO, validates TLS, ignores environment proxies and connects to a checked resolved address. Embedded credentials and non-HTTP schemes are rejected. OS-managed DNS resolution can take longer than an application timeout.

Hosts are exact; subdomains do not join the page queue automatically. Configured hosts use the seed port or standard HTTP/HTTPS ports. External links are recorded without being crawled. Known asset extensions are excluded from page discovery; extensionless non-HTML resources may consume a URL slot. Images and fonts are fetched only for screenshot rendering and are not analyzed as media files.

Frontier normalization removes fragments and common tracking parameters. Query ordering, repeated parameters, path case and trailing slashes remain distinct. Original link values remain in the page record.

## Browser options

| Option | CLI default | Meaning |
|---|---:|---|
| `--mode auto\|http\|browser` | auto | Heuristic fallback, raw HTTP only, or render every HTML page |
| `--render` | false | Compatibility alias selecting browser mode |
| `--browser-assets public\|allowlist` | public | Permit observed public dependency hosts or only explicit hosts |
| `--render-allow-host HOST` | none | Exact asset/API hostname for allowlist mode; repeat as needed |
| `--render-wait-ms` | 1000 | Minimum observation wait after navigation/selector readiness |
| `--render-settle-ms` | 1500 | Extra bounded text/link stability window, maximum 30000 ms |
| `--wait-for-selector CSS` | none | Wait for a visible element before capture |
| `--scroll-steps` | 3 | Bounded scroll steps, 0–20 |
| `--render-max-requests` | 100 | Routed browser request cap per page; robots/retries may add HTTP attempts |
| `--screenshot` | false | Select browser mode and save a 1440 × 1000 viewport PNG |
| `--headed` | false | Show the local browser window when rendering |

`Config` defaults to HTTP mode and 50 browser requests for backward-compatible library usage; the CLI uses the defaults shown above. Read [browser behavior](../docs/browser.md) for timing, dependencies, restrictions and robots handling.

## Extraction and output options

| Option | Default | Meaning |
|---|---|---|
| `--selectors FILE.json` | none | Named CSS extraction fields |
| `--no-html` | false | Omit saved raw/rendered HTML; structured content and Markdown remain |
| `--quiet` | false | Hide progress; summary JSON still goes to stdout |
| `--no-color` | false | Disable terminal colors; `NO_COLOR` is also honored |

A selector file maps names to CSS strings or objects with `selector`, optional `attribute`, and `all` (default true). `all: false` returns the first result or null. Text is whitespace-normalized; attributes remain as found. Invalid CSS fails before a crawl starts. See [examples/selectors.json](../examples/selectors.json).

## Robots and sitemaps

Matching uses the BeyondSEO robots group, otherwise wildcard groups. Repeated matching groups merge; the longest matching rule wins and allow wins a tie. Wildcards and terminal `$` are supported. Robots evidence is loaded per origin. Unavailable robots responses are distinguished from unreachable policies as described in [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.3). Network/server failures, challenges and 429 defer requests in respect mode. Other 4xx robots responses permit attempts to public resources. The override is logged; actual resource responses are still checked.

Crawl-delay is honored as an extension. Required waits over 30 seconds defer work rather than shortening the delay. Retry-After is honored for transient failures; values over 30 seconds leave a failure for a later run instead of retrying early.

Discovery reads robots sitemap declarations and conventional sitemap endpoints. It handles XML namespaces, URL sets, indexes and gzip content. Index cycles, DTD/entities and configured growth limits are checked. `lastmod` is stored as a sitemap claim. A sitemap is discovery evidence, not proof of indexing or orphan status.

## Output files

| File | Contents |
|---|---|
| `documents.jsonl` | Readable content, Markdown, metadata and selected HTTP/rendered representation |
| `content/*.md`, `content/*.txt` | Per-page readable exports named by URL hash |
| `pages.jsonl` | Detailed page records: raw extraction and optional rendered extraction |
| `pages.csv` | Selected-representation inventory, with initial title/word-count fields and missing-content flag |
| `links.csv` | Raw/rendered edges, anchors, scope and checked-target status |
| `issues.json`, `issues.csv` | Evidence-bearing observations and review candidates |
| `report.md` | Report with the first 100 findings; full findings remain in exports |
| `summary.json` | Actual configuration, counts, coverage warnings and unmeasured metrics |
| `access.json` | Access assessment, recorded attempt counts and local stop reasons |
| `robots.json` | Policy responses, rules, timestamps and overrides |
| `sitemaps.json`, `sitemap-evidence/` | Membership, fetch history and successful XML evidence |
| `frontier.csv`, `crawl.sqlite3` | Queue, sources, progress and recovery state |
| `html/` | Original decompressed HTML and rendered DOM snapshots |
| `screenshots/` | Optional browser viewport PNGs |

`documents.jsonl`, metadata findings and duplicate checks prefer the extracted DOM when rendering completes without a browser exception, including a successfully captured empty DOM. Failed rendering falls back to HTTP evidence. Raw noindex evidence is retained even if JavaScript removes it. A page may still be partial; detailed `pages.jsonl` records remain the source for interpretation.

Short English missing-content screens behind HTTP 200 are flagged as heuristic candidates. The report also identifies captured internal links to those destinations. Review the page before changing it; this heuristic does not establish a search engine's soft-404 classification and does not cover every language or error layout.

Extraction includes titles, descriptions, generic meta/Open Graph fields, H1–H6, language, canonical links, hreflang, pagination, links/anchors, image declarations, forms, JSON-LD, main/body text and custom fields. JSON-LD syntax is checked; semantic validity is separate. Full body and selected main content have separate counts. Main selection may fall back to body content when a landmark covers only a small part of the page.

Markdown conversion preserves common headings, lists, links, tables and code blocks. It is deterministic and cannot reproduce every layout or complex table. HTML visibility extraction is heuristic; screenshots give a separate viewport observation. CSV formula-like strings are escaped; JSON preserves original data.

## Access diagnostics

HTTP 401/403, 429, server failures, robots decisions and configured limits are separate categories. Attempt history retains recoverable rate limits. Challenge signals include the documented [`cf-mitigated: challenge` header](https://developers.cloudflare.com/cloudflare-challenges/challenge-types/challenge-pages/detect-response/) and a conservative title-plus-markup heuristic. Detection is incomplete by design; saved response evidence allows review.

An exhausted frontier means the discovered, scoped queue has finished. It does not establish full website coverage. A small successful sample does not predict larger or later crawls. Resource redirects, POST APIs, login flows, cross-site frames and unbounded interaction are not supported by the current browser transport.

## Resume and scale

Resume permits changing page budget, HTTP worker count, delay, timeout and retries. Scope, normalization, extraction and browser settings must match. Completed pages, including errors, are not refreshed. Interrupted in-flight queue items become pending. Older schema/configuration snapshots may require their original version; a fresh folder is the supported upgrade path.

Reports load records into memory. BeyondSEO is designed for bounded local website audits, not a distributed crawling service. Scheduling, incremental change detection, authenticated sessions and web-wide search/backlink indexes are separate work.

## Review and implementation commands

`readiness`, `compare`, `watch`, `backlinks` and `edit` are documented in [operations](../docs/operations.md). `search-plan`, `search-import` and `reputation` are documented in [our reputation reference](reputation.md). Every crawl exports `readiness.json` and `readiness.md` alongside the existing evidence.
