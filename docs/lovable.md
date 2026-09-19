# BeyondSEO in Lovable

Use this host guide after importing BeyondSEO as a workspace skill. It adapts execution to Lovable; the crawler, research, scoring, posting library and report engine remain shared with other hosts. Do not build a second crawler or alter the website to repair a skill runtime.

## Install and start

Follow [the native import steps](agent-installation.md#lovable). Import the full prepared bundle, select `/beyondseo` in the project chat and check its attached skill chip. Reading a GitHub URL is not skill registration. Unpublished local changes require the prepared local bundle; a GitHub import uses the published version.

Resolve the actual imported skill folder. Check `SKILL.md`, `scripts/run.py`, `src/beyondseo`, the logo and the posting catalog. Do not replace project knowledge, other skills or application settings. A connector permission failure does not prevent using an already authorised native workspace import.

## Prepare execution without modifying the app

Run `python3 /actual/skill/path/scripts/run.py doctor` in the permitted execution environment. Registration, Python availability and a working browser are separate checks. Reuse available dependencies; do not install everything on every request.

If a mounted skill cannot execute because its filesystem/import path is inaccessible, retain the exact error. If a permitted private writable execution directory is available, copy the complete imported skill there and retry the doctor once. This is a file-location recovery, not permission to evade a host execution denial. Use the host's file tools or, where a shell is available:

```sh
# Replace the source with the actual imported skill directory.
bseo_skill_source=/actual/imported/beyondseo
bseo_execution=$(mktemp -d /tmp/beyondseo-execution.XXXXXX)
cp -R "$bseo_skill_source" "$bseo_execution/engine"
python3 "$bseo_execution/engine/scripts/run.py" doctor
```

Use a different host-approved private parent if `/tmp` is unavailable. Keep runtime, crawl results and project ledgers outside application source, `public/` and the imported skill. Only if the doctor establishes missing dependencies, and setup is authorised, use the bundled [runtime setup](setup.md). Do not change filesystem permissions, weaken network controls or repeatedly retry an explicit execution denial.

Before a later job, check whether the execution folder still exists. A missing temporary folder requires a fresh private copy; it does not prove that every turn resets the sandbox. Check the new copy's doctor before using it. Keep durable evidence through supported private artifact/storage controls. A temporary ledger alone is not durable monitoring.

## Crawl and interpret the result

Use the shared [crawler commands](../references/crawler.md) with the user's actual scope and request/time budget. Use `scrape` for a single page and `--include-www` for normal www/non-www canonical redirects unless exact-host scope was explicitly requested. Automatic mode may perform an initial HTTP fetch and a browser render of the same page. Count these separately from distinct URLs, redirects, robots requests and browser assets. Never expand a test or silently rerun it to obtain a passing result.

Inspect saved page records and `summary.json` before reporting success. In `pages.jsonl`, inspect `rendered.readiness`, `rendered.error`, `rendered.javascript_errors` and the raw/rendered extraction:

- `deadline_reached: true` means the render reached its readiness deadline. Useful text or schema may have been captured, but completeness is not established.
- A `selector_error` identifies the failed selector wait. Report that recorded error rather than guessing a provider or credit failure.
- `text_stable_observed: false` means stability was not observed; it does not prove the page was still changing.
- A zero command exit means the command completed. It does not establish complete rendering, complete website coverage or a clean SEO audit.
- Blocked optional images/fonts, word count and a valid JSON-LD parse do not establish completeness. Preserve positive observations while withholding unsupported missing-content claims.

If the task permits another attempt, resolve an observed readiness problem with a suitable selector or a bounded longer render allowance. Respect the overall budget. If attempts are exhausted, keep the partial evidence and continue independent work. Use Lovable's available preview/browser tools for permitted source and visual checks when the native browser is unavailable; label the different evidence route. Never treat another agent's browser as a capability Lovable itself has.

## Apply website work and monitor it

Follow [website work and design protection](website-work.md). An audit alone changes no application files. For authorised implementation, edit the app's existing framework source, preserve layout and compact copy, and run the existing build and desktop/mobile checks. Changes to the distributable BeyondSEO engine belong in the skill repository, not the customer's application. Private test-report corrections also stay outside the app.

Offer the optional monitor only for authorised implementation or ongoing work. With consent, create a private branded HTML artifact using the project ledger when Python is available. The existing Lovable chat remains the control surface. A snapshot is not a persistent worker, and an unpublished preview is not a schedule. Hosting or scheduling a monitor requires separately authorised authentication, durable storage and a real worker; do not add a public dashboard route automatically.

Report separately: skill loaded, engine ready, browser ready, target capture coverage, search discovery coverage, implementation checks and monitor status. Do not claim paid credits are exhausted unless Lovable reports that failure. Preserve the original error when the cause is unknown.
