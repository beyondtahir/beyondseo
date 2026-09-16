# Search through an available browser

Agents such as Codex, Claude Code, Hermes and OpenClaw can have computer/browser tools, but their tool access depends on the installed host, execution environment and permissions. A ChatGPT Work browser may also be separate from its Python environment. BeyondSEO checks these capabilities instead of assuming that every agent can control Chrome.

## Different agents, different browsers

| Host | What to check | Free local fallback |
|---|---|---|
| Codex / ChatGPT Work | The tools actually exposed in the current session, including browser navigation, search, shell and files. Browser and shell networks can differ. | BeyondSEO's Python/Chromium runtime where local execution is supported. |
| Claude Code | Available browser tools or `/chrome`; the documented Chrome integration also supports Edge and requires its extension and compatible account. | The packaged BeyondSEO CLI with Chromium; its search adapters do not require the Chrome extension. |
| Hermes | Its active browser backend and available `browser_exec` or navigation/snapshot tools. A selected cloud backend is not the same as a working local browser. | Hermes' supported local Chromium setup through `hermes tools`, or BeyondSEO's existing runtime. |
| OpenClaw | Browser tool availability, selected profile and execution host. Its managed profile can use Chrome, Brave, Edge or Chromium. | The managed browser or BeyondSEO's runtime in the agent's actual execution environment. |

These are capability checks, not automatic changes to host settings. Prefer a working surface already available in the session. A failed browser does not block independently permitted search tools or native discovery. A failed search does not block native page inspection. Only install a missing component if it is needed for the chosen workflow and installation is authorized.

Sources: [Claude browser integration](https://code.claude.com/docs/en/chrome), [Hermes browser modes](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser/), [OpenClaw managed browser](https://docs.openclaw.ai/tools/browser), [OpenClaw browser tool setup](https://docs.openclaw.ai/tools/browser/setup).

## Do we need another browser project?

BeyondSEO already uses [Playwright](https://github.com/microsoft/playwright) with Chromium for rendered captures. [agent-browser](https://github.com/vercel-labs/agent-browser) is an existing open-source CLI used by Hermes' local browser integration. Reuse supported host tools or the packaged crawler before adding another dependency. Building or forking a browser would not grant host permissions, remove search-provider limits or create a complete backlink index. No additional BeyondSEO extension is required for the native workflow.

## Choose the working browser

1. The assistant checks its actual browser tool inventory first. If the host exposes an existing permitted Chrome or other browser, reuse that surface. Do not install a second browser just because a separate search tool failed.
2. Run `beyondseo doctor`. It reports locally detected browsers, the independent Playwright Chromium launch check, and host control as unknown until the assistant actually tests it. A browser executable on disk does not prove UI access.
3. If there is no usable host browser and the user wants local browser setup, run the explicit command below in the selected BeyondSEO runtime. It checks first, installs only missing Playwright/Chromium components, then verifies a launch. Chromium and Playwright are free; no SEO API key is needed.

```sh
beyondseo browser-setup
# With an external, host-approved runtime:
python3 scripts/run.py --runtime /path/to/beyondseo-runtime browser-setup
```

The command installs through Python's package manager and Playwright's official Chromium installer. It leaves an already working runtime alone. It does not install extensions, alter host permissions, attach to an arbitrary browser debugging port, read browser cookies, or change a user's profile. An execution denial is reported rather than treated as a missing download. In a runtime without a virtual environment, use the existing `scripts/setup.py --venv <approved-runtime>` route first.

## Google in the host's browser

When the task calls for Google and browser access is permitted, the assistant can navigate to the relevant Google query, inspect the actual visible results and follow ordinary result pages. Use bounded queries/pages, avoid unrelated account content, and stop on a CAPTCHA, security warning or access denial. Do not change location or personalization settings just to improve results.

Record the query, provider (`Google via host browser`), capture time, requested market/language, visible result URLs, actual observable coverage and whether results are personalized. Record location/language only to the level relevant to the task; do not export account identifiers, cookies or precise device location.

Use the same `--host-results` JSON contract described in [shared discovery](discovery-and-competitors.md). The host supplies browser observations; the native engine then deduplicates leads and verifies source pages. For an exported public result HTML file, use `search-import --engine Google`. The existing `search-plan` command can prepare a bounded set of Google navigation links; it does not itself perform browser actions.

```sh
beyondseo discover --query 'automation agency in Pakistan' \
  --market Pakistan --language English --host-results browser-results.json \
  --target https://example.com --out runs/browser-discovery
```

If that browser source fails, the discovery workflow records the failure and tries another independently permitted native source. If the host prohibits network access broadly, use `--offline`. The native CLI does not control the host's Chrome itself; agent browser tools perform that step. A new BeyondSEO extension is not required when a host already provides browser control.

## What a successful browser search proves

It proves that this query returned results in this browser session at that time. It does not guarantee future access, neutral rankings or a complete backlink index. Normal Chrome sessions can still encounter rate limits, CAPTCHAs or environment restrictions. Search snippets remain leads, and candidate pages still need native verification.

See [diagnostics](discovery-diagnostics.md) for the exact failed operation and [browser capture behavior](browser.md) for the local crawler's separate Chromium runtime.

## Avoid unnecessary interruptions

For an authorized audit, the assistant chooses supported fallbacks itself: available host browser, available host search, permitted native discovery, then existing supplied evidence. It does not ask the user to select a provider or repeat granted permission. It continues native website analysis independently. Browser installation is only needed when the selected workflow requires it and no usable authorized browser exists. A remaining restriction is reported with partial results, rather than turning into a generic request to buy tools or abandon the audit.

Use the packaged CLI for crawling, profiling, discovery and source checks. Read/write JSON with the host's file tools when available. Avoid rebuilding these operations as inline Python or shell scripts: some hosts require a separate approval for arbitrary code even when the packaged command is permitted. An actual command denial remains a denial; do not change its encoding or execution mechanism to conceal it.

For full audits, record the host browser/backend/profile in the research evidence and follow the [deep-research sequence](deep-research.md): ordinary Google through the available permitted host browser, then host search and native fallbacks. Hermes' managed local browser and OpenClaw's managed profile can run independently of an interactive personal Chrome window; do not assume they share its login or network behavior. Actual navigation must establish readiness. Native website reading and source verification continue separately.
