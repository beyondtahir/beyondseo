# Review, improve and check again

BeyondSEO supports a practical cycle: collect evidence, explain the gaps, draft changes, apply authorized work and check the result. The skill supplies the SEO decisions and writing; the commands below handle repeatable evidence and file operations.

## A readable readiness review

Every crawl now writes `readiness.md` and `readiness.json`. They summarize sitemap membership, captured main/body text, schema types and syntax errors, raw/rendered indexing declarations, relevant snippet controls and path permissions from the saved robots file for Googlebot and Bingbot. The complete robots text remains available for other named crawler checks.

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
