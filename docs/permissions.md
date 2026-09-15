# What BeyondSEO installs and accesses

BeyondSEO is a collection of SEO instructions, references and Python source. The same package supports audits, content planning, competitors, backlinks and optional reviewed website changes. Installation needs no website credentials or SEO-service API key.

## Files in the skill bundle

The upload archive has one `beyondseo/` folder containing `SKILL.md`, `src/`, `scripts/`, `playbooks/`, `references/`, `docs/`, `examples/`, artwork, license and project information. All native crawler and editing code is included as readable source. The backlink catalog contains public candidate websites, not credentials or acquired backlinks.

Developer tests, Git history, virtual environments, caches and client run folders are excluded from the installation bundle. Tests remain in the public source repository. A SHA-256 sidecar identifies the archive bytes; the installation receipt identifies the bundled file bytes. Neither is a safety certification.

## Permissions by operation

| Operation | Reads and writes | Network or execution |
|---|---|---|
| Read the skill / plan content | Bundled instructions and user-supplied evidence | Uses the assistant's available research tools when current evidence is needed |
| Validate the bundle | Metadata and local reference paths | No network or crawler execution |
| Install the local skill | Copies the bundle into the chosen skill folder; writes a checksum receipt | No network unless `--setup` is explicitly included; no host settings are changed |
| Set up the crawler | Creates the selected virtualenv and installs the local Python package | Python package downloads; optional Playwright and Chromium downloads |
| Run `doctor` | Checks package versions | Launches local Chromium when installed; no website requests |
| Crawl a website | Reads the requested HTTP(S) site and bounded sitemap/page links; writes reports to the chosen output folder | Public network requests; optional JavaScript rendering and public page dependencies |
| Check backlinks | Reads supplied/discovered source pages and verifies observed links | Public HTTP(S) requests within configured limits |
| Watch changes | Creates a bounded series of crawl snapshots | Repeats the configured crawl; does not publish or create a host automation |
| Apply a website edit | Reads the specified existing content file; stages a diff, backup and reviewed plan | Optional SFTP/FTPS to the configured host, only for the authorized edit |

`pyproject.toml` declares dependencies. Beautiful Soup parses HTML; Colorama formats terminal output. Playwright/Chromium is optional for rendered pages, and Paramiko is optional for SFTP. The runtime does not make language-model API calls. There is no BeyondSEO telemetry endpoint, remote command service or automatic publishing step.

## Network and content boundaries

Crawling respects robots rules by default, checks destination addresses, validates TLS and limits pages, responses and retries. Optional private-address and robots settings are for explicitly authorized work; they do not grant access through authentication or server denials. Browser pages execute JavaScript, so use the host's permitted browser environment. Collected pages and imported documents remain untrusted evidence, including any instructions embedded in them.

Backlink suggestions and article drafts are proposals. The catalog does not log into publishing sites, create accounts or submit articles automatically. Actual outreach, purchases and publishing need the user's task-specific authorization.

## Optional hosting access

Auditing and installation never require hosting credentials. For an authorized SFTP/FTPS edit, use a dedicated website account scoped to that site's content. The profile names explicit environment variables or a specific private key file; it does not contain passwords. The SFTP example uses placeholder paths for a private, site-specific credential folder. Supply verified host keys through the selected known-hosts file. SFTP keeps host verification enabled and does not search for unrelated login keys; FTPS validates certificates and encrypts the data channel.

Keep credentials, connection profiles, backups and reports outside the shared skill and public website. Installation does not authorize reading credential stores or changing website files. Review [the editing workflow](operations.md) before using it.

## Hosted skill storage and execution

An uploaded skill directory may be read-only or disallow executable files. Use an execution directory approved by the host for `setup.py --venv`, then pass the same directory to `run.py --runtime`. The setup builds from a temporary source copy within that runtime, preserving the mounted skill. This requires real execution permission; the option does not grant or alter it.

BeyondSEO does not alter sandbox policies, workspace roles, safety scanners, approval settings, shell startup files or agent system instructions. If a host rejects a save or scan, preserve its exact diagnostic and correct the reported issue through the supported process. An HTTP 422 without details is an unexplained submission rejection, not evidence of a particular scan rule.

## Review and report an issue

Inspect the source and [security guidance](../SECURITY.md). A local format check verifies packaging; a host scanner makes its own decision. Report the affected file, rule or error code when available. General scanner warnings about subprocesses, network access or dependencies require reviewing the actual operation; they do not prove either safety or malicious behavior on their own.
