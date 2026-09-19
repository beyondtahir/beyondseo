# Improve a website and keep the work visible

Use this workflow when the user asks BeyondSEO to apply improvements, maintain a website or carry out a goal. A request for advice or an audit remains advice or an audit. The user's existing chat is the control surface. A dashboard is optional, read-only monitoring; it is not another AI subscription or a worker.

## Start with the business and the actual access

Inspect the business, current pages and site implementation before proposing changes. Preserve explicit goals, markets, brand voice and factual claims. Establish the current URL inventory, crawl/render coverage, metadata, indexability, canonicals, redirects, sitemap mechanism and relevant structured data. Failed requests do not establish missing content. Use the existing crawler and research workflow; do not replace them with guesses from source files alone.

Identify the available route: local repository, authorised connected project tools, SFTP/FTPS, or read-only website access. A domain alone is not editing access. Never ask for a master password in chat; use private connection controls, environment variables, a dedicated hosting account or keys. Restrict hosting access to the exact website directory. Plain FTP is unsupported. Credentials, account sessions, client evidence and project ledgers stay outside the distributable skill and public repository.

Create a private project record when implementing an ongoing plan. On later requests, open the existing project with `project status` before creating jobs; reuse its stable job IDs, unfinished work, recorded authorisation and evidence. If the goal changes, preserve completed history and explicitly revise the remaining plan rather than silently repeating applied changes. Save the reviewed business context, constraints and goal; keep it available across sessions. Give a range for implementation effort based on inspected pages and dependencies. Distinguish hands-on time, time waiting for access and future measurement dates. Leave unknown estimates unknown; never promise indexing or ranking by that time.

## Authorised work, with the design protected

A request to apply on-site improvements authorises the relevant work within the user's stated scope. Preserve that authorisation instead of asking again for each small edit. Show the proposed work and preserve a baseline before making it concrete. Ask only for scope expansions, required access, new pages, publication not already authorised, or the optional dashboard. Follow host permission controls.

