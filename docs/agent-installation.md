# Install BeyondSEO in your assistant

Choose the app you actually use. **Claude on the web, Claude Code and ChatGPT Work have different installation steps.** BeyondSEO contains the complete SEO workflow, backlink library and native crawler; no scraping-service account or SEO API key is required. Your assistant's normal model usage still applies.

| Your app | Start here |
|---|---|
| ChatGPT Work | [Ask Work to install it](#chatgpt-work) |
| Claude website / desktop / Cowork | [Upload the skill bundle](#claude-website-and-desktop-skills) |
| Claude Code | [One local installation command](#claude-code) |
| Codex | [One local installation command](#codex) |
| Hermes Agent | [Choose your active profile](#hermes-agent) |
| OpenClaw | [Choose your agent's workspace](#openclaw) |
| Cursor | [Install in your coding project](#cursor) |
| Lovable | [Import a workspace skill](#lovable) |
| Vercel / v0 project | [Install in the agent managing the project](#vercel-and-v0-projects) |
| Another assistant | [Check its capabilities](#other-assistants) |

## Easiest start: paste the GitHub URL

In Work, Cowork or a local coding assistant with installation tools, paste:

```text
Install BeyondSEO from https://github.com/beyondtahir/beyondseo in the
assistant I am using. Follow docs/agent-installation.md for this host.
Use the complete skill bundle, register it through this app's supported
skill controls, and confirm it appears in my Skills list.
Set up the native crawler in a permitted execution environment and run
doctor. Report skill registration, HTTP readiness and browser readiness
separately. If a step fails, show the exact error and resolve that step.

```

This asks the assistant to do the setup for you. It can use its supported importer or download the complete bundle and follow the matching steps below. Confirm that the skill is actually saved; reading a GitHub page alone does not install it. If the app offers manual uploads, use the ready-made ZIP. You do not need to install another SEO plugin.

## ChatGPT Work

### Upload the bundle directly

1. Get the named skill ZIP from the release, when available, or use **Prepare the upload from source** below.
2. Open **Customize → Skills → Create → Upload from your computer**.
3. Choose `beyondseo-<version>-skill.zip`. If BeyondSEO is already saved, choose **Replace existing** when prompted. Wait for it to appear in the Skills list, then open it and confirm the supporting files are present, including `docs/website-work.md` and `src/beyondseo/projects.py`.
4. Choose **Try in chat**, use the **Work** surface, and ask it to run the installation check below. A saved skill and a working crawler are separate results.

These controls were exercised in the ChatGPT web interface. Labels and availability can vary by account. Use the native file chooser for a manual upload; no browser extension is needed. An automated browser's file-upload permission error is separate from the skill's save or safety-scan result.

For a complete bundle update, use the archive importer above. Uploading a ZIP as a chat attachment or as one supporting file in the editor does not replace the skill's contents. After replacement, start a fresh Work task: an already running task may still hold the previous mounted copy.

### Ask Work to install from GitHub

Alternatively, paste this into Work:

```text
Install BeyondSEO from https://github.com/beyondtahir/beyondseo as a reusable
Work skill. Read docs/agent-installation.md and docs/permissions.md first.
Use the complete beyondseo/ skill bundle, including its Python source,
scripts, playbooks and backlink catalog. Use the workspace's supported
skill-save tools and confirm it appears in my Skills list.

Then set up the crawler in this Work execution environment. If the skill
folder cannot host executable files, use scripts/setup.py --venv with a
host-approved writable execution folder and scripts/run.py --runtime
with the same folder. Run doctor. Report skill registration, HTTP readiness
and browser readiness separately. If a step fails, show its exact error
and investigate that step; a format check alone is not installation success.
```

Work needs access to all bundled files and its supported skill-save controls. A GitHub URL provides a source to import; it is not itself an installation endpoint. After saving, find BeyondSEO in the skill picker and select it with `@` where available. Open a fresh task and ask it to read the bundled backlink catalog to confirm the resources were retained.

OpenAI distinguishes workspace skills from local filesystem skills. A copy on your computer does not register a cloud Work skill. Use the installation controls available in your workspace; a normal chat attachment may only make the files available to that conversation. [Skill authoring](https://learn.chatgpt.com/docs/build-skills) · [Workspace and local controls](https://learn.chatgpt.com/docs/enterprise/skills).

### When Work cannot save or run it

| Error | What the assistant should do |
|---|---|
| HTTP 422 during save | Capture the response body, failing operation and submitted file list. Check the skill name, description, complete folder layout and supported file requirements. A 422 alone does not identify a safety finding. |
| Chat has skill list/read tools but no save tool | Use the native archive importer above, including **Replace existing** for an update. Missing chat tools do not prove the UI cannot save the skill. |
| An explicit safety-scan rejection | Read the flagged file/rule, explain the finding and correct the actual issue. Use workspace support if the reason is unavailable. Keep scanning and approval controls enabled. |
| Permission denied launching Python | Identify which path was denied. Use an execution folder supported by that Work environment with `--venv`; do not place a virtualenv inside a read-only or non-executable skill mount. |
| Saved skill, missing bundled files | Re-import the complete bundle through the supported workflow and verify a playbook, the catalog and `src/beyondseo/cli.py` are accessible. |
| Browser cannot launch | Inspect `doctor`; install Chromium/system libraries only where the host permits them. HTTP mode can read initial HTML, but does not establish JavaScript coverage. |
| Chromium download times out | Retain the official download error. Check for an already available permitted host browser; otherwise continue HTTP/supplied-evidence work. Do not disable TLS or repeatedly download without a bound. |
| DNS fails while fetching robots | Report the name-resolution failure and the withheld page request separately. It is not a robots disallow or proof the website is offline. Use a permitted host fetch or supplied capture if available. |

The package validator does not call Work's save service or safety scanner. There is no BeyondSEO switch that grants workspace permissions or guarantees acceptance. Keep a failed save separate from a failed runtime setup; correcting one does not prove the other is resolved.

## Claude website and desktop Skills

This route also covers Claude Cowork through its Skills controls.

Check the actual account capabilities separately. Saving a skill and running it in Claude Chat does not establish Cowork access; if Cowork displays an upgrade requirement, report that feature as unavailable on that account. BeyondSEO does not change the subscription or require an upgrade merely to use another available execution route.

1. Use the matching `beyondseo-<version>-skill.zip` from the [release assets](https://github.com/beyondtahir/beyondseo/releases/latest), if offered. If the release provides source only, use **Prepare the upload from source** below. GitHub’s automatic source ZIP is not a direct skill upload; its enclosing folder has a different name.
2. Enable **Code execution and file creation** in Claude's capabilities if it is available to your account.
3. Open **Customize → Skills → Add skill → Upload skill**, then select the ZIP. Some versions label this **+ → Create skill → Upload a skill**.
4. Enable BeyondSEO in the skill list. Start a new chat and ask: “Use BeyondSEO to explain what you can do and check whether your crawler is ready.”

The archive contains one `beyondseo/` folder, matching `name: beyondseo`, with `SKILL.md` and every runtime resource. Its description is under Claude.ai's documented 200-character limit. The builder also checks a maximum of 200 archive files, including its receipt: Claude Desktop rejected a larger bundle at save time. Reporting and industry guidance is indexed in two consolidated files to stay within this limit without removing capabilities. Creating an account or entering hosting credentials is unnecessary for installation. Organization permissions can affect whether uploads are available. [Create a custom skill](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills) · [Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

If the upload says **“Zip contains too many files (maximum 200)”**, use a bundle built from version 2.7.1 or later. Do not upload the GitHub source archive, remove arbitrary runtime files, or disable the scan. This observed package-limit error does not establish the cause of a different host's unexplained HTTP 422.

Saving the skill does not install Python packages. Ask Claude to follow [crawler setup](#crawler-setup-in-a-hosted-environment) using its available execution environment. The Claude API and Claude Code have separate runtime and installation rules.

### Prepare the upload from source

Download and extract the [complete source](https://github.com/beyondtahir/beyondseo/archive/refs/heads/main.zip). Open a terminal in the extracted `beyondseo-main` folder containing `SKILL.md` and `scripts`. Run:

```sh
python3 scripts/build_skill.py --out ../beyondseo-skill.zip
```

On Windows, use `py -3` instead of `python3`. The builder needs Python 3.10+ but no crawler dependencies, Git or API key. Upload the resulting `beyondseo-skill.zip` using steps 2–4 above. An assistant with file and shell tools can perform this preparation for you. Keep the ZIP and its checksum outside the source folder.

The normal setup also installs the free report renderer. After setup, use `present` for [branded PDF/HTML reports](branded-reports.md). PDF export itself needs no browser or search access; HTML remains available if PDF rendering is unavailable.

## Local assistants: get the folder once

**Without Git:** download the [complete source ZIP](https://github.com/beyondtahir/beyondseo/archive/refs/heads/main.zip), extract it, and open a terminal in `beyondseo-main`. A named skill ZIP, when offered, extracts as `beyondseo` instead. This works when Windows says Git is missing. Confirm that you can see `SKILL.md` and `scripts` directly inside that folder.

**With Git:**

```sh
git clone https://github.com/beyondtahir/beyondseo.git
cd beyondseo
```

Run just the command for your assistant below. It copies the complete skill and prepares the crawler. Python **3.10+** is required; **3.12** is recommended. On Windows PowerShell replace `python3` with `py -3`. Activation and execution-policy changes are unnecessary.

After setup, the launcher hands off to the installed runtime before checking the engine's Python requirement. This allows an older default `python3` to start an already prepared compatible runtime; it does not make the engine compatible with old Python. If no compatible runtime exists, run setup with Python 3.10+.

## Claude Code

```sh
python3 scripts/install_skill.py --host claude-code --setup
```

The personal location is `~/.claude/skills/beyondseo`. To install only for a project, add `--workspace "/path/to/project"`. Start a new Claude Code session, then use:

```text
/beyondseo Audit https://example.com and give me a practical improvement plan.
```

[Claude Code skills](https://code.claude.com/docs/en/skills).

## Codex

```sh
python3 scripts/install_skill.py --host codex --setup
```

The personal location is `~/.agents/skills/beyondseo`. Add `--workspace "/path/to/project"` for project scope. Select BeyondSEO in the skill list; CLI and IDE users can invoke `$beyondseo`. If it is not listed, refresh or open a new session. [Official skill guidance](https://learn.chatgpt.com/docs/build-skills).

## Hermes Agent

```sh
python3 scripts/install_skill.py --host hermes --setup
```

The helper uses `HERMES_HOME` when set. Otherwise it uses `~/.hermes` on macOS/Linux or `%LOCALAPPDATA%/hermes` on native Windows. If a named profile is active but its path is unavailable, the helper asks for that exact location instead of silently installing into the default profile:

```sh
python3 scripts/install_skill.py --host hermes --profile-home "/path/to/active-profile" --setup
```

Start a new Hermes session and ask it to list skills, then invoke `/beyondseo`. Check its active profile if the skill is missing. Remote or container terminals need the same source files and a runtime prepared there.

Hermes' URL importer may fetch only directly referenced resources on some versions. Use the complete folder workflow here so the Python package and nested catalog are retained. Hermes has its own skill scanner; review actual findings and keep its policy enabled. [Hermes skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/) · [Native Windows guidance](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native).

## OpenClaw

For one agent, use its actual workspace:

```sh
python3 scripts/install_skill.py --host openclaw --workspace "/path/to/agent-workspace" --setup
```

For a shared installation under the current state directory:

```sh
python3 scripts/install_skill.py --host openclaw --setup
```

Shared installation uses `OPENCLAW_STATE_DIR/skills/beyondseo`, or `~/.openclaw/skills/beyondseo` with the default state. Confirm discovery with `openclaw skills list` and `openclaw skills check`, then ask that agent to use BeyondSEO.

A sandboxed agent needs Python and optional Chromium **inside its execution environment**, even if they work on the Gateway host. Ask the administrator to provide those capabilities through the supported sandbox setup. BeyondSEO is distributed through this repository; these instructions do not assume a ClawHub listing. [OpenClaw skills](https://docs.openclaw.ai/tools/skills) · [Skill configuration](https://docs.openclaw.ai/tools/skills-config).

## Crawler setup in a hosted environment

The assistant should identify an approved writable/executable runtime directory. The paths below are placeholders that it must replace with actual paths from its environment:

```sh
python3 "/path/to/beyondseo/scripts/setup.py" --venv "/approved/runtime/beyondseo"
python3 "/path/to/beyondseo/scripts/run.py" --runtime "/approved/runtime/beyondseo" doctor
```

External setup builds from a temporary source copy in the selected runtime directory. It does not write build files into the original skill mount. Use the same `--runtime` when crawling. If the environment cannot execute Python or download dependencies, that remains a host capability limitation; moving files arbitrarily or changing security controls is not a supported fix.

For a normal writable local skill folder, `python3 scripts/setup.py` uses its own `.venv`. Add `--http-only` to setup to skip Chromium. With the local installer use `--setup --http-only`. [Detailed runtime troubleshooting](setup.md).

## Know when installation is complete

Ask your assistant:

```text
Check my BeyondSEO installation. Can you find the skill in this host's
Skills list, read its bundled backlink catalog, and run its native doctor?
Report each result separately. Then crawl https://example.com with a
maximum of two pages and save the evidence outside the skill folder.
Tell me whether HTTP and JavaScript rendering actually worked.
```

There are three separate results: **skill registered**, **HTTP ready**, and **browser ready**. A successful command does not prove every requested page was read; inspect the crawl's saved coverage and errors. In HTTP-only mode a missing browser is expected and `doctor` returns a nonzero status.

## Updates and existing installations

Running the same local install again is safe: an identical installation is reported as already installed. After obtaining a newer source folder, add `--update` to the original command. The helper verifies the previous receipt, preserves the old folder under `beyondseo-backups` outside the host's skill discovery folder, and installs a fresh copy. An existing local `.venv` directory is copied back to its original absolute path so an update does not remove a working runtime; the backup remains intact. External or symlinked runtime directories are not copied. Changed skill files are preserved and require review before replacement. Add `--setup` to install or refresh dependencies, then run doctor; preserving a runtime is not proof that it satisfies new dependencies.

Use `--dry-run` to preview without writing or downloading anything. Use `--dest "/exact/path/beyondseo"` for a custom skill location. This is a filesystem installer; it does not save a ChatGPT workspace skill or change host settings. For web uploads, use the host's supported update controls and avoid leaving two enabled versions.

## Other assistants

A host that reads the Agent Skills format can load the workflow. Full native crawling additionally requires accessible source files, Python 3.10+, permitted network access and, for rendered pages, Chromium execution. Register the complete folder using that host's documented controls, then run the checks above. Compatibility with the format is not a promise of every agent's save permissions, tools or operating environment.

## Package review and support

Read [what the package does and accesses](permissions.md). `python3 scripts/validate_skill.py` checks the description, required resources and bundled links without network access. It does not certify a host's safety decision.

For an installation issue, include the app name, version, operating system or cloud environment, whether saving or execution failed, and the exact redacted error. Do not include passwords, keys or private client reports. [Report an installation issue](https://github.com/beyondtahir/beyondseo/issues/new?template=installation.yml).

## Search and browser readiness after installation

Run `beyondseo doctor` in the actual task runtime. Reuse an available host browser when appropriate; `beyondseo browser-setup` checks first and installs missing free local Chromium components only when requested. See [browser-assisted Google search](browser-search.md) and [diagnostics by environment](discovery-diagnostics.md). Installing a skill does not itself grant browser control or network permission.

## Check model access separately

Before blaming BeyondSEO for an agent that cannot start, try one short model response without tools. A saved sign-in indicator does not prove the next request will succeed. For example, if Claude Code's actual response says its OAuth token expired, run `claude auth login` and complete sign-in; reinstalling BeyondSEO or Chromium does not repair that login. Keep authentication failures separate from website or search-provider failures.

Hermes can use an already configured subscription or local model. OpenClaw can use a supported subscription login or local Ollama model. These are host choices, not dependencies required by BeyondSEO. Test that the chosen model can call tools and read evidence; a successful text-only reply does not establish a completed audit. Do not copy credential files between agents. Use each host's supported sign-in flow when needed.

When installing OpenClaw itself, check the selected release's Node requirement before installation. BeyondSEO's Python requirement is separate. Follow [OpenClaw installation](https://docs.openclaw.ai/install) and [local Ollama setup](https://docs.openclaw.ai/providers/ollama/setup); retain existing host configuration unless a particular change is needed and authorized.


## Cursor

Cursor supports the standard skill folder and its bundled scripts. From the downloaded BeyondSEO folder, install into the project you actually edit:

```sh
python3 scripts/install_skill.py --host cursor --workspace "/path/to/website-project" --setup
```

1. Open that website project in Cursor. On Windows use `py -3` instead of `python3`.
2. Refresh skills/start a new session and select `/beyondseo` in Agent chat. Confirm it appears under the app's Skills controls.
3. Ask: “Use BeyondSEO to inspect this website. Apply the agreed on-site improvements while preserving its design. Do not deploy until I authorise it.”
4. Run the installed `scripts/run.py doctor` in the actual terminal. Registration, native HTTP and browser readiness are separate checks.
5. For personal installation omit `--workspace`. For a cloud agent, include the project skill in its authorised repository/environment and prepare its runtime there. Unsynced personal skills are not automatically available remotely.

The command is implemented locally. It does not install Cursor itself or grant permissions. A URL-based prompt can ask Cursor to perform these same steps:

```text
Install BeyondSEO from https://github.com/beyondtahir/beyondseo for this
Cursor project using scripts/install_skill.py --host cursor --workspace
with this project's actual path and --setup. Read docs/agent-installation.md.
Confirm skill discovery and doctor results. Do not modify my website yet.
```

The installer uses `.cursor/skills/beyondseo` for a project and `~/.cursor/skills/beyondseo` for personal installation. Cursor also discovers `.agents/skills/beyondseo`, which Vercel's Skills CLI uses. Choose one installation method for a project to avoid duplicate copies.

Cursor's **From GitHub Repository** control currently expects a plugin marketplace with `.cursor-plugin/marketplace.json`; it is not a standalone `SKILL.md` importer. For BeyondSEO, use the command or chat prompt above, or the [Skills CLI route](#vercel-and-v0-projects). No existing rules, MCP settings or cloud-sync preferences need to change.

[Official Cursor skills](https://cursor.com/docs/skills) · [Cursor automations](https://cursor.com/docs/cloud-agent/automations).

## Lovable

After import, follow [the dedicated Lovable execution guide](lovable.md). It covers mounted skill execution, private runtime recovery, capture limits and optional monitoring without changing application settings.

Lovable now documents native workspace skills and GitHub imports. A workspace owner/admin can:

1. Open **Settings → Skills → Add → Import from GitHub**.
2. Paste `https://github.com/beyondtahir/beyondseo`. For a version not yet published, use the local package/manual route; the public URL cannot fetch unpublished local changes.
3. For a ZIP, choose **Settings → Skills → Add → Upload ZIP**, browse to the prepared bundle, then choose **Import archive**. Expand **Beyondseo** and inspect **Bundled files**: check `docs/website-work.md`, `src/beyondseo/projects.py`, `scripts/run.py`, the logo and backlink catalog. Use the prepared skill bundle, not an arbitrary repository ZIP with tests and private outputs.
4. Open the website's project chat, type `/beyondseo`, and select **Beyondseo — Workspace skills**. Confirm the skill chip is attached before sending. Ask it to follow `docs/website-work.md` and inspect the current source and preview before editing.
5. Check the actual tools. Importing Python files does not establish that Python, browser downloads or persistent background workers can run. Use the project's native tools when available and report any missing crawler coverage separately.

You can also ask Lovable's chat:

```text
Import BeyondSEO from https://github.com/beyondtahir/beyondseo as a workspace
skill using your supported Skills import. Preserve existing skills and project
knowledge. Confirm registration and bundled resources. Then use it on this
project when I request SEO work. Do not publish or create a dashboard yet.
```

If chat cannot import, use the Settings steps above; reading the URL alone is not installation. Current documented limits: 200 files, 1 MB per file and 10 MB total content. BeyondSEO's validator enforces these limits. The local installer cannot register a Lovable workspace skill. An owner/admin may use the native importer independently of a connector. A connector error mentioning `workspaces:write` or `projects:write` concerns that connector grant; it does not prove the archive is invalid. Use the authorised native UI where available, or correct that connector's permissions through its supported setup. Preserve existing skills and project knowledge.

For implementation, Lovable's agent edits the existing application and checks its preview. For recurring work, a connected worker and durable store are separate setup. Ask before provisioning or exposing a monitor. The existing chat operates the project; dashboard AI is optional and not included automatically in editor credits.

[Official Lovable skills/import guide](https://docs.lovable.dev/features/skills) · [GitHub sync](https://docs.lovable.dev/integrations/github).

## Vercel and v0 projects

Vercel hosts the application; install BeyondSEO into the agent that manages its source (Cursor, Codex, Claude Code or another supported host). For example, use the Cursor command above with the Vercel-connected repository. There is no `--host vercel` that registers a skill in the hosting dashboard.

Vercel's open Skills CLI can install a GitHub skill into supported agents. Run this from the website project and choose the intended agent:

```sh
npx skills add https://github.com/beyondtahir/beyondseo
```

For an explicit Cursor project installation:

```sh
npx skills add https://github.com/beyondtahir/beyondseo --agent cursor --skill beyondseo --copy
```

For unpublished local changes, replace the URL with the absolute path to the extracted complete `beyondseo` skill folder. The public URL always reads the published version. Skills CLI 1.7.0 was exercised with a local bundle in an isolated project: all source-file hashes matched and existing rules, settings and a separate skill were retained. This checks installation, not a Cursor Agent session or Vercel deployment. The CLI may maintain its own skill lockfile; review any existing BeyondSEO collision before confirming a replacement. Its optional telemetry can be disabled with `DISABLE_TELEMETRY=1`.

After copying, use the installed folder (the tested CLI used `.agents/skills/beyondseo`):

```sh
python3 .agents/skills/beyondseo/scripts/setup.py
python3 .agents/skills/beyondseo/scripts/run.py doctor
```

Use `py -3` on Windows. Confirm BeyondSEO in the agent's skill picker too. Copying the skill does not install dependencies or a background service. Use BeyondSEO's Python installer if a generic importer omits resources, and keep existing installation receipts/configuration intact.

1. Connect/open the website's source using its existing project workflow.
2. Install BeyondSEO in that coding agent and inspect the site before edits.
3. Make scoped changes and run the existing build and preview checks.
4. Keep previews separate from production. Publish only within the user's authorisation.
5. For scheduled work, prepare a durable worker and a protected trigger. Vercel Cron invokes production HTTP endpoints; it does not keep a browser or Python process running indefinitely. Do not store persistent client state on a Function's temporary filesystem. A preview-only test does not demonstrate cron execution.

In v0, first check the actual available skill and execution controls. If it cannot register/run the complete skill, work through the connected repository in a supported agent; do not report native v0 installation as tested.

[Official Vercel skills](https://vercel.com/docs/agent-resources/skills) · [Skills CLI](https://skills.sh/docs/cli) · [Vercel Cron](https://vercel.com/docs/cron-jobs).

## Website implementation and optional monitor

After installation, [website work](website-work.md) explains design-preserving edits, private project records, optional monitoring, bounded review jobs and off-site planning. These functions use the current agent's chat. Installation alone starts no crawl, schedule, publishing job or dashboard. Runtime/model access and credentials are not inherited across hosts.


### Preserve existing settings

Add BeyondSEO as its own skill. Do not replace existing rules, workspace/project knowledge, MCP settings, deployment settings or other skills. The local installer writes only the selected `beyondseo` folder and its receipt; it refuses an unmanaged existing folder and refuses to overwrite modified installed files. A requested update backs up the prior managed installation. Lovable imports must add a new skill; inspect any name collision before replacing it.

The optional project monitor works across all these hosts, including ChatGPT Work, Claude, Hermes and OpenClaw. Use a private HTML artifact where local serving is unavailable. See [monitoring in each execution environment](website-work.md#offer-monitoring-once).
