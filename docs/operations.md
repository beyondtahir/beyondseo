# Review, improve and check again

BeyondSEO supports a practical cycle: collect evidence, explain the gaps, draft changes, apply authorized work and check the result. The skill supplies the SEO decisions and writing; the commands below handle repeatable evidence and file operations.

## A readable readiness review

Every crawl writes `readiness.md` and `readiness.json`. They summarize sitemap membership, captured main/body text, schema types and syntax errors, raw/rendered indexing declarations, relevant snippet controls and path permissions from the saved robots file for Googlebot and Bingbot. They also show the recorded robots policy for OAI-SearchBot, GPTBot, Claude-SearchBot, ClaudeBot and Google-Extended separately when a robots file was successfully retrieved. These are declared rules, not evidence of an actual bot request or AI citation. A missing or blocked robots capture remains unknown. Search access and model-training choices are separate; do not recommend opening training access automatically. [OpenAI crawler purposes](https://developers.openai.com/api/docs/bots) · [Anthropic crawler purposes](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) · [Google-Extended](https://developers.google.com/crawling/docs/crawlers-fetchers/google-common-crawlers#google-extended).

```sh
beyondseo readiness --out /absolute/path/to/run
```

Readiness is not an AI visibility score. It does not establish indexing, citations, schema semantic validity or independent reputation. HTTP and rendered captures are retained separately; empty or failed observations do not become passing results. Header directives belonging to other agents must be interpreted for those agents.

## Compare and repeat audits


Use a fresh folder for each observation. `compare` requires the same seed URL and reports changed content, metadata, status, schema, canonical and noindex signals. It also records newly observed URLs and pages that were not reobserved. A missing or failed page does not count as a resolved finding.

```sh
beyondseo compare --before runs/baseline --after runs/recheck --out runs/comparison
beyondseo watch https://example.com --out runs/weekly-review --cycles 3 --interval 86400 --max-pages 25 --mode auto
```

`watch` accepts the crawl controls, including host scope, rendering and selector waits. Each cycle creates a fresh `run-0001`, `run-0002` folder and subsequent comparisons. `watch.json` records progress. Intervals are measured from the end of a run; the minimum is 60 seconds. Two consecutive runs without usable HTML stop the loop. Press Ctrl+C to stop and retain completed evidence. Use a new parent folder for a new series.

This is a foreground local process: it runs while the machine and process remain active. It does not install a scheduler, send notifications, deploy edits or rewrite content automatically. For ongoing assisted work, define the sites, cadence and allowed edits with your agent or existing task runner. Review meaningful changes and act only within that agreed scope. An interrupted individual crawl may be continued with `crawl --resume` in its run folder.

## Check supplied backlinks

```sh
beyondseo backlinks --sources playbooks/backlink-system/backlink-source-database.csv --target https://example.com --out runs/backlinks --max-sources 27
```

The CSV needs a `URL` column. Exact duplicates are checked once. Output records links to the target host and www alias, anchors, rel values and source index declarations. Other target subdomains need a separate check. **Automatic mode is the default**: it also renders scripted sources with substantial initial text when no target link was found. Failed or incomplete rendering cannot establish link absence. Add `--brand "Example" --alias "Example Company"` to verify page mentions separately.

Observed redirect hosts can be followed in at most five scope expansions; ordinary outgoing links are not followed. Every request retains public-address, robots, response and request-budget checks. Use `--no-follow-redirects` to retain the initial host scope, or `--mode http` for initial-response evidence only. Records distinguish an explicit robots disallow, unavailable policy, robots scope limit and redirect loop. No submissions or purchases occur.

Use [our reputation workflow](../references/reputation.md) for five-page discovery, source review, a transparent score with its range, and strongest observed backlink/mention lists.

## Draft and apply website text

A change plan operates on one existing UTF-8 content file, up to 5 MB. Use it for a title, heading, answer section, schema block or other reviewed page update. The skill writes the replacement file first using real business facts. The tool shows the diff, preserves exact original bytes and checks that the target has not changed since review.

```sh
beyondseo edit plan --site /absolute/path/to/site --file index.html --replacement /absolute/path/to/drafts/index.html --out /absolute/path/to/changes/home-answer
```

Review `review.diff`, `after.txt` and `plan.json`. The result prints a `plan_sha256` value. Once this exact change is authorized, use that value:

```sh
beyondseo edit apply --site /absolute/path/to/site --plan /absolute/path/to/changes/home-answer --expect-plan REVIEWED_SHA256
beyondseo edit rollback --site /absolute/path/to/site --plan /absolute/path/to/changes/home-answer --expect-plan REVIEWED_SHA256
```

Rollback only proceeds if the current file still matches the applied version. A later edit causes a stop, so someone else's work is not overwritten. The plan and backups belong outside the public website and outside the repository. Their files are created with restrictive local permissions; protect the parent folder and backups too.

Content hashes verify the file transfer, not the correctness of the writing. Inspect the resulting page, relevant links and structured data, then recrawl. A source-file change may require the website's own build/deployment pipeline before it is visible. For a database-driven CMS, use its authorized content API or administration workflow; uploading an HTML file is not a general CMS editor.

## Connect to hosting

Use an encrypted SFTP or explicit FTPS connection. The profile holds references to local credentials, not passwords. Copy [the SFTP example](../examples/sftp-connection.json) or [FTPS example](../examples/ftps-connection.json) to a private location and fill in the host and canonical website root. Set the named environment variables through your shell or secret manager; do not paste secrets into reports or version control.

For SFTP install the optional library:

```sh
python -m pip install -e '.[sftp]'
```

Use a dedicated website account and replace the example key/known-hosts paths with files in a private folder for that site. SFTP requires a verified host key in your known-hosts file and either the configured private key or password variable. Unknown host keys are rejected. FTPS uses the standard Python library, validates the TLS certificate and encrypts its data channel. Plain FTP is not supported.

```sh
beyondseo edit plan --connection /absolute/path/to/private/connection.json --file index.html --replacement /absolute/path/to/drafts/index.html --out /absolute/path/to/changes/home-answer
beyondseo edit apply --connection /absolute/path/to/private/connection.json --plan /absolute/path/to/changes/home-answer --expect-plan REVIEWED_SHA256
```

Remote checks reject symlink content paths. SFTP requires the server's POSIX rename extension; FTPS requires MLSD path facts and rename-over-existing support. The tool verifies the uploaded temporary bytes before replacing the file and reads the result afterward. It does not delete a live file to work around unsupported rename behavior. FTPS file permission behavior depends on the server; confirm it on staging.

These are optimistic single-file updates, not distributed transactions. Avoid concurrent website deployments. If a connection fails during replacement, `receipt.json` marks the outcome as needing inspection and retains the backup. Check the actual remote bytes before retrying or rolling back. Multi-file builds, databases, account creation and backlink publishing need their own supported workflow.

Transport references: [Python FTPS](https://docs.python.org/3/library/ftplib.html), [SFTP client and host-key verification](https://docs.paramiko.org/en/stable/api/client.html).


## Project-based website improvements

Use [website work and monitoring](website-work.md) when the user asks to apply a plan. `project` adds persistent jobs and an optional private monitor; `onsite` prepares guarded HTML and sitemap drafts. The older `watch` command remains a foreground evidence loop. `project run` can be invoked by an external scheduler, but it performs read-only HTTP reviews, not automatic content edits or model calls.

## Review Search Console exports

Use this free, offline workflow when the user provides a Search Console CSV. It does not sign in, call Google or require an API key. Export the English **Queries** or **Pages** table from Performance for one property, search type, date range and set of filters; unzip Google’s export if needed. Keep client exports and generated reports in a private folder outside the repository.

```sh
python3 scripts/run.py search-performance --input ../private/Pages.csv --dimension page \
  --property "Example business" --period "Last 28 complete days" \
  --crawl-out ../private/crawl --out ../private/search-review
python3 scripts/run.py present --performance ../private/search-review/search-performance.json \
  --out ../private/client-report
```

`--crawl-out` is optional and accepts a saved native crawl for exact URL matches only. Unreadable or partial captures cannot establish missing content. Query CSVs do not identify a page: filter the query in Search Console and inspect its Pages tab, or supply separate evidence before making a page-specific finding.

The report sorts the supplied rows by impressions and screens up to 15 query/page rows using configurable `--min-impressions` (default 100) and `--max-ctr` (default 2). These are triage filters, **not universal benchmarks or proof of a defect**. Review the search intent, page, search appearance and market before changing titles or copy. Empty results do not establish a healthy site. Clicks and impressions cover the exported rows only; Google can omit anonymized queries or truncate results. Never add query totals to page totals or represent them as a complete site total.

For a comparison, export the same dimension separately for each period, choose equivalent complete periods and matching filters, and add `--previous ../private/earlier.csv --previous-period "Earlier 28 days" --comparison-context "Same property, Web search, country and device filters; equal 28-day periods"`. The context is supplied by the user, not verified from CSV. Only matching rows are compared; unmatched rows remain unknown, not zero. Record the change date and other influences; a before/after difference does not establish that BeyondSEO caused it.

The command accepts one English-language UTF-8 CSV table with Clicks and Impressions columns; separate comparison-column exports, screenshots and non-English headers are not supported by this offline importer. The separate optional Google commands below provide API access. The report does not measure AI citations, conversions, revenue, keyword demand or rankings beyond supplied row-level average position. The branded export presents these observations and limits; it does not verify the data independently.

## Google account access

Ask **“Connect Google and find opportunities for this website.”** The assistant first inspects its actual connected tools. A suitable authorised Search Console/Analytics connector or compatible `gog` installation may already provide access. Verify that service and the exact property; Google Drive or Gmail permission is not permission to read search or analytics. A saved Chrome login is usable only through an actual permitted host browser, and browser exports remain distinct from API access. Do not read or transfer cookies. Public Google searching works independently of private account authorization.

The optional native route uses Google's browser consent and official authentication library. The base crawler needs neither this extra nor Google access:

```sh
python -m pip install -e '.[google]'
python3 scripts/run.py google status
python3 scripts/run.py google connect --client-json /private/google-desktop-client.json
python3 scripts/run.py google properties
```

On Windows use `py -3`. Install the extra in the same runtime used by the launcher. `connect` requires a valid **Desktop app** OAuth client JSON, with the intended APIs enabled and consent configured. No OAuth client or user credentials are bundled. A public shared BeyondSEO Google app has not been registered or verified; there is no universal preconfigured one-click connection. For your own client follow [Google's installed-app setup](https://developers.google.com/identity/protocols/oauth2/native-app). Prefer an already authorised suitable connector when it removes this setup. `gog` is optional; see [its setup requirements](https://gogcli.sh/quickstart.html) and check the installed version's capabilities before using its commands.

Google opens in the default system browser; `--browser chrome` selects a browser only if Python's browser registry supports that name. Use the user's actual allowed browser otherwise. The user chooses the account and grants selected read-only services; add `--service search-console` or `--service analytics` to narrow consent. This is a local loopback flow with a three-minute consent window, not an embedded login page. A cloud runtime cannot receive a callback addressed to a different computer. There use the host's approved connector/authentication or browser/export route instead of weakening permissions or copying a browser session.

Credentials are stored outside the source in a private per-account folder, default `~/.config/beyondseo/google`, with restrictive files. Set `--state-dir /private/account-folder` for separate accounts. Protect that folder on the host OS. Never paste credentials into chat or version control. The token refreshes when supported; revoked/missing scopes require a new grant. Requested scopes and provider-observed grants are recorded separately, including partial consent. Missing grant evidence stays unknown until service access is tested. `google status` reports saved credentials, not live property access. `google properties` checks Search Console and Analytics independently and preserves partial access. Property lists can be incomplete; select an exact property, and confirm the GA4 property's relationship to the website instead of guessing from its account name.

```sh
python3 scripts/run.py google search-console --property sc-domain:example.com \
  --start 2026-10-01 --end 2026-10-28 --dimension page --out ../private/google-pages
python3 scripts/run.py search-performance --input ../private/google-pages/search-console.csv \
  --dimension page --property sc-domain:example.com --period "2026-10-01 to 2026-10-28" \
  --out ../private/google-review
python3 scripts/run.py google analytics --property 123456789 \
  --start 2026-10-01 --end 2026-10-28 --out ../private/organic-landing-pages
python3 scripts/run.py google disconnect
```

These commands make bounded read-only reports. Search Console saves the query/property/date/dimension, final-data request, returned rows and CSV compatible with the offline reviewer. It retrieves up to `--limit` rows (default 1,000, maximum 25,000) without claiming complete data; Google can omit rows. GA4 retrieves Organic Search landing pages, sessions, engaged sessions and configured key events, retaining response metadata and quota information; key events are meaningful only when correctly configured. It does not infer a complete funnel, revenue, real search demand or SEO causation. Empty results differ from parsing failures. Neither Search Console nor GA4 measures all AI citations. Disconnect removes this local saved connection; revoke the Google grant in your account when desired. Other host/gog authorizations are separate.

Errors distinguish missing libraries, local execution denial, observed DNS/TLS/connection failure, timeout, HTTP authorization/rate restrictions and response parsing. HTTP 403 alone cannot establish whether a property permission, disabled API or organisation policy caused it. Refresh failures retain an unknown underlying cause. No successful real-account consent, property access or cross-host compatibility is implied by deterministic tests.

## Install specialist definitions

For a chosen existing project, these commands add eleven namespaced definitions without changing model selection or unrelated settings:

```sh
python3 scripts/run.py agent-setup --host codex --workspace /absolute/project --dry-run
python3 scripts/run.py agent-setup --host codex --workspace /absolute/project
python3 scripts/run.py agent-setup --host claude-code --workspace /absolute/project
```

Codex receives `.codex/agents/beyondseo-*.toml`; Claude Code receives `.claude/agents/beyondseo-*.md`. Conflicting files are preserved and reported, not overwritten. Definitions point to the installed skill's absolute path: rerun/review setup after moving that skill. Confirm host loading, any required restart and actual delegation. Hermes uses its available `delegate_task`; OpenClaw uses its available `sessions_spawn`. Work, Cursor and other environments use only the delegation tools actually exposed to that session; otherwise responsibilities run sequentially. The generated swarm plan and definition installer launch zero agents. The Publishing Agent is excluded from ordinary audit plans and joins with explicit `--specialist seo-publisher` for a requested campaign. See [coordination](../playbooks/core/seo-house-workflow.md#coordinate-the-specialists).

## Review a saved Lighthouse report

Generate a Lighthouse report in Chrome DevTools or your existing approved Lighthouse tool, then use its menu to save the report as JSON. See [Chrome’s export instructions](https://developer.chrome.com/docs/lighthouse/overview#share-reports-as-json). BeyondSEO does not install or run Lighthouse in this workflow.

```sh
python3 scripts/run.py lighthouse-review --input ../private/lighthouse.json --out ../private/lab-review
python3 scripts/run.py present --lighthouse ../private/lab-review/lighthouse-review.json --out ../private/lab-client-report
```

The offline review preserves the supplied URL, timestamp, device setting, run warnings, available performance score and five lab metrics: LCP, CLS, Total Blocking Time, First Contentful Paint and Speed Index. Missing or failed measurements are never replaced with zero. A runtime failure withholds the score and metrics. Inspect the original report for contributing elements and details before making changes.

This is **lab data**, not CrUX or other real-user field data. Total Blocking Time is not Interaction to Next Paint (INP). Lighthouse results vary with device, conditions and other settings; a single run is not proof of a lasting improvement. This workflow requires no API key or paid service, but it requires an existing Lighthouse JSON file. [Lab versus field data](https://developer.chrome.com/docs/crux/guides/pagespeed-insights).

## Run an optional public performance check

The public PageSpeed command makes one bounded request to Google's official API, without OAuth or a required key. It retains the attempt and saves `lighthouse.json` only when an actual report was returned. This command uses Python's standard library; the optional Google authentication dependencies are needed only for the separate private-account commands. The base crawl and saved-report importer do not need this public request.

```sh
python3 scripts/run.py google pagespeed --url https://example.com --strategy mobile --out ../private/pagespeed
# Only when an actual lighthouse.json was returned:
python3 scripts/run.py lighthouse-review --input ../private/pagespeed/lighthouse.json --out ../private/lab-review
```

Quota errors, access denials, timeouts, runtime failures and malformed responses remain unavailable with their evidence; they are not zero scores or missing-content findings. There is no automatic retry loop or claim that a paid tool is necessary. The provider performs this public-site check; local browser access is separate. See [Google's endpoint guide](https://developers.google.com/speed/docs/insights/v5/get-started).

If this provider is unavailable, use an already approved local Lighthouse installation, Chrome DevTools or a supplied report. With a compatible Node.js runtime and Chrome, the official free CLI is another optional route:

```sh
npx --yes --package lighthouse@13.6.0 lighthouse https://example.com \
  --output=json --output-path=../private/lighthouse.json \
  --only-categories=performance,accessibility,best-practices,seo \
  --chrome-flags="--headless" --max-wait-for-load=30000
```

Create the private output directory first. This downloads the official optional package if needed; use the host's installation permissions and the runtime requirements in [Lighthouse's documentation](https://github.com/GoogleChrome/lighthouse). The host runs this command, not BeyondSEO's PageSpeed adapter. Use a fresh browser session for a public page; this does not need the user's signed-in profile. Never disable browser sandboxing or certificate checks to make it run. If execution is denied, retain the exact denial and continue the other audit work. Inspect the returned JSON for warnings and actual contributing elements before proposing fixes. Lighthouse's basic SEO score is not a complete website, reputation or AI visibility score.

## Review entity declarations

```sh
python3 scripts/run.py entity-review --crawl ../private/site-crawl --out ../private/entity-review
```

This reads saved JSON-LD without new network requests. It inventories captured declarations, preserves URI fragments and document-scoped blank nodes, and flags conservative cross-page name, URL and publisher variations for review. Each candidate includes captured URLs, evidence dates and a practical acceptance check. Multiple legitimate people, organisations or publishers are not automatically defects. Review the visible business facts and intended relationships before changing IDs or claims.

Failed or partial captures cannot establish missing entities or schema. Repeated/nested declarations are not counts of unique real-world people. This is not full schema semantic validation, a knowledge-graph match, a reputation score or proof of indexing/AI citations.