- Keep the existing layout, components, typography, spacing, navigation, conversions and functional behaviour. Work in the framework's source or CMS, not generated build files.
- Improve titles, descriptions, headings, internal links, canonical consistency, language declarations, suitable schema and sitemap coverage where the inspected evidence supports a change. Inspect existing rules first. Do not remove intentional noindex/robots restrictions or redirect rules to make a score look better.
- Rewrite brief visible text to answer the customer's question directly while preserving its meaning, facts and approximate space. Character length is a guard, not a line-count guarantee. Inspect wrapping, overflow and section height at representative desktop and mobile widths. Preserve nested links and accessible names. Avoid keyword stuffing.
- Add an accessible accordion using the current design system only when useful page-specific questions remain unanswered and the change is in scope. Do not add duplicate FAQs to every page. Essential service information belongs in visible main content. Do not claim FAQ schema guarantees a rich result.
- Structured data describes real visible content. Do not invent ratings, offices, credentials, offers or reviews. Preserve existing valid schema and merge deliberately. Check property meaning as well as valid JSON: [areaServed](https://schema.org/areaServed) describes geography, so a customer segment belongs in a suitable audience field, not a service-area field. Omit unknown geography.
- Use the site's existing sitemap generator where present. Include canonical, indexable successful pages only; exclude redirects, errors, private routes and the monitor. Never invent lastmod dates. Check sitemap indexes, URL duplication and robots references.
- Propose a new page with purpose, proposed URL, existing-page overlap, outline and effort. Create it only after authorisation. Do not add location doorway pages to meet a quota.

Before editing, retain the diff/base revision or backup. After editing, run relevant build/content/link checks, inspect rendered layouts and test key interactions. Verify the deployment separately if publishing is authorised. Report checks and coverage limits; never promise a universally error-free website. A passed content hash verifies the uploaded bytes, not appearance, indexing or business outcomes.

## Choose the execution route

**Cursor / local coding agents:** install the complete skill in the actual execution environment. Use native repository editing and the existing preview/build workflow. Prepare a branch or working copy, preserve unrelated edits, then deploy only within authorisation. Use `project` below for private state. A cloud agent needs the skill and runtime there; a local installation is not automatically copied.

**Lovable:** use the imported workspace skill and the project's existing chat/tools. Read the full imported resources if available. Apply changes in the current project, preserve its framework and design, and verify its preview. Check Python/Chromium in the actual sandbox; if available, run the bundled engine there and keep project records outside the website. If unavailable, use native source/browser checks and report partial crawler coverage. With monitor consent, generate a private HTML artifact through supported file controls when possible. A persistent remote monitor additionally needs an authorised authenticated durable store and real worker; never put client logs under an unprotected public route. A sandbox file or downloaded HTML is a snapshot and may not survive sandbox replacement. Never claim a schedule exists without its saved registration and a successful run.

**Vercel:** install in the agent managing the repository; Vercel hosting itself is not skill registration. Use preview checks and the project's deployment workflow. Vercel Cron calls production HTTP endpoints; a preview is not an active schedule. Authenticate any future job endpoint, store state durably, prevent overlapping runs and observe function limits. Do not put this local SQLite worker inside an ephemeral Function and call it persistent. A long crawl needs a suitable external worker. No Vercel scheduler or hosted monitor is provisioned by this package.

**SFTP/FTPS:** use the existing guarded single-file `edit` workflow. It verifies target identity, expected bytes, reviewed plan hash and readback, and retains rollback bytes. It does not edit CMS databases, create arbitrary new pages or deploy multi-file applications. Use framework/CMS tools for those tasks.

## Private project commands

Replace paths with private locations outside the website and the skill. These commands record work; the host agent still makes and checks the edits.

```sh
beyondseo project init --project /private/client-project --url https://example.com --goal "Improve service enquiries while preserving the design"
beyondseo project profile --project /private/client-project --input /private/business.json
beyondseo project plan --project /private/client-project --input /private/jobs.json
beyondseo project status --project /private/client-project
beyondseo project update --project /private/client-project --job service-title --state running --note "Baseline saved; implementing the approved title"
beyondseo project update --project /private/client-project --job service-title --state applied --note "Preview updated; live verification remains"
beyondseo project update --project /private/client-project --job service-title --state verified --note "Acceptance checks passed within recorded coverage" --evidence /private/check.json
```

Profile fields: `business`, `services`, `customers`, `offices`, `markets`, `languages`, `sources`, `unknowns`, `constraints`, `access_route`. Save context only, never credentials.

A plan is a JSON array. Each job needs a stable `id`, `title`, `kind` (`onsite`, `new_page`, `offsite_plan`, `report`, `review`), affected `url`, concrete `action`, `acceptance` and starting `evidence`. Optional fields: `priority`, `estimate_minutes` as `[minimum, maximum]`, timezone-qualified `due_at`, external `destination`, and `requires_approval`. Reimporting identical jobs does not duplicate them. New-page jobs require an authorisation reference via `--approval` before work begins.

Verification JSON needs `url`, timezone-qualified `captured_at`, `checks` (each with `name`, `result: "pass"`, and actual `observation`), `coverage` and `artifacts` (local filenames relative to the verification file). Keep the files; hashes are retained. For copy changes include desktop/mobile layout checks. Record failed or incomplete checks as a blocked/applied job, not verified. The ledger validates the evidence format, not the truth of a fabricated observation.

## Offer monitoring once

Monitoring is a shared BeyondSEO capability for **ChatGPT Work, Codex, Claude, Hermes, OpenClaw, Cursor and agents managing Lovable/Vercel projects**. It is not restricted to website builders. For any authorised ongoing job, retain the same business context, work plan, evidence and activity; offer the same optional monitor. Ordinary one-off questions do not require dashboard setup.

| Execution environment | How the user views progress |
|---|---|
| Local Codex, Claude Code, Hermes, OpenClaw or Cursor with Python | Open the private HTML file or the local read-only monitor URL. The same project commands apply. |
| ChatGPT Work or Claude hosted execution with Python/files | Generate the private HTML artifact and return it through that host's supported file/preview controls. Regenerate after work; a downloaded copy is a snapshot, not a live connection. |
| Lovable or another host without the native runtime | Use native project tools for implementation. A live monitor needs an explicitly authorised authenticated store and worker; otherwise provide a clearly dated private snapshot through available artifact controls. |
| Vercel hosting | The connected coding agent owns the job. Hosting a monitor is separate, requires authorisation and access control, and does not itself run the SEO worker. |

Detect capabilities, not product names. Do not expose a local port publicly or claim a localhost link works in a remote chat. If a host cannot create/open HTML, give the same saved progress as a concise chat report and explain the missing artifact capability. Never require a separate model API merely to view the monitor.

After the user agrees to a private monitor, ask their preferred check cadence and summary frequency together if not already supplied. Progress records update after actions; dashboard refresh is not audit frequency. The dashboard never sends messages or incurs model usage itself.

```sh
beyondseo project dashboard --project /private/client-project --consent --refresh-seconds 30
beyondseo project dashboard --project /private/client-project --consent --serve --port 8765
```

The first command creates `dashboard.html`. Open that private file in the host. The second prints a private localhost URL and serves current database state until stopped. It binds only to 127.0.0.1, serves one secret path, and exposes no editing API. It is not remotely accessible from a cloud chat. Do not deploy the HTML or database publicly. Sharing/hosting needs separate authorisation and authentication. Consent persists in the project; don't ask the user repeatedly when restarting an agreed monitor.

```sh
beyondseo project schedule --project /private/client-project --interval 604800 --max-pages 10
beyondseo project run --project /private/client-project
beyondseo project pause --project /private/client-project
beyondseo project resume --project /private/client-project
```

`schedule` saves the requested cadence, not an OS/host cron registration. A host scheduler must invoke `project run` in this environment. Run one observed trial first. Each invocation claims at most one due **read-only HTTP crawl**, retains evidence and sets the next due time. Duplicate/overlapping invocations do not create extra reviews. Empty captures are blocked, not a clean audit. Pausing prevents future claims; it does not kill a currently executing crawl. After a hard interruption, confirm the old process stopped before `project recover --run RUN_ID --note "..."`. Nothing silently retries website writes. The local computer or configured remote worker must remain available. Agent reasoning, content changes, summaries and reports need their own supported host task, bounded scope and verification; the native runner does not invoke a model.

## Guarded HTML and sitemap drafts

For an existing static HTML file, prepare a reviewed JSON object with optional `title`, `description`, `canonical`, `language`, `copy` (`selector` and replacement `text`) and `schema` (JSON-LD). Copy replacements support plain-text paragraphs/headings with exactly one match and 80–115% of the existing character count. Complex markup, framework templates, existing JSON-LD merges and new accordion components belong in the native editor.

```sh
beyondseo onsite plan --site /private/site --file services.html --changes /private/changes.json --out /private/change-plan
beyondseo edit apply --site /private/site --plan /private/change-plan --expect-plan REVIEWED_SHA256
```

Use `--connection /private/connection.json` instead of `--site` for SFTP/FTPS. The plan is not applied automatically. Review its diff and `checks.json`. Use the existing `edit rollback` with the same plan/hash if needed; never overwrite newer changes.

`onsite sitemap --url https://example.com --input /private/urls.json --out /private/sitemap-draft.xml` writes a draft from reviewed entries containing `url`, `status: 200`, `indexable: true`, matching `canonical` and `captured_at`. Duplicate URLs collapse. Integrate with the existing sitemap mechanism instead of blindly replacing it.

## Off-site plan on the same project

Use the bundled posting library and reputation research. Select destinations by audience/service/market fit, current rules and capacity. Provide exact submission links, free/paid status and check date, eligibility, purpose, article title, outline, search intent, related questions, target page, acceptable link placement and proposed dates. Include suitable profiles, industry directories, social presence and genuine customer-review opportunities when relevant. Do not make 20 articles/10 comments a universal quota or invent keyword volume/authority. Add these as `offsite_plan` jobs: completing a plan is not acquiring a backlink. External posting, reviews, purchases and messages are outside this implementation workflow. The customer signs up and publishes; BeyondSEO can draft requested content and later verify supplied placement URLs.
