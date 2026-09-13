# Use BeyondSEO with your assistant

One folder contains the skill, specialist playbooks and native Python engine. No crawling-service account, SEO-data subscription, plugin or API key is required by BeyondSEO. Your assistant needs its own working model connection or subscription; its usage is separate.

## Choose your environment

| Environment | Local installation or use | Validation status |
|---|---|---|
| Claude Code | `.claude/skills/beyondseo` in a project, or `~/.claude/skills/beyondseo` | Official folder format checked; CLI present locally; a model-driven acceptance run remains to be done |
| Codex | `.agents/skills/beyondseo` in a project, or `~/.agents/skills/beyondseo` | Actual CLI 0.153.4 discovered the new project skill through `skills/list`; native engine and local browser tested |
| ChatGPT Work | For local Work, open the source folder and explicitly load `SKILL.md`; select an installed skill through the available picker | Local file workflow documented; cloud installation and execution are not certified |
| Hermes Agent | `~/.hermes/skills/beyondseo` for the default macOS/Linux profile | Actual v0.21.1 loader discovered the skill and read its scoring reference in an isolated profile; no model call |
| OpenClaw | `<active-workspace>/skills/beyondseo`, or `~/.openclaw/skills/beyondseo` | Official format checked; host execution has not been tested here |

Host names identify compatibility, not authorship. BeyondSEO is created and maintained by Muhammad Tahir Ashraf — Beyond Tahir.

## Install a local skill folder

Clone `https://github.com/beyondtahir/beyondseo.git` and start in that source folder. Choose **one** destination for the host you use. The helper copies the bundled source and documentation, excludes virtual environments, caches and root-level run folders, and writes a checksum receipt. Keep all client files outside the source folder. It performs no downloads, installs no host software and creates no archive.

Preview a Claude Code installation:

```sh
python3 scripts/install_skill.py --dest "$HOME/.claude/skills/beyondseo" --dry-run
```

Install using the relevant command:

```sh
# Claude Code, personal
python3 scripts/install_skill.py --dest "$HOME/.claude/skills/beyondseo"

# Codex, personal
python3 scripts/install_skill.py --dest "$HOME/.agents/skills/beyondseo"

# Hermes, default macOS/Linux profile
python3 scripts/install_skill.py --dest "$HOME/.hermes/skills/beyondseo"

# OpenClaw, shared local skill directory
python3 scripts/install_skill.py --dest "$HOME/.openclaw/skills/beyondseo"
```

For a project installation, give the full path to that project's skill folder. The destination must be outside this source checkout and must not exist. Existing installations are never overwritten. For an update, preserve the previous folder as a backup outside the host's discovery folders, then install a fresh copy at the intended location. Keep reports separately.

On Windows PowerShell use `py -3` in place of `python3`. For example:

```powershell
py -3 scripts/install_skill.py --dest "$env:USERPROFILE\.claude\skills\beyondseo"
```

Hermes profiles and native Windows installations may use a different data directory. Use the active profile's actual skills path, not an assumed home folder. OpenClaw custom state directories and agent allowlists can also affect discovery. Consult the host references below.

## Prepare the engine where it will run

Inside the **installed BeyondSEO folder**, run:

```sh
python3 scripts/setup.py
python3 scripts/run.py --version
python3 scripts/run.py doctor
```

Use `py -3` on Windows. Python 3.10+ is required; 3.12 is recommended. Setup creates a local `.venv`, installs the engine and downloads Chromium. `doctor` should report both `http_ready` and `browser_ready` as true. See [complete setup](setup.md) for Linux system libraries, HTTP-only operation and troubleshooting.

The launcher selects the folder's virtual environment automatically. An assistant can call it from any working directory:

```sh
python3 "/absolute/path/to/beyondseo/scripts/run.py" crawl https://example.com \
  --out "/absolute/path/to/client-runs/first-audit" --max-pages 10
```

Resolve that path from the loaded `SKILL.md`; never reuse another person's path. Relative output paths resolve from the command's working directory. Prefer absolute output paths outside the skill. A remote, container or cloud terminal needs its own copy, dependencies, writable output directory and permitted network access. A local installation does not install Python or Chromium in a remote worker.

## Invoke the skill

Claude Code and Hermes:

```text
/beyondseo Audit https://example.com. Include backlinks, named competitors,
answer readiness, useful copy drafts and a practical 30/60/90-day plan.
```

Codex CLI/IDE:

```text
$beyondseo Audit https://example.com for our target customers.
Show the evidence and keep uncertain reputation scores conservative.
```

In OpenClaw, select BeyondSEO from the skill picker or ask it to use the installed skill by name. In any host, an explicit fallback is: “Read the SKILL.md in this BeyondSEO folder and follow it for this audit.” Restart or refresh the host if its skill list has not updated. A loaded skill still uses the host's ordinary file, shell, browser and network permissions.

## ChatGPT Work: local and cloud

For local Work, open or provide access to the BeyondSEO folder and ask:

```text
Read SKILL.md and use the bundled BeyondSEO workflow. Check the local engine
with scripts/run.py doctor, then audit https://example.com. Save client
evidence outside the skill folder and report any missing capabilities.
```

Use the skill picker when the installed skill is available. OpenAI documents standalone desktop skills separately from workspace skills and plugin distribution; a filesystem copy does not establish cloud installation or sharing. [Build skills](https://learn.chatgpt.com/docs/build-skills), [skill controls](https://learn.chatgpt.com/docs/enterprise/skills).

For cloud Work, use the workspace's supported skill controls if available and confirm that **all supporting files**, Python dependencies and browser execution are accessible. This release does not provide or claim a tested cloud importer. If the worker cannot run the native engine, run it locally and supply the resulting reports and relevant evidence for analysis. Describe that run as analysis of supplied evidence. Do not claim a fresh crawl, native execution or an installed cloud skill merely because a Markdown file was attached.

## Check a new host before client work

1. Ask it to name the skill and locate its bundled references and launcher.
2. Run the version and doctor commands from that host's actual execution environment.
3. Crawl ten permitted public pages to a fresh folder. Check `summary.json`, captured content and any access errors.
4. Ask for a complete audit and confirm that it includes backlink evidence, named competitor pages and actions with acceptance checks. Missing evidence must be labeled, not filled with invented facts.
5. Ask a focused writing question and confirm it supplies usable copy without launching an unnecessary full audit.

Passes here establish compatibility with that installed host/version and permissions. They do not guarantee every website, future dependency version or ranking outcome. The [validation record](validation.md) describes completed checks.

## Host references

Installation guidance checked September 14, 2026. These are host documentation links; BeyondSEO does not call their APIs.

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Codex and ChatGPT skill authoring](https://learn.chatgpt.com/docs/build-skills)
- [Hermes skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)
- [Hermes Windows paths](https://hermes-agent.nousresearch.com/docs/user-guide/windows-native)
- [OpenClaw skills](https://docs.openclaw.ai/tools/skills)

Next: [questions you can ask](questions.md), [full capabilities](../references/capabilities.md), or [scoring explained](scoring-explained.md).
